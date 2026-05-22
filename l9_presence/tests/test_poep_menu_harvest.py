"""Tests for the sub-lane B menu-lull harvester (Option A handoff). No hardware."""
from l9_presence.bcc import BCCConfig, BCCHarvester
from l9_presence.poep_menu_harvest import (
    HandoffMachine, LullDetector, MenuHarvestConfig, MenuHarvester, should_harvest_b,
)


def test_lull_detector_needs_sustained_quiet():
    d = LullDetector(activity_threshold=8.0, sustain_samples=3)
    assert d.update(50.0) is False                 # active
    assert d.update(2.0) is False                  # quiet 1
    assert d.update(2.0) is False                  # quiet 2
    assert d.update(2.0) is True                   # quiet 3 -> lull
    assert d.update(40.0) is False                 # activity breaks it


def test_should_harvest_b_gate():
    assert should_harvest_b(290, sham_reaction=False) is True
    assert should_harvest_b(290, sham_reaction=True) is False    # sham noisy -> reject
    assert should_harvest_b(40, sham_reaction=False) is False     # out of band
    assert should_harvest_b(None, sham_reaction=False) is False   # no reaction


def _ok():
    return True


def test_handoff_all_success_reacquires():
    m = HandoffMachine(_ok, _ok, lambda: {"reflex_latency_ms": 290, "sham_reaction": False},
                       _ok, _ok)
    r = m.run_one()
    assert r["ok"] is True and r["reacquired"] is True
    assert r["sample"]["reflex_latency_ms"] == 290


def test_handoff_acquire_failure_restores_passive():
    calls = {"reacquire": 0}

    def reacq():
        calls["reacquire"] += 1
        return True
    m = HandoffMachine(_ok, lambda: False, lambda: None, _ok, reacq)  # acquire fails
    r = m.run_one()
    assert r["ok"] is False and r["stage"] == "acquire_active"
    assert calls["reacquire"] == 1 and r["reacquired"] is True        # device returned to reader


def test_handoff_fire_exception_returns_device():
    calls = {"reacquire": 0}

    def reacq():
        calls["reacquire"] += 1
        return True

    def boom():
        raise RuntimeError("capture blew up")
    m = HandoffMachine(_ok, _ok, boom, _ok, reacq)
    r = m.run_one()
    assert r["ok"] is False and "error" in r["error"]
    assert calls["reacquire"] == 1                                    # still handed back


def test_handoff_reacquire_failure_is_not_ok():
    m = HandoffMachine(_ok, _ok, lambda: {"reflex_latency_ms": 290, "sham_reaction": False},
                       _ok, lambda: False)                            # reacquire fails
    r = m.run_one()
    assert r["ok"] is False and r["reacquired"] is False              # lost the reader -> not ok


def test_menu_harvester_records_when_enabled(tmp_path):
    bcc = BCCHarvester(BCCConfig(enabled=True, sublane_b_enabled=True, out_dir=str(tmp_path / "b")))
    h = MenuHarvester(bcc, MenuHarvestConfig(enabled=True))
    assert h.offer_sample(True, 290, False)["harvested"] is True
    assert h.offer_sample(True, 40, False)["harvested"] is False      # out of band -> skip
    assert h.offer_sample(False, 290, False)["harvested"] is False    # no lull -> skip
    assert bcc.store.status()["sub_lane_b"] == 1


def test_menu_harvester_dormant_by_default(tmp_path):
    bcc = BCCHarvester(BCCConfig(out_dir=str(tmp_path / "b")))        # bcc disabled
    h = MenuHarvester(bcc, MenuHarvestConfig())                       # menu disabled
    assert h.offer_sample(True, 290, False)["harvested"] is False
