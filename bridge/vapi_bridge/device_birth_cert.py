"""DeviceBirthCertificate — Path A Arc 1 Commit 3.

Off-chain attestation that a specific device shipped from a specific
manufacturer with a specific ECDSA-P256 public key. The cert is:

  • Persisted at ~/.vapi/device_birth_cert.json (per-device, by the
    gamer's host after manufacturer ceremony OR via the bridge if Path B
    self-attesting).
  • Hash-anchored on-chain via VAPIManufacturerDeviceRegistry's
    birthCertHash field at registerDevice() time.
  • ECDSA-P256-signed by the ManufacturerRootCA (the QorTroller Foundation
    reference-impl root CA for Arc 1; a partner-HSM root CA in production).

NOT a FROZEN-v1 PATTERN-017 commitment family. This is OPERATIONAL
infrastructure that evolves with manufacturer partnerships (version field
on the cert allows controlled migration).

CANONICAL BYTES DISCIPLINE (D-3C two-method shape):
  • canonical_bytes_for_signing()   — all fields EXCEPT signature_hex
                                       (the bytes the issuer signs over)
  • canonical_bytes_full()          — all fields INCLUDING signature_hex
                                       (the bytes hashed for on-chain anchor
                                        AND for cert hash determinism tests)
Both use json.dumps(..., sort_keys=True, separators=(",", ":"),
ensure_ascii=True) matching the protocol-wide canonical-JSON convention
(cedar_parser.py, agent_review_emitter.py, cdrr_dag_tracker.py).

ON-CHAIN BIND:
  birthCertHash (bytes32, anchored at registerDevice) =
      sha256(canonical_bytes_full(signed_cert))
A tournament operator running verify_device_cert.py re-derives this hash
and compares against the on-chain value — any cert tampering breaks the
match.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, fields
from typing import Literal, Optional

# Cert format version. Bumping requires reconciliation with on-chain anchors
# (the hash binding includes the version field). Currently "1.0" — partner-HSM
# rollout may bump to "1.1" to introduce required attestation_chain fields.
CERT_VERSION = "1.0"

SigningPathLiteral = Literal["A", "B"]
ProofTierLiteral = Literal["FULL", "STANDARD", "BASIC"]


@dataclass
class DeviceBirthCertificate:
    """Off-chain birth attestation; on-chain hash anchor is bytes32 birthCertHash.

    NOTE: signature_hex is OPTIONAL during construction (an unsigned cert may
    exist temporarily during ceremony assembly), but MUST be present + valid
    before the cert is hashed for on-chain anchoring or persisted to disk.
    """
    version: str                              # cert format version (CERT_VERSION)
    device_id_hex: str                        # bytes32 as 64 hex chars (no "0x")
    ecdsa_p256_pubkey_hex: str                # compressed SEC1, 66 hex chars (33 B)
    controller_model: str                     # "CFI-ZCP1" | "CFI-ZCT1" | ...
    manufacturer_id: str                      # "QorTrollerFoundation" | partner id
    manufacturing_date: str                   # ISO 8601 (e.g. "2026-05-26T03:11:00Z")
    signing_path: SigningPathLiteral          # "A" (silicon) | "B" (host JSON)
    proof_tier: ProofTierLiteral              # "FULL" | "STANDARD" | "BASIC"
    issuer_pubkey_hex: str                    # ManufacturerRootCA SEC1 uncompressed,
                                              # 130 hex chars (65 B with 0x04 prefix)
    atecc_chip_id: Optional[str] = None       # ATECC608A serial; None for Path B
    issuer_backend: Optional[str] = None      # "software" / "atecc608" / "yubikey"
                                              # (issuer ROOT-CA backend; not device)
    signature_hex: Optional[str] = None       # 64-byte raw r||s ECDSA-P256 over
                                              # SHA-256(canonical_bytes_for_signing)
                                              # = 128 hex chars

    # ── Canonical-bytes pair (D-3C) ───────────────────────────────────────

    def canonical_bytes_for_signing(self) -> bytes:
        """All fields EXCEPT signature_hex, in canonical JSON. These are the
        bytes the issuer signs over. None-valued optional fields are EXCLUDED
        from the canonical bytes (so an unsigned issuer_backend or absent
        atecc_chip_id doesn't change the hash relative to a future version
        that fills those fields)."""
        d = {f.name: getattr(self, f.name) for f in fields(self)
             if f.name != "signature_hex"}
        d = {k: v for k, v in d.items() if v is not None}
        return json.dumps(d, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True).encode("utf-8")

    def canonical_bytes_full(self) -> bytes:
        """All fields INCLUDING signature_hex, in canonical JSON. SHA-256 of
        these bytes is what gets hash-anchored on-chain (birthCertHash). MUST
        only be called on a signed cert (signature_hex non-None); raises if
        unsigned to prevent anchoring an unsigned cert."""
        if self.signature_hex is None:
            raise ValueError(
                "canonical_bytes_full requires a signed cert "
                "(signature_hex is None — call sign_cert first)"
            )
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d = {k: v for k, v in d.items() if v is not None}
        return json.dumps(d, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True).encode("utf-8")


def compute_cert_hash(cert: DeviceBirthCertificate) -> bytes:
    """SHA-256(canonical_bytes_full(cert)). 32 bytes. This is the value
    anchored on-chain via VAPIManufacturerDeviceRegistry.registerDevice's
    birthCertHash parameter. Equivalence verified bidirectionally:
        chain.getDevice(deviceId).birthCertHash
            == compute_cert_hash(deserialized_local_cert_json)
    """
    return hashlib.sha256(cert.canonical_bytes_full()).digest()


def sign_cert(cert: DeviceBirthCertificate, root_ca) -> DeviceBirthCertificate:
    """Sign the unsigned cert with the ManufacturerRootCA. Mutates and returns
    the same cert object so callers can chain: ``signed = sign_cert(cert, ca)``.

    Pre-conditions:
      - cert.signature_hex is None (cert is unsigned)
      - cert.issuer_pubkey_hex matches root_ca.issuer_pubkey_hex()
        (anti-foot-shooting: signing with the wrong key would silently
        produce an unverifiable cert)
      - root_ca exposes sign_cert_body(body: bytes) -> bytes (raw r||s 64B)
    """
    if cert.signature_hex is not None:
        raise ValueError("sign_cert: cert already signed (signature_hex set)")
    expected_issuer = root_ca.issuer_pubkey_hex()
    if cert.issuer_pubkey_hex != expected_issuer:
        raise ValueError(
            f"sign_cert: issuer_pubkey_hex mismatch — cert says "
            f"{cert.issuer_pubkey_hex[:32]}... but root_ca has "
            f"{expected_issuer[:32]}... (refusing to sign; the cert would "
            f"be unverifiable)"
        )
    body = cert.canonical_bytes_for_signing()
    sig = root_ca.sign_cert_body(body)
    assert len(sig) == 64, f"expected 64-byte r||s, got {len(sig)}"
    cert.signature_hex = sig.hex()
    return cert


def verify_cert(cert: DeviceBirthCertificate) -> tuple[bool, str]:
    """Verify the cert's ECDSA-P256 sig against its claimed issuer_pubkey_hex.
    Returns (valid: bool, reason: str). reason is a human-readable explanation
    on failure (empty string on success).

    Pure-local verification. Does NOT consult the chain — that's the job of
    verify_device_cert.py (which calls this PLUS chain.isActive). Separation:
    this answers 'is the cert self-consistent?'; the chain check answers 'is
    the cert active on-chain?'.
    """
    from .manufacturer_root_ca import verify_cert_signature

    if cert.signature_hex is None:
        return False, "unsigned cert (signature_hex is None)"
    if cert.version != CERT_VERSION:
        return False, f"version mismatch: cert={cert.version!r} expected={CERT_VERSION!r}"
    try:
        issuer_pub = bytes.fromhex(cert.issuer_pubkey_hex)
        sig_raw    = bytes.fromhex(cert.signature_hex)
    except (ValueError, TypeError) as exc:
        return False, f"hex decode failed: {exc}"
    if len(issuer_pub) != 65:
        return False, f"issuer_pubkey wrong length: {len(issuer_pub)} != 65"
    if len(sig_raw) != 64:
        return False, f"signature wrong length: {len(sig_raw)} != 64"

    body = cert.canonical_bytes_for_signing()
    ok = verify_cert_signature(issuer_pub, body, sig_raw)
    if not ok:
        return False, "ECDSA-P256 signature verification failed"
    return True, ""


def cert_to_json(cert: DeviceBirthCertificate, *, pretty: bool = True) -> str:
    """Serialize a cert to JSON (NOT canonical — for human-readable storage).
    Use canonical_bytes_full() for cryptographic operations, never this.
    None fields are dropped to keep the JSON tidy."""
    d = {f.name: getattr(cert, f.name) for f in fields(cert)}
    d = {k: v for k, v in d.items() if v is not None}
    return json.dumps(d, indent=2 if pretty else None, ensure_ascii=False)


def cert_from_json(s: str) -> DeviceBirthCertificate:
    """Deserialize a cert from JSON. Optional fields default to None; required
    fields raise KeyError if missing (caller can catch and report)."""
    d = json.loads(s)
    # Required fields per the dataclass (no default)
    return DeviceBirthCertificate(
        version=d["version"],
        device_id_hex=d["device_id_hex"],
        ecdsa_p256_pubkey_hex=d["ecdsa_p256_pubkey_hex"],
        controller_model=d["controller_model"],
        manufacturer_id=d["manufacturer_id"],
        manufacturing_date=d["manufacturing_date"],
        signing_path=d["signing_path"],
        proof_tier=d["proof_tier"],
        issuer_pubkey_hex=d["issuer_pubkey_hex"],
        atecc_chip_id=d.get("atecc_chip_id"),
        issuer_backend=d.get("issuer_backend"),
        signature_hex=d.get("signature_hex"),
    )
