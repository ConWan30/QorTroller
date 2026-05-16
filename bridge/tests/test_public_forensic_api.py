"""Phase O5-PUBLIC-VIEWER — backend tests for /public/* sub-app.

T-PUB-FORENSIC-1   /public/health returns 200 + ok payload
T-PUB-FORENSIC-2   /public/algorithms returns 16 FROZEN-v1 tag entries
T-PUB-FORENSIC-3   /public/session/{hash} returns found:False for unknown commit
T-PUB-FORENSIC-4   /public/session/{hash} returns composite for known VPM row
T-PUB-FORENSIC-5   /public/vpm/{hash} mirrors get_vpm_artifact_status shape
T-PUB-FORENSIC-6   /public/vpm/{hash}/preimage returns preimage_json
T-PUB-FORENSIC-7   /public/gic/{sid} returns chain status
T-PUB-FORENSIC-8   /public/record/{device}/{counter} returns 228-byte binary
T-PUB-FORENSIC-9   /public/record/{device}/{counter} returns 404 for missing
T-PUB-FORENSIC-10  /public/agent-roots returns 3 agents with frozen merkles
T-PUB-FORENSIC-11  /public/protocol-state returns snapshot keys
T-PUB-FORENSIC-12  Rate-limit kicks in after RPM threshold
T-PUB-FORENSIC-13  All endpoints accept NO x-api-key / api_key (public)
T-PUB-FORENSIC-14  VAME headers stamped on JSON responses
T-PUB-FORENSIC-15  /public/gic/{sid}/links returns chain links with codes
T-PUB-FORENSIC-16  GIC links carry prev_gic_hex chain so browser can replay
T-PUB-FORENSIC-17  GIC links endpoint unknown session returns empty list
T-PUB-FORENSIC-18  /public/vhp/{tokenId} returns credential row when found
T-PUB-FORENSIC-19  /public/vhp/{tokenId} returns found:False for missing tokenId
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_app(td: str, *, rpm: int = 60):
    from vapi_bridge.store import Store
    from vapi_bridge.public_forensic_api import create_public_forensic_app
    cfg = MagicMock()
    cfg.public_forensic_rate_limit_per_min = rpm
    cfg.grind_session_id = "test_grind_v1"
    cfg.operator_agent_sentry_id = "0x" + "a" * 64
    cfg.operator_agent_guardian_id = "0x" + "b" * 64
    cfg.operator_agent_curator_id = "0x" + "c" * 64
    store = Store(db_path=os.path.join(td, "t.db"))
    app = create_public_forensic_app(cfg=cfg, store=store)
    return TestClient(app), store


# ----- T-1 -----

def test_t_pub_forensic_1_health():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["scope"] == "public"


# ----- T-2 -----

def test_t_pub_forensic_2_algorithms_manifest():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/algorithms")
        assert r.status_code == 200
        body = r.json()
        assert body["schema"] == "vapi-public-algorithm-manifest-v1"
        assert body["count"] >= 14  # 14 FROZEN-v1 tags + 2 NO-tag entries
        # spot-check a few canonical tags
        tag_names = [t["tag"] for t in body["tags"]]
        assert "VAPI-GIC-GENESIS-v1" in tag_names
        assert "VAPI-MLGA-SESSION-v1" in tag_names
        assert "VAPI-VAME-v1" in tag_names
        assert "VAPI-ZKBA-ARTIFACT-v1" in tag_names


# ----- T-3 -----

def test_t_pub_forensic_3_session_unknown_returns_not_found():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/session/" + "f" * 64)
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False


# ----- T-4 -----

def test_t_pub_forensic_4_session_with_vpm_row():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        # Seed a VPM artifact row to look up
        commit = "ab" * 32
        store.insert_vpm_artifact(
            commitment_hex=commit,
            vpm_id="MLGA-SESSION-v1",
            zkba_class=2, proof_weight=3,
            visual_state="live", capture_mode="live",
            integrity_label_hash_hex="11" * 32,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex="22" * 32,
            manifest_uri="/tmp/x.html",
            compiler_output_hash_hex=commit,
            preimage_json="{}",
            ts_ns=int(time.time_ns()),
        )
        r = client.get(f"/session/{commit}")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["vpm"]["commitment_hex"] == commit
        assert body["vpm"]["vpm_id"] == "MLGA-SESSION-v1"


# ----- T-5 -----

def test_t_pub_forensic_5_vpm_endpoint():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        commit = "cd" * 32
        store.insert_vpm_artifact(
            commitment_hex=commit,
            vpm_id="GIC-LEDGER-BETA-v1",
            zkba_class=2, proof_weight=3,
            visual_state="live", capture_mode="live",
            integrity_label_hash_hex="33" * 32,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex="44" * 32,
            manifest_uri=None,
            compiler_output_hash_hex=commit,
            preimage_json='{"vpm_id":"GIC-LEDGER-BETA-v1"}',
            ts_ns=int(time.time_ns()),
        )
        r = client.get(f"/vpm/{commit}")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["vpm"]["vpm_id"] == "GIC-LEDGER-BETA-v1"


# ----- T-6 -----

def test_t_pub_forensic_6_vpm_preimage_endpoint():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        commit = "ee" * 32
        store.insert_vpm_artifact(
            commitment_hex=commit, vpm_id="HONESTY-BOARD-v1",
            zkba_class=2, proof_weight=3, visual_state="live",
            capture_mode="live", integrity_label_hash_hex="55" * 32,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex="66" * 32, manifest_uri=None,
            compiler_output_hash_hex=commit,
            preimage_json='{"snapshot":{"pv_ci":117}}',
            ts_ns=int(time.time_ns()),
        )
        r = client.get(f"/vpm/{commit}/preimage")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["vpm_id"] == "HONESTY-BOARD-v1"
        assert "snapshot" in body["preimage_json"]


# ----- T-7 -----

def test_t_pub_forensic_7_gic_chain_endpoint():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/gic/test_grind_v1")
        assert r.status_code == 200
        body = r.json()
        assert body["grind_session_id"] == "test_grind_v1"
        assert "chain_length" in body
        assert "latest_gic_hash" in body
        assert "discipline" in body


# ----- T-8 -----

def test_t_pub_forensic_8_record_binary_returns_228b():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        # Seed a fake 228-byte record into the records table
        import sqlite3 as _sql
        raw228 = bytes(range(228))
        con = _sql.connect(store._db_path, timeout=2.0)
        try:
            con.execute(
                "INSERT INTO records (device_id, counter, raw_data, "
                "                     timestamp_ms, inference, action_code, "
                "                     confidence, battery_pct, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("dev_test", 42, raw228, 1, 0, 0, 0, 50, time.time()),
            )
            con.commit()
        finally:
            con.close()
        r = client.get("/record/dev_test/42")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "application/octet-stream"
        assert r.headers.get("x-vapi-wire-length") == "228"
        assert len(r.content) == 228


# ----- T-9 -----

def test_t_pub_forensic_9_record_missing_returns_404():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/record/nonexistent/9999")
        assert r.status_code == 404


# ----- T-10 -----

def test_t_pub_forensic_10_agent_roots():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/agent-roots")
        assert r.status_code == 200
        body = r.json()
        assert body["schema"] == "vapi-public-agent-roots-v1"
        assert len(body["agents"]) == 3
        names = [a["canonical"] for a in body["agents"]]
        assert "anchor_sentry" in names
        assert "guardian" in names
        assert "curator" in names
        assert body["chain"]["chain_id"] == 4690


# ----- T-11 -----

def test_t_pub_forensic_11_protocol_state():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/protocol-state")
        assert r.status_code == 200
        body = r.json()
        assert body["schema"] == "vapi-public-protocol-state-v1"
        for key in [
            "pv_ci_invariants_count", "total_vpm_artifacts",
            "total_mlga_sessions", "total_grind_chain_links",
            "kill_switch_paused", "separation_ratios",
        ]:
            assert key in body


# ----- T-12 -----

def test_t_pub_forensic_12_rate_limit():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td, rpm=3)  # tight limit for fast test
        # First 3 OK
        for _ in range(3):
            r = client.get("/algorithms")
            assert r.status_code == 200
        # 4th should 429
        r = client.get("/algorithms")
        assert r.status_code == 429
        assert "rate limit" in r.json()["detail"].lower()
        assert r.headers.get("retry-after") == "60"


# ----- T-13 -----

def test_t_pub_forensic_13_no_auth_required():
    """Every endpoint accepts requests with NO x-api-key + NO api_key query."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        # Hit endpoints with zero auth-related headers/params; all should
        # work (not return 401/403)
        for path in ["/health", "/algorithms", "/agent-roots",
                     "/protocol-state", "/gic/anything", "/session/" + "0" * 64,
                     "/vpm/" + "0" * 64, "/vpm/" + "0" * 64 + "/preimage",
                     "/mlga/" + "0" * 64]:
            r = client.get(path)
            assert r.status_code in (200, 404), (
                f"path {path} returned {r.status_code} (expected 200 or 404, "
                f"NEVER 401/403)"
            )
            assert r.status_code not in (401, 403)


