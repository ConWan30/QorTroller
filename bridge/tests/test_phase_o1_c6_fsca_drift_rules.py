"""Phase O1 C6 — FSCA wiring of drift findings.

Tests the two new CONTRADICTION_RULES that surface
operator_agent_drift_log entries via FleetSignalCoherenceAgent:

  T-O1-C6-1: BUNDLE_HASH_DRIFT_DETECTED fires when drift in last 1h
  T-O1-C6-2: BUNDLE_HASH_DRIFT_DETECTED does NOT fire when drift > 1h old
  T-O1-C6-3: SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED fires (severity=CRITICAL)
  T-O1-C6-4: Both rules quiet when drift_log empty (no false positives)

Uses direct SQL insert to control detected_at — the helper
insert_operator_agent_drift() always stamps now() so we can't simulate the
"older than 1h" case via the public API.
"""

import asyncio
import logging
import sqlite3
import sys
import time
import types as _types
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy optional deps before bridge import
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _make_cfg():
    cfg = MagicMock()
    cfg.fleet_coherence_enabled = True
    cfg.dry_run = True
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    return cfg


def _seed_drift_row(db_path: str, *, drift_type: str, detected_at: float,
                    agent_id: str = SENTRY_ID) -> None:
    """Insert one drift_log row at a specific detected_at (bypasses helper)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO operator_agent_drift_log "
        "(agent_id, drift_type, expected_value, actual_value, "
        " bundle_path, evidence_json, sweep_id, "
        " detected_at, detected_at_bucket) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            agent_id, drift_type,
            "0x" + "a" * 64,            # expected_value
            "0x" + "b" * 64,            # actual_value
            "bridge/vapi_bridge/cedar_bundles/test.json",
            '{"reason":"test"}',
            "sweep_test_c6",
            float(detected_at),
            int(detected_at),
        ),
    )
    conn.commit()
    conn.close()


def _run_fsca(store) -> list:
    """Run FSCA _check_contradictions and return the list of fired entries."""
    from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent
    cfg = _make_cfg()
    bus = MagicMock()
    logger = logging.getLogger("test_phase_o1_c6")
    agent = FleetSignalCoherenceAgent(store=store, config=cfg, bus=bus, logger=logger)
    return asyncio.get_event_loop().run_until_complete(agent._check_contradictions())


# ---------------------------------------------------------------------------
# T-O1-C6-1: BUNDLE_HASH_DRIFT_DETECTED fires on recent drift
# ---------------------------------------------------------------------------

def test_t_o1_c6_1_bundle_drift_fires_within_1h(tmp_path):
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "c6_1.db")
    store = Store(db_path)

    # Drift 5 minutes ago — well within 1h window
    _seed_drift_row(db_path, drift_type="BUNDLE_HASH_DRIFT",
                    detected_at=time.time() - 300)

    results = _run_fsca(store)
    fired = [r for r in results if r.get("rule_name") == "BUNDLE_HASH_DRIFT_DETECTED"]
    assert len(fired) == 1, (
        f"Expected BUNDLE_HASH_DRIFT_DETECTED to fire once, got {len(fired)} "
        f"(other rules fired: {[r.get('rule_name') for r in results]})"
    )
    # Severity carried through
    assert fired[0]["severity"] == "HIGH"
    assert "CedarDriftSweeper" in fired[0]["agents_involved"]


# ---------------------------------------------------------------------------
# T-O1-C6-2: BUNDLE_HASH_DRIFT_DETECTED quiet when drift older than 1h
# ---------------------------------------------------------------------------

def test_t_o1_c6_2_bundle_drift_silent_after_1h(tmp_path):
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "c6_2.db")
    store = Store(db_path)

    # Drift 90 minutes ago — outside 1h window
    _seed_drift_row(db_path, drift_type="BUNDLE_HASH_DRIFT",
                    detected_at=time.time() - 5400)

    results = _run_fsca(store)
    fired = [r for r in results if r.get("rule_name") == "BUNDLE_HASH_DRIFT_DETECTED"]
    assert len(fired) == 0, (
        f"BUNDLE_HASH_DRIFT_DETECTED must NOT fire on drift older than 1h, "
        f"but {len(fired)} rule(s) fired"
    )


# ---------------------------------------------------------------------------
# T-O1-C6-3: SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED fires (CRITICAL severity)
# ---------------------------------------------------------------------------

def test_t_o1_c6_3_scope_drift_fires_critical(tmp_path):
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "c6_3.db")
    store = Store(db_path)

    _seed_drift_row(db_path, drift_type="SCOPE_HASH_GOVERNANCE_DRIFT",
                    detected_at=time.time() - 60)

    results = _run_fsca(store)
    fired = [r for r in results
             if r.get("rule_name") == "SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED"]
    assert len(fired) == 1, (
        f"Expected SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED to fire once, got {len(fired)}"
    )
    assert fired[0]["severity"] == "CRITICAL", (
        f"Scope drift must be CRITICAL severity, got {fired[0]['severity']}"
    )


# ---------------------------------------------------------------------------
# T-O1-C6-4: Both rules quiet when drift_log is empty
# ---------------------------------------------------------------------------

def test_t_o1_c6_4_both_rules_silent_on_empty_log(tmp_path):
    from vapi_bridge.store import Store
    db_path = str(tmp_path / "c6_4.db")
    store = Store(db_path)
    # No drift seeded

    results = _run_fsca(store)
    fired_names = {r.get("rule_name") for r in results}
    assert "BUNDLE_HASH_DRIFT_DETECTED" not in fired_names
    assert "SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED" not in fired_names
