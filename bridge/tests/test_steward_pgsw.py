"""A2A-STEWARD-EVOLVE B6 — PGSW tests. Pins the presence window (live session OR fresh SYNCHRONIZED PoSP),
the KAS-hygiene rail (authorship is NOT presence), the read-only disposition gate (HIGH parks to backlog
when the window is closed), and the fail-closed unknown-severity handling.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_pgsw import (
    SCHEMA,
    gate_draft,
    max_active_severity,
    presence_window,
    presence_window_from_store,
)

_SEC = 1_000_000_000


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# --- window ----------------------------------------------------------------------------------------

def test_live_session_opens_window():
    w = presence_window(live_session_active=True, now_ns=1000 * _SEC)
    assert w["window_open"] is True and w["presence_source"] == "live_session"


def test_fresh_synchronized_posp_opens_window():
    now = 1000 * _SEC
    w = presence_window(posp_verdict="SYNCHRONIZED", posp_ts_ns=now - 60 * _SEC, now_ns=now, tau_s=3600)
    assert w["window_open"] is True and w["presence_source"] == "posp_synchronized"


def test_stale_synchronized_posp_closes_window():
    now = 100000 * _SEC
    w = presence_window(posp_verdict="SYNCHRONIZED", posp_ts_ns=now - 7200 * _SEC, now_ns=now, tau_s=3600)
    assert w["window_open"] is False and "stale" in w["reason"]


def test_future_dated_posp_closes_window():
    now = 1000 * _SEC
    w = presence_window(posp_verdict="SYNCHRONIZED", posp_ts_ns=now + 60 * _SEC, now_ns=now)
    assert w["window_open"] is False   # future timestamp is not fresh presence


def test_authorship_verdict_is_not_presence():
    # THE KAS-hygiene rail: an AUTHORED verdict must NOT open the window
    now = 1000 * _SEC
    w = presence_window(posp_verdict="AUTHORED_SESSION", posp_ts_ns=now, now_ns=now)
    assert w["window_open"] is False and "KAS hygiene" in w["reason"]


def test_no_signal_closes_window():
    w = presence_window(now_ns=1000 * _SEC)
    assert w["window_open"] is False


def test_live_session_overrides_authorship_verdict():
    # grok round-10: live session opens even if an AUTHORED verdict is also present (live wins, cleanly)
    now = 1000 * _SEC
    w = presence_window(posp_verdict="AUTHORED_SESSION", posp_ts_ns=now, now_ns=now,
                        live_session_active=True)
    assert w["window_open"] is True and w["presence_source"] == "live_session"


def test_whitespace_synchronized_stays_closed():
    # exact allowlist (no strip on verdict) -> fail-closed, ' SYNCHRONIZED ' does not open
    now = 1000 * _SEC
    w = presence_window(posp_verdict=" SYNCHRONIZED ", posp_ts_ns=now, now_ns=now)
    assert w["window_open"] is False


def test_partial_surfaces_posp_closes_window():
    now = 1000 * _SEC
    w = presence_window(posp_verdict="PARTIAL_SURFACES", posp_ts_ns=now, now_ns=now)
    assert w["window_open"] is False


# --- gate ------------------------------------------------------------------------------------------

def _open_w():
    return presence_window(live_session_active=True, now_ns=1000 * _SEC)


def _closed_w():
    return presence_window(now_ns=1000 * _SEC)


def test_open_window_activates_high_severity():
    g = gate_draft(_open_w(), "HIGH")
    assert g["disposition"] == "ACTIVE"


def test_closed_window_backlogs_high_activates_low():
    assert gate_draft(_closed_w(), "HIGH")["disposition"] == "BACKLOG"
    assert gate_draft(_closed_w(), "MED")["disposition"] == "BACKLOG"
    assert gate_draft(_closed_w(), "LOW")["disposition"] == "ACTIVE"


def test_unknown_severity_fails_closed_to_high():
    g = gate_draft(_closed_w(), "WHATEVER")
    assert g["severity"] == "HIGH" and g["disposition"] == "BACKLOG"


def test_max_active_severity():
    assert max_active_severity(_open_w()) == "HIGH"
    assert max_active_severity(_closed_w()) == "LOW"


def test_gate_is_read_only_disposition_not_suppression():
    g = gate_draft(_closed_w(), "HIGH")
    assert "never deletes or suppresses" in g["note"] and g["schema"] == SCHEMA


# --- adapter ---------------------------------------------------------------------------------------

def test_adapter_disabled_by_default():
    assert presence_window_from_store(store=None, cfg=_Cfg(pgsw_enabled=False))["enabled"] is False


def test_adapter_enabled_is_honest_stub():
    r = presence_window_from_store(store=None, cfg=_Cfg(pgsw_enabled=True))
    assert r["enabled"] is True and "STUB" in r["adapter_scope"]
    assert "refuses to fabricate presence" in r["note"]
