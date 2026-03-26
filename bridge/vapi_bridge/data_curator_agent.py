"""Phase 69 — DataCuratorAgent: autonomous data sovereignty + oracle publishing agent.

Lead architect of VAPI data handling. Runs on 5-minute poll cycle (peer to SessionAdjudicator).

Responsibilities:
  1. Classify all new records into 7-class taxonomy
  2. Build data lineage: session → proof → ruling → token eligibility
  3. Compute data quality index per device (0.0–1.0)
  4. Publish oracle updates: HumanityOracle.sol + RulingOracle.sol + PassportOracle.sol
  5. Compute token eligibility scores → log to token_eligibility table
  6. Log all data operations to DataSovereigntyRegistry event stream
  7. Enforce data licensing — only MANUFACTURER / DEVELOPER / GAMER tiers
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_CURATOR_MODEL     = "claude-opus-4-6"
_POLL_INTERVAL_S   = 300   # 5 minutes — same cadence as SessionAdjudicator

# ---------------------------------------------------------------------------
# Data Taxonomy (mirrors VAPIDataMarketplace.sol DataClass enum)
# ---------------------------------------------------------------------------

DATA_TAXONOMY = {
    "SESSION_DATA":     "Raw PoAC records, 228B wire format, inference codes",
    "CALIBRATION_DATA": "L4 thresholds (7.009/5.367), EMA tracks, N=74 corpus",
    "PROOF_DATA":       "Groth16 ZK proofs, Poseidon commitments, MPC ceremony",
    "RULING_DATA":      "Agent rulings, enforcement streaks, credential suspensions",
    "BIOMETRIC_DATA":   "12-feature vectors, tremor FFT, jitter variance IBI",
    "ORACLE_DATA":      "Published oracle values, on-chain update history",
    "REWARD_DATA":      "Token distribution records, eligibility verdicts, multipliers",
}

# Inference code maps (mirrors PITL stack)
_NOMINAL_CODE  = 0x20
_HARD_CODES    = {0x28, 0x29, 0x2A}
_ADV_CODES     = {0x2B, 0x30, 0x31, 0x32}

# Reward multipliers (×100 integer, 100 = 1.0×) — must match VAPIRewardDistributor.sol
_MULT_PASSPORT     = 150   # 1.5×
_MULT_ENROLLMENT   = 200   # 2.0×
_MULT_CLEAN_STREAK = 250   # 2.5×
_MULT_MPC_VERIFIED = 125   # 1.25×
_MULT_GATE_CLEARED = 300   # 3.0×
_CLEAN_STREAK_MIN  = 5     # consecutive NOMINAL sessions required for streak multiplier


@dataclass
class EligibilityScore:
    device_id:          str
    nominal_sessions:   int   = 0
    clean_streak:       int   = 0
    passport_held:      bool  = False
    enrollment_complete: bool = False
    mpc_verified:       bool  = False
    gate_passed:        bool  = False
    base_multiplier:    float = 1.0
    total_multiplier:   float = 1.0
    eligibility_score:  float = 0.0


class DataCuratorAgent:
    """Phase 69 — Autonomous data curator.

    Runs a 5-minute poll loop classifying records, building lineage,
    computing eligibility, and publishing oracle state to IoTeX.

    Never raises to caller — all exceptions caught and logged.
    """

    def __init__(self, cfg, store, chain=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._chain = chain  # may be None if oracle publish disabled
        self._enabled = getattr(cfg, "curator_enabled", True)
        self._publish = getattr(cfg, "curator_oracle_publish", True)

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Background loop: classify + compute + publish every 5 minutes."""
        if not self._enabled:
            log.info("DataCuratorAgent disabled (CURATOR_ENABLED=false)")
            return
        log.info("DataCuratorAgent started (Phase 69) poll=%ds", _POLL_INTERVAL_S)
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._run_curation_cycle()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "DataCuratorAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("DataCuratorAgent: cycle error: %s", exc)

    # -----------------------------------------------------------------------
    # Curation cycle
    # -----------------------------------------------------------------------

    async def _run_curation_cycle(self) -> None:
        """Full curation cycle: classify → lineage → eligibility → oracle publish."""
        devices = self._store.list_known_devices()
        if not devices:
            return
        log.info("DataCuratorAgent: curating %d device(s)", len(devices))

        for device_id in devices:
            try:
                await self._curate_device(device_id)
            except Exception as exc:
                log.warning("DataCuratorAgent: device %s curation error: %s",
                            device_id[:16], exc)

    async def _curate_device(self, device_id: str) -> None:
        # 1. Pull recent records
        records = self._store.get_recent_records(limit=50, device_id=device_id)
        if not records:
            return

        # 2. Classify into taxonomy
        classified = self._classify_records(device_id, records)

        # 3. Build lineage + quality index
        quality_index = self._compute_quality_index(records)

        # 4. Store lineage entries
        for entry in classified:
            self._store.upsert_data_lineage(
                device_id=device_id,
                record_hash=entry.get("record_hash"),
                taxonomy_class=entry["class"],
                quality_index=quality_index,
                curator_note=entry.get("note", ""),
            )

        # 5. Compute token eligibility
        score = self._compute_eligibility(device_id, records)
        self._store.upsert_token_eligibility(
            device_id=score.device_id,
            nominal_sessions=score.nominal_sessions,
            clean_streak=score.clean_streak,
            passport_held=score.passport_held,
            enrollment_complete=score.enrollment_complete,
            mpc_verified=score.mpc_verified,
            gate_passed=score.gate_passed,
            base_multiplier=score.base_multiplier,
            total_multiplier=score.total_multiplier,
            eligibility_score=score.eligibility_score,
        )

        # 6. Publish oracles on-chain
        if self._publish and self._chain is not None:
            await self._publish_oracles(device_id, records, score)

    # -----------------------------------------------------------------------
    # Classification
    # -----------------------------------------------------------------------

    def _classify_records(self, device_id: str, records: list[dict]) -> list[dict]:
        """Classify each record into the 7-class taxonomy."""
        classified = []
        for r in records:
            rec_hash = r.get("record_hash", "")
            inf = r.get("inference")

            # SESSION_DATA — base class for all PoAC records
            classified.append({
                "record_hash": rec_hash,
                "class":       "SESSION_DATA",
                "note":        f"inf=0x{inf:02x}" if inf is not None else "inf=none",
            })

            # BIOMETRIC_DATA — records with feature vectors
            if r.get("mean_json") or r.get("l4_distance") is not None:
                classified.append({
                    "record_hash": rec_hash,
                    "class":       "BIOMETRIC_DATA",
                    "note":        f"l4_dist={r.get('l4_distance', 'N/A')}",
                })

            # PROOF_DATA — records linked to a ZK proof
            if r.get("pitl_proof_tx_hash") or r.get("pitl_proof_commitment"):
                classified.append({
                    "record_hash": rec_hash,
                    "class":       "PROOF_DATA",
                    "note":        f"proof_tx={r.get('pitl_proof_tx_hash', '')[:16]}",
                })

        return classified

    # -----------------------------------------------------------------------
    # Quality Index
    # -----------------------------------------------------------------------

    def _compute_quality_index(self, records: list[dict]) -> float:
        """Data quality index 0.0–1.0 based on:
           - Fraction of NOMINAL sessions (0x20)
           - Presence of feature vectors (l4_distance not None)
           - Absence of hard cheat codes
        """
        if not records:
            return 0.0
        total = len(records)
        nominal_count = sum(1 for r in records if r.get("inference") == _NOMINAL_CODE)
        has_features  = sum(1 for r in records if r.get("l4_distance") is not None)
        hard_count    = sum(1 for r in records
                           if r.get("inference") in _HARD_CODES)

        # 60% weight: nominal fraction; 30% feature coverage; 10% clean (no hard codes)
        q_nominal   = nominal_count / total
        q_features  = has_features / total
        q_clean     = 0.0 if hard_count > 0 else 1.0

        return round(0.60 * q_nominal + 0.30 * q_features + 0.10 * q_clean, 4)

    # -----------------------------------------------------------------------
    # Token Eligibility
    # -----------------------------------------------------------------------

    def _compute_eligibility(self, device_id: str, records: list[dict]) -> EligibilityScore:
        score = EligibilityScore(device_id=device_id)

        # Count NOMINAL sessions lifetime
        enrollment = self._store.get_enrollment(device_id) or {}
        score.nominal_sessions   = enrollment.get("nominal_sessions", 0)
        score.enrollment_complete = enrollment.get("status") == "eligible"

        # Passport
        passport = self._store.get_tournament_passport(device_id)
        score.passport_held = bool(passport and passport.get("on_chain"))

        # Clean streak from ruling state
        streak = self._store.get_ruling_streak(device_id) or {}
        if streak.get("verdict") == "NOMINAL":
            score.clean_streak = streak.get("count", 0)
        else:
            score.clean_streak = 0

        # MPC verified — any record from a V2 proof session (C3 circuit = MPC-verified)
        score.mpc_verified = any(
            r.get("pitl_proof_commitment") for r in records
        )

        # Gate passed — enrollment complete + passport + no active suspension
        ruling_streak = self._store.get_ruling_streak(device_id) or {}
        suspended = ruling_streak.get("verdict") in ("HOLD", "BLOCK")
        score.gate_passed = (
            score.enrollment_complete
            and score.passport_held
            and not suspended
        )

        # Compute multiplier (×100 integer, matching VAPIRewardDistributor.sol)
        m = 100
        if score.passport_held:        m = m * _MULT_PASSPORT    // 100
        if score.enrollment_complete:  m = m * _MULT_ENROLLMENT  // 100
        if score.clean_streak >= _CLEAN_STREAK_MIN:
                                       m = m * _MULT_CLEAN_STREAK // 100
        if score.mpc_verified:         m = m * _MULT_MPC_VERIFIED // 100
        if score.gate_passed:          m = m * _MULT_GATE_CLEARED // 100

        score.total_multiplier = round(m / 100.0, 4)
        score.base_multiplier  = 1.0

        # Eligibility score = (nominal_sessions × multiplier) capped to 1.0 / 100 scale
        # Used for dashboard display and oracle publication
        score.eligibility_score = round(
            min(score.nominal_sessions * score.total_multiplier, 10000.0) / 100.0, 4
        )
        return score

    # -----------------------------------------------------------------------
    # Oracle Publishing
    # -----------------------------------------------------------------------

    async def _publish_oracles(
        self, device_id: str, records: list[dict], score: EligibilityScore
    ) -> None:
        """Publish HumanityOracle, RulingOracle, PassportOracle on IoTeX."""

        # HumanityOracle
        try:
            await self._publish_humanity_oracle(device_id, records)
        except Exception as exc:
            log.warning("DataCuratorAgent: HumanityOracle publish failed %s: %s",
                        device_id[:16], exc)

        # RulingOracle
        try:
            await self._publish_ruling_oracle(device_id)
        except Exception as exc:
            log.warning("DataCuratorAgent: RulingOracle publish failed %s: %s",
                        device_id[:16], exc)

        # PassportOracle
        try:
            await self._publish_passport_oracle(device_id, score)
        except Exception as exc:
            log.warning("DataCuratorAgent: PassportOracle publish failed %s: %s",
                        device_id[:16], exc)

    async def _publish_humanity_oracle(self, device_id: str, records: list[dict]) -> None:
        addr = getattr(self._cfg, "humanity_oracle_address", "")
        if not addr:
            return
        if not records:
            return

        # Latest inference code + humanity stats from most recent enrollment record
        latest = sorted(records, key=lambda r: r.get("created_at", 0), reverse=True)
        inf_code   = latest[0].get("inference", 0) or 0
        enrollment = self._store.get_enrollment(device_id) or {}
        humanity   = enrollment.get("avg_humanity", 0.5)
        human_pct  = min(int(humanity * 1000), 1000)  # scaled ×10

        # L4 distance — average over last 20 records
        l4_vals = [r.get("l4_distance") for r in records[:20]
                   if r.get("l4_distance") is not None]
        l4_dist_x1000 = int(sum(l4_vals) / len(l4_vals) * 1000) if l4_vals else 0

        # L5 CV from most recent record
        l5_cv = latest[0].get("pitl_l5_cv") or 0.0
        l5_cv_x1000 = int(l5_cv * 1000)

        tx_hash = await self._chain.update_humanity_oracle(
            device_id_hex=device_id,
            inference_code=inf_code & 0xFF,
            humanity_pct=human_pct,
            l4_distance_x1000=l4_dist_x1000,
            l5_cv_x1000=l5_cv_x1000,
        )
        self._store.insert_oracle_publication(
            oracle_type="HUMANITY",
            device_id=device_id,
            tx_hash=tx_hash,
            payload_json=json.dumps({
                "inference_code": hex(inf_code),
                "humanity_pct":   human_pct,
                "l4_dist_x1000":  l4_dist_x1000,
            }),
        )
        log.info("DataCuratorAgent: HumanityOracle updated device=%s tx=%s",
                 device_id[:16], tx_hash[:16])

    async def _publish_ruling_oracle(self, device_id: str) -> None:
        addr = getattr(self._cfg, "ruling_oracle_address", "")
        if not addr:
            return

        streak = self._store.get_ruling_streak(device_id) or {}
        # Determine suspension state from credential_enforcement table
        # (RulingEnforcementAgent writes this)
        susp = self._store.get_device_suspension(device_id) or {}
        suspended      = bool(susp.get("suspended"))
        suspended_until = int(susp.get("suspended_until", 0) or 0)

        verdict = streak.get("verdict", "CLEAR")
        count   = streak.get("count",   0)
        flag_streak = count if verdict == "FLAG" else 0
        hold_streak = count if verdict == "HOLD" else 0

        last_hash = streak.get("commitment_hash", "0" * 64)
        last_hash_bytes = bytes.fromhex(last_hash.replace("0x", "").zfill(64))[:32]

        tx_hash = await self._chain.update_ruling_oracle(
            device_id_hex=device_id,
            suspended=suspended,
            flag_streak=flag_streak,
            hold_streak=hold_streak,
            suspended_until=suspended_until,
            last_commitment_hash=last_hash_bytes,
        )
        self._store.insert_oracle_publication(
            oracle_type="RULING",
            device_id=device_id,
            tx_hash=tx_hash,
            payload_json=json.dumps({
                "suspended": suspended,
                "flag_streak": flag_streak,
                "hold_streak": hold_streak,
            }),
        )
        log.info("DataCuratorAgent: RulingOracle updated device=%s tx=%s",
                 device_id[:16], tx_hash[:16])

    async def _publish_passport_oracle(
        self, device_id: str, score: EligibilityScore
    ) -> None:
        addr = getattr(self._cfg, "passport_oracle_address", "")
        if not addr:
            return

        passport = self._store.get_tournament_passport(device_id)
        issued   = bool(passport)
        on_chain = bool(passport and passport.get("on_chain"))
        p_hash_hex = (passport or {}).get("passport_hash", "0" * 64)
        p_hash_bytes = bytes.fromhex(p_hash_hex.replace("0x", "").zfill(64))[:32]
        session_count = score.nominal_sessions

        tx_hash = await self._chain.update_passport_oracle(
            device_id_hex=device_id,
            issued=issued,
            on_chain=on_chain,
            passport_hash=p_hash_bytes,
            session_count=session_count,
        )
        self._store.insert_oracle_publication(
            oracle_type="PASSPORT",
            device_id=device_id,
            tx_hash=tx_hash,
            payload_json=json.dumps({
                "issued":         issued,
                "on_chain":       on_chain,
                "session_count":  session_count,
            }),
        )
        log.info("DataCuratorAgent: PassportOracle updated device=%s tx=%s",
                 device_id[:16], tx_hash[:16])

    # -----------------------------------------------------------------------
    # Public: sovereignty pledge
    # -----------------------------------------------------------------------

    async def publish_sovereignty_pledge(self, schema_hash_hex: str) -> str:
        """Commit the data sovereignty pledge to DataSovereigntyRegistry.sol.

        schema_hash_hex = keccak256(228B wire format + SQLite DDL + all table schemas).
        Returns tx_hash. Raises RuntimeError if address not configured.
        """
        return await self._chain.publish_sovereignty_pledge(schema_hash_hex)

    # -----------------------------------------------------------------------
    # Public: compute reward score (used by BridgeAgent tool #44)
    # -----------------------------------------------------------------------

    def compute_reward_score_sync(self, device_id: str) -> dict:
        """Synchronous wrapper for reward score computation (for BridgeAgent tools)."""
        try:
            records = self._store.get_recent_records(limit=50, device_id=device_id)
            score = self._compute_eligibility(device_id, records)
            return {
                "device_id":          device_id,
                "nominal_sessions":   score.nominal_sessions,
                "clean_streak":       score.clean_streak,
                "passport_held":      score.passport_held,
                "enrollment_complete": score.enrollment_complete,
                "mpc_verified":       score.mpc_verified,
                "gate_passed":        score.gate_passed,
                "base_multiplier":    score.base_multiplier,
                "total_multiplier":   score.total_multiplier,
                "eligibility_score":  score.eligibility_score,
                "multiplier_breakdown": {
                    "passport":     f"{_MULT_PASSPORT/100:.2f}×" if score.passport_held else "1.0×",
                    "enrollment":   f"{_MULT_ENROLLMENT/100:.2f}×" if score.enrollment_complete else "1.0×",
                    "clean_streak": f"{_MULT_CLEAN_STREAK/100:.2f}×" if score.clean_streak >= _CLEAN_STREAK_MIN else "1.0×",
                    "mpc_verified": f"{_MULT_MPC_VERIFIED/100:.2f}×" if score.mpc_verified else "1.0×",
                    "gate_passed":  f"{_MULT_GATE_CLEARED/100:.2f}×" if score.gate_passed else "1.0×",
                },
            }
        except Exception as exc:
            log.warning("DataCuratorAgent.compute_reward_score_sync: %s", exc)
            return {"error": str(exc), "device_id": device_id}
