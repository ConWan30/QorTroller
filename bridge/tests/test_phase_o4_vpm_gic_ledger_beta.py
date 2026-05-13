"""Phase O4-VPM-INTEGRATION Stream A.1.d — GIC Continuity Ledger Beta tests.

Test band:
  T-VPM-GIC-1: compiler ID + ZKBA class + proof weight pinning
  T-VPM-GIC-2: end-to-end happy path (GIC_100 fixture; Phase 239 G3 anchor)
  T-VPM-GIC-3: rebuild idempotency
  T-VPM-GIC-4: byte-stable two-build determinism
  T-VPM-GIC-5: chain length surfaces in HTML body + GIC_100 milestone badge
               appears at chain_length >= 100
  T-VPM-GIC-6: chain head + genesis hashes surface in HTML body with
               data-gic-head / data-gic-genesis markers
  T-VPM-GIC-7: on-chain anchor status surfaces correctly (ANCHORED vs
               NOT ON CHAIN) per data-gic-on-chain marker
  T-VPM-GIC-8: invalid hex inputs (wrong length / non-hex chars) raise
               ValueError before disk write

Plus T-VPM-GRAMMAR-1..6 parametrized over GIC Ledger Beta.

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
from vpm_compile_gic_ledger_beta import (  # noqa: E402
    _VPM_ID,
    _GIC_BETA_INTERNAL_ID,
    build_gic_ledger_beta_artifact,
)


# Canonical fixtures: GIC_100 head + genesis from Phase 239 G3 (on-chain
# permanently anchored 2026-05-06 tx 0xe807347eb...)
_FIXTURE_HEAD = "0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da"
_FIXTURE_GENESIS = "87ce52cd21f9037730262debd4d247a76a6439bb754d9219fe10346ee1278c05"
_FIXTURE_TX = "0xe807347eb837a2ac9db0da51de7ddba5952a3e0e2509e197d9cac3375d23aa23"
_FIXTURE_BLOCK = 43348052
_FIXTURE_GENESIS_TS = 1777142267690827300
_FIXTURE_SESSION = "grind_phase235_v1"

_INTEGRITY_LABEL = {
    "proof_type":             "VPM-GIC-LEDGER-BETA",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        True,
    "proof_weight":           "CHAIN_ONLY",
    "revocation_status":      "active",
    "limitations":            ["Promotion of Phase O3 Alpha projection"],
}

_FIXTURE_TS_NS = 1779300000000000000
_FIXTURE_ZKBA_HASH = "1" * 64


def _kwargs(**overrides) -> dict:
    base = dict(
        gic_chain_head_hex=_FIXTURE_HEAD,
        gic_chain_length=100,
        gic_genesis_hash_hex=_FIXTURE_GENESIS,
        gic_genesis_ts_ns=_FIXTURE_GENESIS_TS,
        on_chain_anchor_tx_hash=_FIXTURE_TX,
        on_chain_anchor_block=_FIXTURE_BLOCK,
        grind_session_id=_FIXTURE_SESSION,
        integrity_label=_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH,
        visual_state="live",
        capture_mode="live",
        ts_ns=_FIXTURE_TS_NS,
    )
    base.update(overrides)
    return base


def test_t_vpm_gic_1_compiler_identifiers_pinned():
    assert _VPM_ID == "HONESTY-BOARD-v1"
    assert _GIC_BETA_INTERNAL_ID == "GIC-LEDGER-BETA-v1"


def test_t_vpm_gic_2_end_to_end_happy_path(tmp_path):
    manifest = build_gic_ledger_beta_artifact(**_kwargs(output_dir=tmp_path / "gic_t2"))
    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == _VPM_ID
    assert manifest.zkba_class == int(ZKBAClass.GIC)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    html_bytes = Path(manifest.output_path).read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex


def test_t_vpm_gic_3_rebuild_idempotent(tmp_path):
    out = tmp_path / "gic_t3"
    m1 = build_gic_ledger_beta_artifact(**_kwargs(output_dir=out))
    m2 = build_gic_ledger_beta_artifact(**_kwargs(output_dir=out))
    assert m1.output_path == m2.output_path
    assert m1.output_hash_hex == m2.output_hash_hex


def test_t_vpm_gic_4_byte_stable_two_runs(tmp_path):
    m_a = build_gic_ledger_beta_artifact(**_kwargs(output_dir=tmp_path / "gic_a"))
    m_b = build_gic_ledger_beta_artifact(**_kwargs(output_dir=tmp_path / "gic_b"))
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


def test_t_vpm_gic_5_chain_length_milestone_badge(tmp_path):
    """At chain_length >= 100, the GIC_100 MILESTONE badge appears.
    Below 100, a plain N/100 link counter appears instead."""
    # Below threshold
    sub = build_gic_ledger_beta_artifact(**_kwargs(
        gic_chain_length=87,
        output_dir=tmp_path / "gic_t5_sub",
    ))
    sub_html = Path(sub.output_path).read_text(encoding="utf-8")
    assert "87 / 100 links" in sub_html
    assert "GIC_87 MILESTONE" not in sub_html
    # At threshold
    at_100 = build_gic_ledger_beta_artifact(**_kwargs(
        gic_chain_length=100,
        output_dir=tmp_path / "gic_t5_at",
    ))
    at_html = Path(at_100.output_path).read_text(encoding="utf-8")
    assert "GIC_100 MILESTONE" in at_html


def test_t_vpm_gic_6_chain_head_and_genesis_markers(tmp_path):
    """Both chain head and genesis hashes must appear with their
    data-gic-head / data-gic-genesis markers for programmatic verification."""
    manifest = build_gic_ledger_beta_artifact(**_kwargs(output_dir=tmp_path / "gic_t6"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert f'<code data-gic-head>{_FIXTURE_HEAD}</code>' in html_text
    assert f'<code data-gic-genesis>{_FIXTURE_GENESIS}</code>' in html_text


def test_t_vpm_gic_7_on_chain_anchor_status(tmp_path):
    """data-gic-on-chain="true" when anchored; "false" when not."""
    anchored = build_gic_ledger_beta_artifact(**_kwargs(
        output_dir=tmp_path / "gic_t7_anchored",
    ))
    anchored_html = Path(anchored.output_path).read_text(encoding="utf-8")
    assert 'data-gic-on-chain="true"' in anchored_html
    assert "ANCHORED at block 43348052" in anchored_html

    unanchored = build_gic_ledger_beta_artifact(**_kwargs(
        on_chain_anchor_tx_hash="n/a",
        on_chain_anchor_block=0,
        output_dir=tmp_path / "gic_t7_unanchored",
    ))
    unanchored_html = Path(unanchored.output_path).read_text(encoding="utf-8")
    assert 'data-gic-on-chain="false"' in unanchored_html
    assert "NOT ON CHAIN" in unanchored_html


def test_t_vpm_gic_8_invalid_hex_inputs_rejected(tmp_path):
    """Wrong-length or non-hex chain head / genesis must raise ValueError
    before any disk write."""
    # Wrong length (63 chars)
    with pytest.raises(ValueError) as ex1:
        build_gic_ledger_beta_artifact(**_kwargs(
            gic_chain_head_hex="abc" * 21,
            output_dir=tmp_path / "gic_bad1",
        ))
    assert "gic_chain_head_hex" in str(ex1.value)

    # Non-hex chars
    with pytest.raises(ValueError) as ex2:
        build_gic_ledger_beta_artifact(**_kwargs(
            gic_genesis_hash_hex="z" * 64,
            output_dir=tmp_path / "gic_bad2",
        ))
    assert "gic_genesis_hash_hex" in str(ex2.value)


@pytest.mark.parametrize("state", VISUAL_STATES, ids=list(VISUAL_STATES))
def test_t_vpm_grammar_gic_ledger_beta_dom_signature(state, tmp_path):
    """T-VPM-GRAMMAR-N (GIC LEDGER BETA): all canonical signature substrings
    for the visual state must appear in emitted HTML."""
    capture_mode_map = {
        "live": "live", "dry-run": "dry-run", "emulated": "emulated",
        "frozen-disabled": "frozen-disabled", "revoked": "live", "unverified": "demo",
    }
    manifest = build_gic_ledger_beta_artifact(**_kwargs(
        visual_state=state,
        capture_mode=capture_mode_map[state],
        output_dir=tmp_path / f"gic_grammar_{state}",
    ))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for required in VISUAL_STATE_SIGNATURES[state]:
        assert required in html_text, (
            f"state={state}: missing DOM signature substring {required!r} "
            f"in GIC LEDGER BETA emitted HTML"
        )
    assert META_TAG_SIGNATURE in html_text
    assert ARIA_LABEL_SIGNATURE in html_text
    assert f'content="{state}"' in html_text
