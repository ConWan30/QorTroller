"""A2A-STEWARD-EVOLVE — operator-held-key CO-SIGN for REAL non-repudiation (the v1 grok named).

The SEL graduation attestation (steward_sel_attestation.py) has Guardian's HSM sign a decision package, but
its honest limit is that `operator_id` is DECLARATIVE — the signature proves GUARDIAN recorded it, not that
the operator authorized it (the bridge holds Guardian's AWS creds, so it could produce Guardian's half).

This module closes that gap. The operator co-signs the SAME digest Guardian signed, with a secp256k1 key
THE OPERATOR HOLDS and the bridge never sees. Because `operator_id` IS the operator's address, verification
RECOVERS the signer from the operator signature and checks it equals `operator_id` — which AUTHENTICATES the
previously-declarative field. `fully_authorized` then means: Guardian's HSM recorded package P AND the
keyholder controlling `operator_id` authorized the same P. The bridge cannot forge the operator half.

HONEST CLAIM (grok round-17): this is real non-repudiation IN THE PROTOCOL SENSE — proof that the keyholder
of address A authorized decision package P alongside Guardian. It does NOT prove a named human read and
cognitively intended it (key theft and blind-signing a staged file are honest residuals; crypto
non-repudiation != cognitive intent). SEL still never auto-applies; a dual-signed record is EVIDENCE of a
past decision, not a capability token.

Design (grok round-17): independent co-sign of the SAME preimage digest (no bind to Guardian's sig —
preimage uniqueness incl. ts_ns + SEL chain-head already prevents mix-and-match); RAW SHA-256 digest to
match Guardian's KMS DIGEST mode (NOT EIP-191); `eth_keys` (repo house style, stable) not
Account.unsafe_sign_hash. Leaves the `operator_dual_key_present` bool alone — exports
`cryptographic_dual_key_satisfied` for consumers to gate on the real dual-key later. secp256k1 (matches
Guardian's key + makes operator_id=address recover-native). CANDIDATE; 0-IOTX; off-chain; no O3 rewire.
"""
from __future__ import annotations

import hashlib

# The co-sign key MUST NOT be the bridge/deployer wallet — if the bridge holds it, there is no
# non-repudiation. Mirrors the refuse-guard in contracts/scripts/set-world-model-consent.js.
BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
OPERATOR_SIGNING_METHOD = "raw-sha256-digest-secp256k1"


def _is_address(s) -> bool:
    return (isinstance(s, str) and s.startswith("0x") and len(s) == 42
            and all(c in "0123456789abcdefABCDEF" for c in s[2:]))


def _recover_address(digest: bytes, sig_bytes: bytes) -> str:
    from eth_keys import keys
    return keys.Signature(sig_bytes).recover_public_key_from_msg_hash(digest).to_checksum_address()


def assert_operator_key_not_bridge(address: str) -> None:
    """Refuse the bridge/deployer wallet as the operator co-sign key (trust-collapse guard)."""
    if str(address).lower() == BRIDGE_WALLET.lower():
        raise ValueError(
            f"operator co-sign key derives the BRIDGE wallet {address} — refusing. If the bridge holds "
            "the key there is NO non-repudiation. Use a separate operator-held key.")


def _digest_from_record(record: dict) -> bytes:
    """Re-derive the SHA-256 digest from the record's public fields via the ONE canonical preimage builder
    (never trust a stored digest_hex — recompute)."""
    from .steward_sel_attestation import build_graduation_attestation_preimage
    preimage = build_graduation_attestation_preimage(
        steward=record["steward"], task_class=record["task_class"],
        precision_milli=record["precision_milli"], n_labels=record["n_labels"],
        min_samples=record["min_samples"], precision_floor_milli=record["precision_floor_milli"],
        decision=record["decision"], operator_id=record["operator_id"], ts_ns=record["ts_ns"],
        sel_chain_head_hex=record["sel_chain_head_hex"])
    return hashlib.sha256(preimage).digest()