# ----- T-15 -----

def test_t_pub_forensic_15_gic_links_endpoint_shape():
    """Phase O5-PUBLIC-VIEWER Stage 2 — GIC chain links endpoint must
    return the link-shape the browser-side verifyGicChainLink expects."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        # Seed a chain link
        import sqlite3 as _sql
        con = _sql.connect(store._db_path, timeout=2.0)
        try:
            con.execute(
                "INSERT INTO ruling_validation_log (ruling_id, device_id, "
                "  llm_verdict, fallback_verdict, llm_confidence, "
                "  fallback_confidence, divergence, grind_chain_hash, "
                "  gic_ts_ns, pcc_host_state, grind_session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "d1", "FLAG", "FLAG", 0.1, 0.05, 0,
                 "ab" * 32, int(time.time_ns()),
                 "EXCLUSIVE_USB", "test_grind", time.time()),
            )
            con.commit()
        finally:
            con.close()
        r = client.get("/gic/test_grind/links")
        assert r.status_code == 200
        body = r.json()
        assert body["schema"] == "vapi-public-gic-chain-links-v1"
        assert body["chain_length"] >= 1
        assert isinstance(body["links"], list)
        link = body["links"][0]
        assert "verdict_code" in link
        assert "host_state_code" in link
        assert "prev_gic_hex" in link
        assert link["verdict_code"] == 0x10  # FLAG
        assert link["host_state_code"] == 0x01  # EXCLUSIVE_USB


# ----- T-16 -----

def test_t_pub_forensic_16_gic_links_prev_chain_consistency():
    """prev_gic_hex of link[N+1] == grind_chain_hash of link[N]."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        import sqlite3 as _sql
        con = _sql.connect(store._db_path, timeout=2.0)
        try:
            for i in range(3):
                con.execute(
                    "INSERT INTO ruling_validation_log (ruling_id, device_id, "
                    "  llm_verdict, fallback_verdict, llm_confidence, "
                    "  fallback_confidence, divergence, grind_chain_hash, "
                    "  gic_ts_ns, pcc_host_state, grind_session_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (i + 1, "d1", "FLAG", "FLAG", 0.1, 0.05, 0,
                     f"{i:02x}" * 32, (i + 1) * 1000,
                     "EXCLUSIVE_USB", "test_grind_chain", time.time() + i),
                )
            con.commit()
        finally:
            con.close()
        r = client.get("/gic/test_grind_chain/links")
        body = r.json()
        links = body["links"]
        assert len(links) == 3
        # link[0].prev_gic_hex == "" (caller will compute genesis)
        assert links[0]["prev_gic_hex"] == ""
        # link[1].prev_gic_hex == link[0].grind_chain_hash
        assert links[1]["prev_gic_hex"] == links[0]["grind_chain_hash"]
        # link[2].prev_gic_hex == link[1].grind_chain_hash
        assert links[2]["prev_gic_hex"] == links[1]["grind_chain_hash"]


