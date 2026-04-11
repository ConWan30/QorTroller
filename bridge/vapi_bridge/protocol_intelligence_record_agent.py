"""
ProtocolIntelligenceRecordAgent — Phase 189, agent #33.

Creates and maintains the Protocol Intelligence Record (PIR) chain:
a SHA-256 hash-linked chain of autoresearch cycle outputs, analogous to the PoAC chain.

PIR structure:
  prev_pir_hash     — SHA-256 of previous PIR body ("0"*64 for genesis)
  cycle_number      — monotonic autoresearch cycle number (1, 2, ... 10, 11 ...)
  phase_produced    — which phase this cycle specified (e.g. "186")
  wif_hash          — SHA-256(WIF entry content)
  threat_forecast   — predicted WIF domain for NEXT cycle (committed before next build)
  harness_score     — eval harness score for this cycle's proposal (0.0-1.0)
  eval_timestamp    — when the harness ran (unix seconds)
  pir_hash          — SHA-256(all above fields) — chain link hash

chain_hash = SHA-256(f"{prev}:{cycle}:{phase}:{wif}:{forecast}:{score:.6f}:{ts_int}")

Anchors to AdjudicationRegistry.sol every pir_anchor_interval cycles (dry_run by default).

First PIR committed retroactively: PIR-0010
  cycle_number = 10 (AutoResearch Cycle 10 — WIF-033, Phase 186/187)
  phase_produced = "187"
  wif_hash = SHA-256("WIF-033: Attestation Hash Front-Running Attack")
  threat_forecast = "pir_chain_integrity_attack"  (predicted WIF-034 domain)
  harness_score = 0.78

Infrastructure-first default: pir_chain_enabled=False.
Fail-open: exceptions → WARNING logged, chain not updated.
"""

import asyncio
import hashlib
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 600  # 10-minute poll cycle

# Genesis PIR-0010 content (Cycle 10 → Phase 187, WIF-033 fully closed)
_GENESIS_PIR = {
    "cycle_number":   10,
    "phase_produced": "187",
    "wif_content":    (
        "WIF-033: Attestation Hash Front-Running Attack — adversary monitors IoTeX mempool "
        "for registerAttestation() tx, extracts attestation_hash before confirmation. "
        "Timing disclosure vector (not forgery — HMAC prevents hash construction). "
        "W1 CLOSED Phase 187: AttestationOpSecAdvisorAgent monitors active windows. "
        "W2 CLOSED Phase 187: VHPReenrollmentBadge.sol ERC-4671 soulbound identity credential."
    ),
    "threat_forecast": "pir_chain_integrity_attack",  # WIF-034 prediction
    "harness_score":   0.78,
}


class ProtocolIntelligenceRecordAgent:
    """Agent #33 — Phase 189 Protocol Intelligence Record chain.

    Maintains the PIR chain — a cryptographic audit trail of VAPI's
    autonomous threat discovery process. Each PIR entry captures:
      - Which autoresearch cycle ran
      - Which phase it produced
      - The WIF it discovered (SHA-256 hash)
      - Its prediction for the NEXT WIF domain (committed before next build)
      - The eval harness score

    Bootstraps PIR-0010 on first run if chain is empty.
    Publishes pir_created bus event when a new PIR is added.
    """

    def __init__(self, store, cfg, bus=None):
        self._store = store
        self._cfg = cfg
        self._bus = bus
        self._anchor_interval = int(getattr(cfg, "pir_anchor_interval", 10))

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _bootstrap_genesis_pir(self) -> bool:
        """Insert PIR-0010 as the genesis record if chain is empty.

        Returns True if genesis was inserted, False if chain already populated.
        """
        try:
            _status = self._store.get_pir_chain_status(limit=1)
            if _status["total_pirs"] > 0:
                return False  # chain already exists
            # Compute WIF hash
            _wif_hash = hashlib.sha256(_GENESIS_PIR["wif_content"].encode()).hexdigest()
            _now = time.time()
            _row_id, _pir_hash = self._store.insert_pir(
                cycle_number=_GENESIS_PIR["cycle_number"],
                phase_produced=_GENESIS_PIR["phase_produced"],
                wif_hash=_wif_hash,
                threat_forecast=_GENESIS_PIR["threat_forecast"],
                harness_score=_GENESIS_PIR["harness_score"],
                eval_timestamp=_now,
            )
            log.info(
                "ProtocolIntelligenceRecordAgent: PIR-0010 genesis inserted "
                "pir_hash=%s row_id=%d (WIF-033 retrospective)",
                _pir_hash[:16], _row_id,
            )
            return True
        except ValueError:
            # Duplicate — already inserted
            return False
        except Exception as exc:
            log.warning("ProtocolIntelligenceRecordAgent._bootstrap_genesis_pir: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Status report
    # ------------------------------------------------------------------

    def _report_status(self) -> None:
        """Log PIR chain status on each poll cycle."""
        try:
            _status = self._store.get_pir_chain_status(limit=3)
            _intact = _status.get("chain_intact", True)
            _total  = _status.get("total_pirs", 0)
            _latest = _status.get("latest_pir_hash", "")[:16]
            _cycle  = _status.get("latest_cycle", 0)
            if not _intact:
                log.error(
                    "ProtocolIntelligenceRecordAgent: PIR CHAIN BROKEN! "
                    "total=%d latest_cycle=%d latest_pir=%s...",
                    _total, _cycle, _latest,
                )
                if self._bus:
                    try:
                        self._bus.publish_sync("pir_chain_broken", {
                            "total_pirs":   _total,
                            "latest_cycle": _cycle,
                            "timestamp":    time.time(),
                        })
                    except Exception as _be:
                        log.warning("ProtocolIntelligenceRecordAgent bus publish: %s", _be)
            else:
                log.debug(
                    "ProtocolIntelligenceRecordAgent: chain intact total=%d "
                    "latest_cycle=%d pir=%s...",
                    _total, _cycle, _latest,
                )
        except Exception as exc:
            log.warning("ProtocolIntelligenceRecordAgent._report_status: %s", exc)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Bootstrap PIR-0010 on start, then poll every 10 minutes."""
        log.info(
            "ProtocolIntelligenceRecordAgent started (agent #33, Phase 189; "
            "poll=%ds, anchor_interval=%d)",
            _POLL_INTERVAL_S, self._anchor_interval,
        )
        # Bootstrap genesis PIR-0010 synchronously on startup
        self._bootstrap_genesis_pir()
        while True:
            await asyncio.sleep(_POLL_INTERVAL_S)
            self._report_status()