def add_operator_cosignature(record: dict, *, operator_sign) -> dict:
    """Attach the operator's co-signature to a Guardian-signed attestation. `operator_sign(digest32) ->
    65-byte secp256k1 sig` is the injected OPERATOR signer (never the bridge). REFUSES unless the record's
    `operator_id` is a real address AND the recovered signer equals it — the operator cannot override the
    signed decision field by co-signing a different one."""
    op_id = record.get("operator_id")
    if not _is_address(op_id):
        raise ValueError(f"operator_id must be a 0x20-byte address for dual-sign, got {op_id!r}")
    # trust-collapse guard at the LIBRARY boundary (grok round-18 F1): a future non-CLI caller must not be
    # able to dual-sign with operator_id == the bridge wallet (both halves bridge-held = no non-repudiation).
    assert_operator_key_not_bridge(op_id)
    digest = _digest_from_record(record)
    sig_bytes = bytes(operator_sign(digest))
    recovered = _recover_address(digest, sig_bytes)
    assert_operator_key_not_bridge(recovered)
    if recovered.lower() != str(op_id).lower():
        raise ValueError(
            f"operator key {recovered} != record operator_id {op_id} — refusing (the operator cannot "
            "override the signed decision package by co-signing).")
    out = dict(record)
    out["operator_signature_hex"] = sig_bytes.hex()
    out["operator_address"] = recovered            # checksummed (== operator_id, case-fold)
    out["operator_signing_method"] = OPERATOR_SIGNING_METHOD
    out["dual_signed"] = True
    out["cosign_note"] = (
        "REAL non-repudiation: Guardian's HSM recorded this package AND the keyholder of operator_id "
        "co-signed the SAME digest with a key the bridge does not hold. Proves the ADDRESS authorized the "
        "package (not a named human's cognitive intent; key theft / blind-sign are residuals). SEL still "
        "never auto-applies — this is evidence of a past decision, not a capability token.")
    return out


def verify_dual_signed_attestation(record: dict, *, guardian_pubkey_hex: str | None = None) -> dict:
    """Verify BOTH signatures over the same decision package. `fully_authorized` requires Guardian's HSM
    signature AND the operator's secp256k1 signature AND that the recovered operator address == operator_id
    (authenticating the field). Fails CLOSED on any malformed input — never a silent false-OK."""
    from .steward_sel_attestation import verify_graduation_attestation
    guardian_ok = False
    operator_sig_ok = False
    operator_id_authenticated = False
    try:
        guardian_ok = bool(verify_graduation_attestation(record, guardian_pubkey_hex))
    except Exception:  # noqa: BLE001
        guardian_ok = False
    try:
        if record.get("operator_signing_method") == OPERATOR_SIGNING_METHOD and record.get(
                "operator_signature_hex"):
            digest = _digest_from_record(record)
            recovered = _recover_address(digest, bytes.fromhex(record["operator_signature_hex"]))
            operator_sig_ok = True                 # a recoverable operator signature is present
            operator_id_authenticated = (_is_address(record.get("operator_id"))
                                         and recovered.lower() == str(record["operator_id"]).lower())
            if operator_id_authenticated:
                # trust-collapse guard (grok round-18 F1): a bridge-wallet operator_id/signer is NOT
                # non-repudiation even with a matching sig — refuse it at the verify boundary too.
                try:
                    assert_operator_key_not_bridge(record["operator_id"])
                    assert_operator_key_not_bridge(recovered)
                except ValueError:
                    operator_id_authenticated = False
    except Exception:  # noqa: BLE001
        operator_sig_ok = False
        operator_id_authenticated = False
    fully_authorized = bool(guardian_ok and operator_sig_ok and operator_id_authenticated)
    return {
        "guardian_ok": guardian_ok, "operator_sig_ok": operator_sig_ok,
        "operator_id_authenticated": operator_id_authenticated, "fully_authorized": fully_authorized,
        "note": "fully_authorized = Guardian HSM recorded the package AND the keyholder of operator_id "
                "co-signed the same digest (bridge cannot forge the operator half). Real non-repudiation "
                "of the ADDRESS's authorization; not proof of cognitive intent.",
    }


def cryptographic_dual_key_satisfied(record: dict, *, guardian_pubkey_hex: str | None = None) -> bool:
    """The pure helper a consumer calls to gate on the REAL cryptographic dual-key (distinct from the
    declarative `operator_dual_key_present` config bool — grok round-17 leaves that bool alone this pass)."""
    return verify_dual_signed_attestation(record, guardian_pubkey_hex=guardian_pubkey_hex)["fully_authorized"]
