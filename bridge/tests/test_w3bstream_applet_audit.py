"""Tests for scripts/w3bstream_applet_audit.py."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "w3bstream_applet_audit.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("w3b_audit", SCRIPT_PATH)
w3b_audit = importlib.util.module_from_spec(_spec)  # type: ignore
sys.modules["w3b_audit"] = w3b_audit
_spec.loader.exec_module(w3b_audit)  # type: ignore


# ---- T-W3B-1: selector_for produces canonical Ethereum keccak256 ------

def test_t_w3b_1_selector_for_canonical():
    """The selector_for function must compute keccak256 (NOT NIST SHA-3).
    Known-good test vector from Ethereum: balanceOf(address)."""
    sel = w3b_audit.selector_for("balanceOf(address)")
    assert sel == "0x70a08231"


# ---- T-W3B-2: VAPIConsentRegistry isConsentValid selector --------------

def test_t_w3b_2_consent_selector():
    """isConsentValid(address,uint8) -> 0xbabcf9f5."""
    sel = w3b_audit.selector_for("isConsentValid(address,uint8)")
    assert sel == "0xbabcf9f5"


# ---- T-W3B-3: PITLSessionRegistry submitPITLProof selector ------------

def test_t_w3b_3_submitpitlproof_selector():
    """submitPITLProof full 7-arg signature -> 0x7c4847ed."""
    sel = w3b_audit.selector_for(
        "submitPITLProof(bytes32,bytes,uint256,uint256,uint256,uint256,uint256)"
    )
    assert sel == "0x7c4847ed"


# ---- T-W3B-4: live audit against real applet dir reports STUB ---------

def test_t_w3b_4_live_audit_reports_stub_state():
    """Against the real scripts/w3bstream/ directory, the audit MUST
    report validate_poac_record.ts as STUB or STUB_DEPS_BLOCKED
    (placeholders + crypto deltas). Phase O4-VPM-INT-A.5 added the
    STUB_DEPS_BLOCKED verdict tier when the deltas overlap with
    DEPENDENCY_BLOCKERS (P256_VERIFY / POSEIDON_HASH currently dep-
    blocked per the upstream @assemblyscript/wasm-crypto 404)."""
    report, exit_code = w3b_audit.run_audit(
        PROJECT_ROOT / "scripts" / "w3bstream"
    )
    assert exit_code == 1  # one or more applets non-production-ready
    poac = next(
        a for a in report["applets"] if a["applet"] == "validate_poac_record.ts"
    )
    assert poac["verdict"] in ("STUB", "STUB_DEPS_BLOCKED")
    placeholders = {p["placeholder"] for p in poac["placeholders_found"]}
    assert "0xCAFE0237" in placeholders
    assert "0xDEADBEEF" in placeholders


# ---- T-W3B-5: missing applet dir returns exit 2 -----------------------

def test_t_w3b_5_missing_applet_dir_returns_exit_2():
    nonexistent = Path("/nonexistent/path/applets")
    report, exit_code = w3b_audit.run_audit(nonexistent)
    assert exit_code == 2
    assert "error" in report


# ---- T-W3B-6: empty applet dir returns exit 2 -------------------------

def test_t_w3b_6_empty_applet_dir_returns_exit_2():
    with tempfile.TemporaryDirectory() as tmp:
        report, exit_code = w3b_audit.run_audit(Path(tmp))
        assert exit_code == 2
        assert "error" in report


# ---- T-W3B-7: synthetic applet with no placeholders reports SELECTORS_OK

def test_t_w3b_7_clean_applet_reports_selectors_ok():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # process_gsr_packet.ts is in KNOWN_PLACEHOLDERS targets none, so
        # any synthetic file with that name + no 0xCAFE0237/0xDEADBEEF
        # in body should report SELECTORS_OK.
        (tmp_path / "process_gsr_packet.ts").write_text(
            "// Clean applet with no placeholders\n", encoding="utf-8"
        )
        report, exit_code = w3b_audit.run_audit(tmp_path)
        assert exit_code == 0  # all SELECTORS_OK
        a = report["applets"][0]
        assert a["verdict"] == "SELECTORS_OK"


# ---- T-W3B-8: synthetic applet with placeholder reports STUB ----------

def test_t_w3b_8_placeholder_applet_reports_stub():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "validate_poac_record.ts").write_text(
            "store<u32>(callPtr, 0xCAFE0237);  // STUB SELECTOR\n",
            encoding="utf-8",
        )
        report, exit_code = w3b_audit.run_audit(tmp_path)
        assert exit_code == 1
        a = report["applets"][0]
        # Phase O4-VPM-INT-A.5: validate_poac_record.ts has crypto_deltas
        # keyed on its name; if any of those overlap with DEPENDENCY_BLOCKERS
        # the verdict surfaces STUB_DEPS_BLOCKED. Either is acceptable.
        assert a["verdict"] in ("STUB", "STUB_DEPS_BLOCKED")
        assert len(a["placeholders_found"]) >= 1


# ---- T-W3B-9: JSON output mode produces valid JSON --------------------

def test_t_w3b_9_json_mode(capsys):
    exit_code = w3b_audit.main([
        "--applet-dir", str(PROJECT_ROOT / "scripts" / "w3bstream"),
        "--json",
    ])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert exit_code in (0, 1, 2)
    assert "authoritative_signatures" in parsed
    assert "applets" in parsed


# ---- T-W3B-10: authoritative signatures match applet documentation -----

def test_t_w3b_10_authoritative_signatures_pinned():
    """Catch silent drift between the AUTHORITATIVE_SIGNATURES list and
    the KNOWN_PLACEHOLDERS list — every placeholder MUST reference a
    real signature."""
    real_sigs = {sig for sig, _, _, _ in w3b_audit.AUTHORITATIVE_SIGNATURES}
    placeholder_refs = {sig for _, _, sig in w3b_audit.KNOWN_PLACEHOLDERS}
    missing = placeholder_refs - real_sigs
    assert not missing, (
        f"Placeholders reference signatures not in AUTHORITATIVE_SIGNATURES: "
        f"{missing}"
    )


# ---- T-W3B-11: applet source contains the real selector value as comment

# ---- T-W3B-12: A.5 — check_dependency_blockers shape ---------------

def test_t_w3b_12_dependency_blockers_shape():
    """Phase O4-VPM-INT-A.5 — check_dependency_blockers returns a
    structured dict with as_of_date + blockers list + any_blocked bool
    + rationale string."""
    result = w3b_audit.check_dependency_blockers()
    assert "as_of_date" in result
    assert "blockers" in result
    assert "any_blocked" in result
    assert "rationale" in result
    assert isinstance(result["blockers"], list)
    assert isinstance(result["any_blocked"], bool)
    # Per A.0 preflight 2026-05-14: @assemblyscript/wasm-crypto + AS
    # Poseidon both unavailable → 2 blockers documented.
    assert result["any_blocked"] is True
    assert len(result["blockers"]) >= 2


# ---- T-W3B-13: A.5 — STUB_DEPS_BLOCKED verdict tier --------------

def test_t_w3b_13_stub_deps_blocked_verdict_for_validate_poac():
    """Live audit against scripts/w3bstream/ MUST report
    validate_poac_record.ts as STUB_DEPS_BLOCKED (not generic STUB)
    because its open deltas overlap with DEPENDENCY_BLOCKERS entries
    (P256_VERIFY blocked by @assemblyscript/wasm-crypto 404)."""
    report, _ = w3b_audit.run_audit(
        PROJECT_ROOT / "scripts" / "w3bstream"
    )
    poac = next(
        a for a in report["applets"] if a["applet"] == "validate_poac_record.ts"
    )
    # At this commit state, the deltas P256_VERIFY + POSEIDON_HASH are
    # both dep-blocked; verdict MUST be STUB_DEPS_BLOCKED.
    assert poac["verdict"] == "STUB_DEPS_BLOCKED"


# ---- T-W3B-14: A.5 — dependency_blockers surfaces in run_audit output -

def test_t_w3b_14_dependency_blockers_in_report():
    """run_audit's report MUST include the dependency_blockers field so
    the operator audit surface explicitly carries the upstream blocker
    inventory (not just inferred from per-applet verdicts)."""
    report, _ = w3b_audit.run_audit(
        PROJECT_ROOT / "scripts" / "w3bstream"
    )
    assert "dependency_blockers" in report
    db = report["dependency_blockers"]
    assert db["any_blocked"] is True
    pkg_names = {b["package"] for b in db["blockers"]}
    assert "@assemblyscript/wasm-crypto" in pkg_names


def test_t_w3b_11_real_selector_in_applet_source():
    """The applet source MUST mention the real selector value somewhere
    in the placeholder comments. This catches the case where the audit
    script declares a real selector but the applet author forgot to
    document it inline."""
    applet_path = PROJECT_ROOT / "scripts" / "w3bstream" / "validate_poac_record.ts"
    source = applet_path.read_text(encoding="utf-8")

    # Both real selectors must appear somewhere in the file.
    assert "0xbabcf9f5" in source, (
        "Real isConsentValid selector 0xbabcf9f5 not documented inline"
    )
    assert "0x7c4847ed" in source, (
        "Real submitPITLProof selector 0x7c4847ed not documented inline"
    )
