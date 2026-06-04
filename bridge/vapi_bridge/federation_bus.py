"""
FederationBus — Phase 34

Background asyncio task that shares privacy-preserving cluster fingerprints with
peer bridge instances every poll_interval seconds. When a cluster fingerprint
appears on ≥2 independent bridges, a federated_cluster alert is dispatched.

Privacy model: only 16-char SHA-256 hex hashes of sorted device-ID sets are
shared — raw device identities never leave the originating bridge.

Three operations per sync cycle:
  1. _publish_local_clusters — detect flagged clusters locally, store as is_local=True
  2. _fetch_peer_clusters    — GET /federation/clusters from each peer
  3. _process_peer_clusters  — store remote; check cross-confirmation; dispatch escalation

VAPI-EXT addition (Phase 204+):
  Namespace isolation for sub-protocol event publishing.
  register_namespace(prefix, owner) — claims an event prefix for a sub-protocol.
  validate_event_namespace(event_type) — raises NamespaceViolationError if the event
    prefix is registered but the expected owner doesn't match.
  publish_namespaced(event_type, payload, source) — validates namespace then delegates
    to the AsyncIO message bus.

  All existing VAPI core events pass through AgentMessageBus directly and are unaffected.
  Sub-protocols MUST call register_namespace() before publishing prefixed events.
  Empty-prefix events ("" owner = VAPI_CORE) are never blocked — backward compatible.
"""
import asyncio
import hashlib
import json
import logging
import time

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VAPI-EXT Namespace isolation — Phase 204+
# ---------------------------------------------------------------------------


class NamespaceConflictError(Exception):
    """Raised when two sub-protocols attempt to register the same event namespace prefix."""


class NamespaceViolationError(Exception):
    """Raised when an event is published under a prefix owned by a different sub-protocol."""


class _NamespaceRegistry:
    """Thread/coroutine-safe namespace registry.

    Stores prefix → owner mappings. A prefix is a non-empty string that event_type
    strings must start with (e.g., "mobile." or "pragma.").

    VAPI_CORE events have no prefix (empty string owner) and are never validated —
    backward compatible.
    """

    def __init__(self) -> None:
        self._namespaces: dict[str, str] = {}  # prefix → owner name

    def register(self, prefix: str, owner: str) -> None:
        """Register prefix as owned by owner.

        Raises NamespaceConflictError if prefix is already owned by a different owner.
        Idempotent: re-registering the same prefix/owner pair is allowed.
        """
        if not prefix:
            raise ValueError("Namespace prefix must be non-empty.")
        if not owner:
            raise ValueError("Namespace owner must be non-empty.")
        if prefix in self._namespaces:
            existing_owner = self._namespaces[prefix]
            if existing_owner != owner:
                raise NamespaceConflictError(
                    f"Namespace prefix '{prefix}' is already owned by '{existing_owner}'. "
                    f"'{owner}' cannot claim it."
                )
            # Same owner re-registering — idempotent, no error
            return
        self._namespaces[prefix] = owner

    def validate(self, event_type: str, expected_owner: str) -> None:
        """Validate that event_type's prefix is owned by expected_owner.

        Only validates events whose type starts with a registered prefix.
        Unregistered-prefix events pass through without validation (backward compatible).
        Empty-prefix events (VAPI_CORE) always pass through.

        Raises NamespaceViolationError if the owning sub-protocol does not match
        expected_owner.
        """
        for prefix, owner in self._namespaces.items():
            if event_type.startswith(prefix):
                if owner != expected_owner:
                    raise NamespaceViolationError(
                        f"Event '{event_type}' uses prefix '{prefix}' owned by "
                        f"'{owner}', but caller claims ownership as '{expected_owner}'."
                    )
                return
        # No registered prefix matched — VAPI_CORE backward-compatible passthrough

    def get_owner(self, prefix: str) -> "str | None":
        """Returns the owner of a prefix, or None if not registered."""
        return self._namespaces.get(prefix)

    def get_all(self) -> dict[str, str]:
        """Returns a copy of all registered prefix → owner mappings."""
        return dict(self._namespaces)

    def _reset(self) -> None:
        """Test-only helper."""
        self._namespaces.clear()


# Module-level namespace registry — shared by FederationBus instance and all sub-protocols
_NAMESPACE_REGISTRY = _NamespaceRegistry()


def register_namespace(prefix: str, owner: str) -> None:
    """Module-level helper: register a namespace prefix for a sub-protocol.

    Sub-protocols call this at startup, before publishing any events:
        from vapi_bridge.federation_bus import register_namespace
        register_namespace("mobile.", "VAPI_MOBILE")
    """
    _NAMESPACE_REGISTRY.register(prefix, owner)


def validate_event_namespace(event_type: str, expected_owner: str) -> None:
    """Module-level helper: validate that event_type belongs to expected_owner.

    Raises NamespaceViolationError if the prefix is owned by a different sub-protocol.
    """
    _NAMESPACE_REGISTRY.validate(event_type, expected_owner)

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

# Module-level import with fallback so tests can patch vapi_bridge.federation_bus.ws_broadcast
try:
    from .transports.http import ws_broadcast
