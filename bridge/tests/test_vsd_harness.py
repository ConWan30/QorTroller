"""Tests for the VSD immutable harness (parse + VSD-3 honesty + integration on the seeded vault)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_VAULT = Path(__file__).resolve().parent.parent.parent / "vsd-vault"
sys.path.insert(0, str(_VAULT / ".vsd"))

import vsd_eval_harness as H  # noqa: E402
import vsd_provenance as prov  # noqa: E402


def test_parse_frontmatter():
    fm = H.parse_frontmatter("---\ntype: claim\nid: c-1\neffort: 12\nrefs: []\n---\nbody")
    assert fm["type"] == "claim" and fm["id"] == "c-1" and fm["effort"] == 12 and fm["refs"] == []


def test_confidence_words_are_eight():
    assert len(H.CONFIDENCE_WORDS) == 8
    assert "likely" in H.CONFIDENCE_WORDS and "definitely" not in H.CONFIDENCE_WORDS


def test_seeded_vault_passes_if_present():
    """Integration: if cycle 1 has seeded the real vault, the harness is clean."""
    if not (_VAULT / "notes" / "synthesis" / "s-purpose-of-vapi.md").exists():
        pytest.skip("vault not seeded in this checkout")
    if not (_VAULT / "architect_key.pem").exists():
        pytest.skip(
            "architect_key.pem (gitignored) not present — run "
            "python vsd-vault/.vsd/vsd_synthesizer.py --cycle N to sign ingest notes"
        )
    rep = H.run_harness()
    assert rep.passed and rep.n_notes >= 1
    assert "s-purpose-of-vapi" in rep.passing_note_ids


@pytest.mark.skipif(not (_VAULT / "architect_key.pem").exists(),
                    reason="architect_key.pem (gitignored) not present")
def test_bad_confidence_flagged(tmp_path, monkeypatch):
    # isolate the harness + provenance to a tmp vault so we don't touch the real one
    notes = tmp_path / "notes"; (notes / "synthesis").mkdir(parents=True)
    monkeypatch.setattr(H, "_NOTES", notes)
    monkeypatch.setattr(H, "_MANIFESTS", tmp_path / "m")
    monkeypatch.setattr(prov, "_MANIFEST_ROOT", tmp_path / "m")
    note = notes / "synthesis" / "s-bad.md"
    note.write_text("---\ntype: synthesis\nid: s-bad\nconfidence: definitely\neffort: 5\n"
                    f"deployer: {H.BRIDGE_WALLET}\n---\nbody\n", encoding="utf-8")
    prov.sign_note(note, "s-bad", "synthesis")
    fnd, passes = H.check_note(note)
    assert any(f.invariant == "VSD-3" and "estimative" in f.message for f in fnd)


@pytest.mark.skipif(not (_VAULT / "architect_key.pem").exists(),
                    reason="architect_key.pem (gitignored) not present")
def test_good_note_passes(tmp_path, monkeypatch):
    notes = tmp_path / "notes"; (notes / "synthesis").mkdir(parents=True)
    monkeypatch.setattr(H, "_NOTES", notes)
    monkeypatch.setattr(H, "_MANIFESTS", tmp_path / "m")
    monkeypatch.setattr(prov, "_MANIFEST_ROOT", tmp_path / "m")
    note = notes / "synthesis" / "s-ok.md"
    note.write_text("---\ntype: synthesis\nid: s-ok\nconfidence: likely\neffort: 10\n"
                    f"deployer: {H.BRIDGE_WALLET}\n---\nbody\n", encoding="utf-8")
    prov.sign_note(note, "s-ok", "synthesis")
    fnd, passes = H.check_note(note)
    assert passes and not fnd
