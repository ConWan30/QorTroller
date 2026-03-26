"""Phase 84 — AdjudicationWarmUpRunner.

Pre-live-mode dry-run batch: adjudicates the N most recently active devices via
SessionAdjudicator._adjudicate_device_directly() before the operator flips
AGENT_DRY_RUN=false. Exposes whether LLM is available (W1: warm-up must
document if it ran via _rule_fallback, not the actual LLM).

Also provides compute_gate_attestation_hash() — the canonical formula that
produces the attestation_hash recorded in both SQLite (gate_attestations table)
and on IoTeX (GateAttestationAnchor.sol).

Never raises — all errors logged and returned in the WarmUpReport.
"""

import asyncio
import hashlib
import logging
import struct
import time

log = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 5
_DEFAULT_TIMEOUT_S = 30.0


def compute_gate_attestation_hash(
    consecutive_clean: int,
    gate_n: int,
    divergence_rate: float,
    timestamp_ns: int,
) -> str:
    """Return hex SHA-256 of (consecutive_clean || gate_n || divergence_rate || timestamp_ns).

    Formula (Phase 84):
        SHA-256(
            struct.pack(">I", consecutive_clean) ||
            struct.pack(">I", gate_n) ||
            struct.pack(">d", divergence_rate) ||
            struct.pack(">Q", timestamp_ns)
        )

    Matches GateAttestationAnchor.sol logical binding — the on-chain record uses
    divergenceRateMillis (int(divergence_rate * 1000)) for gas efficiency, but the
    hash is computed off-chain from the full float for exact reproducibility.

    Returns: lowercase hex string (64 chars).
    """
    data = (
        struct.pack(">I", int(consecutive_clean)) +
        struct.pack(">I", int(gate_n)) +
        struct.pack(">d", float(divergence_rate)) +
        struct.pack(">Q", int(timestamp_ns))
    )
    return hashlib.sha256(data).hexdigest()


