"""VSD Self-Verifying Loop — per-note Ed25519 provenance (VSD-2).

Generalizes the proven `vsd-proposal-manifest-v1` pattern (vsd-vault/manifests/proposals-*/)
to per-NOTE manifests: a signed, content-bound manifest beside each note, Ed25519-signed by the
architect key (vsd-vault/architect_key.pem), itself wallet-attested
(eval/architect_key_attestation.json). Mirrors scripts/vsd_attest_architect_key.py's crypto.

Signing policy (split-signing decision):
  - ROUTINE notes (claim/ingredient/synthesis/pbsa) -> loop-signed (signed=True).
  - DECISION notes + eval/ re-freeze -> write a STUB manifest (signed=False, pending="operator").
    The loop NEVER forges the architect's signature on a decision.

Pure stdlib + `cryptography` ed25519. No bridge import.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_VAULT = Path(__file__).resolve().parent.parent           # vsd-vault/
_KEY_PEM = _VAULT / "architect_key.pem"
_PUBKEY_PEM = _VAULT / "architect_pubkey.pem"
_ATTESTATION_REF = "vsd-vault/eval/architect_key_attestation.json"
_MANIFEST_ROOT = _VAULT / "manifests" / "notes"
SCHEMA = "vsd-note-manifest-v1"
# note types the loop may sign autonomously; everything else is operator-pending
ROUTINE_TYPES = frozenset({"claim", "ingredient", "synthesis", "pbsa"})


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def note_canonical_hash(note_path: str | Path) -> str:
    """SHA-256 (hex) of the note's raw bytes — the content binding."""
    return hashlib.sha256(Path(note_path).read_bytes()).hexdigest()


def _load_private_key() -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(_KEY_PEM.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("architect_key.pem is not an Ed25519 private key")
    return key


def architect_pubkey_hex() -> str:
    """32-byte raw Ed25519 architect public key (hex). Reads pubkey PEM if present, else key."""
    if _PUBKEY_PEM.exists():
        pub = serialization.load_pem_public_key(_PUBKEY_PEM.read_bytes())
    else:
        pub = _load_private_key().public_key()
    raw = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    return raw.hex()


def _manifest_path(note_id: str, rev: int) -> Path:
    return _MANIFEST_ROOT / note_id / f"{rev:03d}.manifest.json"


def sign_note(note_path: str | Path, note_id: str, note_type: str, *,
              rev: int = 1, ts_ns: Optional[int] = None) -> dict:
    """Write a signed (routine) or pending (decision) manifest for a note. Returns the manifest
    dict (with `manifest_canonical_hash`). Decision/non-routine types are NOT loop-signed."""
    note_path = Path(note_path)
    ch = note_canonical_hash(note_path)
    ts_ns = ts_ns if ts_ns is not None else time.time_ns()
    base = {
        "schema_version": SCHEMA,
        "note_id": note_id,
        "note_type": note_type,
        "note_path": str(note_path).replace("\\", "/"),
        "note_canonical_hash": ch,
        "frozen_at_ts_ns": int(ts_ns),
        "architect_pubkey_ed25519": architect_pubkey_hex(),
        "bridge_wallet_attestation_ref": _ATTESTATION_REF,
        "signed_object": "note_canonical_hash bytes (32B from hex)",
        "signing_method": "Ed25519 (cryptography.hazmat.primitives.asymmetric.ed25519)",
    }
    if note_type in ROUTINE_TYPES:
        sig = _load_private_key().sign(bytes.fromhex(ch))
        base["signed"] = True
        base["signer"] = "loop"
        base["signature"] = sig.hex()
    else:
        base["signed"] = False
        base["signer"] = None
        base["pending"] = "operator"          # decision/re-freeze: operator co-signs
        base["signature"] = None
    mpath = _manifest_path(note_id, rev)
    mpath.parent.mkdir(parents=True, exist_ok=True)
    blob = _canonical(base)
    mpath.write_bytes(blob)
    base["manifest_canonical_hash"] = hashlib.sha256(blob).hexdigest()
    base["manifest_path"] = str(mpath).replace("\\", "/")
    return base


def verify_note(note_path: str | Path, manifest_path: str | Path) -> tuple[bool, str]:
    """Verify a note against its manifest. Returns (ok, reason). A pending (unsigned) manifest
    verifies its content binding only and reports signed=False honestly (not a failure)."""
    try:
        m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"manifest unreadable: {exc}"
    if note_canonical_hash(note_path) != m.get("note_canonical_hash"):
        return False, "note bytes changed since signing (canonical hash mismatch)"
    if not m.get("signed"):
        return True, "content-bound; UNSIGNED (pending operator)"
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(m["architect_pubkey_ed25519"]))
        pub.verify(bytes.fromhex(m["signature"]), bytes.fromhex(m["note_canonical_hash"]))
        return True, "Ed25519 signature verified"
    except Exception as exc:
        return False, f"Ed25519 verify failed: {exc}"
