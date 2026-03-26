"""Phase 76 — RulingProvenanceAnchorAgent.

Computes a cryptographic provenance anchor for every agent ruling by binding three
independent evidence streams into a single verifiable hash:

  provenance_hash = SHA-256(
      commitment_hash_hex            # Phase 66 ruling commitment (on-chain)
      + "|" + ceremony_canonical     # Canonical ceremony data (beacon + contributors)
      + "|" + evidence_canonical     # Canonical evidence set (sort_keys=True)
  )

This creates the first verifiable AI cognitive audit trail in competitive gaming:
anyone with the ruling, ceremony, and evidence data can independently recompute the hash
and confirm it matches the stored anchor.

Canonical serialization rules (W1 mitigation — deterministic across Python versions):
  - beacon_block_number: int(x) — never float
  - contributor_count:   int(x) — never float
  - ceremony_canonical:  JSON-serialized dict with only {beacon_block_number, contributor_count}
  - evidence_canonical:  JSON-serialized evidence_json with sort_keys=True

On-chain publication (optional, RULING_PROVENANCE_PUBLISH_ENABLED=false default):
  When enabled, calls chain.record_ruling_on_chain() for dry_run=0 rulings using
  provenance_hash as the commitment — creating a second on-chain trace that binds
  the AI ruling to its ceremony and evidence provenance.

Never raises — all errors logged, agent continues polling.
"""

import asyncio
import hashlib
import json
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300  # 5 minutes — same as other agents


def compute_provenance_hash(
    commitment_hash: str,
    ceremony_data: dict,
    evidence_data: dict,
) -> str:
    """Compute provenance anchor hash deterministically.

    Canonical rules per W1 mitigation:
    - Only beacon_block_number and contributor_count from ceremony_data
    - Both cast to int() to avoid float serialization differences across Python versions
    - evidence_data serialized with sort_keys=True
    - Components joined by "|" separator (not present in any component value)
    """
    ceremony_canonical = json.dumps(
        {
            "beacon_block_number": int(ceremony_data.get("beacon_block_number") or 0),
            "contributor_count": int(ceremony_data.get("contributor_count") or 0),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    evidence_canonical = json.dumps(
        evidence_data,
        sort_keys=True,
        separators=(",", ":"),
    )
    raw = "|".join([commitment_hash or "", ceremony_canonical, evidence_canonical])
    return hashlib.sha256(raw.encode()).hexdigest()


class RulingProvenanceAnchorAgent:
    """Computes provenance anchor hashes for agent rulings (Phase 76).

    Polls agent_rulings LEFT JOIN ruling_provenance_anchors for entries without
    a provenance record. Computes and stores the anchor hash. Optionally publishes
    to RulingRegistry.sol for dry_run=0 rulings when RULING_PROVENANCE_PUBLISH_ENABLED.
    """

    def __init__(self, cfg, store, chain=None) -> None:
        self._cfg = cfg
        self._store = store
        self._chain = chain  # ChainClient or None — only needed for on-chain publish
        self._publish_enabled = bool(
            getattr(cfg, "ruling_provenance_publish_enabled", False)
        )

    async def run_event_consumer(self) -> None:
        """Background loop — polls for rulings needing provenance anchoring every 5 minutes."""
        log.info(
            "RulingProvenanceAnchorAgent started (Phase 76) publish_enabled=%s",
            self._publish_enabled,
        )
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._anchor_pending_rulings()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "RulingProvenanceAnchorAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("RulingProvenanceAnchorAgent: cycle error: %s", exc)

    async def _anchor_pending_rulings(self) -> None:
        """Fetch rulings without provenance anchors and compute + store hashes."""
        try:
            with self._store._conn() as conn:
                rows = conn.execute(
                    "SELECT ar.* FROM agent_rulings ar "
                    "LEFT JOIN ruling_provenance_anchors rpa ON ar.id = rpa.ruling_id "
                    "WHERE rpa.id IS NULL "
                    "ORDER BY ar.created_at ASC LIMIT 50"
                ).fetchall()
        except Exception as exc:
            log.warning("RulingProvenanceAnchorAgent: query failed: %s", exc)
            return

        if not rows:
            return

        log.info(
            "RulingProvenanceAnchorAgent: anchoring %d ruling(s)",
            len(rows),
        )
        for row in rows:
            try:
                await self._anchor_ruling(dict(row))
            except Exception as exc:
                log.warning(
                    "RulingProvenanceAnchorAgent: anchor failed ruling_id=%s: %s",
                    row["id"] if hasattr(row, "__getitem__") else "?", exc,
                )

    async def _anchor_ruling(self, row: dict) -> None:
        """Compute and store the provenance anchor for one ruling."""
        ruling_id = row["id"]
        device_id = row.get("device_id", "")
        commitment_hash = row.get("commitment_hash") or ""
        verdict = row.get("verdict", "FLAG")
        confidence = float(row.get("confidence", 0.5))
        dry_run = bool(row.get("dry_run", True))

        # Parse ceremony and evidence — both stored as JSON; default to empty dict
        try:
            ceremony_data = json.loads(row.get("ceremony_integrity") or "{}")
        except (json.JSONDecodeError, TypeError):
            ceremony_data = {}

        try:
            evidence_data = json.loads(row.get("evidence_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            evidence_data = {}

        # Compute ceremony and evidence sub-hashes for audit transparency
        ceremony_canonical = json.dumps(
            {
                "beacon_block_number": int(ceremony_data.get("beacon_block_number") or 0),
                "contributor_count": int(ceremony_data.get("contributor_count") or 0),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        ceremony_hash = hashlib.sha256(ceremony_canonical.encode()).hexdigest()

        evidence_canonical = json.dumps(
            evidence_data,
            sort_keys=True,
            separators=(",", ":"),
        )
        evidence_hash = hashlib.sha256(evidence_canonical.encode()).hexdigest()

        provenance_hash = compute_provenance_hash(
            commitment_hash, ceremony_data, evidence_data
        )

        # Store locally — always
        self._store.insert_provenance_anchor(
            ruling_id=ruling_id,
            device_id=device_id,
            provenance_hash=provenance_hash,
            ceremony_hash=ceremony_hash,
            evidence_hash=evidence_hash,
        )

        log.debug(
            "RulingProvenanceAnchorAgent: anchored ruling_id=%d provenance=%s...",
            ruling_id, provenance_hash[:16],
        )

        # On-chain publication — optional, only for live (non-dry-run) rulings
        if self._publish_enabled and not dry_run and self._chain is not None:
            try:
                provenance_bytes = bytes.fromhex(provenance_hash)
                confidence_1000 = int(confidence * 1000)
                await self._chain.record_ruling_on_chain(
                    device_id, provenance_bytes, verdict, confidence_1000
                )
                log.info(
                    "RulingProvenanceAnchorAgent: provenance published on-chain "
                    "ruling_id=%d device=%s...",
                    ruling_id, device_id[:12],
                )
            except Exception as exc:
                log.warning(
                    "RulingProvenanceAnchorAgent: on-chain publish failed ruling_id=%d: %s",
                    ruling_id, exc,
                )
