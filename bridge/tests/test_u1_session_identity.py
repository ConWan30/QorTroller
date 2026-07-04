"""U1 — shared session identifier (PoSP prerequisite; docs/d-cert5-unified-presence-design-2026-07-04.md).

Pins: the ONE preimage (SHA-256 of "{label}_{stamp}" — no fifth hash scheme, D-CERT-5.3 rider); the KAS
byte-stability rail (session_id rides to_dict, NEVER the commitment — two records differing only in
session_id share a commitment); log-filename re-derivation equals the daemon-side mint (the join is the
SAME id derived at two independent points); the tier-1 archive manifest carries it; the co-capture
passthrough carries it null-safely. D-CERT-9 posture: label reuse yields DISTINCT ids (stamp = instance
nonce) — pinned.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os

import pytest

from l9_presence import kill_authorship_session as kas
from l9_presence.session_identity import (ENV_SESSION_DISPLAY, ENV_SESSION_ID, derive_session_id,
                                          parse_daemon_log_name, session_display)

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_one_preimage_exactly():
    # THE preimage, pinned byte-for-byte: SHA-256(UTF-8("{label}_{stamp}")). Plain SHA-256, no domain tag.
    assert derive_session_id("corpus_growth_20260704", 1783188334) == hashlib.sha256(
        b"corpus_growth_20260704_1783188334").hexdigest()
    assert session_display("corpus_growth_20260704", 1783188334) == "corpus_growth_20260704_1783188334"


def test_label_reuse_yields_distinct_ids_dcert9_posture():
    # The stamp is the built-in instance nonce: the SAME label across two sessions -> two ids.
    # (Observed live 2026-07-04: corpus_growth_20260704 ran under stamps 1783187401 and 1783188334.)
    a = derive_session_id("corpus_growth_20260704", 1783187401)
    b = derive_session_id("corpus_growth_20260704", 1783188334)
    assert a != b


def test_log_filename_rederivation_matches_daemon_mint():
    # The stop-time issuance path re-derives from the log filename; it MUST equal the start-time env mint.
    parsed = parse_daemon_log_name("retina_daemon_corpus_growth_20260704_1783188334.log")
    assert parsed == ("corpus_growth_20260704", 1783188334)
    assert derive_session_id(*parsed) == derive_session_id("corpus_growth_20260704", 1783188334)
    assert parse_daemon_log_name("not_a_daemon_log.txt") is None      # fail-open on foreign names


def _c(ts, gate):
    return {"ts_ms": ts, "verdict": "AUTHORED_PRESENT", "composite_score": 0.8,
            "window_gate_ms": gate, "anchor": "session_x@0.66"}


_H_OK = {"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "timespan"}


def test_kas_session_id_rides_to_dict_never_the_commitment():
    # THE byte-stability rail: two records differing ONLY in session_id share a commitment (the id is a
    # join key, not evidence); to_dict surfaces it; pre-U1 records read None (null-safe).
    kw = dict(session_label="m", handle="h", composites=[_c(1000, 900), _c(2000, 1900)], hygiene=_H_OK)
    base = kas.build_session_record(**kw)
    tagged = kas.build_session_record(**kw, session_id="ab" * 32, session_display="m_123")
    assert tagged.commitment() == base.commitment()          # NOT in the preimage
    d = tagged.to_dict()
    assert d["session_id"] == "ab" * 32 and d["session_display"] == "m_123"
    assert base.to_dict()["session_id"] is None              # null-safe on old paths


def test_archive_manifest_carries_the_same_id(tmp_path, monkeypatch):
    # Tier-1 standing manifest (sink iii): _archive_ring writes manifest.json with the SAME derived id +
    # per-file SHA-256. Uses a tmp ring + tmp archive root so no real artifact is touched.
    spec = importlib.util.spec_from_file_location(
        "retina_capture_daemon", os.path.join(_REPO, "scripts", "retina_capture_daemon.py"))
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    ring = tmp_path / "ring"
    ring.mkdir()
    (ring / "panel_1.png").write_bytes(b"fakepng-1")
    (ring / "panel_2.png").write_bytes(b"fakepng-22")
    monkeypatch.setattr(daemon, "_REPO", tmp_path)
    monkeypatch.setenv("RETINA_KILLFEED_CAPTURE_DIR", "ring")
    dst, n = daemon._archive_ring("lbl", 1234567890)
    assert n == 2
    m = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    assert m["schema"] == "qortroller-session-archive-v1"
    assert m["session_id"] == derive_session_id("lbl", 1234567890)
    assert m["session_display"] == "lbl_1234567890"
    assert m["count"] == 2 and len(m["files"]) == 2
    assert m["files"][0]["sha256"] == hashlib.sha256(b"fakepng-1").hexdigest()


def test_cocapture_passthrough_null_safe():
    # Sink (i): the co-capture fields carry the id when the meta has it, None when it doesn't (pre-U1 /
    # non-daemon runs) — never fabricated, never required.
    pytest.importorskip("numpy")
    from vapi_bridge.novel_presence_fusion import cocapture_fields_from_pitl_meta
    with_id = cocapture_fields_from_pitl_meta({"session_id": "x" * 64, "session_display": "l_1"})
    assert with_id["session_id"] == "x" * 64 and with_id["session_display"] == "l_1"
    without = cocapture_fields_from_pitl_meta({})
    assert without["session_id"] is None and without["session_display"] is None


def test_env_names_are_the_wiring_contract():
    # The daemon mints these env names; dualshock_integration reads them. Renaming either side silently
    # breaks the join — pin the contract.
    assert ENV_SESSION_ID == "QORTROLLER_SESSION_ID"
    assert ENV_SESSION_DISPLAY == "QORTROLLER_SESSION_DISPLAY"
