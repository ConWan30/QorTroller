"""Phase O4-VPM-INTEGRATION Stream A.1.c — CDRR DAG VPM tests.

Test band:
  T-VPM-CDRR-1:  compiler ID + ZKBA class + proof weight pinning
                 (under HONESTY-BOARD-v1 umbrella per VBDIP-0002A §10 discipline)
  T-VPM-CDRR-2:  end-to-end happy path (state=live; manifest + HTML)
  T-VPM-CDRR-3:  rebuild idempotency
  T-VPM-CDRR-4:  byte-stable determinism across two builds
  T-VPM-CDRR-5:  all 7 ZKBAClass nodes present in emitted SVG with
                 data-cdrr-node markers + lane attribution
  T-VPM-CDRR-6:  FROZEN 5-edge composition lattice integrity — each edge
                 must appear in emitted SVG with correct child->parent
                 direction
  T-VPM-CDRR-7:  CFSS lane attribution per node — each node carries
                 data-cdrr-lane matching the canonical assignment
                 (Sentry/Guardian/Curator)
  T-VPM-CDRR-8:  inline SVG only — no <link>, no <script>, no http://,
                 no @import in emitted output (defense-in-depth against
                 the compiler discipline guards)
  T-VPM-CDRR-9:  zkba_manifest_hash_hex binding (changes input_commitment)
  T-VPM-CDRR-10: per-edge-list <li> markers present for accessibility
                 (data-cdrr-edge= markers in HTML body, not just SVG)

Plus T-VPM-GRAMMAR-1..6 parametrized over CDRR DAG.

Author: VAPI Architect (Phase O4 Commit 4)
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_BRIDGE = os.path.normpath(os.path.join(_REPO, "bridge"))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import VPMArtifactManifest, _VPM_ARTIFACT_SCHEMA  # noqa: E402
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    VISUAL_STATE_SIGNATURES,
    META_TAG_SIGNATURE,
    ARIA_LABEL_SIGNATURE,
)
from vpm_compile_cdrr_dag import (  # noqa: E402
    CDRR_NODES,
    CDRR_EDGES,
    _VPM_ID,
    _CDRR_INTERNAL_ID,
    build_cdrr_dag_artifact,
)


_INTEGRITY_LABEL = {
    "proof_type":             "VPM-CDRR-DAG",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        False,
    "proof_weight":           "CHAIN_ONLY",
    "revocation_status":      "active",
    "limitations":            ["Topology-only projection"],
}

_FIXTURE_TS_NS = 1779200000000000000
_FIXTURE_ZKBA_HASH = "e" * 64


def _kwargs(**overrides) -> dict:
    base = dict(
        integrity_label=_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH,
        visual_state="live",
        capture_mode="live",
        ts_ns=_FIXTURE_TS_NS,
    )
    base.update(overrides)
    return base


def test_t_vpm_cdrr_1_compiler_identifiers_pinned():
    """Under HONESTY-BOARD-v1 §10 umbrella; internal ID CDRR-DAG-v1."""
    assert _VPM_ID == "HONESTY-BOARD-v1"
    assert _CDRR_INTERNAL_ID == "CDRR-DAG-v1"


def test_t_vpm_cdrr_2_end_to_end_happy_path(tmp_path):
    manifest = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t2"))
    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == "HONESTY-BOARD-v1"
    assert manifest.zkba_class == int(ZKBAClass.HARDWARE)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    html_bytes = Path(manifest.output_path).read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex


def test_t_vpm_cdrr_3_rebuild_idempotent(tmp_path):
    out = tmp_path / "cdrr_t3"
    m1 = build_cdrr_dag_artifact(**_kwargs(output_dir=out))
    m2 = build_cdrr_dag_artifact(**_kwargs(output_dir=out))
    assert m1.output_path == m2.output_path
    assert m1.output_hash_hex == m2.output_hash_hex


def test_t_vpm_cdrr_4_byte_stable_two_runs(tmp_path):
    m_a = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_a"))
    m_b = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_b"))
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


def test_t_vpm_cdrr_5_all_7_nodes_present_in_svg(tmp_path):
    """Every ZKBAClass value must appear as a data-cdrr-node marker in
    emitted SVG. 7-of-7 coverage at the projection layer."""
    manifest = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t5"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert len(CDRR_NODES) == 7
    for node_id in CDRR_NODES:
        marker = f'data-cdrr-node="{node_id}"'
        assert marker in html_text, f"missing node marker {marker} in CDRR SVG"


def test_t_vpm_cdrr_6_frozen_5_edge_composition_lattice(tmp_path):
    """The FROZEN 5-edge composition lattice must appear in emitted SVG
    with each edge's child->parent direction explicit via data-cdrr-child
    and data-cdrr-parent attributes."""
    manifest = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t6"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert len(CDRR_EDGES) == 5
    expected_edges = {
        ("MARKET",     "AIT"),
        ("MARKET",     "CONSENT"),
        ("TOURNAMENT", "GIC"),
        ("TOURNAMENT", "HARDWARE"),
        ("TOURNAMENT", "VHP"),
    }
    assert set(CDRR_EDGES) == expected_edges, "CDRR_EDGES drifted from FROZEN"
    for child, parent in expected_edges:
        marker = f'data-cdrr-child="{child}" data-cdrr-parent="{parent}"'
        assert marker in html_text, (
            f"missing edge marker {marker} in CDRR SVG"
        )


def test_t_vpm_cdrr_7_cfss_lane_attribution_per_node(tmp_path):
    """Each node's data-cdrr-lane attribute matches the canonical CFSS lane
    assignment (Sentry: 5 / Guardian: 1 / Curator: 1)."""
    manifest = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t7"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    expected = {
        "AIT":        "sentry",
        "GIC":        "sentry",
        "VHP":        "sentry",
        "HARDWARE":   "sentry",
        "CONSENT":    "guardian",
        "TOURNAMENT": "sentry",
        "MARKET":     "curator",
    }
    for node_id, lane in expected.items():
        marker = (f'data-cdrr-node="{node_id}" data-cdrr-lane="{lane}"')
        assert marker in html_text, (
            f"missing lane attribution {marker} in CDRR SVG"
        )
    # Lane count sanity
    sentry_count = sum(1 for v in expected.values() if v == "sentry")
    guardian_count = sum(1 for v in expected.values() if v == "guardian")
    curator_count = sum(1 for v in expected.values() if v == "curator")
    assert (sentry_count, guardian_count, curator_count) == (5, 1, 1)


def test_t_vpm_cdrr_8_inline_only_no_external_resources(tmp_path):
    """Defense in depth: emitted HTML contains no http://, no <link rel=>,
    no <script src=>, no @import. The compiler-discipline guard already
    enforces this and would have raised VPMComplianceError if any were
    present; this test asserts the renderer's output cleanly."""
    manifest = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t8"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert "http://" not in html_text
    assert "https://" not in html_text
    assert "<link rel=" not in html_text
    assert "<script src=" not in html_text
    assert "@import" not in html_text


