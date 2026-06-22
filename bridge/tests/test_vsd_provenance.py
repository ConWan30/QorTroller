"""Tests for VSD per-note Ed25519 provenance (uses the real architect key; tmp manifests)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_VAULT = Path(__file__).resolve().parent.parent.parent / "vsd-vault"
sys.path.insert(0, str(_VAULT / ".vsd"))

import vsd_provenance as prov  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (_VAULT / "architect_key.pem").exists(),
    reason="architect_key.pem (gitignored) not present in this checkout",
)


def _note(tmp_path, text="---\ntype: synthesis\nid: t-x\n---\nbody\n"):
    p = tmp_path / "t-x.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_routine_note_signs_and_verifies(tmp_path, monkeypatch):
    monkeypatch.setattr(prov, "_MANIFEST_ROOT", tmp_path / "m")
    note = _note(tmp_path)
    m = prov.sign_note(note, "t-x", "synthesis")
    assert m["signed"] is True and m["signer"] == "loop" and m["signature"]
    ok, reason = prov.verify_note(note, m["manifest_path"])
    assert ok and "verified" in reason


def test_decision_note_is_pending_not_forged(tmp_path, monkeypatch):
    monkeypatch.setattr(prov, "_MANIFEST_ROOT", tmp_path / "m")
    note = _note(tmp_path, "---\ntype: decision\nid: d-x\n---\nbody\n")
    m = prov.sign_note(note, "d-x", "decision")
    assert m["signed"] is False and m.get("pending") == "operator" and m["signature"] is None
    ok, reason = prov.verify_note(note, m["manifest_path"])
    assert ok and "UNSIGNED" in reason  # content-bound, honestly unsigned


def test_tampered_note_fails_verify(tmp_path, monkeypatch):
    monkeypatch.setattr(prov, "_MANIFEST_ROOT", tmp_path / "m")
    note = _note(tmp_path)
    m = prov.sign_note(note, "t-x", "synthesis")
    note.write_text("---\ntype: synthesis\nid: t-x\n---\nTAMPERED\n", encoding="utf-8")
    ok, reason = prov.verify_note(note, m["manifest_path"])
    assert ok is False and "canonical hash mismatch" in reason


def test_forged_pubkey_manifest_is_rejected(tmp_path):
    """Security regression (review MEDIUM): a manifest signed by a DIFFERENT keypair that
    internally self-verifies must be rejected — verify_note pins to the attested architect key."""
    import json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    note = _note(tmp_path)
    ch = prov.note_canonical_hash(note)
    attacker = Ed25519PrivateKey.generate()
    attacker_pub = attacker.public_key().public_bytes_raw().hex()
    assert attacker_pub.lower() != prov.attested_pubkey_hex()  # genuinely a different key
    forged = {
        "schema_version": prov.SCHEMA, "note_id": "t-x", "note_type": "synthesis",
        "note_canonical_hash": ch, "signed": True, "signer": "loop",
        "architect_pubkey_ed25519": attacker_pub,                  # attacker's own pubkey
        "signature": attacker.sign(bytes.fromhex(ch)).hex(),       # valid sig under attacker key
    }
    mpath = tmp_path / "forged.manifest.json"
    mpath.write_text(json.dumps(forged), encoding="utf-8")
    ok, reason = prov.verify_note(note, mpath)
    assert ok is False and "attested architect key" in reason


def test_real_note_still_verifies_after_pinning(tmp_path, monkeypatch):
    monkeypatch.setattr(prov, "_MANIFEST_ROOT", tmp_path / "m")
    note = _note(tmp_path)
    m = prov.sign_note(note, "t-x", "synthesis")
    ok, reason = prov.verify_note(note, m["manifest_path"])
    assert ok and "pinned to attested architect key" in reason


def test_canonical_hash_changes_with_bytes(tmp_path):
    a = tmp_path / "a.md"; a.write_text("x", encoding="utf-8")
    b = tmp_path / "b.md"; b.write_text("y", encoding="utf-8")
    assert prov.note_canonical_hash(a) != prov.note_canonical_hash(b)
