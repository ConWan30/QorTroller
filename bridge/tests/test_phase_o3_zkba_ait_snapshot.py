"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — AIT Separation Snapshot tests.

Third ZKBA artifact target after GIC Continuity Ledger Alpha (commit 3b3081d3)
and VHP Verification Card (commit 4f399282). Mirrors the VHP test pattern
and extends it with the first non-CHAIN_ONLY proof weight class exercise
(CALIBRATION_PLUS_CONTEXT) — proving Layer 7 holds across multiple proof
weights, not just the single-value CHAIN_ONLY profile.

T-ZKBA-AIT-1: _compose_ait_component byte layout matches FROZEN spec
T-ZKBA-AIT-2: build_ait_snapshot_artifact builds end-to-end (manifest + HTML + DB)
T-ZKBA-AIT-3: rebuild idempotent (UNIQUE constraint on commitment_hex)
T-ZKBA-AIT-4: byte-stable across two builds (determinism)
T-ZKBA-AIT-5: VPM wrapper consumes the ZKBA manifest cleanly
T-ZKBA-AIT-6: G4 manifest validator accepts the emitted manifest
              (first non-CHAIN_ONLY proof_weight through the validator)
T-ZKBA-AIT-7: per-field tamper detection (ratio / N / date / pair_distances
              each change the commitment)
T-ZKBA-AIT-8: audit harness Section 3 (CFSS) still PASSES after AIT
              snapshot inserted alongside VHP card
T-ZKBA-AIT-9: pair_distances canonical ordering invariant
              (different dict insertion order produces same component hash)
"""
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_BRIDGE = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import (  # noqa: E402
    ZKBAClass,
    ProofWeightClass,
    compute_zkba_commitment,
)
from vsd_ui_compiler import ZKBAManifest, _MANIFEST_SCHEMA, _COMPILER_VERSION  # noqa: E402
from zkba_compile_ait_snapshot import (  # noqa: E402
    _canonical_pair_distances_bytes,
    _compose_ait_component,
    build_ait_snapshot_artifact,
)


# Canonical fixture: Phase 229 + Phase 231 AIT corpus state
#   - separation_ratio  = 1.199       (TOURNAMENT BLOCKER cleared for AIT)
#   - N total           = 37          (P1=13, P2=10, P3=14; all >= 10)
#   - all pairs > 1.0   = True
#   - analysis_date     = 1745539200  (2026-04-20 UTC corpus close)
_FIXTURE_RATIO_MILLI = 1_199_000
_FIXTURE_N_SESSIONS = 37
_FIXTURE_ANALYSIS_DATE = 1745539200
_FIXTURE_ALL_PAIRS = True
_FIXTURE_PAIR_DISTANCES = {
    "P1vP2": 1.850,
    "P1vP3": 1.846,
    "P2vP3": 1.349,
}
_FIXTURE_TS_NS = 1778900000000000000


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-1: composition byte layout
# ---------------------------------------------------------------------------

def test_t_zkba_ait_1_compose_ait_component_byte_layout():
    """_compose_ait_component matches the FROZEN byte layout:
       SHA-256( ratio_milli_be(8) || n_sessions_be(8) ||
                analysis_date_be(8) || pair_distances_root(32) )"""
    out = _compose_ait_component(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
    )
    pair_bytes = _canonical_pair_distances_bytes(_FIXTURE_PAIR_DISTANCES)
    pair_root = hashlib.sha256(pair_bytes).digest()

    preimage = (
        _FIXTURE_RATIO_MILLI.to_bytes(8, "big")
        + _FIXTURE_N_SESSIONS.to_bytes(8, "big")
        + _FIXTURE_ANALYSIS_DATE.to_bytes(8, "big")
        + pair_root
    )
    assert len(preimage) == 8 + 8 + 8 + 32 == 56
    expected = hashlib.sha256(preimage).digest()
    assert out == expected
    assert len(out) == 32


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-2: end-to-end build
# ---------------------------------------------------------------------------

def test_t_zkba_ait_2_artifact_builds_end_to_end(tmp_path):
    """build_ait_snapshot_artifact produces manifest + HTML file +
    zkba_artifact_log row."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_ait_2.db")
    store = Store(db_path)
    out_dir = tmp_path / "ait_separation_snapshot"

    manifest = build_ait_snapshot_artifact(
        store=store,
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
        all_pairs_above_1=_FIXTURE_ALL_PAIRS,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.AIT)
    # First non-CHAIN_ONLY proof_weight in the pipeline
    assert manifest.proof_weight == int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT)
    assert manifest.proof_weight != int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == _FIXTURE_TS_NS
    assert len(manifest.output_hash_hex) == 64
    assert len(manifest.input_commitment_hex) == 64

    # HTML written and hash matches
    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex
    assert b"AIT Separation Snapshot" in html_bytes
    assert b"ALL PAIRS &gt; 1.0" in html_bytes or b"ALL PAIRS > 1.0" in html_bytes
    assert b"CALIBRATION_PLUS_CONTEXT" in html_bytes

    # Manifest JSON sidecar exists
    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    # DB row inserted with NULL anchor_tx_hash (Track 1 invariant)
    component = _compose_ait_component(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.AIT,
        proof_weight=ProofWeightClass.CALIBRATION_PLUS_CONTEXT,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.AIT)
    assert row["proof_weight"] == int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT)
    assert row["anchor_tx_hash"] is None


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-3: rebuild idempotency
# ---------------------------------------------------------------------------