class AdjudicationWarmUpRunner:
    """Phase 84 — Batch pre-activation dry-run adjudicator.

    Selects the most recently active devices from agent_rulings and fires
    dry-run adjudications through SessionAdjudicator._adjudicate_device_directly().

    W1 mitigation: WarmUpReport includes llm_available (bool) and fallback_count.
    If llm_available=False, the operator knows warm-up ran on rule logic only —
    not the production LLM — and must ensure anthropic key is set before going live.
    """

    def __init__(self, cfg, store) -> None:
        self._cfg = cfg
        self._store = store
        self._batch_size = int(getattr(cfg, "warm_up_batch_size", _DEFAULT_BATCH_SIZE))

    def _llm_available(self) -> bool:
        """Check whether the Anthropic client is importable (W1 llm_available signal)."""
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_recent_devices(self, n: int) -> list:
        """Return up to n device_ids with the most recent agent_ruling entries."""
        try:
            with self._store._conn() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT device_id FROM agent_rulings "
                    "ORDER BY created_at DESC LIMIT ?",
                    (n,),
                ).fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            log.warning("AdjudicationWarmUpRunner: _get_recent_devices failed: %s", exc)
            return []

    async def _anchor_gate_on_chain(self, chain) -> str | None:
        """Compute attestation hash, persist to SQLite, then publish to GateAttestationAnchor.sol.

        W1 invariant: The attestation_hash is computed ONCE here and passed to both the
        SQLite insert and the chain call — it is never recomputed between the two calls.
        This ensures the on-chain record and the SQLite row are cryptographically identical.

        Returns tx_hash hex on success, None on any error (never raises).
        """
        addr = getattr(self._cfg, "gate_attestation_anchor_address", None)
        if not addr:
            return None
        try:
            summary = self._store.get_validation_summary(
                gate_n=int(getattr(self._cfg, "validation_gate_n", 100)),
                max_divergence_rate=float(getattr(self._cfg, "validation_max_divergence_rate", 1.0)),
            )
        except Exception as exc:
            log.warning("AdjudicationWarmUpRunner: get_validation_summary failed: %s", exc)
            return None

        consecutive_clean = int(summary.get("consecutive_clean", 0))
        gate_n = int(getattr(self._cfg, "validation_gate_n", 100))
        divergence_rate = float(summary.get("divergence_rate", 0.0) or 0.0)
        timestamp_ns = time.time_ns()

        attestation_hash_hex = compute_gate_attestation_hash(
            consecutive_clean, gate_n, divergence_rate, timestamp_ns
        )

        try:
            tx_hash = await chain.record_gate_attestation_on_chain(
                attestation_hash_hex=attestation_hash_hex,
                consecutive_clean=consecutive_clean,
                gate_n=gate_n,
                divergence_rate=divergence_rate,
                timestamp_ns=timestamp_ns,
            )
        except Exception as exc:
            log.warning("AdjudicationWarmUpRunner: record_gate_attestation_on_chain failed: %s", exc)
            return None

        # Persist AFTER chain call — INSERT OR IGNORE is idempotent on retry
        try:
            self._store.insert_gate_attestation(
                attestation_hash=attestation_hash_hex,
                consecutive_clean=consecutive_clean,
                gate_n=gate_n,
                divergence_rate=divergence_rate,
                on_chain_tx=tx_hash,
            )
        except Exception as exc:
            log.warning("AdjudicationWarmUpRunner: insert_gate_attestation failed: %s", exc)

        log.info(
            "AdjudicationWarmUpRunner: gate anchored on-chain tx=%s hash=%s... clean=%d",
            tx_hash[:16], attestation_hash_hex[:16], consecutive_clean,
        )
        return tx_hash

    async def run_warm_up(self, device_ids=None, chain=None) -> dict:
        """Run dry-run adjudications for device_ids (or recent devices if None).

        chain — optional ChainClient; when provided AND gate_attestation_anchor_address
                is configured, publishes a gate attestation to GateAttestationAnchor.sol
                after the adjudication batch completes (Phase 87).

        Returns WarmUpReport dict:
            completed: int
            failed: int
            llm_available: bool  (W1 — False means _rule_fallback was used)
            fallback_count: int
            duration_ms: float
            device_ids_attempted: list[str]
            batch_size: int
            on_chain_published: bool  (Phase 87 — True if gate attestation anchored)
            on_chain_tx: str | None   (Phase 87 — tx hash if anchored)
        """
        t0 = time.time()
        if device_ids is None:
            device_ids = self._get_recent_devices(self._batch_size)

        llm_ok = self._llm_available()
        completed = 0
        failed = 0
        fallback_count = 0

        for device_id in device_ids:
            try:
                from .session_adjudicator import SessionAdjudicator
                adj = SessionAdjudicator(self._cfg, self._store)
                verdict, ruling_id = await asyncio.wait_for(
                    adj._adjudicate_device_directly(
                        device_id=device_id,
                        entropy_variance=None,
                        source="warm_up",
                    ),
                    timeout=_DEFAULT_TIMEOUT_S,
                )
                completed += 1
                if not llm_ok:
                    fallback_count += 1
                log.info(
                    "AdjudicationWarmUpRunner: device=%s verdict=%s ruling_id=%s",
                    device_id[:16],
                    verdict,
                    ruling_id,
                )
            except asyncio.TimeoutError:
                log.warning(
                    "AdjudicationWarmUpRunner: timeout for device %s", device_id[:16]
                )
                failed += 1
            except Exception as exc:
                log.warning(
                    "AdjudicationWarmUpRunner: error for device %s: %s",
                    device_id[:16],
                    exc,
                )
                failed += 1

        # Phase 87: optionally anchor gate attestation on-chain
        on_chain_tx = None
        if chain is not None:
            on_chain_tx = await self._anchor_gate_on_chain(chain)

        duration_ms = (time.time() - t0) * 1000
        return {
            "completed": completed,
            "failed": failed,
            "llm_available": llm_ok,
            "fallback_count": fallback_count,
            "duration_ms": round(duration_ms, 1),
            "device_ids_attempted": list(device_ids),
            "batch_size": self._batch_size,
            "on_chain_published": on_chain_tx is not None,
            "on_chain_tx": on_chain_tx,
        }
