"""Consent-gated notary wrap. Bridge cannot grant consent."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from .envelope import ObservationEnvelope
from .locks import DualLocks, compose_locks
from .sanitize import strip_truth_leaks

@dataclass(frozen=True)
class ConsentRecord:
    gamer: str
    granted: bool
    purpose: str
    signed_by: str
    note: str = ""
    def valid_for_wrap(self) -> bool:
        if not self.granted or not self.gamer or not self.signed_by:
            return False
        if self.signed_by.lower() != self.gamer.lower():
            return False
        if self.signed_by.lower() in {"bridge", "operator", "qortroller", "qoresence"}:
            return False
        return self.purpose in {"portcert", "wmp", "portcert+wmp"}

@dataclass
class WrapResult:
    status: str
    reason: str
    locks: DualLocks
    envelope_commitment: str | None
    portcert: dict | None
    wmp_precursor: dict | None
    def to_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason, "locks": self.locks.to_hud(), "envelope_commitment": self.envelope_commitment, "portcert": self.portcert, "wmp_precursor": self.wmp_precursor}

def wrap_notary(envelope: ObservationEnvelope, consent: ConsentRecord | None, *, coupling_present: bool | None = None, same_seq: bool = True) -> WrapResult:
    strip_truth_leaks(envelope.to_dict())
    commitment = envelope.clock_commitment
    if coupling_present is None:
        coupling_present = any(t.get("ticket_kind") == "coupling" and t.get("ticket_id") for t in envelope.ticks)
    if consent is None or not consent.valid_for_wrap():
        locks = compose_locks(coupling_ticket=coupling_present, same_seq=same_seq, consent_granted=False, wrap_sealed=False)
        reason = "consent missing or invalid — bridge cannot grant"
        if consent is not None and consent.signed_by.lower() != (consent.gamer or "").lower():
            reason = "signed_by != gamer — wrap REFUSED"
        return WrapResult("REFUSED", reason, locks, commitment, None, None)
    portcert_body: dict[str, Any] = {
        "schema": "qortroller.portcert-lite.v0", "plane": "truth", "advisory": True, "never_ban": True,
        "session_id": envelope.session_id, "clock_commitment": commitment, "tick_count": len(envelope.ticks),
        "sidecar_hashes": envelope.sidecar_hashes,
        "consent": {"gamer": consent.gamer, "purpose": consent.purpose, "granted": True, "signed_by": consent.signed_by},
        "sealed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ceilings": {"scope": "developer_self", "network": "off-chain-lite", "humanity_claim": False},
    }
    portcert_body["receipt"] = "sha256:" + hashlib.sha256(json.dumps(portcert_body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    wmp = None
    if consent.purpose in {"wmp", "portcert+wmp"}:
        wmp = {"schema": "qortroller.wmp-precursor.v0", "channel": "action-only", "biometric_export": False, "session_id": envelope.session_id, "clock_commitment": commitment, "consent_purpose": consent.purpose, "note": "precursor only — no buyer implied"}
    locks = compose_locks(coupling_ticket=coupling_present, same_seq=same_seq, consent_granted=True, wrap_sealed=True)
    return WrapResult("SEALED", "gamer-signed consent accepted", locks, commitment, portcert_body, wmp)