except Exception:
    async def ws_broadcast(message: str) -> None:
        pass


_CLUSTER_HASH_RE = __import__("re").compile(r"^[0-9a-f]{16}$")


def _is_valid_cluster_hash(h) -> bool:
    """Cluster hash MUST be exactly 16 lowercase hex chars (see
    compute_cluster_hash). Peer-supplied values that fail are rejected to
    prevent malformed data flowing into DB writes, WebSocket broadcasts, or
    on-chain calls."""
    return isinstance(h, str) and bool(_CLUSTER_HASH_RE.match(h))


def compute_cluster_hash(device_ids: list) -> str:
    """Stable 16-char hex fingerprint of a device cluster (non-reversible).

    Uses sorted device IDs so cluster identity is order-independent.
    """
    return hashlib.sha256("|".join(sorted(device_ids)).encode()).hexdigest()[:16]


def compute_bridge_id(api_key: str) -> str:
    """Anonymous 16-char bridge identity derived from api_key (non-reversible)."""
    return hashlib.sha256(f"bridge:{api_key}".encode()).hexdigest()[:16]


class FederationBus:
    """Cross-bridge cluster intelligence task (Phase 34).

    Polls peer VAPI bridge instances and exchanges privacy-preserving cluster
    fingerprints. When the same fingerprint is detected on ≥2 independent bridges,
    a federated_cluster protocol insight is dispatched and optionally anchored on-chain.
    """

    def __init__(self, store, network_detector, chain, cfg, poll_interval: float = 120.0):
        self._store = store
        self._network_detector = network_detector
        self._chain = chain
        self._cfg = cfg
        self._poll_interval = poll_interval
        self._running = True
        # Per-peer dedup: peer_url → set[cluster_hash] already processed this session
        self._known_peer_hashes: dict[str, set] = {}
        self._bridge_id = compute_bridge_id(
            getattr(cfg, "federation_api_key", "") or "default"
        )

    # ------------------------------------------------------------------
    # VAPI-EXT: Namespace isolation (Phase 204+)
    # ------------------------------------------------------------------

    @staticmethod
    def register_namespace(prefix: str, owner: str) -> None:
        """Register a namespace prefix for a sub-protocol.

        Delegates to the module-level _NAMESPACE_REGISTRY.
        Raises NamespaceConflictError if prefix is owned by a different sub-protocol.
        Idempotent: safe to call multiple times with the same prefix/owner.

        Usage:
            bus.register_namespace("mobile.", "VAPI_MOBILE")
        """
        _NAMESPACE_REGISTRY.register(prefix, owner)

    @staticmethod
    def validate_event_namespace(event_type: str, expected_owner: str) -> None:
        """Validate that event_type's namespace prefix is owned by expected_owner.

        Only fires for events whose type starts with a registered prefix.
        VAPI_CORE events (no prefix) pass through unchanged — backward compatible.
        Raises NamespaceViolationError on ownership mismatch.
        """
        _NAMESPACE_REGISTRY.validate(event_type, expected_owner)

    async def publish_namespaced(
        self,
        event_type: str,
        payload: dict,
        source: str,
        owner: str,
        agent_bus=None,
    ) -> None:
        """Publish a namespace-validated event.

        Validates the namespace before publishing. If agent_bus is provided,
        delegates to agent_bus.publish() after validation. If not provided,
        broadcasts via ws_broadcast.

        This is the entry point for sub-protocol event publishing. VAPI_CORE
        continues using AgentMessageBus.publish() directly (no change).

        Args:
            event_type:  The event type string (e.g., "mobile.session_verified")
            payload:     Event payload dict
            source:      Agent/component source identifier
            owner:       The sub-protocol claiming ownership of this event
            agent_bus:   Optional AgentMessageBus instance for intra-bridge delivery
        """
        _NAMESPACE_REGISTRY.validate(event_type, owner)
        if agent_bus is not None:
            await agent_bus.publish(event_type, payload, source)
        else:
            envelope = json.dumps({
                "event_type": event_type,
                "payload": payload,
                "source": source,
                "ts": time.time(),
            })
            try:
                await ws_broadcast(envelope)
            except Exception as exc:
                log.warning("FederationBus.publish_namespaced: ws_broadcast error: %s", exc)

    def _get_peers(self) -> list:
        raw = getattr(self._cfg, "federation_peers", "")
        return [p.strip() for p in raw.split(",") if p.strip()] if raw else []

    def _seed_known_hashes_from_db(self) -> None:
        """Pre-populate _known_peer_hashes from DB on startup (Phase 36).

        Prevents duplicate escalations for clusters already processed in a prior
        session. Non-fatal — startup proceeds even if seeding fails.
        """
        try:
            rows = self._store.get_federation_clusters(limit=10000, is_local=False)
            for row in rows:
                peer_url = row.get("peer_url", "")
                h = row.get("cluster_hash", "")
                if peer_url and _is_valid_cluster_hash(h):
                    self._known_peer_hashes.setdefault(peer_url, set()).add(h)
            total = sum(len(s) for s in self._known_peer_hashes.values())
            if total:
                log.info("FederationBus: seeded %d known peer hashes from DB", total)
        except Exception as exc:
            log.warning("FederationBus: DB seeding failed (non-fatal): %s", exc)

    async def run(self) -> None:
        """Main loop — sync with peers every _poll_interval seconds."""
        log.info(
            "FederationBus started (interval=%.0fs, bridge_id=%s)",
            self._poll_interval,
            self._bridge_id,
        )
        # Phase 36: Seed known hashes from DB before first publish (prevents re-escalation)
        self._seed_known_hashes_from_db()
        # Publish local clusters immediately on startup
        await self._publish_local_clusters()
        while self._running:
            await asyncio.sleep(self._poll_interval)
            try:
                await self._sync_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("FederationBus cycle error (non-fatal): %s", exc)

    async def _sync_cycle(self) -> None:
        """Publish local clusters; fetch and process all peer clusters."""
        await self._publish_local_clusters()
        peers = self._get_peers()
        for peer_url in peers:
            try:
                remote_clusters = await self._fetch_peer_clusters(peer_url)
                await self._process_peer_clusters(peer_url, remote_clusters)
            except Exception as exc:
                log.warning("FederationBus: peer %s fetch error: %s", peer_url, exc)

    async def _publish_local_clusters(self) -> None:
        """Detect flagged clusters locally and store in federation_registry as is_local=True."""
        try:
            clusters = self._network_detector.detect_clusters()
        except Exception as exc:
            log.warning("FederationBus: local detect_clusters error: %s", exc)
            return
        for cluster in clusters:
            if not cluster.is_flagged:
                continue
            h = compute_cluster_hash(cluster.device_ids)
            bucket = "critical" if cluster.farm_suspicion_score > 0.85 else "medium"
            try:
                self._store.store_federation_cluster(
                    cluster_hash=h,
                    peer_url="",
                    device_count=len(cluster.device_ids),
                    suspicion_bucket=bucket,
                    bridge_id=self._bridge_id,
                    is_local=True,
                )
            except Exception as exc:
                log.warning("FederationBus: store local cluster error: %s", exc)

    async def _fetch_peer_clusters(self, peer_url: str) -> list:
        """Fetch /federation/clusters from a peer bridge via httpx.

        Returns empty list when httpx is not installed or peer is unreachable.
        """
        if not _HTTPX_AVAILABLE:
            log.debug("FederationBus: httpx not available — skipping peer %s", peer_url)
            return []
        api_key = getattr(self._cfg, "federation_api_key", "")
        url = peer_url.rstrip("/") + "/federation/clusters"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params={"api_key": api_key, "limit": 50})
            resp.raise_for_status()
            return resp.json()

    async def _process_peer_clusters(self, peer_url: str, remote_clusters: list) -> None:
        """Store new peer clusters; dispatch escalation for cross-confirmed hashes."""
        known = self._known_peer_hashes.setdefault(peer_url, set())
        for c in remote_clusters:
            h = c.get("cluster_hash", "")
            if not _is_valid_cluster_hash(h):
                log.warning(
                    "FederationBus: rejecting peer cluster with malformed cluster_hash from %s",
                    peer_url,
                )
                continue
            if h in known:
                continue
            known.add(h)
            bridge_id = c.get("bridge_id", peer_url[:16])
            try:
                self._store.store_federation_cluster(
                    cluster_hash=h,
                    peer_url=peer_url,
                    device_count=c.get("device_count", 0),
                    suspicion_bucket=c.get("suspicion_bucket", "medium"),
                    bridge_id=bridge_id,
                    is_local=False,
                )
            except Exception as exc:
                log.warning("FederationBus: store remote cluster error: %s", exc)

        # Check for cross-confirmed hashes after processing new peer data
        try:
            confirmed = self._store.get_cross_confirmed_hashes(min_peers=2)
        except Exception as exc:
            log.warning("FederationBus: get_cross_confirmed_hashes error: %s", exc)
            return
        for h in confirmed:
            await self._dispatch_escalation(h)

    async def _dispatch_escalation(self, cluster_hash: str) -> None:
        """Persist federated_cluster insight + broadcast via WebSocket + optional on-chain anchor."""
        content = (
            f"Cross-bridge confirmed cluster: hash={cluster_hash} "
            f"seen on \u22652 independent bridge instances. "
            f"Coordinated bot farm operating across deployment shards."
        )
        try:
            self._store.store_protocol_insight(
                insight_type="federated_cluster",
                device_id="",
                content=content,
                severity="critical",
            )
        except Exception as exc:
            log.warning("FederationBus: insight store error: %s", exc)

        event = {
            "type": "proactive_alert",
            "insight_type": "federated_cluster",
            "cluster_hash": cluster_hash,
            "content": content,
            "severity": "critical",
            "timestamp": time.time(),
        }
        try:
            await ws_broadcast(json.dumps(event))
        except Exception as exc:
            log.warning("FederationBus: ws_broadcast error: %s", exc)

        # Optional on-chain anchor — non-fatal
        try:
            if self._chain:
                await self._chain.report_federated_cluster(cluster_hash)
        except Exception as exc:
            log.warning("FederationBus: chain anchor error (non-fatal): %s", exc)
