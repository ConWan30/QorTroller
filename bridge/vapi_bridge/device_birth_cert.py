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
    device_id_hex: str                        # bytes32 as 64 hex chars (no "0x");
                                              # MUST equal keccak256(65B uncompressed
                                              # SEC1 pubkey) per DEVICE_ID_CANON_v1
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


def compress_sec1_p256_pubkey(uncompressed: bytes) -> bytes:
    """65-byte SEC1 0x04||X||Y -> 33-byte compressed 0x02/0x03||X."""
    if len(uncompressed) != 65 or uncompressed[0] != 0x04:
        raise ValueError(
            f"expected 65-byte uncompressed SEC1 (0x04||X||Y), "
            f"got len={len(uncompressed)} prefix=0x{uncompressed[0]:02x}"
        )
    x = uncompressed[1:33]
    y = uncompressed[33:65]
    prefix = b"\x02" if (y[-1] & 1) == 0 else b"\x03"
    return prefix + x


def decompress_sec1_p256_pubkey(pubkey_bytes: bytes) -> bytes:
    """33-byte compressed or 65-byte uncompressed SEC1 P-256 -> 65-byte uncompressed."""
    if len(pubkey_bytes) == 65 and pubkey_bytes[0] == 0x04:
        return pubkey_bytes
    if len(pubkey_bytes) != 33 or pubkey_bytes[0] not in (0x02, 0x03):
        raise ValueError(
            f"expected 33-byte compressed (0x02/0x03||X) or 65-byte uncompressed "
            f"(0x04||X||Y), got len={len(pubkey_bytes)} prefix=0x{pubkey_bytes[0]:02x}"
        )
    from cryptography.hazmat.primitives.asymmetric.ec import (
        EllipticCurvePublicKey,
        SECP256R1,
    )
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    pub = EllipticCurvePublicKey.from_encoded_point(SECP256R1(), pubkey_bytes)
    return pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)


def compute_device_id_from_pubkey_hex(ecdsa_p256_pubkey_hex: str) -> str:
    """keccak256(65B uncompressed SEC1) per DEVICE_ID_CANON_v1; returns 64 hex chars."""
    from .codec import compute_device_id

    pubkey = bytes.fromhex(ecdsa_p256_pubkey_hex)
    uncompressed = decompress_sec1_p256_pubkey(pubkey)
    return compute_device_id(uncompressed).hex()


def verify_device_id_matches_pubkey(
    device_id_hex: str,
    ecdsa_p256_pubkey_hex: str,
) -> tuple[bool, str]:
    """Verify device_id_hex == keccak256(uncompressed SEC1 ecdsa_p256_pubkey_hex).

    Pure-local check against DEVICE_ID_CANON_v1. The cert stores compressed
    device pubkey (33 B); canon hashes the 65-byte uncompressed form.
    """
    try:
        expected = compute_device_id_from_pubkey_hex(ecdsa_p256_pubkey_hex)
    except (ValueError, TypeError) as exc:
        return False, f"device_id pubkey decode failed: {exc}"
    claimed = device_id_hex.lower().removeprefix("0x")
    if len(claimed) != 64:
        return False, f"device_id_hex wrong length: {len(claimed)} != 64"
    if claimed != expected:
        return (
            False,
            f"device_id_hex mismatch: cert claims 0x{claimed} but "
            f"keccak256(pubkey)=0x{expected} per DEVICE_ID_CANON_v1",
        )
    return True, ""


def assert_mint_device_id_canon(
    device_id_hex: str,
    ecdsa_p256_pubkey_hex: str,
) -> None:
    """MINT-ONLY gate: raise ValueError unless device_id == canon(pubkey).

    Canon is for MINTING new device_ids (registration ceremonies); it stops
    vanity/opaque ids at the door. It is NOT the verify gate for devices
    already registered on VMDR — that is verify_registered_device_binding
    (the on-chain pubkeyHash is the manufacturer's attestation; re-deriving
    device_id locally after registration is what created F-PATHA-1 drift).
    Named so mint and verify cannot be confused (A2A round-26 footgun #2).
    """
    ok, reason = verify_device_id_matches_pubkey(device_id_hex, ecdsa_p256_pubkey_hex)
    if not ok:
        raise ValueError(f"mint canon violation: {reason}")


def compute_pubkey_hash_hex(ecdsa_p256_pubkey_hex: str) -> str:
    """SHA-256(33-byte compressed SEC1 pubkey) — the VMDR on-chain binding hash.

    VMDR stores this as devices[deviceId].pubkeyHash at registration; it is
    canon-stable (survives any device_id derivation change). Accepts compressed
    or uncompressed input; hashes the compressed form, matching what
    provision_device_mfg.py anchored on-chain.
    """
    pubkey = bytes.fromhex(ecdsa_p256_pubkey_hex)
    if len(pubkey) == 65:
        pubkey = compress_sec1_p256_pubkey(pubkey)
    elif len(pubkey) != 33 or pubkey[0] not in (0x02, 0x03):
        raise ValueError(
            f"expected 33-byte compressed or 65-byte uncompressed SEC1 pubkey, "
            f"got len={len(pubkey)}"
        )
    return hashlib.sha256(pubkey).hexdigest()


