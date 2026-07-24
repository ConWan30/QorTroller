"""ATTEST-FEEDS (F-RIG27-1/2) tests - grok attestfeeds-r02 bars, fakes only (no rig, no HTTP).

T-AF-1 stall detect + honest-degraded feed + forced re-open; T-AF-2 healthy counter path; T-AF-3
counter-never-started fallback; T-AF-4 fabrication pin (empty frames never take the len(frames)
path - a real disconnect is never masked); T-AF-5 recovery resets; T-AF-6 restart cap; T-AF-7 the
live activity window through the SEALED classify_activity oracle (idle=MENU, active=ACTIVE,
cold=UNKNOWN, disconnect decays); T-AF-8 the CLI fetcher mapping (omit-when-cold, no
gameplay_context on the live path); T-AF-9 source pins (drain-loop force-reopen check + call sites).
"""
import re
from collections import deque
from pathlib import Path
from types import SimpleNamespace

from bridge.vapi_bridge.dualshock_integration import DualShockTransport
from l9_presence.poep_gameplay_session import ActivityState, classify_activity

_SRC = (Path(__file__).resolve().parents[2] / "bridge" / "vapi_bridge" / "dualshock_integration.py"
        ).read_text(encoding="utf-8")
_CLI = (Path(__file__).resolve().parents[2] / "scripts" / "poep_session_identity_attach.py"
        ).read_text(encoding="utf-8")


class _FakeMonitor:
    def __init__(self):
        self.samples = []

    def update_sample(self, n, window_s, **kw):
        self.samples.append(int(n))


class _AliveThread:
    def is_alive(self):
        return True


def _ns(*, total=0, last=0, thread=_AliveThread(), monitor=None, restarts=0):
    return SimpleNamespace(
        _pcc_monitor=monitor if monitor is not None else _FakeMonitor(),
        _hid_counter_thread=thread,
        _hid_report_total=total,
        _last_hid_report_total=last,
        _hid_counter_silent_iters=0,
        _hid_counter_force_reopen=False,
        _hid_counter_restarts=restarts,
        _rate_counter_stalled=False,
        _rate_source="hid_interface3",
        _live_activity_window=deque(maxlen=20),
        _interval=1.0,
        _PCC_STALL_ITERS=DualShockTransport._PCC_STALL_ITERS,
        _HID_RESTART_CAP=DualShockTransport._HID_RESTART_CAP,
    )


def _feed(ns, frames, trigger=False):
    DualShockTransport._pcc_rate_feed(ns, frames, {"trigger_active": trigger})


FRAMES = [object()] * 120   # a main-reader batch (~120/s cadence)


# ── T-AF-1: alive-but-silent -> stall confirmed at N=3, len(frames) fed, re-open forced ────────
def test_taf1_silent_counter_stalls_and_heals():
    ns = _ns()                                   # frozen total: delta always 0
    _feed(ns, FRAMES); _feed(ns, FRAMES)
    assert ns._rate_counter_stalled is False     # below N - not yet confirmed
    assert ns._pcc_monitor.samples == [0, 0]     # honest zeros pre-confirmation
    _feed(ns, FRAMES)                            # third consecutive silent iter
    assert ns._rate_counter_stalled is True
    assert ns._pcc_monitor.samples[-1] == len(FRAMES)   # honest-degraded main-reader cadence
    assert ns._rate_source == "main_reader_frames"
    assert ns._hid_counter_force_reopen is True  # the drain loop will re-open


# ── T-AF-2: healthy counter -> delta fed, source hid, no stall ────────────────────────────────
def test_taf2_healthy_counter_feeds_delta():
    ns = _ns(total=1000, last=0)
    _feed(ns, FRAMES)
    assert ns._pcc_monitor.samples == [1000]
    assert ns._rate_source == "hid_interface3"
    assert ns._rate_counter_stalled is False and ns._hid_counter_force_reopen is False


# ── T-AF-3: counter never started -> documented len(frames) fallback ──────────────────────────
def test_taf3_no_counter_thread_falls_back():
    ns = _ns(thread=None)
    _feed(ns, FRAMES)
    assert ns._pcc_monitor.samples == [len(FRAMES)]
    assert ns._rate_source == "main_reader_frames"


# ── T-AF-4 (fabrication pin): empty frames NEVER take the len(frames) path ────────────────────
def test_taf4_empty_frames_never_masks_disconnect():
    ns = _ns()                                   # silent counter AND no frames
    for _ in range(6):
        _feed(ns, [])
    assert ns._rate_counter_stalled is False     # stall requires frames flowing
    assert ns._hid_counter_force_reopen is False
    assert all(s == 0 for s in ns._pcc_monitor.samples)   # honest zeros -> DISCONNECTED path