def test_t_zkba_ait_3_rebuild_idempotent(tmp_path):
    """Building the same AIT snapshot twice yields the same manifest fields
    and a single DB row (UNIQUE on commitment_hex)."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_ait_3.db")
    store = Store(db_path)
    out_dir = tmp_path / "ait_separation_snapshot"

    kwargs = dict(
        store=store,
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
        all_pairs_above_1=_FIXTURE_ALL_PAIRS,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    m1 = build_ait_snapshot_artifact(**kwargs)
    m2 = build_ait_snapshot_artifact(**kwargs)

    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    component = _compose_ait_component(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
    )
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.AIT,
        proof_weight=ProofWeightClass.CALIBRATION_PLUS_CONTEXT,
        component_hashes=(component,),
        ts_ns=_FIXTURE_TS_NS,
    )
    with store._conn() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM zkba_artifact_log WHERE commitment_hex=?",
            (expected_zkba.hex(),),
        ).fetchone()[0]
    assert int(cnt) == 1


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-4: byte-stable determinism across two builds
# ---------------------------------------------------------------------------

def test_t_zkba_ait_4_byte_stable_two_runs(tmp_path):
    """Same inputs across two independent builds produce byte-identical HTML."""
    from vapi_bridge.store import Store

    out_a = tmp_path / "ait_a"
    out_b = tmp_path / "ait_b"

    common = dict(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
        all_pairs_above_1=_FIXTURE_ALL_PAIRS,
        ts_ns=_FIXTURE_TS_NS,
    )
    m_a = build_ait_snapshot_artifact(store=Store(str(tmp_path / "a.db")), output_dir=out_a, **common)
    m_b = build_ait_snapshot_artifact(store=Store(str(tmp_path / "b.db")), output_dir=out_b, **common)

    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.output_hash_hex == m_b.output_hash_hex
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-5: VPM wrapper consumes the ZKBA manifest
# ---------------------------------------------------------------------------

def test_t_zkba_ait_5_vpm_wrapper_consumes_manifest(tmp_path):
    """The emitted ZKBA manifest wraps cleanly into a VPM wrapper.
    First non-CHAIN_ONLY proof_weight through wrap_zkba_manifest."""
    from vapi_bridge.store import Store
    from vsd_vpm_wrapper import (
        VPMAnchorStatus,
        VPMCaptureMode,
        VPMIntegrityLabel,
        VPMRevocationStatus,
        VPMVisualState,
        VPM_WRAPPER_SCHEMA,
        VPM_WRAPPER_VERSION,
        ZKBA_WRAPPED_SCHEMA,
        wrap_zkba_manifest,
        vpm_canonical_json,
    )

    db_path = str(tmp_path / "test_ait_5.db")
    store = Store(db_path)
    out_dir = tmp_path / "ait_separation_snapshot"

    manifest = build_ait_snapshot_artifact(
        store=store,
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
        all_pairs_above_1=_FIXTURE_ALL_PAIRS,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    zkba_dict = asdict(manifest)
    assert zkba_dict["schema"] == ZKBA_WRAPPED_SCHEMA
    assert zkba_dict["proof_weight"] == int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT)

    label = VPMIntegrityLabel(
        proof_type="ZKBA-AIT",
        capture_mode=VPMCaptureMode.LIVE.value,
        raw_biometrics_exposed=False,
        consent_active=True,
        zk_verified=False,
        on_chain_anchor=False,
        proof_weight=int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT),
        revocation_status=VPMRevocationStatus.ACTIVE.value,
        limitations=(
            "Separation ratio empirical to current corpus only; "
            "subject to recompute on new session ingestion.",
        ),
    )

    wrapper = wrap_zkba_manifest(
        zkba_manifest_dict=zkba_dict,
        vpm_id="AIT-SEPARATION-SNAPSHOT-v1",
        audience="Tournament Organizers",
        source_commitment=manifest.input_commitment_hex,
        integrity_label=label,
        visual_state=VPMVisualState.LIVE,
        anchor_status=VPMAnchorStatus.NONE,
    )
    assert wrapper.schema == VPM_WRAPPER_SCHEMA
    assert wrapper.wrapper_version == VPM_WRAPPER_VERSION
    assert wrapper.zkba_manifest_schema == ZKBA_WRAPPED_SCHEMA
    assert wrapper.proof_weight == int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT)
    assert wrapper.anchor_status == VPMAnchorStatus.NONE.value
    expected_hash = hashlib.sha256(vpm_canonical_json(zkba_dict)).hexdigest()
    assert wrapper.zkba_manifest_hash == expected_hash


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-6: G4 manifest validator accepts the emitted manifest
# ---------------------------------------------------------------------------

def test_t_zkba_ait_6_g4_manifest_validator_accepts(tmp_path):
    """The emitted ZKBA manifest passes validate_zkba_manifest.
    First CALIBRATION_PLUS_CONTEXT-weight manifest through the validator."""
    from vapi_bridge.store import Store
    from zkba_manifest_validator import validate_zkba_manifest

    db_path = str(tmp_path / "test_ait_6.db")
    store = Store(db_path)
    out_dir = tmp_path / "ait_separation_snapshot"

    manifest = build_ait_snapshot_artifact(
        store=store,
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
        all_pairs_above_1=_FIXTURE_ALL_PAIRS,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )
    result = validate_zkba_manifest(asdict(manifest))
    assert result.valid, f"validator returned errors: {list(result.errors)}"


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-7: per-field tamper detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated_kwargs", [
    ("ratio_milli", {"ratio_milli": _FIXTURE_RATIO_MILLI + 1}),
    ("n_sessions", {"n_sessions": _FIXTURE_N_SESSIONS + 1}),
    ("analysis_date", {"analysis_date": _FIXTURE_ANALYSIS_DATE + 1}),
    ("pair_distances_value", {
        "pair_distances": {**_FIXTURE_PAIR_DISTANCES, "P1vP2": 1.851},
    }),
    ("pair_distances_extra_key", {
        "pair_distances": {**_FIXTURE_PAIR_DISTANCES, "P4vP5": 9.999},
    }),
])
def test_t_zkba_ait_7_tamper_detection(field, mutated_kwargs):
    """Mutating any single field changes the component hash."""
    base = dict(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
    )
    canonical = _compose_ait_component(**base)
    mutated = {**base, **mutated_kwargs}
    tampered = _compose_ait_component(**mutated)
    assert tampered != canonical, f"field {field}: tamper not detected"


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-8: audit harness CFSS still PASSES (post-VHP + post-AIT)
# ---------------------------------------------------------------------------

def test_t_zkba_ait_8_audit_harness_cfss_unchanged(tmp_path):
    """Inserting an AIT snapshot row alongside a VHP row MUST NOT affect
    Section 3 CFSS lane authority. Audit harness reads bundles directly,
    never zkba_artifact_log — structural invariant verification."""
    from vapi_bridge.store import Store
    from zkba_post_ceremony_audit import (
        EXPECTED_LANE_MATRIX,
        section_3_lane_matrix,
    )

    db_path = str(tmp_path / "test_ait_8.db")
    store = Store(db_path)
    out_dir = tmp_path / "ait_separation_snapshot"

    # Insert the AIT artifact
    build_ait_snapshot_artifact(
        store=store,
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=_FIXTURE_PAIR_DISTANCES,
        all_pairs_above_1=_FIXTURE_ALL_PAIRS,
        output_dir=out_dir,
        ts_ns=_FIXTURE_TS_NS,
    )

    bundle_dir = Path(_REPO) / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, findings = section_3_lane_matrix(bundle_dir)
    assert ok, f"CFSS regressed: {findings}"
    assert len(findings) == len(EXPECTED_LANE_MATRIX)
    for f in findings:
        assert f["status"] == "OK", f"row failed: {f}"


# ---------------------------------------------------------------------------
# T-ZKBA-AIT-9: pair_distances canonical ordering invariant
# ---------------------------------------------------------------------------

def test_t_zkba_ait_9_pair_distances_canonical_ordering():
    """Different dict insertion orders MUST produce the same component hash.
    Canonical-JSON serialization with sort_keys=True enforces this."""
    forward = {"P1vP2": 1.850, "P1vP3": 1.846, "P2vP3": 1.349}
    reversed_order = {"P2vP3": 1.349, "P1vP3": 1.846, "P1vP2": 1.850}
    out_forward = _compose_ait_component(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=forward,
    )
    out_reversed = _compose_ait_component(
        ratio_milli=_FIXTURE_RATIO_MILLI,
        n_sessions=_FIXTURE_N_SESSIONS,
        analysis_date=_FIXTURE_ANALYSIS_DATE,
        pair_distances=reversed_order,
    )
    assert out_forward == out_reversed, (
        "pair_distances ordering MUST NOT affect component hash"
    )
