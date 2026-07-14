"""A2A-STREAM-2 — status/stream snapshot node face (Q1–Q5).

T-S2-1  node identity face DERIVED when birth + device_id present
T-S2-2  node identity ABSENT honest when no birth
T-S2-3  contribution pulse PENDING never claims on-chain without tx
T-S2-4  scorecard summary preserves MEASURED / OPERATOR-REPORTED tags
T-S2-5  witness blink kills_seen MEASURED; fresh_fires ABSENT (HARD-1 gated)
T-S2-6  status snapshot additive keys; no secret-shaped; no fabricated LIVE
T-S2-7  stream view model pass-through + novelty node_face
T-S2-8  old-shell compatibility: missing face keys still build quiet stream
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))
sys.path.insert(0, str(_REPO / "bridge"))

import qortroller as q  # noqa: E402
from vapi_bridge import node_contribution_ledger as ncl  # noqa: E402

REF_DEVICE = "58" * 32  # 64 hex
REF_SESSION = "match_stream2_birth_001"
REF_NODE = q.derive_node_id(REF_DEVICE, REF_SESSION)


def _write_birth(home: Path, *, with_device: bool = True) -> dict:
    birth = {
        "schema": "qortroller-birth-receipt-v0",
        "first_session_id": REF_SESSION,
        "path": "B",
        "ts": 1,
    }
    if with_device:
        birth["device_id_hex"] = REF_DEVICE
        birth["node_id"] = REF_NODE
    (home / "birth_receipt.json").write_text(json.dumps(birth), encoding="utf-8")
    return birth


def test_s2_1_node_identity_derived(tmp_path: Path):
    _write_birth(tmp_path, with_device=True)
    face = q.build_node_identity_face(tmp_path)
    assert face["present"] is True
    assert face["node_id"] == REF_NODE
    assert face["node_id_short"] == q.node_id_short(REF_NODE)
    assert face["node_id_source"] == q.SRC_DERIVED
    assert face["claim_language"] == "derived_not_minted"
    assert face["device_on_chain_evidence"] is True
    assert "minted" not in face["line"].lower() or "not minted" in face["line"].lower() or "derived" in face["line"].lower()


def test_s2_2_node_identity_absent(tmp_path: Path):
    face = q.build_node_identity_face(tmp_path)
    assert face["present"] is False
    assert face["node_id"] is None
    assert face["node_id_source"] == q.SRC_ABSENT
    assert "unformed" in face["line"].lower() or "required" in face["line"].lower()


def test_s2_3_contribution_pulse_pending_honesty(tmp_path: Path):
    path = ncl.default_ledger_path(tmp_path)
    e = ncl.build_entry(
        node_id_hex=REF_NODE,
        session_id="sess_stream2_1",
        scorecard_root_hex="cd" * 32,
        posp_verdict="SYNCHRONIZED",
        w3s_attested=True,
        ts_ns=1_752_400_000_000_000_001,
    )
    assert e["anchored"] is False
    ncl.append_entry(path, e)
    pulse = q.build_contribution_pulse(tmp_path, node_id_hex=REF_NODE)
    assert pulse["present"] is True
    assert pulse["entry_count"] == 1
    assert pulse["chain_intact"] is True
    row = pulse["recent"][-1]
    assert row["lifecycle"] == "PENDING"
    assert row["anchored"] is False
    assert row["anchor_tx_short"] is None
    assert row["w3s_attested"] is True
    assert "on-chain" in " ".join(pulse["must_not_claim"]).lower() or any(
        "on-chain" in m.lower() for m in pulse["must_not_claim"]
    )


def test_s2_4_scorecard_tags(tmp_path: Path):
    card = {
        "schema": q.MATCH_SCORECARD_SCHEMA,
        "label": "m_test",
        "dignity": {"tone": "honest_null", "notes": []},
        "fields": {
            "kas_verdict": {"value": "AUTHORED_SESSION", "source": "MEASURED"},
            "posp_verdict": {"value": "SYNCHRONIZED", "source": "MEASURED"},
            "recall": {
                "status": "UNSCORED",
                "display": "authored 8 / reported UNSCORED",
                "authored": {"value": 8, "source": "MEASURED"},
                "reported": {"value": None, "source": "OPERATOR-REPORTED"},
            },
        },
    }
    ui = (tmp_path / "ui")
    ui.mkdir()
    (ui / "scorecard.json").write_text(json.dumps(card), encoding="utf-8")
    s = q.load_scorecard_summary(home=tmp_path, session={"label": "m_test"})
    assert s["present"] is True
    assert s["authored"]["source"] == "MEASURED"
    assert s["authored"]["value"] == 8
    assert s["reported"]["source"] == "OPERATOR-REPORTED"
    assert s["reported"]["value"] is None
    assert s["recall_status"] == "UNSCORED"


def test_s2_5_witness_blink_fresh_fires_gated(tmp_path: Path):
    cap = tmp_path / "cap"
    cap.mkdir()
    (cap / "killfeed_events.jsonl").write_text(
        '{"k":1}\n{"k":2}\n', encoding="utf-8"
    )
    blink = q.build_witness_blink(capture_dir=cap)
    assert blink["kills_seen"] == 2
    assert blink["kills_seen_source"] == q.SRC_MEASURED
    assert blink["fresh_fires"] is None
    assert blink["fresh_fires_status"] == q.SRC_ABSENT
    assert "GATED" in blink["fresh_fires_note"] or "process-memory" in blink["fresh_fires_note"]


def test_s2_6_status_snapshot_additive_no_secrets(tmp_path: Path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    _write_birth(tmp_path, with_device=True)
    snap = q.build_status_snapshot(
        home=tmp_path, session=None, port_owners=[], pack="observer-only",
        audits_dir=tmp_path / "audits",
    )
    assert snap["schema"] == q.STATUS_SNAPSHOT_SCHEMA
    assert snap["freshness_class"] == q.FRESHNESS_EMPTY
    assert snap["witness_live"] is False
    assert snap["fabricated_liveness"] is False
    assert "node_identity" in snap
    assert "contribution" in snap
    assert "scorecard" in snap
    assert "witness_blink" in snap
    assert snap["node_id"] == REF_NODE
    assert snap["fresh_fires"] is None
    assert not any(q.secret_shaped(k) for k in snap)
    assert snap["signing_material_present"] is False


def test_s2_7_stream_view_pass_through(tmp_path: Path):
    q.write_flat_toml(tmp_path / "node.toml", {"uvc_index": 1, "pack": "observer-only"})
    _write_birth(tmp_path, with_device=True)
    snap = q.build_status_snapshot(home=tmp_path, session={"label": "m", "stamp": 1},
                                   port_owners=[], pack="observer-only",
                                   audits_dir=tmp_path / "nope")
    # force live presence fields for stream model test
    snap["freshness_class"] = q.FRESHNESS_LIVE
    snap["witness_live"] = True
    snap["node_state"] = q.NODE_STATE_LIVE
    m = q.build_stream_view_model(snap)
    assert m["on_screen"]["presence_tone"] == "live"
    assert m["on_screen"]["node_identity"]["present"] is True
    assert m["on_screen"]["node_id_short"] == q.node_id_short(REF_NODE)
    assert "node_face" in m["novelty"]
    assert m["mock"] is False


def test_s2_8_old_shell_missing_face_keys():
    quiet = q.build_stream_view_model({
        "freshness_class": q.FRESHNESS_STALE,
        "node_state": "NODE_BORN",
    })
    assert quiet["on_screen"]["presence_tone"] == "quiet"
    assert quiet["on_screen"]["node_identity"] is None
    assert quiet["on_screen"]["scorecard"] is None
    assert quiet["on_screen"]["contribution"] is None
    assert "live" not in quiet["on_screen"]["presence_line"]