def verify_registered_device_binding(
    device_id_hex: str,
    ecdsa_p256_pubkey_hex: str,
    *,
    on_chain_pubkey_hash_hex: Optional[str] = None,
) -> tuple[bool, str]:
    """Verify a device's key binding with chain-first precedence (A2A round-26).

    TRUST BOUNDARY (round-27 F1 — load-bearing): on_chain_pubkey_hash_hex MUST
    be the RPC-FETCHED devices[deviceId].pubkeyHash from VMDR for THAT
    device_id. NEVER pass compute_pubkey_hash_hex(cert pubkey) or any
    locally-derived hash — that is circular ("hash-of-local-key wins") and
    grandfathers ANY device_id for any key. This function verifies the binding
    AGAINST supplied chain evidence; it cannot verify the evidence's
    provenance. When in doubt, pass None (honest canon best-effort) — never
    fabricate chain evidence to make a check pass.

    Precedence (never a bare OR):
      - on_chain_pubkey_hash_hex supplied (device is VMDR-registered and the
        caller read devices[deviceId].pubkeyHash): AUTHORITATIVE — pass iff
        SHA-256(compressed cert pubkey) == the on-chain pubkeyHash. Chain wins
        in BOTH directions: a match passes even when local canon disagrees
        (grandfathers pre-canon registrations like 581a836c); a mismatch fails
        even when local canon agrees (the cert key is not the registered key).
      - on_chain_pubkey_hash_hex is None (offline / unregistered): best-effort
        mint-shape check — device_id == keccak256(uncompressed pubkey) per
        DEVICE_ID_CANON_v1. For a known-registered pre-canon device this
        honestly reads INVALID offline; only the chain binding can validate it.
    """
    if on_chain_pubkey_hash_hex is None:
        ok, reason = verify_device_id_matches_pubkey(device_id_hex, ecdsa_p256_pubkey_hex)
        if not ok:
            return False, (
                f"{reason} (offline canon best-effort; a VMDR-registered device "
                f"is authoritatively verified against its on-chain pubkeyHash)"
            )
        return True, ""

    claimed_id = device_id_hex.lower().removeprefix("0x")
    if len(claimed_id) != 64:
        return False, f"device_id_hex wrong length: {len(claimed_id)} != 64"
    chain_hash = str(on_chain_pubkey_hash_hex).lower().removeprefix("0x")
    if len(chain_hash) != 64:
        return False, (
            f"on_chain_pubkey_hash_hex wrong length: {len(chain_hash)} != 64 "
            f"(refusing binding check on malformed chain evidence)"
        )
    try:
        local_hash = compute_pubkey_hash_hex(ecdsa_p256_pubkey_hex)
    except (ValueError, TypeError) as exc:
        return False, f"pubkey decode failed: {exc}"
    if local_hash != chain_hash:
        return False, (
            f"pubkeyHash mismatch: sha256(compressed cert pubkey)=0x{local_hash} "
            f"but VMDR attests 0x{chain_hash} — the cert key is NOT the "
            f"registered key for device_id 0x{claimed_id}"
        )
    return True, ""


def resolve_device_id_hex(
    cli_device_id_hex: Optional[str],
    ecdsa_p256_pubkey_hex: str,
) -> str:
    """Derive device_id from pubkey; if CLI value given, fail closed on mismatch.

    Used by provision_device_mfg.py so Arc 1 ceremonies cannot anchor a cert
    whose device_id_hex disagrees with DEVICE_ID_CANON_v1. MINT path only —
    re-issue of an already-registered device_id goes through the --reissue
    ceremony (chain-gated on the VMDR pubkeyHash), never through this.
    """
    derived = compute_device_id_from_pubkey_hex(ecdsa_p256_pubkey_hex)
    if cli_device_id_hex is None:
        return derived
    claimed = cli_device_id_hex.lower().removeprefix("0x")
    if len(claimed) != 64:
        raise ValueError(
            f"--device-id must be 32 bytes (64 hex chars), got {len(claimed)}"
        )
    if claimed != derived:
        raise ValueError(
            f"--device-id mismatch: CLI claims 0x{claimed} but "
            f"keccak256(pubkey)=0x{derived} per DEVICE_ID_CANON_v1"
        )
    return derived


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


def verify_cert(
    cert: DeviceBirthCertificate,
    *,
    on_chain_pubkey_hash_hex: Optional[str] = None,
) -> tuple[bool, str]:
    """Verify the cert's ECDSA-P256 sig against its claimed issuer_pubkey_hex.
    Returns (valid: bool, reason: str). reason is a human-readable explanation
    on failure (empty string on success).

    Pure-local verification by default. Does NOT consult the chain — that's the
    job of verify_device_cert.py (which calls this PLUS chain.isActive).
    Separation: this answers 'is the cert self-consistent?'; the chain check
    answers 'is the cert active on-chain?'.

    Device-id binding (mint/verify split, A2A round-26): with the default
    on_chain_pubkey_hash_hex=None the binding is the offline canon best-effort
    (device_id == keccak256(pubkey), byte-identical to the pre-split behavior).
    A caller that has read devices[deviceId].pubkeyHash from VMDR passes it
    here and the binding becomes the AUTHORITATIVE chain check instead —
    see verify_registered_device_binding for the precedence rules AND the
    trust boundary: the hash MUST be RPC-fetched from VMDR for this cert's
    device_id, never derived from the cert's own pubkey (circular — would
    grandfather any id).
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

    ok_id, reason_id = verify_registered_device_binding(
        cert.device_id_hex, cert.ecdsa_p256_pubkey_hex,
        on_chain_pubkey_hash_hex=on_chain_pubkey_hash_hex,
    )
    if not ok_id:
        return False, reason_id
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
