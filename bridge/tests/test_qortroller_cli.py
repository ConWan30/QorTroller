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
