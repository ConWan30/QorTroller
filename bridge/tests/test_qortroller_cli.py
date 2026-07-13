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
    # PKG-D-15: Stage 4 pass required before FIRST_PROOF_PENDING
    (tmp_path / "setup" / "stage4_controller_pass.json").write_text(
        '{"schema":"qortroller-stage4-controller-v1","present":true,"operator_ack":true}',
        encoding="utf-8")
    ns = q.compute_node_state(tmp_path)
    assert ns["state"] == q.NODE_STATE_FIRST_PROOF_PENDING
    assert ns.get("stage5_deferred") is True
    assert "first proof pending" in ns["detail"]


def test_node_state_provisioning_controller_pending(tmp_path):
    """ROI done but Stage 4 missing -> still PROVISIONING (PKG-D-15)."""
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    (tmp_path / "setup").mkdir()
    (tmp_path / "setup" / "stage3_roi_pass.json").write_text("{}", encoding="utf-8")
    ns = q.compute_node_state(tmp_path)
    assert ns["state"] == q.NODE_STATE_PROVISIONING
    assert "controller" in ns["detail"]


def test_node_state_born(tmp_path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    (tmp_path / "setup").mkdir()
    (tmp_path / "setup" / "stage3_roi_pass.json").write_text("{}", encoding="utf-8")
    (tmp_path / "setup" / "stage4_controller_pass.json").write_text(
        '{"present":true,"operator_ack":true}', encoding="utf-8")
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


# --- PKG-D-15: Stage 4 controller presence (safe fields only) ----------------
def test_classify_controller_presence_found_and_absent():
    found = q.classify_controller_presence([
        {"vendor_id": 0x054C, "product_id": 0x0DF2, "product_string": "DualSense Edge",
         "path": "\\\\?\\HID#SHOULD_NOT_LEAK", "serial_number": "SERIAL_NO"},
        {"vendor_id": 0x1234, "product_id": 0x5678},
    ])
    assert found["present"] is True
    assert found["vid_hex"] == "054C" and found["pid_hex"] == "0DF2"
    assert found["product"] == "DualSense Edge"
    assert found["n_matches"] == 1
    assert "path" not in found and "serial" not in found and "serial_number" not in found

    absent = q.classify_controller_presence([{"vendor_id": 0x1234, "product_id": 0x5678}])
    assert absent["present"] is False and absent["n_matches"] == 0


def test_build_stage4_pass_record_strips_forbidden():
    presence = q.classify_controller_presence([
        {"vendor_id": q.EDGE_VID, "product_id": q.EDGE_PID, "product_string": "Edge"}
    ])
    # attacker-shaped extras must not land on disk even if smuggled into presence
    presence["path"] = "C:\\evil"
    presence["serial_number"] = "ABC"
    rec = q.build_stage4_pass_record(presence, operator_ack=True,
                                     dual_connection_note_shown=True, ts=42)
    assert rec["schema"] == q.STAGE4_SCHEMA
    assert rec["present"] is True and rec["operator_ack"] is True
    assert rec["dual_connection_note_shown"] is True
    assert rec["ts"] == 42
    assert "path" not in rec and "serial_number" not in rec
    # soft-skip path
    skip = q.build_stage4_pass_record(
        q.classify_controller_presence([]), operator_ack=True,
        dual_connection_note_shown=True, operator_skip=True, ts=1)
    assert skip["present"] is False and skip["operator_skip"] is True


def test_probe_controller_presence_injectable():
    def fake_enum(vid, pid):
        assert vid == q.EDGE_VID and pid == q.EDGE_PID
        return [{"vendor_id": vid, "product_id": pid, "product_string": "Injected Edge",
                 "path": "must-not-return", "serial_number": "nope"}]
    out = q.probe_controller_presence(enumerate_fn=fake_enum)
    assert out["present"] is True and out["detection"] == "injected"
    assert out["product"] == "Injected Edge"
    assert "path" not in out and "serial_number" not in out


def test_dual_connection_note_mentions_usb_and_bt():
    note = q.DUAL_CONNECTION_NOTE.lower()
    assert "usb" in note and "bluetooth" in note or "bt" in note
    assert "ps5" in note


# --- PKG-D-16: dogfood report schema ----------------------------------------
# --- PKG-UI stream UX pure helpers (round-11) ---------------------------------
def test_classify_freshness_class_taxonomy():
    assert q.classify_freshness_class(30.0) == q.FRESHNESS_LIVE
    assert q.classify_freshness_class(180.0) == q.FRESHNESS_FRESH
    assert q.classify_freshness_class(4000.0) == q.FRESHNESS_STALE
    assert q.classify_freshness_class(None) == q.FRESHNESS_UNKNOWN
    assert q.classify_freshness_class(10.0, n_crops=0) == q.FRESHNESS_EMPTY
    assert q.classify_freshness_class(float("inf"), n_crops=0) == q.FRESHNESS_EMPTY
    # Share surface stays coarser (FROZEN redaction matrix)
    assert q.freshness_for_share(30.0) == q.FRESHNESS_FRESH
    assert q.freshness_for_share(4000.0) == q.FRESHNESS_STALE
    assert q.freshness_for_share(None) == q.FRESHNESS_UNKNOWN


def test_status_snapshot_no_secrets_no_fabricated_live(tmp_path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    snap = q.build_status_snapshot(home=tmp_path, session=None, port_owners=[], pack="observer-only")
    assert snap["schema"] == q.STATUS_SNAPSHOT_SCHEMA
    assert snap["signing_material_present"] is False and snap["consent_authority"] is False
    assert snap["mock"] is False and snap["fabricated_liveness"] is False
    assert snap["freshness_class"] == q.FRESHNESS_EMPTY
    assert snap["witness_live"] is False
    assert not any(q.secret_shaped(k) for k in snap)


def test_stream_view_model_witness_live_and_absences(tmp_path):
    snap = {
        "schema": q.STATUS_SNAPSHOT_SCHEMA,
        "node_state": q.NODE_STATE_LIVE,
        "freshness_class": q.FRESHNESS_LIVE,
        "witness_live": True,
        "session_label": "m13",
        "session_id_display": "m13_..._x",
        "pack": "observer-only",
    }
    m = q.build_stream_view_model(snap)
    assert m["schema"] == q.STREAM_VIEW_SCHEMA
    assert m["on_screen"]["presence_line"] == "your witness is live"
    assert m["on_screen"]["presence_tone"] == "live"
    assert m["novelty"] == "witness_respiration"
    assert "crop_counts" in m["deliberately_absent"]
    assert "fps" in m["deliberately_absent"]
    assert m["mock"] is False and m["signing_material_present"] is False
    # Quiet path: never invent LIVE
    quiet = q.build_stream_view_model({"freshness_class": q.FRESHNESS_STALE, "node_state": "NODE_BORN"})
    assert quiet["on_screen"]["presence_tone"] == "quiet"
    assert "live" not in quiet["on_screen"]["presence_line"]


def test_receipt_reveal_dignified_verdicts_and_choreography():
    kas = {"verdict": "HYGIENE_FAIL", "commitment": "ab" * 32}
    posp = {"verdict": "PARTIAL_SURFACES", "events_roots": {"retina_perception_root": "cc" * 32}}
    rev = q.build_receipt_reveal_model("match_1", kas, posp, None, None,
                                      pack="observer-only", ring_age_s=40.0)
    assert rev["schema"] == q.RECEIPT_REVEAL_SCHEMA
    assert [c["stage"] for c in rev["choreography"]] == [
        "SETTLE", "SURFACES", "HONESTY", "SHARE_SPLIT"]
    assert rev["surfaces"]["kas"]["tone"] == q.VERDICT_TONE_HYGIENE
    assert "not a player failure" in rev["surfaces"]["kas"]["line"]
    assert rev["surfaces"]["posp"]["tone"] == q.VERDICT_TONE_PARTIAL
    assert rev["surfaces"]["v3"]["tone"] == q.VERDICT_TONE_ABSENT
    assert rev["f_t66b1"]["visible_on_share"] is True
    assert rev["share"]["shows_crop_counts"] is False
    assert "HYGIENE_FAIL" in rev["local"]["body_text"]
    assert "F-T66B-1" in rev["share"]["body_text"]
    assert rev["signing_material_present"] is False


def test_receipt_reveal_synchronized_is_earned():
    posp = {"verdict": "SYNCHRONIZED", "events_roots": {}}
    rev = q.build_receipt_reveal_model("m", None, posp, {"commitment": "dd" * 32}, None)
    assert rev["surfaces"]["posp"]["tone"] == q.VERDICT_TONE_EARNED
    assert rev["surfaces"]["v3"]["tone"] == q.VERDICT_TONE_EARNED


def test_birth_ceremony_map_stages_and_roi_visual(tmp_path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    (tmp_path / "setup").mkdir()
    (tmp_path / "setup" / "stage3_roi_pass.json").write_text(
        '{"roi":"0,0,1,1","operator_ack":true}', encoding="utf-8")
    (tmp_path / "setup" / "stage3_roi_check.png").write_bytes(b"\x89PNG\r\n")
    m = q.build_birth_ceremony_map(tmp_path)
    assert m["schema"] == q.BIRTH_CEREMONY_SCHEMA
    ids = [s["id"] for s in m["stages"]]
    assert ids == ["port", "card", "roi", "controller", "drill"]
    roi = next(s for s in m["stages"] if s["id"] == "roi")
    assert roi["visual"] == "roi_overlay_png"
    assert roi["overlay_exists"] is True
    assert roi["status"] == "done"
    ctrl = next(s for s in m["stages"] if s["id"] == "controller")
    assert ctrl["status"] == "current"  # ROI done, stage4 missing
    assert m["ceremony_complete"] is False
    assert m["signing_material_present"] is False


def test_dogfood_report_scaffold_and_validate():
    r = q.scaffold_dogfood_report(run_label="tonight", path="B")
    assert r["schema"] == q.DOGFOOD_REPORT_SCHEMA
    assert r["run_label"] == "tonight" and r["path"] == "B"
    assert r["operator_would_rerun_without_chat"] is None  # operator fills after run
    ok, errs = q.validate_dogfood_report(r)
    assert ok and errs == []

    # Phase D bar set true
    r["operator_would_rerun_without_chat"] = True
    r["friction_events"] = [{"code": "ROI_CONFUSION", "stage": "roi", "detail": "green box?"}]
    ok, errs = q.validate_dogfood_report(r)
    assert ok

    bad = dict(r)
    bad["path"] = "C"
    bad["friction_events"] = [{"code": "NOT_A_CODE"}]
    bad["bridge_private_key"] = "x"  # secret-shaped key
    ok, errs = q.validate_dogfood_report(bad)
    assert not ok
    joined = " ".join(errs)
    assert "path" in joined and "friction" in joined.lower() or "NOT_A_CODE" in joined
    assert any("secret" in e for e in errs)
