"""Phase O4-VPM-INTEGRATION Stream A.0 — VPM compiler discipline tests.

Test band T-VPM-COMPILER-1..10 for the new `compile_vpm_artifact()` entry-point
added to `scripts/vsd_ui_compiler.py` in Phase O4 Commit 1 per
`wiki/proposals/Phase_O4_VPM_Integration_Plan.md` §3 Stream A.0 + §10 row 1.

Each test asserts ONE compiler-discipline invariant from the plan:

  T-VPM-COMPILER-1:  Schema literal pinned ('vapi-vpm-artifact-v1') and
                     distinct from existing 'vapi-zkba-manifest-v1' (ZKBA)
                     and 'vapi-vpm-manifest-v1' (wrapper)
  T-VPM-COMPILER-2:  End-to-end happy path — manifest + HTML file + 9-field
                     Integrity Label all present, hashes match
  T-VPM-COMPILER-3:  Two-build byte-stable determinism (plan A.0 item 8)
  T-VPM-COMPILER-4:  Discipline guard — external URL `https?://` rejected
                     (plan A.0 item 1)
  T-VPM-COMPILER-5:  Discipline guard — `<script src=>` rejected (plan A.0 item 1)
  T-VPM-COMPILER-6:  Discipline guard — runtime `fetch()` rejected (plan A.0 item 5)
  T-VPM-COMPILER-7:  Discipline guard — runtime `Math.random()` rejected (plan A.0 item 4)
  T-VPM-COMPILER-8:  Discipline guard — runtime `Date.now()` rejected (plan A.0 item 3)
  T-VPM-COMPILER-9:  Integrity Label container absence rejected (plan A.0 item 9)
  T-VPM-COMPILER-10: Per-field marker absence rejected — any of the 9
                     required `data-vpm-field="<name>"` markers missing
                     surfaces a precise violation message

Author: VAPI Architect (Phase O4 Commit 1)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_BRIDGE = os.path.normpath(os.path.join(_REPO, "bridge"))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import (  # noqa: E402
    VPMArtifactManifest,
    VPMComplianceError,
    _COMPILER_VERSION,
    _VPM_ARTIFACT_SCHEMA,
    _VPM_INTEGRITY_LABEL_FIELDS,
    _VPM_VISUAL_STATES,
    _VPM_CAPTURE_MODES,
    _VPM_WRAPPER_SCHEMA_REF,
    compile_vpm_artifact,
    canonical_json,
)


# ---------------------------------------------------------------------------
# Canonical compliant fixture — used as the positive-path baseline
# ---------------------------------------------------------------------------

_FIXTURE_VPM_ID = "HONESTY-BOARD-v1"
_FIXTURE_ZKBA_CLASS = ZKBAClass.GIC  # GIC Continuity Ledger is the canonical internal VPM target
_FIXTURE_PROOF_WEIGHT = ProofWeightClass.CHAIN_ONLY
_FIXTURE_VISUAL_STATE = "live"
_FIXTURE_CAPTURE_MODE = "live"
_FIXTURE_TS_NS = 1778900000000000000

_FIXTURE_INTEGRITY_LABEL = {
    "proof_type": "ZKBA-GIC",
    "capture_mode": "live",
    "raw_biometrics_exposed": False,
    "consent_active": True,
    "zk_verified": False,
    "on_chain_anchor": True,
    "proof_weight": "CHAIN_ONLY",
    "revocation_status": "active",
    "limitations": ["GIC head hash referential; not biometric proof"],
}

# Dummy ZKBA manifest hash — content-shape only, no live verification at compile
_FIXTURE_ZKBA_MANIFEST_HASH = "a" * 64


def _compliant_renderer(inputs: dict) -> str:
    """Reference renderer producing a fully-compliant VPM HTML body.

    Used as the positive-path fixture; tampered copies of this renderer
    (e.g. injecting a forbidden token) drive the negative-path tests below.
    """
    ts_ns = inputs["ts_ns"]
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>HONESTY BOARD VPM</title>\n"
        "  <style>\n"
        "    body { font-family: 'Courier New', monospace; "
        "background: #020408; color: #cfe8ff; margin: 0; padding: 1.5em; }\n"
        "    .vpm-integrity-label { border: 1px solid #1a2a40; "
        "padding: 1em; margin-top: 1em; }\n"
        "    .vpm-integrity-label dt { color: #5a8fb8; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>VAPI Honesty Board (VPM)</h1>\n"
        "  <p>Protocol state projection. Deterministic. Self-contained.</p>\n"
        "  <div class=\"vpm-integrity-label\">\n"
        "    <h2>Integrity Nutrition Label</h2>\n"
        "    <dl>\n"
        f"      <dt>Proof type:</dt><dd data-vpm-field=\"proof_type\">ZKBA-GIC</dd>\n"
        f"      <dt>Capture mode:</dt><dd data-vpm-field=\"capture_mode\">live</dd>\n"
        f"      <dt>Raw biometrics exposed:</dt><dd data-vpm-field=\"raw_biometrics_exposed\">No</dd>\n"
        f"      <dt>Consent active:</dt><dd data-vpm-field=\"consent_active\">Yes</dd>\n"
        f"      <dt>ZK verified:</dt><dd data-vpm-field=\"zk_verified\">No</dd>\n"
        f"      <dt>On-chain anchor:</dt><dd data-vpm-field=\"on_chain_anchor\">Yes</dd>\n"
        f"      <dt>Proof weight:</dt><dd data-vpm-field=\"proof_weight\">CHAIN_ONLY</dd>\n"
        f"      <dt>Revocation status:</dt><dd data-vpm-field=\"revocation_status\">active</dd>\n"
        f"      <dt>Limitations:</dt><dd data-vpm-field=\"limitations\">"
        "GIC head hash referential; not biometric proof</dd>\n"
        "    </dl>\n"
        "  </div>\n"
        f"  <footer>ts_ns={ts_ns}</footer>\n"
        "</body>\n"
        "</html>\n"
    )


def _make_kwargs(*, output_dir: Path, html_renderer=_compliant_renderer):
    """Helper — returns the kwarg bundle for compile_vpm_artifact()."""
    return dict(
        vpm_id=_FIXTURE_VPM_ID,
        zkba_class=_FIXTURE_ZKBA_CLASS,
        proof_weight=_FIXTURE_PROOF_WEIGHT,
        visual_state=_FIXTURE_VISUAL_STATE,
        capture_mode=_FIXTURE_CAPTURE_MODE,
        integrity_label=_FIXTURE_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_MANIFEST_HASH,
        inputs={"ts_ns": _FIXTURE_TS_NS},
        output_dir=output_dir,
        html_renderer=html_renderer,
    )


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-1 — Schema literal pinned and distinct
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_1_schema_literal_pinned_and_distinct():
    """vapi-vpm-artifact-v1 must be a distinct schema from
    vapi-zkba-manifest-v1 (ZKBA projection) and vapi-vpm-manifest-v1 (wrapper)."""
    assert _VPM_ARTIFACT_SCHEMA == "vapi-vpm-artifact-v1"
    # Distinct from wrapper schema (different ref the compiler holds)
    assert _VPM_WRAPPER_SCHEMA_REF == "vapi-vpm-manifest-v1"
    assert _VPM_ARTIFACT_SCHEMA != _VPM_WRAPPER_SCHEMA_REF
    # Distinct from ZKBA manifest schema (compile_artifact's schema)
    from vsd_ui_compiler import _MANIFEST_SCHEMA
    assert _MANIFEST_SCHEMA == "vapi-zkba-manifest-v1"
    assert _VPM_ARTIFACT_SCHEMA != _MANIFEST_SCHEMA
    # 9-field Integrity Label set pinned
    assert _VPM_INTEGRITY_LABEL_FIELDS == (
        "proof_type", "capture_mode", "raw_biometrics_exposed",
        "consent_active", "zk_verified", "on_chain_anchor",
        "proof_weight", "revocation_status", "limitations",
    )
    # 6-element visual states pinned
    assert _VPM_VISUAL_STATES == (
        "live", "dry-run", "emulated", "frozen-disabled", "revoked", "unverified",
    )
    # 5-element capture modes pinned
    assert _VPM_CAPTURE_MODES == (
        "live", "dry-run", "emulated", "demo", "frozen-disabled",
    )


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-2 — End-to-end happy path
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_2_end_to_end_happy_path(tmp_path):
    """compile_vpm_artifact() writes HTML + .vpm.manifest.json, returns
    well-formed VPMArtifactManifest; emitted HTML contains all 9 Integrity
    Label markers; output_hash_hex matches SHA-256 of emitted bytes;
    integrity_label_hash_hex matches SHA-256 of canonical_json(label)."""
    manifest = compile_vpm_artifact(**_make_kwargs(output_dir=tmp_path / "vpm_out"))

    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == _FIXTURE_VPM_ID
    assert manifest.zkba_class == int(ZKBAClass.GIC)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.visual_state == "live"
    assert manifest.capture_mode == "live"
    assert manifest.wrapper_schema == _VPM_WRAPPER_SCHEMA_REF
    assert manifest.zkba_manifest_hash_hex == _FIXTURE_ZKBA_MANIFEST_HASH
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == _FIXTURE_TS_NS
    assert len(manifest.output_hash_hex) == 64
    assert len(manifest.input_commitment_hex) == 64
    assert len(manifest.integrity_label_hash_hex) == 64

    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    # Output hash matches
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex
    # Integrity label hash matches canonical-JSON of label
    expected_label_hash = hashlib.sha256(
        canonical_json(_FIXTURE_INTEGRITY_LABEL)
    ).hexdigest()
    assert manifest.integrity_label_hash_hex == expected_label_hash
    # All 9 Integrity Label markers present in emitted HTML
    for field in _VPM_INTEGRITY_LABEL_FIELDS:
        assert f'data-vpm-field="{field}"' in html_bytes.decode("utf-8")

    # Sidecar exists and is canonical JSON
    sidecar_path = html_path.with_name(html_path.stem + ".vpm.manifest.json")
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["schema"] == _VPM_ARTIFACT_SCHEMA
    assert sidecar["vpm_id"] == _FIXTURE_VPM_ID


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-3 — Two-build byte-stable determinism
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_3_two_build_byte_stable_determinism(tmp_path):
    """Same inputs to two independent compilations produce byte-identical
    HTML output + identical manifest fields. Plan §3 Stream A.0 item 8."""
    out_a = tmp_path / "build_a"
    out_b = tmp_path / "build_b"
    m_a = compile_vpm_artifact(**_make_kwargs(output_dir=out_a))
    m_b = compile_vpm_artifact(**_make_kwargs(output_dir=out_b))

    bytes_a = Path(m_a.output_path).read_bytes()
    bytes_b = Path(m_b.output_path).read_bytes()
    assert bytes_a == bytes_b
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex
    assert m_a.integrity_label_hash_hex == m_b.integrity_label_hash_hex


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-4 — Forbidden external URL https?:// rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_4_external_url_rejected(tmp_path):
    """Renderer emitting `https://cdn.example.com/style.css` reference must
    be rejected with VPMComplianceError before file is written."""
    def renderer_with_external_url(inputs):
        html = _compliant_renderer(inputs)
        # Inject a forbidden external URL (a comment is enough — the regex
        # is global over the body)
        return html.replace(
            "<title>HONESTY BOARD VPM</title>",
            "<title>HONESTY BOARD VPM</title>\n  <!-- https://cdn.example.com/x -->",
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t4",
                html_renderer=renderer_with_external_url,
            )
        )
    assert "external URL" in str(excinfo.value)
    # No HTML file should have been written
    assert not (tmp_path / "vpm_t4").exists() or \
        not any((tmp_path / "vpm_t4").glob("*.html"))


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-5 — Forbidden <script src=> rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_5_external_script_src_rejected(tmp_path):
    """Renderer emitting <script src="..."> must be rejected.

    Note: the test uses a relative (non-http) src so this isolates the
    `<script src=` guard from the `https?://` guard exercised in T-4.
    """
    def renderer_with_script_src(inputs):
        html = _compliant_renderer(inputs)
        return html.replace(
            "</head>",
            "  <script src=\"local.js\"></script>\n</head>",
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t5",
                html_renderer=renderer_with_script_src,
            )
        )
    assert "external script src" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-6 — Forbidden runtime fetch() rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_6_runtime_fetch_rejected(tmp_path):
    """Inline JS calling fetch(...) must be rejected (no runtime network)."""
    def renderer_with_fetch(inputs):
        html = _compliant_renderer(inputs)
        return html.replace(
            "</body>",
            "  <script>fetch('data.json');</script>\n</body>",
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t6",
                html_renderer=renderer_with_fetch,
            )
        )
    assert "fetch()" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-7 — Forbidden Math.random() rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_7_runtime_random_rejected(tmp_path):
    """Inline JS calling Math.random() must be rejected (no runtime randomness)."""
    def renderer_with_random(inputs):
        html = _compliant_renderer(inputs)
        return html.replace(
            "</body>",
            "  <script>var x = Math.random();</script>\n</body>",
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t7",
                html_renderer=renderer_with_random,
            )
        )
    assert "Math.random()" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-8 — Forbidden Date.now() rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_8_runtime_wallclock_rejected(tmp_path):
    """Inline JS calling Date.now() must be rejected (no runtime wall-clock)."""
    def renderer_with_dateNow(inputs):
        html = _compliant_renderer(inputs)
        return html.replace(
            "</body>",
            "  <script>var t = Date.now();</script>\n</body>",
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t8",
                html_renderer=renderer_with_dateNow,
            )
        )
    assert "Date.now()" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-9 — Missing Integrity Label container rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_9_missing_integrity_label_container_rejected(tmp_path):
    """Renderer producing HTML without the
    `<div class="vpm-integrity-label">` container must be rejected."""
    def renderer_without_container(inputs):
        html = _compliant_renderer(inputs)
        # Strip the container class
        return html.replace(
            "class=\"vpm-integrity-label\"",
            "class=\"some-other-class\"",
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t9",
                html_renderer=renderer_without_container,
            )
        )
    assert "Integrity Label container" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T-VPM-COMPILER-10 — Missing per-field marker rejected
# ---------------------------------------------------------------------------

def test_t_vpm_compiler_10_missing_perfield_marker_rejected(tmp_path):
    """Renderer missing one of the 9 required `data-vpm-field=` markers
    must be rejected; error must list the specific missing field(s)."""
    def renderer_missing_proof_type_field(inputs):
        html = _compliant_renderer(inputs)
        # Strip just one of the 9 field markers
        return html.replace(
            'data-vpm-field="proof_type"',
            'data-vpm-field="some_other_field"',
        )

    with pytest.raises(VPMComplianceError) as excinfo:
        compile_vpm_artifact(
            **_make_kwargs(
                output_dir=tmp_path / "vpm_t10",
                html_renderer=renderer_missing_proof_type_field,
            )
        )
    msg = str(excinfo.value)
    assert "data-vpm-field=\"proof_type\"" in msg
    # Should specifically call out the missing field name, not a generic error
    assert "proof_type" in msg
