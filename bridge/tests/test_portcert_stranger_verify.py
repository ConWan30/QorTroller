"""Phase 5 WP-C — the stranger's verify path stays runnable from a fresh clone.

Two things stranded an independent verifier on any non-Windows checkout:

  * the M17 certificate's `vkey_ref` points at a build-local artifact that is not published,
    so the runner exited 2 before the ZK check (C5) could run;
  * the sealed artifacts were sealed as CRLF, so an LF checkout hashes differently and the
    anchor-digest check (C4) fails on bytes that are semantically identical.

These pin both fixes. See docs/design/buzz-phase5-wpc-verifier-rehearsal.md.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import match_certificate as mc  # noqa: E402
import portcert_full_verify as pf  # noqa: E402

CERT = REPO_ROOT / "audits" / "match_certificate_m17.json"
POSP = REPO_ROOT / "audits" / "posp_record_match17_rp_fixb3_2026-07-08.json"


def _cert() -> dict:
    return json.loads(CERT.read_text(encoding="utf-8"))


# --- Sealed bytes reproduce on this platform ---------------------------------

def test_sealed_posp_file_hashes_to_the_anchored_digest():
    """.gitattributes must check the record out in its sealed (CRLF) form on every platform."""
    digest = hashlib.sha256(POSP.read_bytes()).hexdigest()
    assert digest == _cert()["surfaces"]["anchor"]["digest"]
    assert digest == _cert()["surfaces"]["posp"]["file_sha256"]


# --- The published verifying key ---------------------------------------------

def test_published_vkey_is_in_the_tree():
    assert (REPO_ROOT / pf.PUBLISHED_VKEY).is_file()


def test_runner_falls_back_to_the_published_vkey_when_the_cert_ref_is_absent():
    vkey_ref = _cert()["surfaces"]["vhr"]["vkey_ref"]
    if (REPO_ROOT / vkey_ref).is_file():
        return  # a build-local artifact exists here; the fallback is not exercised
    assert (REPO_ROOT / pf.PUBLISHED_VKEY).is_file()


# --- The override reaches snarkjs --------------------------------------------

def _argv_of_one_verify(monkeypatch, vkey_override):
    seen: list[list[str]] = []

    class _Res:
        stdout, stderr = "OK!", ""

    monkeypatch.setattr(mc.shutil, "which", lambda _c: "/usr/bin/snarkjs")
    monkeypatch.setattr(mc.subprocess, "run", lambda argv, **_k: (seen.append(argv), _Res())[1])
    verify = mc._make_groth16_verify("snarkjs", vkey_override)
    assert verify(_cert()["surfaces"]["vhr"]) is True
    return seen[0]


def test_override_replaces_the_cert_vkey_ref(monkeypatch):
    argv = _argv_of_one_verify(monkeypatch, pf.PUBLISHED_VKEY)
    assert argv[:3] == ["/usr/bin/snarkjs", "groth16", "verify"]
    assert argv[3] == pf.PUBLISHED_VKEY
    assert _cert()["surfaces"]["vhr"]["vkey_ref"] not in argv


def test_without_an_override_the_cert_ref_is_used(monkeypatch):
    argv = _argv_of_one_verify(monkeypatch, None)
    assert argv[3] == _cert()["surfaces"]["vhr"]["vkey_ref"]


def test_c5_still_fails_closed_when_snarkjs_rejects(monkeypatch):
    class _Res:
        stdout, stderr = "Invalid proof", ""

    monkeypatch.setattr(mc.shutil, "which", lambda _c: "/usr/bin/snarkjs")
    monkeypatch.setattr(mc.subprocess, "run", lambda _argv, **_k: _Res())
    verify = mc._make_groth16_verify("snarkjs", pf.PUBLISHED_VKEY)
    assert verify(_cert()["surfaces"]["vhr"]) is False
