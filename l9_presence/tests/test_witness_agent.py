"""Tests for the Gameplay Witness Agent Phase-1 core (numpy-only; no hardware)."""
import json

import numpy as np

from l9_presence.bcc import BCCStore
from l9_presence.pocp import compute_pocp_commitment, preimage_len
from l9_presence.verification_card import render_card
from l9_presence.witness_agent import WitnessConfig, _should_harvest_l9, process_session


def _write_coupled(path, n=500, rate_hz=100.0, lag_ms=40.0, seed=0, player="P1"):
    rng = np.random.default_rng(seed)
    dt = 1000.0 / rate_hz
    ts = np.arange(n) * dt
    sx = 128 + 60.0 * np.sin(2 * np.pi * 0.8 * ts / 1000.0)
    sy = 128 + 8.0 * np.sin(2 * np.pi * 0.3 * ts / 1000.0)
    lag = int(round(lag_ms / dt))
    yaw = rng.normal(0, 0.4, n)
    yaw[lag:] += (sx[: n - lag] - 128) * 1.5
    pitch = rng.normal(0, 0.4, n)
    fire = np.zeros(n); fire[n // 2:] = 200.0
    np.savez(path, in_ts=ts, in_sx=sx, in_sy=sy, in_fire=fire,
             mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch, label="human", player=player)
    return str(path)


# ---- PoCP commitment ----

def test_pocp_is_deterministic_and_sensitive():
    kw = dict(player="P1", session_id="s1", coupling=0.4, lag_ms=42.0,
              negative_control=0.02, decoupled_energy=0.84, n_samples=1800, ts_ns=123)
    a = compute_pocp_commitment(**kw)
    assert a == compute_pocp_commitment(**kw)            # deterministic
    assert len(a) == 64                                  # sha-256 hex
    kw2 = dict(kw); kw2["coupling"] = 0.41
    assert compute_pocp_commitment(**kw2) != a           # sensitive to inputs


def test_pocp_preimage_len_guard():
    assert preimage_len() == 113


# ---- verification card ----

def test_card_contains_verdict_and_commitment():
    html = render_card(player="P1", session_id="s1", label="human", verdict="PRESENT",
                       coupling=0.4, lag_ms=42, negative_control=0.02, neg_margin=0.38,
                       decoupled_energy=0.84, n_samples=1800, commitment="deadbeef",
                       ts_iso="2026-05-21T00:00:00+00:00")
    assert "PRESENT" in html and "deadbeef" in html
    assert "not" in html.lower() and "zero-knowledge" in html.lower()  # honest disclaimer


# ---- process_session orchestration ----

def test_process_session_emits_card_commitment_and_dryrun_handoffs(tmp_path):
    p = _write_coupled(tmp_path / "P1_01.npz")
    m = process_session(p, WitnessConfig(out_dir=str(tmp_path)))
    assert m["verdict"] == "PRESENT"
    assert len(m["pocp_commitment"]) == 64
    assert (tmp_path / "P1_01.verification.html").exists()
    assert (tmp_path / "P1_01.manifest.json").exists()
    # every governed seam is OFF / dry-run by default
    for tgt in ("sentry", "guardian", "curator", "zkba"):
        assert m["handoffs"][tgt]["enabled"] is False
        assert m["handoffs"][tgt]["action"] == "dry_run"
    # manifest on disk round-trips
    saved = json.loads((tmp_path / "P1_01.manifest.json").read_text())
    assert saved["pocp_commitment"] == m["pocp_commitment"]


def test_process_session_handoff_goes_live_when_enabled(tmp_path):
    p = _write_coupled(tmp_path / "P1_02.npz")
    cfg = WitnessConfig(out_dir=str(tmp_path), sentry_anchor_enabled=True)
    m = process_session(p, cfg)
    assert m["handoffs"]["sentry"]["enabled"] is True
    assert m["handoffs"]["sentry"]["action"] == "live_pending_governance"
    assert m["handoffs"]["guardian"]["enabled"] is False  # others still dry-run


def _write_uncoupled(path, n=500, rate_hz=100.0, seed=1, player="P1"):
    rng = np.random.default_rng(seed)
    ts = np.arange(n) * (1000.0 / rate_hz)
    sx = 128 + 60.0 * np.sin(2 * np.pi * 0.8 * ts / 1000.0)   # active aim...
    sy = 128 + 8.0 * np.sin(2 * np.pi * 0.3 * ts / 1000.0)
    yaw = rng.normal(0, 0.4, n)                                # ...but render motion is pure noise
    pitch = rng.normal(0, 0.4, n)
    fire = np.zeros(n); fire[n // 2:] = 200.0
    np.savez(path, in_ts=ts, in_sx=sx, in_sy=sy, in_fire=fire,
             mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch, label="human", player=player)
    return str(path)


# ---- BCC sealed-lane harvest wiring ----

def test_should_harvest_gate():
    assert _should_harvest_l9("PRESENT", True) is True
    assert _should_harvest_l9("PRESENT", False) is False        # unreliable -> no
    assert _should_harvest_l9("DECOUPLED", True) is False        # not causally present -> no
    assert _should_harvest_l9("INSUFFICIENT_AIM", True) is False


def test_bcc_dormant_by_default(tmp_path):
    p = _write_coupled(tmp_path / "P1_01.npz")
    m = process_session(p, WitnessConfig(out_dir=str(tmp_path)))   # bcc_enabled False
    assert m["bcc"]["harvested"] is False and m["bcc"]["reason"] == "bcc_disabled"


def test_bcc_harvests_present_session(tmp_path):
    lane = str(tmp_path / "bcc")
    p = _write_coupled(tmp_path / "P1_01.npz")
    m = process_session(p, WitnessConfig(out_dir=str(tmp_path), bcc_enabled=True, bcc_out_dir=lane))
    assert m["verdict"] == "PRESENT"
    assert m["bcc"]["harvested"] is True and m["bcc"]["sub_lane"] == "A"
    st = BCCStore(lane)
    assert st.status()["chain_length"] == 1 and st.verify() is True
    rec = st.load()[0]
    assert rec["payload"]["pocp_commitment"] == m["pocp_commitment"]   # provenance link to L9 verification


def test_bcc_skips_non_present_session(tmp_path):
    lane = str(tmp_path / "bcc")
    p = _write_uncoupled(tmp_path / "P1_01.npz")
    m = process_session(p, WitnessConfig(out_dir=str(tmp_path), bcc_enabled=True, bcc_out_dir=lane))
    assert m["verdict"] != "PRESENT"
    assert m["bcc"]["harvested"] is False                    # causal-presence gate rejected it
    assert BCCStore(lane).status()["chain_length"] == 0      # nothing entered the lane
