"""Phase O2-GUARDIAN-TRIGGERS tests.

Verifies GuardianFscaTriggerSource produces correct fsca_finding triggers
from new rows of fleet_coherence_log.

  T-O2-GUARDIAN-TRIG-1: factory returns None when flag=False; instance when True
  T-O2-GUARDIAN-TRIG-2: first call seeds baseline (returns []); idle store
                         second call also returns []
  T-O2-GUARDIAN-TRIG-3: new rows -> triggers in id-ascending order
  T-O2-GUARDIAN-TRIG-4: severity mapping FSCA -> Guardian
                         (CRITICAL->critical, HIGH->error, MEDIUM->warn,
                          LOW->info, unknown->info)
  T-O2-GUARDIAN-TRIG-5: agents_involved JSON parsed to list
  T-O2-GUARDIAN-TRIG-6: malformed agents_involved doesn't crash; row still
                         emitted with agents_involved=[]
  T-O2-GUARDIAN-TRIG-7: missing fleet_coherence_log table doesn't crash
                         (use a fresh empty SQLite db without the migration)
"""
from __future__ import annotations

import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy chain deps so vapi_bridge imports cheaply in tests.
for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_guardian_fsca_trigger_enabled = True  # default ON in tests
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _insert_fsca_row(
    db_path: str,
    *,
    coherence_id: str,
    failure_mode: str = "CONTRADICTION",
    rule_name: str = "TEST_RULE",
    agents_involved: object = ("agent_a", "agent_b"),
    severity: str = "HIGH",
    explanation: str = "test explanation",
    resolution: str = "test resolution",
) -> int:
    """Insert a row directly into fleet_coherence_log; return rowid."""
    if isinstance(agents_involved, str):
        agents_json = agents_involved  # caller wants a raw string (e.g. malformed)
    else:
        agents_json = json.dumps(list(agents_involved))
    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        cur = conn.execute(
            "INSERT INTO fleet_coherence_log "
            "(coherence_id, failure_mode, rule_name, agents_involved, "
            " severity, explanation, resolution, evidence_json, "
            " phase_detected, ts_ns) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                coherence_id, failure_mode, rule_name, agents_json,
                severity, explanation, resolution, "[]", 193, 0,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


# T-O2-GUARDIAN-TRIG-1: factory opt-in
def test_T_O2_GUARDIAN_TRIG_1_factory_opt_in(tmp_path):
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
        make_guardian_fsca_trigger_source,
    )
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "fsca_trig_factory.db"))

    # Flag False -> None
    cfg_off = _make_cfg(operator_agent_guardian_fsca_trigger_enabled=False)
    assert make_guardian_fsca_trigger_source(cfg=cfg_off, store=store) is None

    # Flag True -> instance
    cfg_on = _make_cfg(operator_agent_guardian_fsca_trigger_enabled=True)
    src = make_guardian_fsca_trigger_source(cfg=cfg_on, store=store)
    assert isinstance(src, GuardianFscaTriggerSource)
    # Smoke: callable returns list
    assert isinstance(src(), list)


# T-O2-GUARDIAN-TRIG-2: first call seeds baseline; idle returns []
def test_T_O2_GUARDIAN_TRIG_2_baseline_seeding(tmp_path):
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
    )
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "fsca_trig_baseline.db"))
    # Pre-existing rows must NOT replay on first call.
    _insert_fsca_row(store._db_path, coherence_id="pre1")
    _insert_fsca_row(store._db_path, coherence_id="pre2")

    src = GuardianFscaTriggerSource(cfg=_make_cfg(), store=store)
    # First call: baseline (no commits-since concept)
    assert src() == []
    # Second call: no new rows -> []
    assert src() == []


# T-O2-GUARDIAN-TRIG-3: new rows -> triggers in id-ascending order
def test_T_O2_GUARDIAN_TRIG_3_id_ascending_order(tmp_path):
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
    )
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "fsca_trig_order.db"))
    src = GuardianFscaTriggerSource(cfg=_make_cfg(), store=store)
    src()  # seed baseline (empty store)

    _insert_fsca_row(store._db_path, coherence_id="c1", rule_name="R_ONE")
    _insert_fsca_row(store._db_path, coherence_id="c2", rule_name="R_TWO")
    _insert_fsca_row(store._db_path, coherence_id="c3", rule_name="R_THREE")

    triggers = src()
    assert len(triggers) == 3
    finding_ids = [t["payload"]["finding_id"] for t in triggers]
    assert finding_ids == ["c1", "c2", "c3"]
    assert all(t["kind"] == "fsca_finding" for t in triggers)

    # Next call: high-water mark advanced -> []
    assert src() == []


