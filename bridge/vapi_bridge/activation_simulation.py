"""Phase 103 — ActivationSimulator: seeds all VAPI gate conditions synthetically.

Seeding order satisfies Phase 96 chronological invariant:
1. ruling_validation_log  -> consecutive_clean >= gate_n
2. protocol_intelligence_reports -> ready_for_live_mode=True
3. live_mode_activation_log -> first_ready_check_at established
4. gate_attestations -> created_at >= first_ready_check_at V
5. enforcement_certificates -> audit_valid=True, cert_valid=True
6. vhp_issuances -> VHP #1 (tx_hash="sim_mint_<hash>", no chain call)

Never raises.
"""
import hashlib
import hmac
import time


class ActivationSimulator:
    """Seeds all VAPI gate conditions synthetically (Phase 103)."""

    SIM_DEVICE_ID  = "sim_activation_phase103"
    SIM_TO_ADDRESS = "0x0000000000000000000000000000000000000001"

    def __init__(self, cfg, store):
        self._cfg   = cfg
        self._store = store
        self._gate_n = int(getattr(cfg, "validation_gate_n", 100)) if cfg else 100

    def seed_validation_records(self, n: int = 110) -> int:
        """Insert n CERTIFY/no-divergence records. Returns count inserted."""
        count = max(n, self._gate_n + 10)
        for i in range(count):
            try:
                self._store.insert_validation_record(
                    ruling_id=i,
                    device_id=self.SIM_DEVICE_ID,
                    llm_verdict="CERTIFY",
                    fallback_verdict="CERTIFY",
                    llm_confidence=0.95,
                    fallback_confidence=0.95,
                    divergence=0,
                    divergence_reason="{}",
                    pcc_state="NOMINAL",
                    pcc_host_state="EXCLUSIVE_USB",
                )
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        return count

    def seed_protocol_intelligence(self) -> None:
        """Insert protocol_health_score=90, ready_for_live_mode=True report."""
        try:
            report = {
                "protocol_health_score": 90,
                "ready_for_live_mode": True,
                "bottleneck": "none",
                "estimated_days_to_gate": 0,
                "components": {
                    "gate_progress": 95,
                    "fleet_health": 90,
                    "divergence_clarity": 88,
                    "corpus_pass": 85,
                    "class_j_confidence": 90,
                },
            }
            self._store.insert_protocol_intelligence_report(report)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    def seed_live_mode_activation_log(self) -> None:
        """Insert ready_for_live_mode=1 -- establishes first_ready_check_at."""
        try:
            self._store.insert_live_mode_activation_log(
                event_type="sim_activation_phase103",
                ready_for_live_mode=True,
                protocol_health_score=90,
                bottleneck="none",
                blocking_conditions=None,
                operator_notes="Phase 103 simulation seed",
            )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    def seed_gate_attestation(self) -> str:
        """Insert gate_attestation AFTER live_mode log. Returns attestation_hash."""
        ts = int(time.time() * 1_000_000_000)
        raw = f"sim_gate_phase103_{ts}".encode()
        attestation_hash = hashlib.sha256(raw).hexdigest()
        try:
            self._store.insert_gate_attestation(
                attestation_hash=attestation_hash,
                consecutive_clean=self._gate_n + 10,
                gate_n=self._gate_n,
                divergence_rate=0.0,
                on_chain_tx=None,
            )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        return attestation_hash

    def seed_enforcement_certificate(self, hmac_key: str = "sim_phase103") -> dict:
        """Insert enforcement cert with audit_valid=True. Returns cert dict."""
        now = time.time()
        audit_summary = {"first_ready_check_at": now, "gate_attestation_count": 1}
        audit_hash_raw = f"sim_audit_{int(now)}".encode()
        audit_hash = hashlib.sha256(audit_hash_raw).hexdigest()
        hmac_sig = hmac.new(
            hmac_key.encode(), audit_hash.encode(), hashlib.sha256
        ).hexdigest()
        expires_at = now + 86400.0
        try:
            cert_id = self._store.insert_enforcement_certificate(
                audit_hash=audit_hash,
                hmac_sig=hmac_sig,
                audit_valid=True,
                first_ready_check_at=audit_summary["first_ready_check_at"],
                gate_attestation_count=audit_summary["gate_attestation_count"],
                latest_attestation_at=now,
                expires_at=expires_at,
            )
        except Exception:
            cert_id = None
        return {
            "cert_id": cert_id,
            "audit_hash": audit_hash,
            "hmac_sig": hmac_sig,
            "audit_valid": True,
            "expires_at": expires_at,
        }

    def seed_vhp_issuance(self, consecutive_clean: int = 110) -> dict:
        """Insert vhp_issuance with tx_hash='sim_mint_<sha256_hex16>'. Returns vhp dict."""
        now = time.time()
        raw = f"sim_vhp_{int(now * 1e9)}_{self.SIM_DEVICE_ID}".encode()
        tx_suffix = hashlib.sha256(raw).hexdigest()[:16]
        tx_hash = f"sim_mint_{tx_suffix}"
        expires_at = now + 90 * 86400.0
        token_id = 1
        try:
            self._store.insert_vhp_issuance(
                device_id=self.SIM_DEVICE_ID,
                token_id=token_id,
                tx_hash=tx_hash,
                expires_at=expires_at,
                cert_level=1,
                consecutive_clean=consecutive_clean,
                to_address=self.SIM_TO_ADDRESS,
            )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        return {
            "device_id": self.SIM_DEVICE_ID,
            "token_id": token_id,
            "tx_hash": tx_hash,
            "expires_at": expires_at,
            "is_simulation": True,
        }
