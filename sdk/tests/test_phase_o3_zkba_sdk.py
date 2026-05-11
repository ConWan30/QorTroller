"""Phase O3-ZKBA-TRACK1 C4 — VAPIZKBA SDK tests (Stream Z6 + Z7).

T-ZKBA-14: VAPIZKBA.status fail-open when bridge unreachable
T-ZKBA-15: VAPIZKBA.get_artifact fail-open when bridge unreachable
T-ZKBA-16: VAPIZKBA.history fail-open when bridge unreachable

All three tests verify the SDK never raises on transport failure — instead
returning a Result dataclass with .error populated. This matches the
VAPIDraftReview / VAPIFleetReadinessRoot fail-open pattern.

Bridge HTTP endpoints (/operator/zkba-*) do not yet ship at C4; these
tests intentionally point at an unreachable port to exercise the
fail-open path.
"""
import os
import sys

import pytest


# Add sdk/ to sys.path
_HERE = os.path.dirname(__file__)
_SDK_DIR = os.path.normpath(os.path.join(_HERE, ".."))
if _SDK_DIR not in sys.path:
    sys.path.insert(0, _SDK_DIR)

from vapi_sdk import (  # noqa: E402
    VAPIZKBA,
    ZKBAStatusResult,
    ZKBAArtifactResult,
    ZKBAHistoryResult,
    SDK_VERSION,
)

# Deliberately-unreachable URL for fail-open verification
# (port 1 is reserved + cannot be bound, guaranteeing connection refused)
_UNREACHABLE_URL = "http://127.0.0.1:1"


# ---------------------------------------------------------------------------
# T-ZKBA-14: status fail-open
# ---------------------------------------------------------------------------

def test_t_zkba_14_sdk_vapi_zkba_status_fail_open():
    """VAPIZKBA.status() returns ZKBAStatusResult with .error populated
    when the bridge is unreachable. NEVER raises."""
    client = VAPIZKBA(_UNREACHABLE_URL, api_key="test_key")
    result = client.status()
    assert isinstance(result, ZKBAStatusResult)
    assert result.error is not None, "error field should be populated on connection failure"
    assert result.error != ""
    # Default values present
    assert result.total_artifacts == 0
    assert result.anchored_count == 0
    assert result.frozen_v1_position == 10
    assert result.domain_tag == "VAPI-ZKBA-ARTIFACT-v1"
    # No exception raised — we got here


# ---------------------------------------------------------------------------
# T-ZKBA-15: get_artifact fail-open
# ---------------------------------------------------------------------------

def test_t_zkba_15_sdk_vapi_zkba_get_artifact_fail_open():
    """VAPIZKBA.get_artifact(commitment_hex) returns ZKBAArtifactResult
    with .error populated when bridge is unreachable. NEVER raises."""
    client = VAPIZKBA(_UNREACHABLE_URL, api_key="test_key")
    result = client.get_artifact("0" * 64)
    assert isinstance(result, ZKBAArtifactResult)
    assert result.error is not None
    assert result.commitment_hex == "0" * 64
    assert result.found is False
    assert result.anchor_tx_hash is None


# ---------------------------------------------------------------------------
# T-ZKBA-16: history fail-open
# ---------------------------------------------------------------------------

def test_t_zkba_16_sdk_vapi_zkba_history_fail_open():
    """VAPIZKBA.history(limit=N) returns ZKBAHistoryResult with .error
    populated when bridge is unreachable. NEVER raises."""
    client = VAPIZKBA(_UNREACHABLE_URL, api_key="test_key")
    result = client.history(limit=10)
    assert isinstance(result, ZKBAHistoryResult)
    assert result.error is not None
    assert result.limit == 10
    assert result.row_count == 0
    assert result.rows == []


# ---------------------------------------------------------------------------
# Sanity: SDK_VERSION bumped to C4 marker
# ---------------------------------------------------------------------------

def test_sdk_version_bumped_for_zkba_c4():
    """SDK_VERSION reflects ZKBA C4 ship (Phase O3-ZKBA-TRACK1 C4)."""
    assert "zkba" in SDK_VERSION.lower(), f"SDK_VERSION={SDK_VERSION!r} does not mention zkba"
    assert SDK_VERSION.startswith("3.1.0"), f"SDK_VERSION={SDK_VERSION!r} should start with 3.1.0"


