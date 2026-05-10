"""Phase O1-FRR-SDK tests.

Verifies VAPIFleetReadinessRoot client wraps GET /operator/fleet-readiness-root
+ GET /operator/operator-initiative-advancement-log correctly. Uses an
in-process FastAPI + uvicorn server in a background thread so the SDK's
stdlib urllib calls hit the real bridge endpoint surface.

  T-O1-FRR-SDK-1: status() returns FleetReadinessRootResult with per_agent
                   rollup (empty fleet still returns deterministic shape)
  T-O1-FRR-SDK-2: status() with wrong api_key surfaces error and never raises
  T-O1-FRR-SDK-3: advancement_log() returns AdvancementLogResult; limit param
                   pass-through; row_count and rows shape correct
  T-O1-FRR-SDK-4: per_agent_row() returns AgentReadinessRow when agent
                   present; None when absent
  T-O1-FRR-SDK-5: network error (unreachable base_url) populates .error
                   without raising
"""
from __future__ import annotations

import dataclasses
import sys
import threading
import time
from pathlib import Path

import pytest

# Add bridge/ + sdk/ to sys.path so direct imports work from this test.
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "bridge", ROOT / "sdk"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(scope="module")
def live_app():
    """Start the operator_app via FastAPI in a background thread on a
    free port. Yields (base_url, store, api_key)."""
    import socket
    import uvicorn

    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    db_path = str(ROOT / "bridge" / f".tmp_o1_frr_sdk_{port}.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db_path,
        operator_api_key="k_o1_frr_sdk",
    )
    store = Store(db_path)
    app = create_operator_app(cfg, store)

    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
    ))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    # Wait for server to come up.
    deadline = time.time() + 5.0
    import urllib.request
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/operator/fleet-readiness-root",
                headers={"x-api-key": "k_o1_frr_sdk"},
            )
            with urllib.request.urlopen(req, timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        raise RuntimeError("test server failed to start")

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, store, "k_o1_frr_sdk"

    server.should_exit = True
    th.join(timeout=5.0)
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


# T-O1-FRR-SDK-1: status() shape + per_agent rollup
def test_T_O1_FRR_SDK_1_status_shape(live_app):
    from vapi_sdk import VAPIFleetReadinessRoot, FleetReadinessRootResult

    base_url, store, api_key = live_app
    client = VAPIFleetReadinessRoot(base_url, api_key=api_key)
    result = client.status()

    assert isinstance(result, FleetReadinessRootResult)
    assert result.error is None
    # frr_hex is 64 hex chars (SHA-256) — deterministic for empty fleet via
    # the canonical pre-image.
    assert isinstance(result.frr_hex, str)
    assert len(result.frr_hex) == 64
    assert isinstance(result.per_agent, list)
    assert result.domain_tag == "VAPI-FRR-v1"
    # fleet_size matches the three Operator Initiative agents structurally
    assert result.fleet_size == 3


# T-O1-FRR-SDK-2: wrong api_key returns error, never raises
def test_T_O1_FRR_SDK_2_wrong_api_key_error(live_app):
    from vapi_sdk import VAPIFleetReadinessRoot

    base_url, _, _ = live_app
    client = VAPIFleetReadinessRoot(base_url, api_key="WRONG_KEY")
    result = client.status()

    assert result.error is not None
    # Bridge returns 403 on wrong key (per existing _check_read_key behavior)
    assert "403" in str(result.error) or "Forbidden" in str(result.error)
    # Other fields remain at defaults
    assert result.frr_hex == ""
    assert result.fleet_size == 0


# T-O1-FRR-SDK-3: advancement_log shape + limit pass-through
def test_T_O1_FRR_SDK_3_advancement_log_shape(live_app):
    from vapi_sdk import VAPIFleetReadinessRoot, AdvancementLogResult

    base_url, _, api_key = live_app
    client = VAPIFleetReadinessRoot(base_url, api_key=api_key)
    result = client.advancement_log(limit=25)

    assert isinstance(result, AdvancementLogResult)
    assert result.error is None
    assert result.limit == 25
    assert isinstance(result.rows, list)
    assert result.row_count == len(result.rows)


# T-O1-FRR-SDK-4: per_agent_row returns row for known agent / None for unknown
def test_T_O1_FRR_SDK_4_per_agent_row_lookup(live_app):
    from vapi_sdk import VAPIFleetReadinessRoot, AgentReadinessRow

    base_url, _, api_key = live_app
    client = VAPIFleetReadinessRoot(base_url, api_key=api_key)

    # The three Operator Initiative agents are always present in fleet
    # (per FRR evaluation contract — per_agent is sorted by agent_id).
    sentry = client.per_agent_row("anchor_sentry")
    assert sentry is not None
    assert isinstance(sentry, AgentReadinessRow)
    assert sentry.agent_id == "anchor_sentry"
    assert isinstance(sentry.o2_blockers, list)
    assert isinstance(sentry.o3_blockers, list)

    # Unknown agent returns None (forward-compat — never raises)
    bogus = client.per_agent_row("nonexistent_agent")
    assert bogus is None


# T-O1-FRR-SDK-5: unreachable base_url populates .error without raising
def test_T_O1_FRR_SDK_5_network_error_fail_open():
    from vapi_sdk import VAPIFleetReadinessRoot

    # Port 1 is reserved/unreachable; instant connection refused.
    client = VAPIFleetReadinessRoot("http://127.0.0.1:1", api_key="any")
    s = client.status()
    h = client.advancement_log(limit=10)

    assert s.error is not None
    assert s.frr_hex == ""
    assert h.error is not None
    assert h.rows == []
    # per_agent_row also fails open
    assert client.per_agent_row("anchor_sentry") is None
