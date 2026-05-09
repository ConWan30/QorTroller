"""Phase 237-ZK-SEPPROOF SDK (Step D) tests.

Tests the BiometricSnapshotResult / BiometricSnapshotAnchorResult dataclasses
+ VAPIZKSepProof client class (snapshot_status, anchor_snapshot, verify_local).

Network calls are mocked via urllib.request.urlopen patching so tests run
without a live bridge.

T-237-SEP-SDK-1..7.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SDK_DIR = Path(__file__).parents[1]
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from vapi_sdk import (  # noqa: E402
    VAPIZKSepProof,
    BiometricSnapshotResult,
    BiometricSnapshotAnchorResult,
)


def _fake_urlopen(payload: dict):
    """Build a context-manager mock that returns `payload` JSON-encoded."""
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    cm.__exit__.return_value = False
    return cm


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-1: BiometricSnapshotResult dataclass slots
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_1_snapshot_result_slots():
    """@dataclass(slots=True) per Phase 184+ pattern — unknown attribute raises."""
    r = BiometricSnapshotResult()
    assert r.total_snapshots == 0
    assert r.on_chain_confirmed is False
    with pytest.raises(AttributeError):
        r.injected = "x"  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-2: BiometricSnapshotAnchorResult slots + sorted_player_ids default
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_2_anchor_result_slots_and_default():
    r = BiometricSnapshotAnchorResult()
    assert r.row_id == 0
    assert r.sorted_player_ids == []   # __post_init__ replaces None with []
    with pytest.raises(AttributeError):
        r.injected = "x"  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-3: snapshot_status parses bridge response
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_3_snapshot_status_parse():
    payload = {
        "total_snapshots":    3,
        "latest_commitment":  "ab" * 32,
        "feature_dim":        4,
        "n_players":          3,
        "ts_ns":              1_778_316_000_000_000_000,
        "on_chain_confirmed": True,
        "tx_hash":            "0x" + "cd" * 32,
        "trigger_reason":     "post_ait_recompute_2026_05_09",
    }
    client = VAPIZKSepProof("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = client.snapshot_status()
    assert result.error == ""
    assert result.total_snapshots == 3
    assert result.latest_commitment == "ab" * 32
    assert result.feature_dim == 4
    assert result.n_players == 3
    assert result.on_chain_confirmed is True
    assert result.tx_hash == "0x" + "cd" * 32


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-4: snapshot_status handles HTTP error (returns result with error)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_4_snapshot_status_http_error():
    """Bridge unreachable / 5xx → SDK returns BiometricSnapshotResult(error=...)
    rather than raising. Caller-friendly contract per Phase 184 pattern."""
    client = VAPIZKSepProof("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", side_effect=ConnectionError("conn refused")):
        result = client.snapshot_status()
    assert result.error != ""
    assert "conn refused" in result.error
    # Defaults preserved on error
    assert result.total_snapshots == 0
    assert result.on_chain_confirmed is False


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-5: anchor_snapshot validates reason length locally
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_5_anchor_short_reason_local_validation():
    """Local pre-validation (no network call) when reason < 10 chars.
    Mirrors the bridge-side 422 error message for client UX consistency."""
    client = VAPIZKSepProof("http://localhost:8080", "test-key")
    # Should not even attempt the network call
    with patch("urllib.request.urlopen") as mock_urlopen:
        result = client.anchor_snapshot(reason="short")
    assert result.error != ""
    assert "at least 10 characters" in result.error
    mock_urlopen.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-6: anchor_snapshot parses success response
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_6_anchor_snapshot_success():
    payload = {
        "row_id":              42,
        "snapshot_commitment": "ef" * 32,
        "feature_dim":         4,
        "n_players":           3,
        "sorted_player_ids":   [0, 1, 2],
        "ts_ns":               1_778_316_500_000_000_000,
        "trigger_reason":      "operator_initial_anchor_2026_05_09",
        "on_chain_confirmed":  True,
        "tx_hash":             "0x" + "9a" * 32,
        "ait_session_log_id":  10,
    }
    client = VAPIZKSepProof("http://localhost:8080", "test-key")
    with patch("urllib.request.urlopen", return_value=_fake_urlopen(payload)):
        result = client.anchor_snapshot(reason="operator_initial_anchor_2026_05_09")
    assert result.error == ""
    assert result.row_id == 42
    assert result.snapshot_commitment == "ef" * 32
    assert result.sorted_player_ids == [0, 1, 2]
    assert result.on_chain_confirmed is True
    assert result.ait_session_log_id == 10


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-SDK-7: verify_local checks proof byte length only (Step D scope)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_sdk_7_verify_local_structural():
    """verify_local is a structural pre-flight (256-byte length check) until
    the trusted setup ceremony deploys the on-chain verifier.  Returns True
    only for exactly-256-byte input.  Cryptographic verification is on-chain."""
    assert VAPIZKSepProof.verify_local(b"\x00" * 256) is True
    assert VAPIZKSepProof.verify_local(b"\x42" * 256) is True   # any 256 bytes
    assert VAPIZKSepProof.verify_local(b"\x00" * 255) is False  # too short
    assert VAPIZKSepProof.verify_local(b"\x00" * 257) is False  # too long
    assert VAPIZKSepProof.verify_local(b"") is False
    assert VAPIZKSepProof.verify_local("not bytes") is False  # type: ignore[arg-type]
