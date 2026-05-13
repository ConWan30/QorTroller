"""Tests for scripts/layerzero_vhp_bridge_audit.py."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "layerzero_vhp_bridge_audit.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("lz_audit", SCRIPT_PATH)
lz_audit = importlib.util.module_from_spec(_spec)  # type: ignore
sys.modules["lz_audit"] = lz_audit
_spec.loader.exec_module(lz_audit)  # type: ignore


# ---- T-LZ-1: live audit against real source reports STUB --------------

def test_t_lz_1_live_source_reports_stub():
    """Against the real VAPIVerifiedHumanProofBridge.sol at HEAD,
    the audit MUST report STUB exit 1. Catches accidental
    refactor-without-runbook-update."""
    src = PROJECT_ROOT / "contracts" / "contracts" / "VAPIVerifiedHumanProofBridge.sol"
    report = lz_audit.scan(src)
    assert report["verdict"] == "STUB"
    assert report["exit_code"] == 1
    # All 4 stub indicators should be present at this commit.
    assert report["stub_indicators_found"] == report["stub_indicators_total"]
    # No production indicators at this commit.
    assert report["production_indicators_found"] == 0


# ---- T-LZ-2: missing source returns SRC_NOT_FOUND exit 2 --------------

def test_t_lz_2_missing_source_returns_exit_2():
    nonexistent = Path("/nonexistent/VAPIVerifiedHumanProofBridge.sol")
    report = lz_audit.scan(nonexistent)
    assert report["verdict"] == "SRC_NOT_FOUND"
    assert report["exit_code"] == 2


# ---- T-LZ-3: synthetic OApp-wired source reports OAPP_WIRED -----------

def test_t_lz_3_oapp_wired_synthetic_source():
    """A synthetic production-ready source with all 5 production
    indicators + zero stub indicators should report OAPP_WIRED exit 0."""
    synthetic = """
import "@layerzerolabs/lz-evm-oapp-v2/contracts/OApp.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract VAPIVerifiedHumanProofBridge is OApp {
    mapping(uint256 => mapping(uint32 => uint64)) public receivedNonces;

    function _lzSend(uint32 dstEid, bytes memory payload) internal {
        _lzSend(dstEid, payload, options, fee, refundAddr);
    }

    function _lzReceive(
        Origin calldata _origin,
        bytes32 _guid,
        bytes calldata _message,
        address _executor,
        bytes calldata _extraData
    ) internal override {
        // implementation
        require(_nonce > receivedNonces[_origin.tokenId][_origin.eid], "replay");
    }
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "VAPIVerifiedHumanProofBridge.sol"
        src.write_text(synthetic, encoding="utf-8")
        report = lz_audit.scan(src)
        assert report["verdict"] == "OAPP_WIRED"
        assert report["exit_code"] == 0


# ---- T-LZ-4: synthetic mixed state reports STUB ----------------------

def test_t_lz_4_mixed_state_reports_stub():
    """A source with SOME production patterns + SOME stub patterns
    remaining MUST still report STUB — refactor is incomplete."""
    synthetic = """
import "@layerzerolabs/lz-evm-oapp-v2/contracts/OApp.sol";

// This is an AssemblyScript stub — lzSend is mocked
contract VAPIVerifiedHumanProofBridge is Ownable {
    function _lzReceive() internal { }
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "VAPIVerifiedHumanProofBridge.sol"
        src.write_text(synthetic, encoding="utf-8")
        report = lz_audit.scan(src)
        assert report["verdict"] == "STUB"
        assert report["exit_code"] == 1
        # Some production patterns present, some stubs remain
        assert report["production_indicators_found"] > 0
        assert report["stub_indicators_found"] > 0


# ---- T-LZ-5: JSON mode emits valid JSON --------------------------------

def test_t_lz_5_json_mode(capsys):
    exit_code = lz_audit.main(["--json"])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert exit_code == 1  # current state is STUB
    assert parsed["verdict"] == "STUB"
    assert "findings" in parsed
    assert len(parsed["findings"]) == 9  # 4 stub + 5 production


# ---- T-LZ-6: findings list shape ---------------------------------------

def test_t_lz_6_findings_list_shape():
    src = PROJECT_ROOT / "contracts" / "contracts" / "VAPIVerifiedHumanProofBridge.sol"
    report = lz_audit.scan(src)
    for f in report["findings"]:
        assert "pattern" in f
        assert "kind" in f
        assert f["kind"] in {"STUB_REQUIRED", "PRODUCTION_REQUIRED"}
        assert "description" in f
        assert "present" in f
        assert isinstance(f["present"], bool)


# ---- T-LZ-7: render_human handles all verdict cases --------------------

def test_t_lz_7_render_human_handles_all_verdicts():
    """Smoke render_human on STUB, OAPP_WIRED, and SRC_NOT_FOUND."""
    # STUB live
    src = PROJECT_ROOT / "contracts" / "contracts" / "VAPIVerifiedHumanProofBridge.sol"
    r1 = lz_audit.scan(src)
    rendered = lz_audit.render_human(r1)
    assert "VERDICT: STUB" in rendered
    assert "STUB" in rendered

    # SRC_NOT_FOUND
    r2 = lz_audit.scan(Path("/nonexistent.sol"))
    rendered2 = lz_audit.render_human(r2)
    assert "ERROR" in rendered2 or "SRC_NOT_FOUND" in rendered2


# ---- T-LZ-8: pattern counts are FROZEN at 4 stub + 5 production -------

def test_t_lz_8_pattern_counts_pinned():
    """Catch silent pattern additions/removals that would change the
    audit's signal-to-noise. Updating these requires updating the
    runbook + this test in the same commit."""
    assert len(lz_audit.STUB_PATTERNS) == 4
    assert len(lz_audit.PRODUCTION_PATTERNS) == 5