# ===========================================================================
# Phase O3-ZKBA-TRACK1 (post-C5) — VAPIZKBA live-bridge round-trip tests.
#
# C4 shipped the SDK with wire-locked endpoints not-yet-implemented; the
# fail-open tests above (T-ZKBA-14/15/16) verified the SDK never raises
# against an unreachable URL. The bridge endpoints
# (/operator/zkba-status, /operator/zkba-artifact/<hex>, /operator/zkba-history)
# now ship; these tests prove the SDK round-trip works end-to-end against
# a live uvicorn-hosted operator_api app.
#
#   T-ZKBA-EP-SDK-1: VAPIZKBA.status() over live bridge with seeded rows
#                    returns populated dataclass; .error is None
#   T-ZKBA-EP-SDK-2: VAPIZKBA.get_artifact(hex) returns found=True + full
#                    row over live bridge
#   T-ZKBA-EP-SDK-3: VAPIZKBA.history() returns DESC ts_ns rows over live
#                    bridge
# ===========================================================================

import dataclasses
import threading
import time
from pathlib import Path

# Add bridge/ to sys.path so we can construct the operator_app directly
_REPO = Path(__file__).resolve().parents[2]
_BRIDGE_DIR = _REPO / "bridge"
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


@pytest.fixture(scope="module")
def live_bridge():
    """Start operator_api in a uvicorn background thread on a free port.

    Yields (base_url, store, api_key). DB is wiped on teardown.
    """
    import socket
    import urllib.request
    import uvicorn

    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    # Pick a free port
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    db_path = str(_BRIDGE_DIR / f".tmp_o3_zkba_sdk_{port}.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db_path,
        operator_api_key="k_zkba_sdk",
    )
    store = Store(db_path)
    app = create_operator_app(cfg, store)

    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
    ))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    # Wait for server readiness
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/operator/zkba-status",
                headers={"x-api-key": "k_zkba_sdk"},
            )
            with urllib.request.urlopen(req, timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        raise RuntimeError("live_bridge fixture failed to start")

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, store, "k_zkba_sdk"

    server.should_exit = True
    th.join(timeout=5.0)
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


def _seed_live(store, n: int) -> list[str]:
    hexes: list[str] = []
    base_ts_ns = 1_700_000_000_000_000_000
    for i in range(n):
        hex_i = f"{(i + 100):064x}"  # offset to avoid hex collision w/ other tests
        store.insert_zkba_artifact(
            zkba_class=(i % 3) + 1,
            proof_weight=3,
            commitment_hex=hex_i,
            preimage_json=f'{{"i":{i}}}',
            ts_ns=base_ts_ns + i,
            manifest_uri=f"file://manifest_live_{i}.json",
            compiler_output_hash_hex=f"out_{i:060x}",
        )
        hexes.append(hex_i)
    return hexes


def test_t_zkba_ep_sdk_1_status_round_trip(live_bridge):
    base_url, store, api_key = live_bridge
    _seed_live(store, n=3)

    client = VAPIZKBA(base_url, api_key=api_key)
    result = client.status()

    assert isinstance(result, ZKBAStatusResult)
    assert result.error is None, f"unexpected error: {result.error!r}"
    assert result.total_artifacts >= 3
    assert result.anchored_count == 0
    assert result.track1_invariant_holds is True
    assert result.frozen_v1_position == 10
    assert result.domain_tag == "VAPI-ZKBA-ARTIFACT-v1"
    # latest_* fields populated
    assert len(result.latest_commitment_hex) == 64
    assert result.latest_proof_weight == 3


def test_t_zkba_ep_sdk_2_get_artifact_round_trip(live_bridge):
    base_url, store, api_key = live_bridge
    hexes = _seed_live(store, n=2)
    target = hexes[0]

    client = VAPIZKBA(base_url, api_key=api_key)
    result = client.get_artifact(target)

    assert isinstance(result, ZKBAArtifactResult)
    assert result.error is None, f"unexpected error: {result.error!r}"
    assert result.found is True
    assert result.commitment_hex == target
    assert result.proof_weight == 3
    assert result.anchor_tx_hash is None  # Track 1 invariant
    assert result.manifest_uri.startswith("file://manifest_live_")


def test_t_zkba_ep_sdk_3_history_round_trip(live_bridge):
    base_url, store, api_key = live_bridge
    _seed_live(store, n=2)

    client = VAPIZKBA(base_url, api_key=api_key)
    result = client.history(limit=50)

    assert isinstance(result, ZKBAHistoryResult)
    assert result.error is None, f"unexpected error: {result.error!r}"
    assert result.limit == 50
    assert result.row_count >= 2
    assert len(result.rows) >= 2
    # DESC by ts_ns — first row newest
    if len(result.rows) >= 2:
        assert int(result.rows[0]["ts_ns"]) >= int(result.rows[1]["ts_ns"])