def test_t_vpm_cdrr_9_zkba_manifest_hash_binding(tmp_path):
    base = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t9_base"))
    rebound = build_cdrr_dag_artifact(**_kwargs(
        zkba_manifest_hash_hex="f" * 64,
        output_dir=tmp_path / "cdrr_t9_rebound",
    ))
    assert base.input_commitment_hex != rebound.input_commitment_hex


def test_t_vpm_cdrr_10_per_edge_list_markers_for_accessibility(tmp_path):
    """In addition to the SVG data-cdrr-edge markers, the HTML must contain
    an accessible <ul> with <li data-cdrr-edge="<child>-to-<parent>"> entries
    for each edge — machine-readable + screen-reader-friendly."""
    manifest = build_cdrr_dag_artifact(**_kwargs(output_dir=tmp_path / "cdrr_t10"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for child, parent in CDRR_EDGES:
        marker = f'data-cdrr-edge="{child}-to-{parent}"'
        assert marker in html_text, (
            f"missing accessible edge list marker {marker} in CDRR HTML"
        )


@pytest.mark.parametrize("state", VISUAL_STATES, ids=list(VISUAL_STATES))
def test_t_vpm_grammar_cdrr_dom_signature(state, tmp_path):
    """T-VPM-GRAMMAR-N (CDRR DAG): emitted HTML for visual_state=N must
    contain all canonical signature substrings."""
    capture_mode_map = {
        "live": "live", "dry-run": "dry-run", "emulated": "emulated",
        "frozen-disabled": "frozen-disabled", "revoked": "live", "unverified": "demo",
    }
    manifest = build_cdrr_dag_artifact(**_kwargs(
        visual_state=state,
        capture_mode=capture_mode_map[state],
        output_dir=tmp_path / f"cdrr_grammar_{state}",
    ))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for required in VISUAL_STATE_SIGNATURES[state]:
        assert required in html_text, (
            f"state={state}: missing DOM signature substring {required!r} "
            f"in CDRR DAG emitted HTML"
        )
    assert META_TAG_SIGNATURE in html_text
    assert ARIA_LABEL_SIGNATURE in html_text
    assert f'content="{state}"' in html_text
