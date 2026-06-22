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


def test_canonical_hash_changes_with_bytes(tmp_path):
    a = tmp_path / "a.md"; a.write_text("x", encoding="utf-8")
    b = tmp_path / "b.md"; b.write_text("y", encoding="utf-8")
    assert prov.note_canonical_hash(a) != prov.note_canonical_hash(b)
