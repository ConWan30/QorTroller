"""SYNC-GO preflight tests (grok syncgo-r02 B3) — fakes only, no HID / no rig.

T1 cold window_n<3 -> not ready
T2 window_n>=3 frac=0 -> not ready (MENU)
T3 window_n>=3 frac>0 + PCC ok -> ready
T4 timeout path -> False / exit 3 semantics (no fabricated GO)
T5 amplitude CLI clamps to <=80
T6 dry attach still IDENTITY_ONLY; sealed refused_activity still holds
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

from l9_presence.poep_gameplay_live import (
    FireResult,
    ImuWindow,
    challenge_live,
    pcc_allows_challenge,
    start_live_session,
    verify_live_seal,
)
from l9_presence.poep_gameplay_session import ChallengeKind, LOW_AMPLITUDE_FORCE_MAX
from l9_presence.poep_session_identity_run import run_session_identity_attach
from l9_presence.controller_presence import IDENTITY_ONLY

_CLI_PATH = Path(__file__).resolve().parents[2] / "scripts" / "poep_session_identity_attach.py"
_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
_IDENT = {
    "owner_did": "did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692",
    "ioid_token_id": 498,
    "tba_address": "0xFCee237789FA91a141781aFB574ADAbcA2660e7b",
    "registration_tx": "0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f",
    "vmdr_pubkey_hash": "0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802",
    "controller_nft": "0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55",
    "controller_nft_token_id": 1,
}


def _load_cli():
    spec = importlib.util.spec_from_file_location("poep_session_identity_attach_syncgo", _CLI_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


cli = _load_cli()


def _pcc_ok_health(**extra):
    base = {
        "capture_state": "NOMINAL",
        "host_state": "EXCLUSIVE_USB",
        "live_activity_window_n": 20,
        "live_trigger_active_fraction": 0.4,
    }
    base.update(extra)
    return base


# ── T1: cold window ───────────────────────────────────────────────────────────
def test_t1_cold_window_not_ready():
    ready, st = cli.eval_preflight_ready(_pcc_ok_health(live_activity_window_n=2,
                                                        live_trigger_active_fraction=1.0))
    assert ready is False
    assert st["window_ok"] is False


# ── T2: MENU (frac=0 with filled window) ──────────────────────────────────────
def test_t2_menu_frac_zero_not_ready():
    ready, st = cli.eval_preflight_ready(_pcc_ok_health(live_trigger_active_fraction=0.0))
    assert ready is False
    assert st["window_ok"] is True
    assert st["frac_ok"] is False


# ── T3: ACTIVE + PCC ok ───────────────────────────────────────────────────────
def test_t3_active_pcc_ready():
    ready, st = cli.eval_preflight_ready(_pcc_ok_health())
    assert ready is True
    assert st["pcc_ok"] is True
    # sealed helper agreement (bar: PCC set equal to pcc_allows_challenge)
    assert pcc_allows_challenge({"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}) is True
    assert pcc_allows_challenge({"capture_state": "NOMINAL", "host_state": "UNKNOWN"}) is True
    assert pcc_allows_challenge({"capture_state": "DEGRADED", "host_state": "EXCLUSIVE_USB"}) is False
    ready_unk, _ = cli.eval_preflight_ready(_pcc_ok_health(host_state="UNKNOWN"))
    assert ready_unk is True
    ready_deg, _ = cli.eval_preflight_ready(_pcc_ok_health(capture_state="DEGRADED"))
    assert ready_deg is False


# ── T4: timeout path — no fabricated GO ───────────────────────────────────────
def test_t4_timeout_returns_false_no_ready():
    calls = {"n": 0}
    t = {"now": 0.0}

    def health():
        calls["n"] += 1
        return _pcc_ok_health(live_trigger_active_fraction=0.0)  # forever MENU

    def now():
        return t["now"]

    def sleep(dt):
        t["now"] += float(dt)

    buf = io.StringIO()
    ok = cli.wait_for_active_gameplay(
        health_fetcher=health, wait_s=2.0, poll_s=0.5,
        now_fn=now, sleep_fn=sleep, stderr=buf,
    )
    assert ok is False
    assert calls["n"] >= 1
    assert "PREFLIGHT TIMEOUT" in buf.getvalue()
    assert cli.EXIT_PREFLIGHT_TIMEOUT == 3


def test_t4_wait_zero_skips_preflight():
    # wait_s<=0 -> immediate True (legacy cold path); never calls fetcher
    ok = cli.wait_for_active_gameplay(
        health_fetcher=lambda: (_ for _ in ()).throw(AssertionError("should not fetch")),
        wait_s=0,
    )
    assert ok is True


def test_t4_ready_on_second_poll():
    states = [
        _pcc_ok_health(live_activity_window_n=1),
        _pcc_ok_health(),
    ]
    t = {"now": 0.0}

    def health():
        return states.pop(0) if states else _pcc_ok_health()

    def now():
        return t["now"]

    def sleep(dt):
        t["now"] += float(dt)

    buf = io.StringIO()
    ok = cli.wait_for_active_gameplay(
        health_fetcher=health, wait_s=5.0, poll_s=1.0,
        now_fn=now, sleep_fn=sleep, stderr=buf,
    )
    assert ok is True
    assert "PREFLIGHT READY" in buf.getvalue()


# ── T5: amplitude clamp ───────────────────────────────────────────────────────
def test_t5_amplitude_cli_clamps():
    assert cli.clamp_cli_amplitude(60) == 60
    assert cli.clamp_cli_amplitude(80) == 80
    assert cli.clamp_cli_amplitude(255) == LOW_AMPLITUDE_FORCE_MAX
    assert cli.clamp_cli_amplitude(0) == 60
    assert cli.clamp_cli_amplitude(-5) == 60
    assert cli.clamp_cli_amplitude(1) == 1


def test_t5_amplitude_threaded_to_challenge_live():
    seen = []

    def fire(amplitude, nonce):
        seen.append(amplitude)
        return FireResult(fired=True, real_hardware=False, t_fire_ns=1_000, amplitude=amplitude)

    def imu(t_fire_ns):
        return ImuWindow(t_response_ns=int(t_fire_ns) + 250_000_000, latency_ms=250.0,
                         peak_lsb=3000.0, precursor_gap_ms=5.0)

    out = run_session_identity_attach(
        device_id=_DEV, player_label="P1", t_start_ns=1_000_000, process_nonce="pn",
        challenge_plan=[(ChallengeKind.GO, "n1")],
        fire_fn=fire, imu_capture_fn=imu,
        activity_fetcher=lambda: {"gameplay_context": "ACTIVE_GAMEPLAY"},
        pcc_sampler=lambda: {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"},
        ioid_identity=_IDENT, include_custody_seal=False, amplitude=80,
    )
    assert seen == [80]
    assert out["controller_presence"]["verdict"] == IDENTITY_ONLY


# ── T6: dry IDENTITY_ONLY + sealed refuse_activity ────────────────────────────
def test_t6_dry_attach_identity_only():
    def fire(amplitude, nonce):
        return FireResult(fired=True, real_hardware=False, t_fire_ns=1_000, amplitude=amplitude)

    def imu(t_fire_ns):
        return ImuWindow(t_response_ns=int(t_fire_ns) + 250_000_000, latency_ms=250.0,
                         peak_lsb=3000.0, precursor_gap_ms=5.0)

    out = run_session_identity_attach(
        device_id=_DEV, player_label="P1", t_start_ns=1_000_000, process_nonce="pn",
        challenge_plan=[(ChallengeKind.GO, "n1"), (ChallengeKind.GO, "n2")],
        fire_fn=fire, imu_capture_fn=imu,
        activity_fetcher=lambda: {"gameplay_context": "ACTIVE_GAMEPLAY"},
        pcc_sampler=lambda: {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"},
        ioid_identity=_IDENT, include_custody_seal=False, amplitude=60,
    )
    assert out["controller_presence"]["verdict"] == IDENTITY_ONLY
    assert out["presence_summary"]["presence_session_candidate_ok"] is False


def test_t6_sealed_refused_activity_still_holds():
    session, seal = start_live_session(
        device_id=_DEV, player_label="P1", t_start_ns=1, process_nonce="pn",
    )
    assert verify_live_seal(session, seal, "pn")
    # no activity sample -> UNKNOWN -> refused_activity (sealed; preflight must not bypass this)
    out = challenge_live(
        session, seal=seal, process_nonce="pn", nonce="n",
        kind=ChallengeKind.GO,
        fire_fn=lambda a, n: (_ for _ in ()).throw(AssertionError("must not fire")),
        imu_capture_fn=lambda t: None,
        pcc_sample={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"},
        amplitude=80,
    )
    assert out["issued"] is False
    assert out["refused"] == "refused_activity"


def test_t6_empty_health_not_ready():
    ready, st = cli.eval_preflight_ready({})
    assert ready is False
    assert st["pcc_ok"] is False