# T-O2-GUARDIAN-TRIG-4: severity mapping FSCA -> Guardian
def test_T_O2_GUARDIAN_TRIG_4_severity_mapping(tmp_path):
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
        _map_severity,
    )
    from vapi_bridge.store import Store

    # Pure-function check
    assert _map_severity("CRITICAL") == "critical"
    assert _map_severity("HIGH") == "error"
    assert _map_severity("MEDIUM") == "warn"
    assert _map_severity("LOW") == "info"
    assert _map_severity("WHATEVER") == "info"
    assert _map_severity("") == "info"
    assert _map_severity(None) == "info"
    # Whitespace + lowercase tolerated by the mapper
    assert _map_severity(" critical ") == "critical"

    # End-to-end via SQLite path
    store = Store(str(tmp_path / "fsca_trig_severity.db"))
    src = GuardianFscaTriggerSource(cfg=_make_cfg(), store=store)
    src()  # seed

    _insert_fsca_row(store._db_path, coherence_id="sev_crit", severity="CRITICAL")
    _insert_fsca_row(store._db_path, coherence_id="sev_high", severity="HIGH")
    _insert_fsca_row(store._db_path, coherence_id="sev_med", severity="MEDIUM")
    _insert_fsca_row(store._db_path, coherence_id="sev_low", severity="LOW")

    triggers = src()
    by_id = {t["payload"]["finding_id"]: t["payload"]["severity"] for t in triggers}
    assert by_id["sev_crit"] == "critical"
    assert by_id["sev_high"] == "error"
    assert by_id["sev_med"] == "warn"
    assert by_id["sev_low"] == "info"


# T-O2-GUARDIAN-TRIG-5: agents_involved JSON parsed to list
def test_T_O2_GUARDIAN_TRIG_5_agents_parsed(tmp_path):
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
    )
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "fsca_trig_agents.db"))
    src = GuardianFscaTriggerSource(cfg=_make_cfg(), store=store)
    src()  # seed

    _insert_fsca_row(
        store._db_path,
        coherence_id="agents_a",
        agents_involved=("anchor_sentry", "guardian", "curator"),
        rule_name="MY_RULE",
        explanation="Some detailed explanation that exceeds sixty characters easily here",
    )

    triggers = src()
    assert len(triggers) == 1
    t = triggers[0]
    assert t["kind"] == "fsca_finding"
    assert t["payload"]["finding_id"] == "agents_a"
    assert t["payload"]["agents_involved"] == [
        "anchor_sentry", "guardian", "curator",
    ]
    # subject should start with rule_name + em-dash separator
    assert t["payload"]["subject"].startswith("MY_RULE — ")
    # subject snippet capped at 60 chars after the separator
    snippet_part = t["payload"]["subject"].split(" — ", 1)[1]
    assert len(snippet_part) <= 60


# T-O2-GUARDIAN-TRIG-6: malformed agents_involved doesn't crash
def test_T_O2_GUARDIAN_TRIG_6_malformed_agents_does_not_crash(tmp_path):
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
    )
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "fsca_trig_malformed.db"))
    src = GuardianFscaTriggerSource(cfg=_make_cfg(), store=store)
    src()  # seed

    # Insert a malformed agents_involved (raw bad-json string)
    _insert_fsca_row(
        store._db_path,
        coherence_id="malformed_a",
        agents_involved="{this is not json",
    )
    # And a well-formed one after it (different id)
    _insert_fsca_row(
        store._db_path,
        coherence_id="wellformed_b",
        agents_involved=("g_one",),
    )

    triggers = src()
    # Both rows must emit triggers; malformed agents falls back to []
    finding_ids = [t["payload"]["finding_id"] for t in triggers]
    assert "malformed_a" in finding_ids
    assert "wellformed_b" in finding_ids

    bad = next(t for t in triggers if t["payload"]["finding_id"] == "malformed_a")
    good = next(t for t in triggers if t["payload"]["finding_id"] == "wellformed_b")
    assert bad["payload"]["agents_involved"] == []
    assert good["payload"]["agents_involved"] == ["g_one"]


# T-O2-GUARDIAN-TRIG-7: missing fleet_coherence_log table doesn't crash
def test_T_O2_GUARDIAN_TRIG_7_missing_table_does_not_crash(tmp_path):
    """If the FSCA table doesn't exist (pre-Phase-193 env or fresh empty
    db), the trigger source must return [] silently without raising."""
    from vapi_bridge.operator_agent_guardian_trigger_sources import (
        GuardianFscaTriggerSource,
    )

    # Build a STAB store-like object: only _db_path, pointing to a fresh
    # SQLite file that has NO fleet_coherence_log table. We bypass Store
    # which would auto-create the table via migrations.
    db_file = tmp_path / "no_table.db"
    # Touch the SQLite file (empty schema)
    conn = sqlite3.connect(str(db_file))
    conn.close()

    stub_store = types.SimpleNamespace(_db_path=str(db_file))
    src = GuardianFscaTriggerSource(cfg=_make_cfg(), store=stub_store)

    # First call: baseline. Must not raise; returns [].
    assert src() == []
    # Second call: still no table; still returns [].
    assert src() == []
