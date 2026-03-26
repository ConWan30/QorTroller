"""Phase 110 — IoSwarm VHP Mint Authorization SDK tests (4 tests).

Tests:
  1. IoSwarmVHPMintResult.__slots__ has exactly 8 fields; all named correctly
  2. VAPISwarmVHPMint("http://localhost:18080", "test-key") initializes without raising
  3. get_vhp_mint_status() bad URL (port 1) → result.error is not None
  4. Error result defaults: ioswarm_vhp_mint_enabled=False, authorized=False, task_spec_registered=True
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_1_ioswarm_vhp_mint_result_slots():
    """IoSwarmVHPMintResult has exactly 8 slots with correct names."""
    from sdk.vapi_sdk import IoSwarmVHPMintResult

    assert hasattr(IoSwarmVHPMintResult, "__slots__"), "Must be a slots=True dataclass"
    slots = set(IoSwarmVHPMintResult.__slots__)
    expected = {
        "ioswarm_vhp_mint_enabled",
        "quorum_verdict",
        "authorized",
        "agreement_ratio",
        "authorized_count",
        "denied_count",
        "task_spec_registered",
        "error",
    }
    assert slots == expected, f"Slot mismatch: got {slots}, expected {expected}"
    assert len(slots) == 8, f"Expected 8 slots, got {len(slots)}"


def test_2_vapi_swarm_vhp_mint_init():
    """VAPISwarmVHPMint initializes without raising."""
    from sdk.vapi_sdk import VAPISwarmVHPMint

    client = VAPISwarmVHPMint("http://localhost:18080", "test-key")
    assert client._base_url == "http://localhost:18080"
    assert client._api_key == "test-key"


def test_3_get_vhp_mint_status_bad_url_returns_error():
    """get_vhp_mint_status() with unreachable URL returns error (never raises)."""
    from sdk.vapi_sdk import VAPISwarmVHPMint

    # Port 1 is not in use — connection refused
    client = VAPISwarmVHPMint("http://localhost:1", "key")
    result = client.get_vhp_mint_status()
    assert result.error is not None, "Expected error on unreachable URL"


def test_4_error_result_defaults():
    """Error result has expected safe defaults."""
    from sdk.vapi_sdk import VAPISwarmVHPMint

    client = VAPISwarmVHPMint("http://localhost:1", "key")
    result = client.get_vhp_mint_status()

    assert result.ioswarm_vhp_mint_enabled is False
    assert result.authorized is False
    assert result.task_spec_registered is True
    assert result.agreement_ratio == 0.0
    assert result.authorized_count == 0
    assert result.denied_count == 0
    assert result.error is not None
