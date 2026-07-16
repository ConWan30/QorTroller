"""Ceremony B — no-spend readiness check for the Manufacturer Root CA HSM flip.

The operator provisions a P-256 AWS KMS key, then runs `scripts/mfg_ca_hsm_preflight.py` BEFORE spending any
IOTX or touching the chain. This module is the pure go/no-go: it proves the KMS-backed CA produces device
certificates that verify, so a misconfigured key is caught for free instead of after a spend.

It checks (grok round-22 go/no-go): the issuer public key is a 65-byte P-256 point; a canary body signs and
verifies through the exact production CA primitive; a FULL DeviceBirthCertificate signs (`sign_cert`) and
passes production `verify_cert` (issuer sig over canonical body + DEVICE_ID_CANON_v1 keccak binding);
the KMS key metadata (if supplied by the operator script's `describe_key`) is Enabled /
KeyUsage=SIGN_VERIFY / KeySpec=ECC_NIST_P256; and — if the prior software CA pubkey is supplied — the
new issuer is genuinely a DIFFERENT root.

IMPORTANT (grok round-22, load-bearing): readiness of the KMS CA does NOT mean the existing on-chain device
can be re-anchored. VMDR `registerDevice` is ONE-SHOT (`require(!registered[deviceId])`) with no
update-hash path, so the live device `581a836c…` (software-anchored) CANNOT be re-anchored under a new
root — that needs a contract change (updateBirthCertHash) or a net-new-devices-only policy. See
`docs/path-a-mfg-ca-hsm-migration.md`. This module never calls the chain, never spends, never provisions.
"""
from __future__ import annotations

_CANARY = b"QORTROLLER-MFG-CA-READINESS-CANARY-v0"


def check_ca_readiness(ca, *, prior_software_ca_pubkey_hex: str | None = None,
                       key_metadata: dict | None = None) -> dict:
    """Pure go/no-go over a ManufacturerRootCA (software- or KMS-backed). No chain, no spend."""
    from .manufacturer_root_ca import verify_cert_signature

    warnings: list[str] = []

    # 1. issuer public key shape (65-byte uncompressed P-256)
    try:
        pub = ca.issuer_pubkey_uncompressed()
    except Exception as exc:  # noqa: BLE001 - a KMS/setup failure is a hard no-go, not a crash
        return {"ready": False, "reason": f"issuer pubkey unavailable: {exc!r}", "warnings": [str(exc)],
                "is_p256_65b": False, "canary_verifies": False, "full_cert_verifies": False,
                "key_enabled": None, "key_usage_ok": None, "key_spec_ok": None, "is_new_root": None,
                "new_issuer_pubkey_hex": None, "note": _NOTE}
    is_p256_65b = (len(pub) == 65 and pub[0] == 0x04)
    new_issuer_pubkey_hex = pub.hex()
    if not is_p256_65b:
        warnings.append(f"issuer pubkey is not a 65-byte uncompressed point (len={len(pub)})")

    # 2. canary through the production CA sign primitive (sign_cert_body -> raw r||s)
    canary_verifies = False
    try:
        csig = ca.sign_cert_body(_CANARY)
        canary_verifies = bool(len(csig) == 64 and verify_cert_signature(pub, _CANARY, csig))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"canary sign/verify errored: {exc!r}")
    if not canary_verifies:
        warnings.append("canary did not sign+verify through the CA")

    # 3. FULL production cert path: build a cert, sign_cert, verify_cert (issuer sig +
    # DEVICE_ID_CANON_v1 binding). Issuer-sig-only would miss a production-shaped body;
    # device_id MUST be keccak256(pubkey), not sha256.
    full_cert_verifies = False
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        from .device_birth_cert import (
            CERT_VERSION, DeviceBirthCertificate, compute_device_id_from_pubkey_hex,
            sign_cert, verify_cert,
        )
        dev_pub = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint)
        cert = DeviceBirthCertificate(
            version=CERT_VERSION,
            device_id_hex=compute_device_id_from_pubkey_hex(dev_pub.hex()),
            ecdsa_p256_pubkey_hex=dev_pub.hex(), controller_model="CFI-ZCP1",
            manufacturer_id=ca.manufacturer_id(), manufacturing_date="2026-01-01T00:00:00Z",
            signing_path="B", proof_tier="FULL", issuer_pubkey_hex=new_issuer_pubkey_hex,
            issuer_backend=ca.backend_type())
        sign_cert(cert, ca)
        ok_full, reason_full = verify_cert(cert)
        full_cert_verifies = bool(ok_full and len(bytes.fromhex(cert.signature_hex or "")) == 64)
        if not ok_full:
            warnings.append(f"full verify_cert failed: {reason_full}")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"full cert path errored: {exc!r}")
    if not full_cert_verifies:
        warnings.append("full DeviceBirthCertificate did not sign+verify")

    # 4. KMS key metadata (from describe_key), if the operator script supplied it
    key_enabled = key_usage_ok = key_spec_ok = None
    if key_metadata:
        key_enabled = (key_metadata.get("Enabled") is True
                       or str(key_metadata.get("KeyState", "")).upper() == "ENABLED")
        key_usage_ok = (key_metadata.get("KeyUsage") == "SIGN_VERIFY")
        key_spec_ok = (str(key_metadata.get("KeySpec", "")) == "ECC_NIST_P256")
        if not key_enabled:
            warnings.append("KMS key is not Enabled")
        if not key_usage_ok:
            warnings.append(f"KeyUsage != SIGN_VERIFY ({key_metadata.get('KeyUsage')!r})")
        if not key_spec_ok:
            warnings.append(f"KeySpec != ECC_NIST_P256 ({key_metadata.get('KeySpec')!r})")

    # 5. new-root check (if the prior software CA pubkey is supplied)
    is_new_root = None
    if prior_software_ca_pubkey_hex:
        is_new_root = (new_issuer_pubkey_hex.lower() != str(prior_software_ca_pubkey_hex).lower())
        if not is_new_root:
            warnings.append("issuer pubkey EQUALS the prior software CA — NOT a new root (nothing migrated)")

    hard = [is_p256_65b, canary_verifies, full_cert_verifies]
    if key_metadata:
        hard += [key_enabled, key_usage_ok, key_spec_ok]
    if prior_software_ca_pubkey_hex is not None:
        hard += [is_new_root]
    ready = all(bool(x) for x in hard)

    return {
        "ready": ready, "reason": "ready" if ready else ("; ".join(warnings) or "hard check failed"),
        "is_p256_65b": is_p256_65b, "canary_verifies": canary_verifies,
        "full_cert_verifies": full_cert_verifies, "key_enabled": key_enabled,
        "key_usage_ok": key_usage_ok, "key_spec_ok": key_spec_ok, "is_new_root": is_new_root,
        "new_issuer_pubkey_hex": new_issuer_pubkey_hex, "warnings": warnings, "note": _NOTE,
    }


_NOTE = ("No-spend KMS-CA readiness only. READY means the KMS CA produces verifying certs — it does NOT mean "
         "the existing on-chain device can be re-anchored: VMDR registerDevice is ONE-SHOT, so 581a836c "
         "cannot move to a new root without an updateBirthCertHash contract path or a net-new-only policy "
         "(docs/path-a-mfg-ca-hsm-migration.md). No chain call, no spend, no provisioning here.")
