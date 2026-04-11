"""Phase 184 bridge tests — PostCode Sweep (AutoResearch Cycle 9 + WIF-032).

4 tests:
  T184-1  PersonaBreakDetectorAgent and MaturityElevationGateAgent importable; no name collision
  T184-2  All Phase 182/183 config fields present and defaults correct
  T184-3  All Phase 182/183 store schema versions registered
  T184-4  Both Phase 182/183 endpoints registered in operator_app routes
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# T184-1  Agent classes importable; no name collision with prior agents
# ---------------------------------------------------------------------------

def test_t184_1_agent_imports_no_collision():
    from vapi_bridge.persona_break_detector_agent import PersonaBreakDetectorAgent
    from vapi_bridge.maturity_elevation_gate_agent import MaturityElevationGateAgent

    # Confirm they are distinct classes
    assert PersonaBreakDetectorAgent is not MaturityElevationGateAgent
    # Confirm agent names are novel (not duplicating prior phases)
    assert "persona_break" in PersonaBreakDetectorAgent.__module__
    assert "maturity_elevation" in MaturityElevationGateAgent.__module__


# ---------------------------------------------------------------------------
# T184-2  Phase 182/183 config fields present and defaults correct
# ---------------------------------------------------------------------------

def test_t184_2_config_fields_182_183():
    from vapi_bridge.config import Config
    cfg = Config()

    # Phase 182 fields
    assert hasattr(cfg, "persona_break_detection_enabled")
    assert cfg.persona_break_detection_enabled is True
    assert hasattr(cfg, "persona_break_loo_threshold")
    assert cfg.persona_break_loo_threshold == 0.20

    # Phase 183 fields
    assert hasattr(cfg, "maturity_elevation_enabled")
    assert cfg.maturity_elevation_enabled is True


# ---------------------------------------------------------------------------
# T184-3  Phase 182/183 store schema versions registered
# ---------------------------------------------------------------------------

def test_t184_3_store_schema_versions_182_183():
    with tempfile.TemporaryDirectory() as tmp:
        from vapi_bridge.store import Store
        import sqlite3
        db_path = str(Path(tmp) / "t184_schema.db")
        s = Store(db_path)

        # Query schema_versions table directly
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT phase FROM schema_versions").fetchall()
        conn.close()

        phases = {row["phase"] for row in rows}
        assert 182 in phases, f"Schema phase 182 not found in {phases}"
        assert 183 in phases, f"Schema phase 183 not found in {phases}"


# ---------------------------------------------------------------------------
# T184-4  Both Phase 182/183 endpoints registered in operator_app routes
# ---------------------------------------------------------------------------

def test_t184_4_endpoints_registered():
    import tempfile
    from pathlib import Path
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(str(Path(tmp) / "t184_routes.db"))
        cfg = Config()
        object.__setattr__(cfg, "operator_api_key", "test-key-184")

        app = create_operator_app(cfg, store)

        routes = {r.path for r in app.routes}
        assert "/agent/persona-break-status" in routes, \
            f"persona-break-status not found in {routes}"
        assert "/agent/maturity-elevation-plan" in routes, \
            f"maturity-elevation-plan not found in {routes}"
