"""Phase 158 — Class K HMAC Validation (WIF-014) + PoHBG Hash (WIF-015).

8 tests → bridge 1877 → 1885.

Deliverables:
  WIF-014: validate_gsr_hmac() authenticates 80-byte GSR frames with HMAC-SHA256
  WIF-015: compute_pohbg_hash() returns 64-char SHA-256 hex (Proof of Hardware Biometric Grip)
"""

import hashlib
import hmac as _hmac
import os
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

for _m in ["anthropic", "web3", "web3.exceptions", "eth_account",
           "pydualsense", "hidapi", "hid"]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

os.chdir(tempfile.mkdtemp())

from bridge.vapi_bridge.store import Store
from bridge.vapi_bridge.gsr_feature_extractor import (
    GSRHMACValidationError,
    MockGSRGrip,
    compute_pohbg_hash,
    make_gsr_frame,
    validate_gsr_hmac,
)


def _make_store() -> Store:
    db_dir = tempfile.mkdtemp()
    return Store(os.path.join(db_dir, "test_p158.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key              = "testkey158"
    cfg.rate_limit_per_minute         = 10000
    cfg.gsr_hmac_enabled              = False
    cfg.gsr_hmac_key_hex              = ""
    cfg.pohbg_enabled                 = False
    cfg.fleet_consensus_enabled       = True
    cfg.fleet_consensus_snapshot_interval_s = 1800
    cfg.validation_gate_n             = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.separation_ratio_current      = 1.261
    cfg.enforcement_cert_ttl_s        = 86400
    cfg.epistemic_consensus_enabled   = False
    cfg.agent_model                   = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache       = None
    cfg.vhp_contract_address          = ""
    cfg.layerzero_endpoint_address    = ""
    cfg.warm_up_batch_size            = 5
    cfg.stiotx_token_address          = ""
    cfg.quicksilver_collateral_address = ""
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


_TEST_KEY_HEX = "a1b2c3d4" * 8   # 64-char hex = 32-byte key


class TestWIF014GSRHMACValidation(unittest.TestCase):
    """WIF-014: validate_gsr_hmac() authenticates 80-byte GSR frames."""

    def test_valid_frame_returns_dict_with_valid_true(self):
        """A well-formed signed frame returns valid=True and correct fields."""
        grip = MockGSRGrip(seed=42)
        frame = grip.get_frame(device_id="dev_p158", hmac_key_hex=_TEST_KEY_HEX)
        self.assertEqual(len(frame), 80)

        result = validate_gsr_hmac(frame, _TEST_KEY_HEX)
        self.assertTrue(result["valid"])
        self.assertIn("arousal_index", result)
        self.assertIn("correlation", result)
        self.assertIn("conductance_raw", result)
        self.assertIn("ts_ns", result)
        self.assertIn("device_id", result)

    def test_tampered_frame_raises_hmac_error(self):
        """Flipping a byte in the payload causes HMAC mismatch → GSRHMACValidationError."""
        grip = MockGSRGrip(seed=42)
        frame = grip.get_frame(device_id="dev_p158", hmac_key_hex=_TEST_KEY_HEX)
        # Tamper byte 10 (inside payload region before HMAC tag)
        tampered = bytearray(frame)
        tampered[10] ^= 0xFF
        with self.assertRaises(GSRHMACValidationError):
            validate_gsr_hmac(bytes(tampered), _TEST_KEY_HEX)

    def test_wrong_key_raises_hmac_error(self):
        """Validating with incorrect key raises GSRHMACValidationError."""
        grip = MockGSRGrip(seed=42)
        frame = grip.get_frame(device_id="dev_p158", hmac_key_hex=_TEST_KEY_HEX)
        wrong_key = "deadbeef" * 8
        with self.assertRaises(GSRHMACValidationError):
            validate_gsr_hmac(frame, wrong_key)

    def test_short_frame_raises_hmac_error(self):
        """Frame shorter than 80 bytes raises GSRHMACValidationError immediately."""
        with self.assertRaises(GSRHMACValidationError):
            validate_gsr_hmac(b"\x00" * 40, _TEST_KEY_HEX)


class TestWIF015PoHBGHash(unittest.TestCase):
    """WIF-015: compute_pohbg_hash() returns 64-char SHA-256 hex."""

    def test_pohbg_hash_is_64_char_hex(self):
        """compute_pohbg_hash returns 64-char lowercase hex SHA-256."""
        h = compute_pohbg_hash(
            device_id          = "dev_abc",
            arousal_millis     = 720,
            correlation_millis = 410,
            conductance_raw_int = 5001,
            ts_ns              = 1712270400_000_000_000,
        )
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_pohbg_hash_is_deterministic(self):
        """Same inputs always produce the same PoHBG hash."""
        kwargs = dict(
            device_id="dev_abc", arousal_millis=720, correlation_millis=410,
            conductance_raw_int=5001, ts_ns=1712270400_000_000_000,
        )
        self.assertEqual(compute_pohbg_hash(**kwargs), compute_pohbg_hash(**kwargs))

    def test_pohbg_store_roundtrip(self):
        """insert_pohbg + get_pohbg_status returns correct hash and device_id."""
        store = _make_store()
        h = compute_pohbg_hash(
            device_id="dev_roundtrip", arousal_millis=500, correlation_millis=300,
            conductance_raw_int=4200, ts_ns=1712270400_000_000_001,
        )
        row_id = store.insert_pohbg(
            device_id="dev_roundtrip",
            pohbg_hash=h,
            arousal_millis=500,
            correlation_millis=300,
            conductance_raw_int=4200,
            ts_ns=1712270400_000_000_001,
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

        status = store.get_pohbg_status(limit=1)
        self.assertEqual(status["total_pohbg"], 1)
        self.assertEqual(status["recent_hashes"][0]["pohbg_hash"], h)
        self.assertEqual(status["recent_hashes"][0]["device_id"], "dev_roundtrip")

    def test_gsr_hmac_store_roundtrip(self):
        """insert_gsr_hmac_validation roundtrip: valid entry retrievable."""
        store = _make_store()
        row_id = store.insert_gsr_hmac_validation(
            device_id="dev_hmac",
            frame_size=80,
            valid=True,
            rejection_reason="",
            ts_ns=1712270400_000_000_002,
        )
        self.assertIsInstance(row_id, int)

        status = store.get_gsr_hmac_validation_status(limit=5)
        self.assertEqual(status["total_validations"], 1)
        self.assertEqual(status["valid_count"], 1)
        self.assertEqual(status["rejected_count"], 0)

        # Insert a rejection
        store.insert_gsr_hmac_validation(
            device_id="dev_hmac",
            frame_size=80,
            valid=False,
            rejection_reason="HMAC-SHA256 tag mismatch — frame rejected",
            ts_ns=1712270400_000_000_003,
        )
        status2 = store.get_gsr_hmac_validation_status(limit=5)
        self.assertEqual(status2["total_validations"], 2)
        self.assertEqual(status2["rejected_count"], 1)


class TestPhase158Endpoints(unittest.TestCase):
    """Phase 158 REST endpoint smoke tests."""

    def test_endpoints_6_keys_each(self):
        """GET /agent/gsr-hmac-validation-status and /agent/pohbg-status return 6 required keys."""
        store = _make_store()
        cfg   = _make_cfg()

        from bridge.vapi_bridge.operator_api import create_operator_app
        try:
            from starlette.testclient import TestClient
        except ImportError:
            from fastapi.testclient import TestClient

        app    = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        # HMAC endpoint
        resp = client.get("/agent/gsr-hmac-validation-status",
                          params={"api_key": "testkey158"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("gsr_hmac_enabled", "gsr_hmac_key_configured", "total_validations",
                    "valid_count", "rejected_count", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")

        # PoHBG endpoint
        resp2 = client.get("/agent/pohbg-status",
                           params={"api_key": "testkey158"})
        self.assertEqual(resp2.status_code, 200)
        body2 = resp2.json()
        for key in ("pohbg_enabled", "total_pohbg", "latest_pohbg_hash",
                    "latest_device_id", "latest_ts_ns", "timestamp"):
            self.assertIn(key, body2, f"Missing key: {key}")


if __name__ == "__main__":
    unittest.main()