# ── T-AF-5: recovery resets the stall state ───────────────────────────────────────────────────
def test_taf5_recovery_resets():
    ns = _ns()
    for _ in range(3):
        _feed(ns, FRAMES)
    assert ns._rate_counter_stalled is True
    ns._hid_report_total = 900                   # the re-opened counter delivers again
    _feed(ns, FRAMES)
    assert ns._rate_counter_stalled is False
    assert ns._hid_counter_silent_iters == 0
    assert ns._pcc_monitor.samples[-1] == 900
    assert ns._rate_source == "hid_interface3"


# ── T-AF-6: forced re-opens are capped ────────────────────────────────────────────────────────
def test_taf6_restart_cap():
    ns = _ns(restarts=DualShockTransport._HID_RESTART_CAP)
    for _ in range(4):
        _feed(ns, FRAMES)
    assert ns._rate_counter_stalled is True      # stall still visible (honesty)
    assert ns._hid_counter_force_reopen is False # but no further thrashing


# ── T-AF-7: the live window through the SEALED classifier oracle ──────────────────────────────
def _fraction_payload(window):
    n = len(window)
    return ({"trigger_active_fraction": sum(window) / n} if n else {})


def test_taf7_live_window_sealed_grammar():
    ns = _ns(total=10, last=0)
    # active play: trigger bits set
    for _ in range(5):
        _feed(ns, FRAMES, trigger=True)
    assert classify_activity(_fraction_payload(ns._live_activity_window)) is ActivityState.ACTIVE_GAMEPLAY
    # idle pad: zeros fill the window -> MENU (never ACTIVE)
    ns2 = _ns(total=10, last=0)
    for _ in range(20):
        _feed(ns2, FRAMES, trigger=False)
    assert classify_activity(_fraction_payload(ns2._live_activity_window)) is ActivityState.MENU
    # cold window: absent field -> UNKNOWN (fail-closed)
    assert classify_activity({}) is ActivityState.UNKNOWN
    # disconnect decays a hot window: no-frames path appends 0 (source-pinned in T-AF-9);
    # simulate the decay and confirm the fraction falls
    hot = ns._live_activity_window
    before = sum(hot) / len(hot)
    for _ in range(20):
        hot.append(0)
    assert sum(hot) / len(hot) == 0.0 < before


# ── T-AF-8: the CLI fetcher mapping (fake HTTP; no gameplay_context on the live path) ─────────
def _fetch_with(monkeypatch, payload):
    import io, json, urllib.request
    import scripts.poep_session_identity_attach as cli

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _Resp(json.dumps(payload).encode()))
    return cli._make_bridge_health_fetcher("http://x", "k", "activity")()


def test_taf8_cli_fetcher_live_mapping(monkeypatch):
    # warm window -> the live fraction, and ONLY that key (stale ctx can never shadow live truth)
    out = _fetch_with(monkeypatch, {"live_activity_window_n": 20,
                                    "live_trigger_active_fraction": 0.4,
                                    "latest_gameplay_context": None})
    assert out == {"trigger_active_fraction": 0.4}
    assert "gameplay_context" not in out
    # cold window -> {} -> UNKNOWN (fail-closed)
    assert _fetch_with(monkeypatch, {"live_activity_window_n": 2,
                                     "live_trigger_active_fraction": 1.0}) == {}
    # absent fields (old bridge) -> {} -> UNKNOWN
    assert _fetch_with(monkeypatch, {"latest_gameplay_context": "ACTIVE_GAMEPLAY"}) == {}


# ── grok r03 belt: the SEALED PCC gate still refuses the honest-degraded state ────────────────
def test_sealed_pcc_gate_line_held():
    from l9_presence.poep_gameplay_live import pcc_allows_challenge
    assert pcc_allows_challenge({"capture_state": "DEGRADED", "host_state": "EXCLUSIVE_USB"}) is False
    assert pcc_allows_challenge({"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}) is True


# ── T-AF-9: source pins ───────────────────────────────────────────────────────────────────────
def test_taf9_source_pins():
    # the drain loop checks the force-reopen flag INSIDE its read loop
    assert "_hid_counter_force_reopen" in _SRC.split("def _drain_loop")[1].split("def ")[0]
    # the session loop calls the extracted feed (the inline delta block is gone)
    assert "_pcc_rate_feed(frames, _spc_kwargs)" in _SRC
    assert len(re.findall(r"update_sample\(_delta", _SRC)) == 1   # only inside the helper
    # the no-frames path decays the live window
    nf = _SRC.split("no frames, sleeping")[1][:600]
    assert "_live_activity_window.append(0)" in nf
    # the CLI live path never forwards gameplay_context (comment mentions allowed; CODE must not)
    act = _CLI.split('if kind == "activity"')[-1].split('return {"capture_state"')[0]
    code_only = "\n".join(l for l in act.splitlines() if not l.strip().startswith("#"))
    assert "n = data.get" in code_only            # we sliced the real branch body
    assert "gameplay_context" not in code_only
