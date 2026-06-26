"""Cycle-30 step-4 — NQPV study-corpus loader (RETINA-EXCL-2).

Pure tests (no DB). Covers: both row shapes (records-table vs co-capture sidecar) normalize
correctly; abstain-on-absent honesty; the controller-lobe signal is NEVER fed to fuse(); the
humanity_prob -> l4_l5_l6 proxy; binding filter; label provenance; and end-to-end fuse_record.
"""
from __future__ import annotations

from vapi_bridge.novel_presence_fusion import NQPVVerdict
from vapi_bridge.nqpv_corpus_loader import (
    LABEL_ADVERSARY,
    LABEL_HUMAN,
    NqpvCorpusRecord,
    fuse_record,
    load_from_rows,
    to_fuse_inputs,
)


# --- records-table shape (today's queryable source: only humanity_prob is live) ---

def test_records_row_derives_l4l5l6_from_humanity_and_abstains_elsewhere():
    rows = [{"device_id": "dev1", "record_hash": "h1", "pitl_humanity_prob": 0.82,
             "created_at": 1_700_000_000.0}]
    [rec] = load_from_rows(rows, default_label=LABEL_HUMAN)
    assert rec.source == "records"
    assert rec.label == LABEL_HUMAN
    assert rec.l4_l5_l6_ok is True              # 0.82 >= 0.5
    assert rec.cco_tier is None                 # abstain (not in records table)
    assert rec.poep_present is None             # abstain
    assert rec.retina_coupled_verdict is None   # abstain
    assert rec.live_oracle_count == 1           # only l4l5l6 is live
    assert rec.ts_ns == 1_700_000_000 * 1_000_000_000


def test_low_humanity_marks_l4l5l6_false():
    [rec] = load_from_rows([{"device_id": "d", "record_hash": "h", "pitl_humanity_prob": 0.3}])
    assert rec.l4_l5_l6_ok is False


def test_missing_humanity_abstains_not_false():
    [rec] = load_from_rows([{"device_id": "d", "record_hash": "h"}])
    assert rec.l4_l5_l6_ok is None              # abstain, NOT a fabricated False
    assert rec.live_oracle_count == 0


# --- co-capture sidecar shape (future, once persisted) ---

def test_cocapture_row_normalizes_full_oracle_set():
    rows = [{
        "device_id": "dev2", "record_hash": "h2",
        "nqpv_cco_tier": "P-T3", "nqpv_l4l5l6_ok": 1, "nqpv_poep_present": 0,
        "nqpv_retina_controller_signal": "CONTROLLER_CLEAN",
        "nqpv_retina_coupled_verdict": "COUPLED_CLEAN", "ts_ns": 123,
    }]
    [rec] = load_from_rows(rows, default_label=LABEL_HUMAN)
    assert rec.source == "cocapture"
    assert rec.cco_tier == "P-T3"
    assert rec.l4_l5_l6_ok is True
    assert rec.poep_present is False
    assert rec.retina_coupled_verdict == "COUPLED_CLEAN"
    assert rec.retina_controller_signal == "CONTROLLER_CLEAN"
    assert rec.live_oracle_count == 4
    assert rec.ts_ns == 123


def test_controller_lobe_signal_is_metadata_not_fed_to_fuse():
    # A row with ONLY the controller-lobe signal (no coupled verdict) must NOT produce a retina
    # presence input -- the screen lobe is genuinely not live.
    [rec] = load_from_rows([{
        "device_id": "d", "record_hash": "h",
        "nqpv_retina_controller_signal": "CONTROLLER_CLEAN",
    }])
    assert rec.retina_controller_signal == "CONTROLLER_CLEAN"
    assert rec.retina_coupled_verdict is None
    assert to_fuse_inputs(rec)["retina_report"] is None   # the load-bearing honesty assertion


# --- binding filter ---

def test_unbound_rows_dropped_by_default():
    rows = [{"record_hash": "h"}, {"device_id": "d"}, {"device_id": "d", "record_hash": "h"}]
    recs = load_from_rows(rows)
    assert len(recs) == 1
    assert recs[0].binding_ok


def test_unbound_rows_kept_when_binding_not_required():
    recs = load_from_rows([{"record_hash": "h"}], require_binding=False)
    assert len(recs) == 1
    assert not recs[0].binding_ok


# --- label provenance ---

def test_per_row_label_overrides_default():
    rows = [{"device_id": "d", "record_hash": "h", "label": LABEL_ADVERSARY}]
    [rec] = load_from_rows(rows, default_label=LABEL_HUMAN)
    assert rec.label == LABEL_ADVERSARY


# --- end-to-end: loader -> fuse() ---

def test_fuse_record_full_cocapture_is_human_verified_hardware():
    [rec] = load_from_rows([{
        "device_id": "d", "record_hash": "h",
        "nqpv_cco_tier": "P-T3", "nqpv_l4l5l6_ok": 1, "nqpv_poep_present": 1,
        "nqpv_retina_coupled_verdict": "COUPLED_CLEAN",
    }], default_label=LABEL_HUMAN)
    proof = fuse_record(rec)
    assert proof.verdict == NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE
    assert proof.presence_score >= 0.6


def test_fuse_record_partial_records_row_is_honest_partial_verdict():
    # The PILOT regime: only l4l5l6 live (humanity proxy). With a single passing oracle the score
    # is 1.0 over the present-weight set -> CONSISTENT_HUMAN (no cco -> not VERIFIED_HARDWARE).
    [rec] = load_from_rows(
        [{"device_id": "d", "record_hash": "h", "pitl_humanity_prob": 0.9}],
        default_label=LABEL_HUMAN,
    )
    proof = fuse_record(rec)
    assert proof.verdict == NQPVVerdict.CONSISTENT_HUMAN
    assert proof.cco_tier is None


def test_fuse_record_injectable_threshold_flips_partial_to_indeterminate():
    # Anti-overclaim: a stricter study-injected threshold must be able to push a partial row below
    # the bar (the operating point is the study's to set, not the loader's).
    [rec] = load_from_rows(
        [{"device_id": "d", "record_hash": "h", "pitl_humanity_prob": 0.9}],
    )
    # single oracle, score 1.0; threshold above 1.0 is impossible to clear -> INDETERMINATE
    proof = fuse_record(rec, threshold=1.01)
    assert proof.verdict == NQPVVerdict.INDETERMINATE