# ----- T-17 -----

def test_t_pub_forensic_17_gic_links_unknown_session_returns_empty():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/gic/totally_nonexistent_session_xyz/links")
        assert r.status_code == 200
        body = r.json()
        assert body["chain_length"] == 0
        assert body["links"] == []


# ----- T-18 -----

def test_t_pub_forensic_18_vhp_credential_found():
    """Phase O5-PUBLIC-VIEWER Stage 4 — VHP credential endpoint."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, store = _make_app(td)
        store.insert_vhp_issuance(
            device_id="test_dev_001",
            token_id=2,
            tx_hash="0xdeadbeef",
            expires_at=time.time() + 86400 * 30,  # 30 days out
            cert_level=1,
            consecutive_clean=100,
        )
        r = client.get("/vhp/2")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is True
        assert body["schema"] == "vapi-public-vhp-credential-v1"
        assert body["vhp"]["token_id"] == 2
        assert body["vhp"]["cert_level"] == 1
        assert body["vhp"]["consecutive_clean"] == 100
        assert body["vhp"]["is_valid_local"] is True
        assert body["vhp"]["seconds_until_expiry"] > 0
        assert body["chain"]["chain_id"] == 4690


# ----- T-19 -----

def test_t_pub_forensic_19_vhp_credential_missing():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/vhp/9999999")
        assert r.status_code == 200
        body = r.json()
        assert body["found"] is False
        assert body["token_id"] == 9999999


# ----- T-14 -----

def test_t_pub_forensic_14_vame_headers_stamped():
    """Every JSON response carries the X-VAME-* sidecar header set."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        client, _ = _make_app(td)
        r = client.get("/algorithms")
        assert r.status_code == 200
        # VAME spec: 5 sidecar headers must be present (when middleware
        # succeeds; on failure middleware logs + passes through unstamped,
        # so this test asserts the happy path).
        assert "x-vame-version" in {k.lower() for k in r.headers.keys()}
        assert "x-vame-commitment" in {k.lower() for k in r.headers.keys()}
        assert "x-vame-endpoint" in {k.lower() for k in r.headers.keys()}
