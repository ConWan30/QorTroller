"""
Phase 148 — VAPI MCP server tests.

Covers the /status, /resources, /resource/{id} and /tool endpoints of the MCP
sub-app plus each _fetch_resource_content() handler, including the fail-soft
branches that return an "error" key instead of raising.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.mcp_server import (
    _MCP_VERSION,
    _RESOURCE_CATALOG,
    _fetch_resource_content,
    create_mcp_app,
)


def _cfg():
    cfg = MagicMock()
    cfg.l4_anomaly_threshold = 7.009
    cfg.l4_continuity_threshold = 5.367
    cfg.live_feature_dim = 13
    cfg.calibration_feature_dim = 12
    cfg.agent_dry_run_mode = True
    return cfg


def _store():
    store = MagicMock()
    store.get_agent_calibration_health.return_value = [
        {"agent_id": 1, "agent_name": "calibration", "result": "PASS"},
        {"agent_id": 1, "agent_name": "calibration", "result": "FAIL"},  # older row
        {"agent_id": 2, "agent_name": "supervisor", "result": "FAIL"},
    ]
    store.get_separation_ratio_status.return_value = {
        "pooled_ratio": 1.4, "tournament_blocker": False
    }
    store.get_activation_state.return_value = {"activation_committed": True}
    store.compute_pmi.return_value = 2
    store.get_readiness_scores.return_value = [
        {"protocol_health_score": 0.93, "recommendation": "READY"}
    ]
    store.get_gamer_readiness_status.return_value = {
        "device_id": "D1", "readiness_score": 0.8, "recommendation": "NOMINAL"
    }
    return store


def _client():
    return TestClient(create_mcp_app(_cfg(), _store()))


class TestMcpEndpoints(unittest.TestCase):

    def test_status(self):
        body = _client().get("/status").json()
        self.assertEqual(body["mcp_version"], _MCP_VERSION)
        self.assertTrue(body["mcp_server_enabled"])
        self.assertEqual(body["resource_count"], len(_RESOURCE_CATALOG))

    def test_resources_catalog(self):
        body = _client().get("/resources").json()
        self.assertEqual(body["total"], len(_RESOURCE_CATALOG))
        self.assertIn("vapi://calibration/health", [r["id"] for r in body["resources"]])

    def test_every_catalog_resource_is_fetchable(self):
        client = _client()
        for meta in _RESOURCE_CATALOG:
            resp = client.get(f"/resource/{meta['id']}")
            self.assertEqual(resp.status_code, 200, meta["id"])
            body = resp.json()
            self.assertEqual(body["id"], meta["id"])
            self.assertEqual(body["name"], meta["name"])
            self.assertIsInstance(body["content"], dict)

    def test_single_slash_resource_id_is_normalised(self):
        resp = _client().get("/resource/vapi:/calibration/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "vapi://calibration/health")

    def test_unknown_resource_404(self):
        resp = _client().get("/resource/vapi://nope/nothing")
        self.assertEqual(resp.status_code, 404)

    def test_content_error_becomes_500(self):
        with patch(
            "vapi_bridge.mcp_server._fetch_resource_content",
            side_effect=RuntimeError("store exploded"),
        ):
            resp = _client().get("/resource/vapi://calibration/health")
        self.assertEqual(resp.status_code, 500)
        self.assertIn("store exploded", resp.json()["detail"])

    def test_tool_call_returns_calibration_health(self):
        body = _client().post("/tool", json={"tool": "get_calibration_health"}).json()
        self.assertEqual(body["agent_count"], 16)
        self.assertEqual(body["healthy_count"], 1)
        self.assertEqual(body["degraded_count"], 1)

    def test_tool_call_error_is_returned_not_raised(self):
        with patch(
            "vapi_bridge.mcp_server._fetch_resource_content",
            side_effect=RuntimeError("nope"),
        ):
            resp = _client().post("/tool", json={"tool": "get_calibration_health"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"error": "nope"})

    def test_unknown_tool_400(self):
        resp = _client().post("/tool", json={"tool": "rm_rf"})
        self.assertEqual(resp.status_code, 400)


class TestFetchResourceContent(unittest.TestCase):

    def test_calibration_health_dedupes_to_latest_per_agent(self):
        content = _fetch_resource_content("vapi://calibration/health", _cfg(), _store())
        self.assertEqual(content["healthy_count"], 1)
        self.assertEqual(content["failed_agents"], ["supervisor"])
        self.assertEqual(len(content["latest_tests"]), 2)

    def test_fleet_health_delegates_to_supervisor(self):
        with patch("vapi_bridge.agent_supervisor.AgentSupervisor") as sup:
            sup.return_value.check_fleet_health.return_value = {"fleet_health": "HEALTHY"}
            content = _fetch_resource_content("vapi://agents/fleet", _cfg(), _store())
        self.assertEqual(content, {"fleet_health": "HEALTHY"})

    def test_fleet_health_error_is_unknown(self):
        with patch(
            "vapi_bridge.agent_supervisor.AgentSupervisor",
            side_effect=RuntimeError("no supervisor"),
        ):
            content = _fetch_resource_content("vapi://agents/fleet", _cfg(), _store())
        self.assertEqual(content["fleet_health"], "UNKNOWN")

    def test_separation_ratio_non_dict_status(self):
        store = _store()
        store.get_separation_ratio_status.return_value = None
        content = _fetch_resource_content("vapi://separation/ratio", _cfg(), store)
        self.assertEqual(content, {"error": "no status"})

    def test_separation_ratio_error_blocks_tournament(self):
        store = _store()
        store.get_separation_ratio_status.side_effect = RuntimeError("db gone")
        content = _fetch_resource_content("vapi://separation/ratio", _cfg(), store)
        self.assertTrue(content["tournament_blocker"])

    def test_l4_thresholds_flag_dim_mismatch_as_stale(self):
        content = _fetch_resource_content("vapi://l4/thresholds", _cfg(), _store())
        self.assertTrue(content["stale"])
        self.assertEqual(content["anomaly_threshold"], 7.009)

        cfg = _cfg()
        cfg.live_feature_dim = 12
        self.assertFalse(
            _fetch_resource_content("vapi://l4/thresholds", cfg, _store())["stale"]
        )

    def test_protocol_maturity(self):
        content = _fetch_resource_content("vapi://protocol/maturity", _cfg(), _store())
        self.assertEqual(content["pmi"], 2)
        self.assertTrue(content["activation_committed"])
        self.assertTrue(content["dry_run_active"])

    def test_protocol_maturity_error_defaults(self):
        store = _store()
        store.get_activation_state.side_effect = RuntimeError("db gone")
        content = _fetch_resource_content("vapi://protocol/maturity", _cfg(), store)
        self.assertEqual(content["pmi"], 0)
        self.assertFalse(content["activation_committed"])

    def test_tournament_readiness_threshold(self):
        content = _fetch_resource_content("vapi://tournament/readiness", _cfg(), _store())
        self.assertTrue(content["ready"])

        store = _store()
        store.get_readiness_scores.return_value = [
            {"protocol_health_score": 0.5, "recommendation": "HOLD"}
        ]
        self.assertFalse(
            _fetch_resource_content("vapi://tournament/readiness", _cfg(), store)["ready"]
        )

    def test_tournament_readiness_without_reports(self):
        store = _store()
        store.get_readiness_scores.return_value = []
        content = _fetch_resource_content("vapi://tournament/readiness", _cfg(), store)
        self.assertEqual(content, {"score": 0.0, "conditions_met": "", "ready": False})

    def test_gamer_readiness_falls_back_to_nominal_defaults(self):
        store = _store()
        store.get_gamer_readiness_status.return_value = None
        content = _fetch_resource_content("vapi://gamer/readiness", _cfg(), store)
        self.assertEqual(content["recommendation"], "NOMINAL")
        self.assertEqual(content["readiness_score"], 1.0)

    def test_unknown_resource_id_returns_error(self):
        content = _fetch_resource_content("vapi://unknown", _cfg(), _store())
        self.assertIn("no content handler", content["error"])


if __name__ == "__main__":
    unittest.main()
