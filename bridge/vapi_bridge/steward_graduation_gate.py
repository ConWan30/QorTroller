"""Ceremony A — the steward-graduation AUTHORIZATION GATE (dual-key teeth).

The governance chain built this session ends at a dual-signed attestation: SEL scores a steward's task-class
→ recommends GRADUATE_TASK_CLASS → the operator accepts → Guardian's HSM attests AND the operator co-signs
(steward_sel_cosign.verify_dual_signed_attestation → fully_authorized). But `fully_authorized` is a
per-RECORD fact with no consumer. This module is the missing predicate that turns "a dual-authorized ACCEPT
exists" into a NAMED, TESTABLE capability an auto-persist path must check: "does a dual-authorized
graduation of (steward, task_class) CURRENTLY hold?"

It is a pure gate over an INJECTED list of dual-signed attestation records — the same shape the cosign CLI
writes. State machine (grok round-20): filter to (steward, task_class); keep only records that verify
fully_authorized against the PINNED Guardian key; the max-`ts_ns` record wins; ACCEPT → graduated, REJECT →
revoked. An ACCEPT whose package is threshold-incoherent (n_labels < min_samples or precision below floor)
does NOT graduate — the math is free and the operator (or a mistaken CLI) can sign a failing package.

HARD BOUNDARIES:
  * Guardian key is PINNED at the gate (mandatory `guardian_pubkey_hex`, no default). Verification uses the
    pinned key ONLY; a record's embedded `pubkey_hex` is display-only and is NEVER the trust root at
    consumption (closes steward_sel_cosign round-18 F4).
  * This does NOT touch `cfg.operator_dual_key_present` or the O3-supersede path — that bool is byte-packed
    into the FROZEN VAPI-O3-SUPERSEDE-v1 preimage and must not move. The `operator_dual_key_...demonstrated`
    helper here is a READ-ONLY advisory, wired nowhere this pass.
  * DORMANT: no live auto-persist consumer is wired (v0.1). This is the primitive that path will call.

V0 LIMIT (honest, grok round-20): the gate is pure over the records it is GIVEN. Ledger completeness is the
consumer's responsibility (same class as SEL's ingestion-authenticity limit): dropping a later REJECT from
the list is an availability / ledger-custody attack, not a crypto forge, and can leave a stale ACCEPT
graduated. The v0.1 fix is an append-only attestation store (optional hash-chain / tip digest) at the store
boundary — not inside this pure gate. Each record is individually non-repudiable (dual-signed) regardless.
"""
from __future__ import annotations


def _require_pin(guardian_pubkey_hex) -> None:
    if not (isinstance(guardian_pubkey_hex, str) and guardian_pubkey_hex.strip()):
        raise ValueError(
            "guardian_pubkey_hex is MANDATORY — the gate must pin the trusted Guardian key at the "
            "consumption point; a record's embedded pubkey is display-only, never the trust root.")


_NOTE = ("v0 pure gate over INJECTED dual-signed records; Guardian key PINNED (embedded pubkey display-only). "
         "Consumer owns ledger completeness — a dropped later REJECT can leave a stale ACCEPT graduated "
         "(availability limit, not a crypto forge) — and must TOTAL-ORDER records (equal ts_ns ties resolve "
         "by list position, so a consumer should use unique/monotonic ts_ns). DORMANT: no auto-persist "
         "consumer wired. Does not touch operator_dual_key_present / the frozen O3-supersede path.")


def is_task_class_graduated(records: list, *, steward: str, task_class: str,
                            guardian_pubkey_hex: str) -> dict:
    """Does a dual-authorized graduation of (steward, task_class) CURRENTLY hold? Pure; fail-closed."""
    _require_pin(guardian_pubkey_hex)
    from .steward_sel_cosign import verify_dual_signed_attestation

    valid = []   # (ts_ns, state, record) where state in {"ACCEPT","REJECT","INCOHERENT"}
    for r in records or []:
        try:
            if r.get("steward") != steward or r.get("task_class") != task_class:
                continue
            v = verify_dual_signed_attestation(r, guardian_pubkey_hex=guardian_pubkey_hex)
            if not v.get("fully_authorized"):
                continue                                   # wrong Guardian key / no operator co-sign / tamper
            decision = str(r.get("decision", "")).upper()
            if decision == "ACCEPT":
                coherent = (int(r.get("n_labels", 0)) >= int(r.get("min_samples", 0))
                            and int(r.get("precision_milli", 0)) >= int(r.get("precision_floor_milli", 0)))
                valid.append((int(r.get("ts_ns", 0)), "ACCEPT" if coherent else "INCOHERENT", r))
            elif decision == "REJECT":
                valid.append((int(r.get("ts_ns", 0)), "REJECT", r))
        except Exception:  # noqa: BLE001 - a bad record is skipped, never a spurious graduate
            continue

    if not valid:
        return {"graduated": False, "reason": "no_valid_record", "steward": steward,
                "task_class": task_class, "n_valid": 0, "authorizing_digest_hex": None,
                "revoked_by": None, "note": _NOTE}

    valid.sort(key=lambda x: x[0])                          # by ts_ns ascending; latest is last
    latest_ts, latest_state, latest_rec = valid[-1]
    digest = latest_rec.get("digest_hex")
    base = {"steward": steward, "task_class": task_class, "n_valid": len(valid), "note": _NOTE}
    if latest_state == "ACCEPT":
        return {**base, "graduated": True, "reason": "graduated",
                "authorizing_digest_hex": digest, "revoked_by": None}
    if latest_state == "REJECT":
        return {**base, "graduated": False, "reason": "revoked",
                "authorizing_digest_hex": None, "revoked_by": digest}
    # latest is a fully-authorized but threshold-incoherent ACCEPT
    return {**base, "graduated": False, "reason": "threshold_incoherent",
            "authorizing_digest_hex": digest, "revoked_by": None}


def operator_dual_key_cryptographically_demonstrated(records: list, operator_address: str, *,
                                                     guardian_pubkey_hex: str) -> bool:
    """READ-ONLY advisory: does a fully_authorized dual-signed record from this operator address exist? Gives
    the dual-key concept cryptographic teeth WITHOUT touching the frozen `operator_dual_key_present` bool or
    the O3-supersede path. Named `_demonstrated` (never `_present`) so it is not confused with the config
    flag. Wired nowhere this pass — a consumer MAY read it; it changes no gating on its own."""
    _require_pin(guardian_pubkey_hex)
    from .steward_sel_cosign import verify_dual_signed_attestation
    for r in records or []:
        try:
            if str(r.get("operator_id", "")).lower() != str(operator_address).lower():
                continue
            if verify_dual_signed_attestation(r, guardian_pubkey_hex=guardian_pubkey_hex).get(
                    "fully_authorized"):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False
