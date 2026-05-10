"""Phase 238 Step I-FINAL — Curator session register tests.

T-238-CUR-SR-1..6 — verifies the Curator-unique post-mint workflow:
agentId substitution across both bundles + Merkle re-derivation.  The
on-chain steps 6-8 are tested separately under bridge/tests/
test_agent_registration.py (existing) with the curator branch added by
the AGENT_TO_DEVICE_TOKEN_ID extension.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import types as _types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from bridge.scripts.curator_session_register import (  # noqa: E402
    substitute_curator_agent_id_in_bundles,
    re_derive_bundle_merkle_roots,
    PLACEHOLDER_AGENT_ID,
    O1_BUNDLE,
    O2_BUNDLE,
)
from bridge.vapi_bridge.agent_registration import AGENT_TO_DEVICE_TOKEN_ID


# ── T-238-CUR-SR-1 ──────────────────────────────────────────────────────────
def test_t_238_cur_sr_1_curator_added_to_token_id_map():
    """AGENT_TO_DEVICE_TOKEN_ID extended with curator → 3."""
    assert "curator" in AGENT_TO_DEVICE_TOKEN_ID
    assert AGENT_TO_DEVICE_TOKEN_ID["curator"] == 3
    # Order preserved
    assert AGENT_TO_DEVICE_TOKEN_ID["anchor-sentry"] == 1
    assert AGENT_TO_DEVICE_TOKEN_ID["guardian"] == 2


# ── T-238-CUR-SR-2 ──────────────────────────────────────────────────────────
def test_t_238_cur_sr_2_kms_alias_for_curator():
    """KMS alias env-var mapping includes curator entry."""
    from bridge.vapi_bridge.kms_client import _AGENT_ALIAS_ENV_VARS
    assert "curator" in _AGENT_ALIAS_ENV_VARS
    assert _AGENT_ALIAS_ENV_VARS["curator"] == "VAPI_KMS_CURATOR_ALIAS"


# ── T-238-CUR-SR-3 ──────────────────────────────────────────────────────────
def test_t_238_cur_sr_3_mock_kms_default_includes_curator():
    """MockKMSClient _DEFAULT_AGENTS includes curator so dev fixtures work."""
    from bridge.vapi_bridge.mock_kms_client import MockKMSClient
    assert "curator" in MockKMSClient._DEFAULT_AGENTS
    # Default-construct mock and verify curator key generated
    mock = MockKMSClient()
    assert "curator" in mock._private_keys


# ── T-238-CUR-SR-4 ──────────────────────────────────────────────────────────
def test_t_238_cur_sr_4_substitute_agent_id_validates_input():
    """substitute_curator_agent_id_in_bundles rejects malformed agentId."""
    with pytest.raises(ValueError, match="must start with 0x"):
        substitute_curator_agent_id_in_bundles("ab" * 32)
    with pytest.raises(ValueError, match="66 chars"):
        substitute_curator_agent_id_in_bundles("0xabcd")
    with pytest.raises(ValueError, match="not valid hex"):
        substitute_curator_agent_id_in_bundles("0x" + "zz" * 32)
    # Refuses to substitute placeholder with itself
    with pytest.raises(ValueError, match="placeholder with itself"):
        substitute_curator_agent_id_in_bundles(PLACEHOLDER_AGENT_ID)


# ── T-238-CUR-SR-5 ──────────────────────────────────────────────────────────
def test_t_238_cur_sr_5_substitute_replaces_all_occurrences(tmp_path, monkeypatch):
    """Substitution rewrites all 41 occurrences across O1+O2 bundles.

    Phase 238 Step I-FINAL note: the canonical bundles in
    bridge/vapi_bridge/cedar_bundles/ have been substituted with the real
    Curator agentId (0xed6a2df5...) post-mint 2026-05-09.  This test
    therefore generates fresh placeholder fixtures in tmp_path rather
    than copying from canonical, decoupling the test from production
    bundle state.
    """
    import bridge.scripts.curator_session_register as csr

    # Build minimal placeholder fixtures with known occurrence counts.
    # O1 bundle: 1 header agent_id + 20 policies = 21 placeholder occurrences.
    # O2 bundle: 1 header agent_id + 21 policies = 22 placeholder occurrences.
    placeholder = csr.PLACEHOLDER_AGENT_ID

    def _fixture(num_policies):
        return {
            "$schema": "vapi-cedar-bundle-v1",
            "agent_id": placeholder,
            "phase": "O1_SHADOW",
            "version": 1,
            "issued_at_iso": "2026-05-09T00:00:00Z",
            "lane_prefixes": ["marketplace/"],
            "policies": [
                {
                    "id": f"P-{i:03d}",
                    "effect": "permit",
                    "principal": {"agentId": placeholder},
                    "action": "skill:read",
                    "resource": "lane://marketplace/**",
                }
                for i in range(num_policies)
            ],
        }

    tmp_o1 = tmp_path / "curator_o1_shadow_v1.json"
    tmp_o2 = tmp_path / "curator_o2_suggest_v1.json"
    tmp_o1.write_text(json.dumps(_fixture(20)), encoding="utf-8")
    tmp_o2.write_text(json.dumps(_fixture(21)), encoding="utf-8")

    monkeypatch.setattr(csr, "O1_BUNDLE", tmp_o1)
    monkeypatch.setattr(csr, "O2_BUNDLE", tmp_o2)

    # Real agentId — fake but well-formed
    real_id = "0xabcd1234ef567890" + "00" * 24
    assert len(real_id) == 66

    result = csr.substitute_curator_agent_id_in_bundles(real_id)
    assert "o1_shadow" in result
    assert "o2_suggest" in result
    # O1 bundle has agentId in 1 header + 20 policies = 21 occurrences
    assert result["o1_shadow"]["replacements"] == 21
    # O2 bundle has agentId in 1 header + 21 policies = 22 occurrences
    assert result["o2_suggest"]["replacements"] == 22

    # Verify substitution actually happened on disk
    o1_after = json.loads(tmp_o1.read_text())
    o2_after = json.loads(tmp_o2.read_text())
    assert o1_after["agent_id"] == real_id
    assert o2_after["agent_id"] == real_id
    # Every policy principal updated
    for pol in o1_after["policies"]:
        assert pol["principal"]["agentId"] == real_id
    for pol in o2_after["policies"]:
        assert pol["principal"]["agentId"] == real_id


# ── T-238-CUR-SR-6 ──────────────────────────────────────────────────────────
def test_t_238_cur_sr_6_re_derive_merkle_validates_bundles():
    """re_derive_bundle_merkle_roots returns Merkle roots for both bundles."""
    # This invokes the actual cedar_bundle_validate.py CLI — works against
    # the canonical bundle files at the locked paths.
    result = re_derive_bundle_merkle_roots()
    assert "o1_shadow" in result
    assert "o2_suggest" in result
    # O1 + O2 should both validate cleanly
    assert result["o1_shadow"].get("validate_ok") is True, \
        f"o1 validate failed: {result['o1_shadow']}"
    assert result["o2_suggest"].get("validate_ok") is True, \
        f"o2 validate failed: {result['o2_suggest']}"
    # Merkle roots present + 0x-prefixed 32-byte hex
    for label in ("o1_shadow", "o2_suggest"):
        m = result[label].get("merkle_root", "")
        assert m.startswith("0x"), f"{label} merkle missing 0x prefix"
        assert len(m) == 66, f"{label} merkle wrong length: {m}"
    # O1 + O2 Merkle roots MUST be different (structural delta verifies graduation)
    assert result["o1_shadow"]["merkle_root"] != result["o2_suggest"]["merkle_root"]
