"""A2A-PKG round-03 tests -- the qortroller CLI spine's pure helpers.

Covers the three live-friction fixes (port-owner parse, ring freshness-not-counts, persisted config)
plus the PKG-D-05 no-secrets pack rail and the PKG-D-03 honest receipt (verdicts render AS-IS).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller as q


# --- friction #1: phantom port-owner parse ---------------------------------
def test_parse_netstat_owners_finds_listener():
    text = ("  TCP    0.0.0.0:8080           0.0.0.0:0              LISTENING       3528\n"
            "  TCP    127.0.0.1:5173         0.0.0.0:0              LISTENING       111\n"
            "  TCP    0.0.0.0:8080           0.0.0.0:0              LISTENING       3528\n"
            "  UDP    0.0.0.0:8080           *:*                                    999\n")
    assert q.parse_netstat_owners(text, 8080) == [3528]        # TCP LISTENING only, deduped


def test_parse_netstat_owners_no_match():
    assert q.parse_netstat_owners("  TCP  0.0.0.0:9999  0.0.0.0:0  LISTENING  7\n", 8080) == []


def test_parse_netstat_port_suffix_not_substring():
    text = "  TCP    0.0.0.0:18080          0.0.0.0:0              LISTENING       42\n"
    assert q.parse_netstat_owners(text, 8080) == []            # :18080 is not :8080


# --- PKG-D-05 rail: secrets never enter the node config --------------------
def test_write_flat_toml_refuses_secret_shaped(tmp_path):
    with pytest.raises(ValueError):
        q.write_flat_toml(tmp_path / "node.toml", {"bridge_private_key": "x"})
    with pytest.raises(ValueError):
        q.write_flat_toml(tmp_path / "node.toml", {"api_token": "x"})


def test_node_config_roundtrip(tmp_path):
    p = tmp_path / "node.toml"
    q.write_flat_toml(p, {"uvc_index": 1, "killfeed_roi": "0.0,0.45,0.26,0.19",
                          "emit_v3": True, "pack": "observer-only"})
    cfg = q.read_node_config(p)
    assert cfg["uvc_index"] == 1 and cfg["emit_v3"] is True
    assert cfg["killfeed_roi"] == "0.0,0.45,0.26,0.19"
    assert cfg["kf_engine"] == "rapidocr"                      # default preserved under overrides


def test_read_node_config_failclosed_on_secret(tmp_path):
    p = tmp_path / "node.toml"
    p.write_text('private_key = "abc"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        q.read_node_config(p)


# --- friction #2: freshness, not counts ------------------------------------
def test_ring_freshness_empty(tmp_path):
    n, age = q.ring_freshness(tmp_path, time.time())
    assert n == 0 and age == float("inf")


def test_ring_freshness_counts_and_age(tmp_path):
    (tmp_path / "panel_1.png").write_bytes(b"x")
    n, age = q.ring_freshness(tmp_path, time.time())
    assert n == 1 and age < 60


# --- PKG-D-03: the honest receipt -------------------------------------------
def test_receipt_renders_honest_verdicts_asis():
    kas = {"verdict": "HYGIENE_FAIL", "authored_kills": 0, "commitment": "ab" * 32}
    posp = {"verdict": "PARTIAL_SURFACES", "fusion": {"n_id_verified": 0},
            "events_roots": {"retina_perception_root": None}}
    text = q.render_receipt("sess1", kas, posp, None, None, pack="observer-only")
    assert "HYGIENE_FAIL" in text and "PARTIAL_SURFACES" in text
    assert "honest-null" in text                               # v3 absent -> honest-null, not hidden
    assert "F-T66B-1" in text                                  # open finding disclosed in-product
    assert "SYNCHRONIZED" not in text.replace("PARTIAL_SURFACES", "")  # never rounded up


def test_receipt_renders_full_pack():
    v3 = {"n_events": 2, "commitment": "8e" * 32}
    posp = {"verdict": "SYNCHRONIZED", "fusion": {"n_id_verified": 72},
            "events_roots": {"retina_perception_root": "cc" * 32}}
    text = q.render_receipt("t66b4", {"verdict": "AUTHORED_SESSION", "authored_kills": 8,
                                      "commitment": "aa" * 32},
                            posp, v3, {"count": 600, "schema": "qortroller-session-archive-v1"},
                            stranger_verified=True, pack="observer-only")
    assert "SYNCHRONIZED" in text and "n_events=2" in text
    assert "stranger_verified: True" in text and "600 crops" in text


# --- PKG-D-10: the pack matrix (capability envelopes) ------------------------
def test_observer_pack_pins_the_safety_floor():
    env = q.apply_pack_env("observer-only", {})
    assert env["CHAIN_SUBMISSION_PAUSED"] == "true"        # the kit never spends/deploys
    for hard_off in ("L6_CHALLENGES_ENABLED", "L6B_ENABLED", "GSR_ENABLED", "GRIND_MODE"):
        assert env[hard_off] == "false"                    # hard rules forced off
    assert env["RETINA_DA_WITNESS_ENABLED"] == "false"
    assert env["RETINA_CAPTURE_SOURCE"] == "uvc"


def test_every_pack_pins_kill_switch_and_no_secrets():
    for name, pins in q.PACKS.items():
        assert pins.get("CHAIN_SUBMISSION_PAUSED") == "true", name
        for k in pins:
            assert not q.secret_shaped(k), f"secret-shaped pin {k!r} in pack {name!r}"


def test_unknown_pack_fails_safe_to_observer():
    env = q.apply_pack_env("no-such-pack", {})
    assert env["GRIND_MODE"] == "false" and env["CHAIN_SUBMISSION_PAUSED"] == "true"


# --- PKG-D-09: the SHARE redaction matrix (FROZEN Phase D) --------------------
def _share(**kw):
    kas = {"verdict": "HYGIENE_FAIL", "commitment": "ab" * 32}
    posp = {"verdict": "SYNCHRONIZED", "events_roots": {"retina_perception_root": "cc" * 32}}
    v3 = {"n_events": 2, "commitment": "8e" * 32}
    defaults = dict(stranger_verified=True, pack="observer-only", ring_age_s=30.0)
    defaults.update(kw)
    return q.render_share_postcard("t66b4", kas, posp, v3, {"count": 600}, **defaults)


def test_share_verdicts_asis_and_gap_disclosed():
    card = _share()
    assert "SYNCHRONIZED" in card and "HYGIENE_FAIL" in card   # never rounded up, never hidden
    assert "F-T66B-1" in card                                  # trust requires the gap


def test_share_truncates_roots_and_hides_counts():
    card = _share()
    assert ("ab" * 32) not in card and ("8e" * 32) not in card  # full roots never on the postcard
    assert "abababababababab..." in card                        # 16-hex prefix present
    assert "600" not in card                                    # counts -> freshness class only
    assert "FRESH" in card


def test_share_freshness_classes():
    assert "STALE" in _share(ring_age_s=4000.0)
    assert "UNKNOWN" in _share(ring_age_s=None)


def test_share_no_paths_no_user():
    card = _share()
    assert "C:\\" not in card and "Users" not in card           # absolute paths / usernames never


def test_trunc_helpers():
    assert q._trunc_hex("ab" * 32) == "ab" * 8 + "..."
    assert q._trunc_hex(None) == "null"
    assert q._trunc_session_id("0123456789abcdef0123") == "0123...0123"


# --- PKG-D-09: offline HTML wrap ---------------------------------------------
def test_html_wrap_escapes_and_offline():
    h = q.html_wrap("T & T", "body <script>alert(1)</script>")
    assert "<script>alert" not in h and "&lt;script&gt;" in h   # escaped, never active
    assert "http" not in h.lower().replace("html", "")          # zero live calls in the artifact


# --- PKG-D-11: node birth state machine --------------------------------------
def test_node_state_unprovisioned(tmp_path):
    ns = q.compute_node_state(tmp_path)
    assert ns["state"] == q.NODE_STATE_UNPROVISIONED


def test_node_state_provisioning_roi_pending(tmp_path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    ns = q.compute_node_state(tmp_path)
    assert ns["state"] == q.NODE_STATE_PROVISIONING
    assert "ROI" in ns["detail"]


def test_node_state_first_proof_pending_path_b(tmp_path):
    q.write_flat_toml(tmp_path / "node.toml",
                      {"uvc_index": 1, "pack": "observer-only", "stage5_deferred": True})
    (tmp_path / "setup").mkdir()
    (tmp_path / "setup" / "stage3_roi_pass.json").write_text(
        '{"roi":"0,0,1,1","operator_ack":true}', encoding="utf-8")
    ns = q.compute_node_state(tmp_path)
    assert ns["state"] == q.NODE_STATE_FIRST_PROOF_PENDING
    assert ns.get("stage5_deferred") is True
    assert "first proof pending" in ns["detail"]


def test_node_state_born(tmp_path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    (tmp_path / "setup").mkdir()
    (tmp_path / "setup" / "stage3_roi_pass.json").write_text("{}", encoding="utf-8")
    (tmp_path / "birth_receipt.json").write_text(
        '{"first_session_id":"proof_drill_x","path":"A"}', encoding="utf-8")
    ns = q.compute_node_state(tmp_path)
    assert ns["state"] == q.NODE_STATE_NODE_BORN
    assert "proof_drill_x" in ns["detail"]


# --- PKG-D-12: verify --share tiers ------------------------------------------
def test_verify_share_postcard_alone_is_indicative():
    card = _share()
    r = q.verify_share_postcard(card)
    assert r["tier"] == "POSTCARD" and r["verdict"] == "INDICATIVE"
    assert "not a proof" in r["note"].lower() or "INDICATIVE" in r["note"]


def test_verify_share_pack_stranger_ok():
    kas = {"verdict": "HYGIENE_FAIL", "commitment": "ab" * 32}
    posp = {"verdict": "SYNCHRONIZED", "events_roots": {"retina_perception_root": "cc" * 32}}
    v3 = {"n_events": 2, "commitment": "8e" * 32}
    card = q.render_share_postcard("t66b4", kas, posp, v3, {"count": 600},
                                   pack="observer-only", ring_age_s=30.0)
    r = q.verify_share_postcard(card, kas=kas, posp=posp, v3=v3, pack_provided=True)
    assert r["verdict"] == "STRANGER_OK"
    assert all(c["ok"] for c in r["checks"])


def test_verify_share_pack_mismatch_on_verdict_upgrade_attempt():
    """Postcard claims SYNCHRONIZED but local pack is PARTIAL -- MISMATCH (never upgrade)."""
    kas = {"verdict": "HYGIENE_FAIL", "commitment": "ab" * 32}
    posp_local = {"verdict": "PARTIAL_SURFACES",
                  "events_roots": {"retina_perception_root": "cc" * 32}}
    # craft a postcard that lies upward
    card = q.render_share_postcard(
        "t", kas, {"verdict": "SYNCHRONIZED",
                   "events_roots": {"retina_perception_root": "cc" * 32}},
        None, None, pack="observer-only", ring_age_s=10.0)
    r = q.verify_share_postcard(card, kas=kas, posp=posp_local, pack_provided=True)
    assert r["verdict"] == "MISMATCH"
    assert any(c["name"] == "posp_verdict" and not c["ok"] for c in r["checks"])


def test_parse_share_claims_extracts_prefixes():
    card = _share()
    claims = q.parse_share_claims(card)
    assert claims["f_t66b1"] is True
    assert claims["posp"] == "SYNCHRONIZED"
    assert claims["kas"] == "HYGIENE_FAIL"
    assert claims["kas_prefix"] == ("ab" * 8)
    assert claims["v3_prefix"] == ("8e" * 8)


# --- PKG-D-13: honesty notes evolution ---------------------------------------
def test_honesty_notes_open_default():
    notes = q.build_honesty_notes()
    codes = {n["code"]: n for n in notes}
    assert codes["F-T66B-1"]["status"] == "OPEN"
    assert codes["VERDICT_AS_IS"]["status"] == "FROZEN"
    text = q.render_receipt("s", None, None, None, None, pack="observer-only")
    assert "[OPEN] F-T66B-1" in text


def test_honesty_notes_measured_and_historical():
    m = q.build_honesty_notes(own_kill_recall=(3, 8))
    assert m[0]["status"] == "MEASURED" and "3/8" in m[0]["detail"]
    h = q.build_honesty_notes(capture_era_has_metric=False)
    assert h[0]["status"] == "HISTORICAL_GAP"
    assert "not re-scored" in h[0]["detail"]
    # SHARE still discloses the code
    card = q.render_share_postcard("old", None, None, None, None,
                                   honesty_notes=h, ring_age_s=None)
    assert "F-T66B-1" in card and "HISTORICAL_GAP" in card


# --- PKG-D-14: dogfood telemetry allowlist + default off ---------------------
def test_dogfood_default_off_and_allowlist(tmp_path):
    q.append_dogfood_event(tmp_path, {"event": "play_start", "pack": "observer-only"},
                           enabled=False)
    assert not (tmp_path / "dogfood_events.jsonl").exists()
    q.append_dogfood_event(tmp_path, {
        "event": "roi_ack", "stage": "roi", "duration_ms": 1200,
        "secret_key": "nope",           # must be stripped by allowlist
        "frames": "BIOMETRIC_NO",       # not in allowlist
    }, enabled=True)
    lines = (tmp_path / "dogfood_events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = __import__("json").loads(lines[0])
    assert row["event"] == "roi_ack" and row["duration_ms"] == 1200
    assert "secret_key" not in row and "frames" not in row
    assert not q.dogfood_enabled({})
