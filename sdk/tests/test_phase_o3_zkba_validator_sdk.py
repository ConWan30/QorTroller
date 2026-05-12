"""Phase O3-ZKBA-TRACK1 Lane B G4 follow-up — VAPIZKBAValidator SDK tests.

Wraps POST /operator/zkba-validate-manifest at
bridge/vapi_bridge/operator_api.py (commit 4f63c5d5).

Closes the C4-style architectural reach trio for the G4 validator:
  Python lib -> MCP tool -> bridge HTTP -> SDK

  T-ZKBA-VSDK-1  fail-open when bridge unreachable (.error populated;
                 never raises)
  T-ZKBA-VSDK-2  fail-open on wrong api_key (HTTPError 403 surfaces in
                 .error field)
  T-ZKBA-VSDK-3  live round-trip happy path (representative GIC manifest)
  T-ZKBA-VSDK-4  live round-trip malformed manifest returns valid=False
                 with errors populated (fail-open contract at validator
                 layer preserved end-to-end through SDK)
  T-ZKBA-VSDK-5  live round-trip 7-class parametrized coverage
  T-ZKBA-VSDK-6  SDK_VERSION reflects G4 validator ship marker
"""
from __future__ import annotations

import dataclasses
import os
import sys
import threading
import time
from pathlib import Path

import pytest

