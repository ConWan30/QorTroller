"""Phase O5-MLGA Stage 4 — VPM artifact compiler tests.

T-MLGA-VPM-1   build_mlga_session_artifact returns expected manifest keys
T-MLGA-VPM-2   Deterministic HTML output (same inputs → byte-identical output_hash)
T-MLGA-VPM-3   Per-input tamper detection on all 8 fields (each changes output_hash)
T-MLGA-VPM-4   9-field Integrity Label populated with FROZEN values
T-MLGA-VPM-5   VPMComplianceError raised on forbidden patterns in renderer
T-MLGA-VPM-6   visual_state determination (healthy → 'live'; zero → 'unverified')
T-MLGA-VPM-7   HTML output contains all 9 data-vpm-field markers + vpm-integrity-label class
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


_BASE_INPUTS = dict(
    session_id="test_session_001",
    session_start_ts_ns=1778000000_000_000_000,
    session_end_ts_ns=1778001800_000_000_000,
    n_poac_records=1_800_000,
    n_trigger_pulls_r2=124,
    n_trigger_pulls_l2=31,
    apop_state_counts={"ACTIVE_MATCH_PLAY": 1500, "MENU_DETECTED": 50},
    bt_observability=1,
    gic_advances_in_session=18,
    dataproof_hex="c0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878",
)


def _build(**overrides):
    import mlga_compile_session_artifact as mod
    args = {**_BASE_INPUTS, **overrides}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        args["output_dir"] = Path(td)
        return mod.build_mlga_session_artifact(**args)


# ----- T-1 -----

def test_t_mlga_vpm_1_manifest_keys():
    """Returns dict with expected VPMArtifactManifest fields + MLGA additions."""
    m = _build()
    required_keys = {
        "schema", "vpm_id", "zkba_class", "proof_weight",
        "visual_state", "capture_mode", "integrity_label_hash_hex",
        "wrapper_schema", "zkba_manifest_hash_hex", "output_path",
        "output_hash_hex", "input_commitment_hex", "compiler_version",
        "ts_ns",
        # MLGA-specific additions
        "commitment_hex", "manifest_uri", "preimage_json",
    }
    assert required_keys.issubset(m.keys()), (
        f"missing keys: {required_keys - m.keys()}"
    )
    assert m["vpm_id"] == "MLGA-SESSION-v1"
    assert m["wrapper_schema"] == "vapi-mlga-session-artifact-v1"
    assert m["zkba_class"] == 2  # ZKBAClass.GIC
    assert m["capture_mode"] == "live"
    assert m["commitment_hex"] == m["output_hash_hex"]


# ----- T-2 -----

def test_t_mlga_vpm_2_deterministic_html():
    """Same inputs → byte-identical output_hash. Foundation of audit-replay."""
    m1 = _build()
    m2 = _build()
    assert m1["output_hash_hex"] == m2["output_hash_hex"]
    assert m1["input_commitment_hex"] == m2["input_commitment_hex"]
    assert m1["integrity_label_hash_hex"] == m2["integrity_label_hash_hex"]


# ----- T-3 -----

@pytest.mark.parametrize("field,new_val", [
    ("session_id", "different_session"),
    ("session_start_ts_ns", _BASE_INPUTS["session_start_ts_ns"] + 1),
    ("session_end_ts_ns", _BASE_INPUTS["session_end_ts_ns"] + 1),
    ("n_poac_records", _BASE_INPUTS["n_poac_records"] + 1),
    ("n_trigger_pulls_r2", _BASE_INPUTS["n_trigger_pulls_r2"] + 1),
    ("n_trigger_pulls_l2", _BASE_INPUTS["n_trigger_pulls_l2"] + 1),
    ("gic_advances_in_session", _BASE_INPUTS["gic_advances_in_session"] + 1),
    ("apop_state_counts", {"ACTIVE_MATCH_PLAY": 1501, "MENU_DETECTED": 50}),
    ("bt_observability", 2),
    ("dataproof_hex", "00" * 32),
])
def test_t_mlga_vpm_3_tamper_detection(field, new_val):
    """Each of the 10 input fields independently load-bearing."""
    m0 = _build()
    mt = _build(**{field: new_val})
    assert mt["output_hash_hex"] != m0["output_hash_hex"], (
        f"tampering field {field} did not change output_hash_hex"
    )


# ----- T-4 -----

def test_t_mlga_vpm_4_integrity_label_frozen_values():
    """Verify the FROZEN 9 fields are present + canonical values."""
    m = _build()
    # The integrity_label is hashed into integrity_label_hash_hex; we can
    # reproduce the canonical hash to verify the 9 fields match.
    label = {
        "proof_type":              "mlga_session",
        "capture_mode":            "live",
        "raw_biometrics_exposed":  "no",
        "consent_active":          "n/a",
        "zk_verified":             "no",
        "on_chain_anchor":         "no",
        "proof_weight":            "CHAIN_ONLY",
        "revocation_status":       "active",
        "limitations": (
            "MLGA v1 ambient capture; supplements lab measurements; "
            "does not replace controlled-environment baseline"
        ),
    }
    canonical = json.dumps(
        label, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    expected = hashlib.sha256(canonical).hexdigest()
    assert m["integrity_label_hash_hex"] == expected


# ----- T-5 -----

def test_t_mlga_vpm_5_compliance_error_on_forbidden_pattern():
    """If the renderer is monkey-patched to inject Math.random(), the
    compiler MUST raise VPMComplianceError BEFORE writing to disk."""
    import mlga_compile_session_artifact as mod
    from vsd_ui_compiler import VPMComplianceError
    original_render = mod._render_html
    def _bad_render(inputs):
        return original_render(inputs) + "<script>Math.random()</script>"
    mod._render_html = _bad_render
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            with pytest.raises(VPMComplianceError):
                mod.build_mlga_session_artifact(
                    **_BASE_INPUTS, output_dir=Path(td),
                )
    finally:
        mod._render_html = original_render


# ----- T-6 -----

def test_t_mlga_vpm_6_visual_state_determination():
    """Healthy session → 'live'; zero-record session → 'unverified'."""
    m_live = _build()
    assert m_live["visual_state"] == "live"

    m_unv = _build(n_poac_records=0, gic_advances_in_session=0,
                   n_trigger_pulls_r2=0, n_trigger_pulls_l2=0)
    assert m_unv["visual_state"] == "unverified"


# ----- T-7 -----

def test_t_mlga_vpm_7_html_contains_9_data_vpm_field_markers():
    """The rendered HTML MUST contain `class="vpm-integrity-label"` plus
    the 9 `data-vpm-field=` markers (FROZEN Anti-Hype Visual Grammar).
    Reading the HTML file on disk verifies the artifact's grammar
    compliance — what VpmGrammarVerifier reads on the frontend."""
    import mlga_compile_session_artifact as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        m = mod.build_mlga_session_artifact(
            **_BASE_INPUTS, output_dir=Path(td),
        )
        html = Path(m["output_path"]).read_text(encoding="utf-8")
        assert 'class="vpm-integrity-label"' in html
        for field in (
            "proof_type", "capture_mode", "raw_biometrics_exposed",
            "consent_active", "zk_verified", "on_chain_anchor",
            "proof_weight", "revocation_status", "limitations",
        ):
            assert f'data-vpm-field="{field}"' in html, (
                f"missing data-vpm-field marker for {field}"
            )
        # Also verify data-vpm-visual-state marker (Layer 3 grammar verifier
        # reads this for the 6-state DOM signature assertion).
        assert 'data-vpm-visual-state="live"' in html