# Add bridge/ + sdk/ + scripts/ to sys.path
_REPO = Path(__file__).resolve().parents[2]
_BRIDGE = _REPO / "bridge"
_SDK = _REPO / "sdk"
_SCRIPTS = _REPO / "scripts"
for p in (_BRIDGE, _SDK, _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from vapi_sdk import (  # noqa: E402
    VAPIZKBAValidator,
    ZKBAValidateResult,
    SDK_VERSION,
)


# Deliberately-unreachable URL for fail-open verification
_UNREACHABLE_URL = "http://127.0.0.1:1"


# ---------------------------------------------------------------------------
# T-ZKBA-VSDK-1: fail-open when bridge unreachable
# ---------------------------------------------------------------------------
def test_t_zkba_vsdk_1_fail_open_unreachable():
    """VAPIZKBAValidator.validate() against unreachable bridge must NOT
    raise. Returns ZKBAValidateResult with .error populated."""
    client = VAPIZKBAValidator(_UNREACHABLE_URL, api_key="test_key")
    result = client.validate({"any": "manifest"})
    assert isinstance(result, ZKBAValidateResult)
    assert result.error is not None
    assert result.error != ""
    # Default fail-open shape
    assert result.valid is False
    assert result.errors == []
    assert result.zkba_class_name == ""
    assert result.proof_weight_name == ""


# ---------------------------------------------------------------------------
# Live bridge fixture (module-scoped — reused across round-trip tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_bridge():
    """Start operator_api on a free port in a uvicorn background thread."""
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

    db_path = str(_BRIDGE / f".tmp_o3_zkba_vsdk_{port}.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db_path,
        operator_api_key="k_zkba_vsdk",
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
                headers={"x-api-key": "k_zkba_vsdk"},
            )
            with urllib.request.urlopen(req, timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        raise RuntimeError("live_bridge fixture failed to start")

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, store, "k_zkba_vsdk"

    server.should_exit = True
    th.join(timeout=5.0)
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


def _gic_manifest():
    """Build a representative GIC manifest via the G4 helper."""
    from zkba_manifest_validator import build_representative_manifest  # type: ignore
    from vapi_bridge.zkba_artifact import ZKBAClass  # type: ignore
    return build_representative_manifest(zkba_class=ZKBAClass.GIC)


# ---------------------------------------------------------------------------
# T-ZKBA-VSDK-2: wrong api_key surfaces as 403 in .error
# ---------------------------------------------------------------------------
def test_t_zkba_vsdk_2_wrong_api_key_403(live_bridge):
    base_url, _store, _api_key = live_bridge
    client = VAPIZKBAValidator(base_url, api_key="wrong_key")
    result = client.validate(_gic_manifest())
    assert isinstance(result, ZKBAValidateResult)
    assert result.error is not None
    # Bridge returns 403 with detail "Invalid x-api-key header"
    assert "Invalid x-api-key" in result.error or "403" in result.error


# ---------------------------------------------------------------------------
# T-ZKBA-VSDK-3: live round-trip happy path
# ---------------------------------------------------------------------------
def test_t_zkba_vsdk_3_live_round_trip_happy_path(live_bridge):
    base_url, _store, api_key = live_bridge
    client = VAPIZKBAValidator(base_url, api_key=api_key)
    result = client.validate(_gic_manifest())
    assert isinstance(result, ZKBAValidateResult)
    assert result.error is None, f"unexpected error: {result.error!r}"
    assert result.valid is True
    assert result.errors == []
    assert result.zkba_class_name == "GIC"
    assert result.proof_weight_name == "CHAIN_ONLY"
    assert result.schema_name_form == "implementation"


# ---------------------------------------------------------------------------
# T-ZKBA-VSDK-4: live round-trip malformed manifest
# ---------------------------------------------------------------------------
def test_t_zkba_vsdk_4_live_round_trip_malformed(live_bridge):
    base_url, _store, api_key = live_bridge
    manifest = _gic_manifest()
    del manifest["proof_weight"]  # trigger validator failure
    client = VAPIZKBAValidator(base_url, api_key=api_key)
    result = client.validate(manifest)
    assert isinstance(result, ZKBAValidateResult)
    # Fail-open contract preserved end-to-end:
    # bridge returns 200 + valid=False + errors populated;
    # SDK exposes that as .valid=False + .errors populated + .error=None
    assert result.error is None, f"unexpected transport error: {result.error!r}"
    assert result.valid is False
    assert len(result.errors) > 0
    assert any("missing required fields" in e for e in result.errors)


# ---------------------------------------------------------------------------
# T-ZKBA-VSDK-5: live round-trip 7-class parametrized coverage
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("class_name", [
    "AIT", "GIC", "VHP", "HARDWARE", "CONSENT", "TOURNAMENT", "MARKET",
])
def test_t_zkba_vsdk_5_live_round_trip_all_seven_classes(live_bridge, class_name):
    """B.8 G4 7-class coverage mirrored end-to-end at SDK layer."""
    from zkba_manifest_validator import build_representative_manifest  # type: ignore
    from vapi_bridge.zkba_artifact import ZKBAClass  # type: ignore

    base_url, _store, api_key = live_bridge
    zkba_class = ZKBAClass[class_name]
    manifest = build_representative_manifest(zkba_class=zkba_class)

    client = VAPIZKBAValidator(base_url, api_key=api_key)
    result = client.validate(manifest)
    assert result.error is None, f"transport error: {result.error!r}"
    assert result.valid is True, f"class {class_name} rejected: {result.errors}"
    assert result.zkba_class_name == class_name
    # proof_weight_name must be present + non-empty
    assert result.proof_weight_name


# ---------------------------------------------------------------------------
# T-ZKBA-VSDK-6: SDK_VERSION marker
# ---------------------------------------------------------------------------
def test_t_zkba_vsdk_6_sdk_version_bumped():
    """SDK_VERSION reflects the G4 validator ship — version string must
    mention zkba + validator."""
    assert "zkba" in SDK_VERSION.lower(), f"SDK_VERSION={SDK_VERSION!r} lacks zkba marker"
    assert "validator" in SDK_VERSION.lower() or "g4" in SDK_VERSION.lower(), \
        f"SDK_VERSION={SDK_VERSION!r} should mention validator or g4"
    assert SDK_VERSION.startswith("3.1."), \
        f"SDK_VERSION={SDK_VERSION!r} should be 3.1.x (G4 follow-up to C4 3.1.0)"
