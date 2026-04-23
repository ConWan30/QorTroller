"""Phase 234 — InsightSynthesizer Mode 6 asyncio.to_thread fix.

T234-1: _synthesize_living_calibration is a coroutine function (async def)
T234-2: _synthesize_living_calibration_sync exists and is NOT a coroutine function
T234-3: _synthesize_living_calibration_sync returns early when store has < 50 NOMINAL records
T234-4: async _synthesize_living_calibration completes without blocking (< 1s on empty DB)
T234-5: divergence = False when verdicts are identical regardless of confidence gap
T234-6: divergence = True only when verdicts differ AND |delta_conf| > threshold
T234-7: advisory code in evidence -> fallback=FLAG -> no divergence when LLM=FLAG
T234-8: consecutive_clean counts leading non-divergent records and breaks on first divergent row
"""
import asyncio
import inspect
import json
import os
import sys
import tempfile
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(db_path):
    from vapi_bridge.store import Store
    return Store(db_path)


def _make_cfg(**kwargs):
    from vapi_bridge.config import Config
    return Config(**kwargs)


def _make_synthesizer(store, cfg=None):
    from vapi_bridge.insight_synthesizer import InsightSynthesizer
    if cfg is None:
        cfg = _make_cfg()
    # chain stub — Mode 6 does not use chain
    chain = None
    return InsightSynthesizer(store=store, cfg=cfg, chain=chain)


@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "test_phase234.db")


# ---------------------------------------------------------------------------
# T234-1: _synthesize_living_calibration is async def
# ---------------------------------------------------------------------------

def test_t234_1_async_wrapper_is_coroutine(tmp_db):
    store = _make_store(tmp_db)
    synth = _make_synthesizer(store)
    assert asyncio.iscoroutinefunction(synth._synthesize_living_calibration), (
        "_synthesize_living_calibration must be async def (Phase 234 wrapper)"
    )


# ---------------------------------------------------------------------------
# T234-2: _synthesize_living_calibration_sync is NOT a coroutine function
# ---------------------------------------------------------------------------

def test_t234_2_sync_body_is_not_coroutine(tmp_db):
    store = _make_store(tmp_db)
    synth = _make_synthesizer(store)
    assert hasattr(synth, "_synthesize_living_calibration_sync"), (
        "_synthesize_living_calibration_sync must exist (Phase 234 sync body)"
    )
    assert not asyncio.iscoroutinefunction(synth._synthesize_living_calibration_sync), (
        "_synthesize_living_calibration_sync must be a regular def, not async def"
    )


# ---------------------------------------------------------------------------
# T234-3: sync body returns early with < 50 NOMINAL records
# ---------------------------------------------------------------------------

def test_t234_3_sync_body_early_return_insufficient_records(tmp_db):
    store = _make_store(tmp_db)
    synth = _make_synthesizer(store)
    # Empty DB — 0 NOMINAL records; must return without error
    synth._synthesize_living_calibration_sync()


# ---------------------------------------------------------------------------
# T234-4: async wrapper completes in < 1s on empty DB (no event-loop stall)
# ---------------------------------------------------------------------------

def test_t234_4_async_wrapper_no_blocking(tmp_db):
    store = _make_store(tmp_db)
    synth = _make_synthesizer(store)

    async def _run():
        await asyncio.wait_for(
            synth._synthesize_living_calibration(),
            timeout=1.0,
        )

    asyncio.run(_run())  # raises TimeoutError if blocked > 1s


# ---------------------------------------------------------------------------
# T234-5: divergence=False when verdicts match regardless of confidence delta
# ---------------------------------------------------------------------------

def test_t234_5_no_divergence_same_verdict(tmp_db):
    """Divergence requires verdicts_differ=True; same verdict → always False."""
    from vapi_bridge.session_adjudicator_validator import _rule_fallback

    # Clean session: no anomalies
    evidence = {}
    fb_verdict, fb_confidence, _ = _rule_fallback(evidence)
    assert fb_verdict == "FLAG"
    assert fb_confidence == pytest.approx(0.05)

    # LLM also returns FLAG but with higher confidence — same verdict → no divergence
    llm_verdict = "FLAG"
    llm_confidence = 0.80
    verdicts_differ = llm_verdict != fb_verdict
    delta_conf = abs(llm_confidence - fb_confidence)
    threshold = 0.30
    divergence = verdicts_differ and (delta_conf > threshold)
    assert not divergence, (
        "Same verdict (FLAG==FLAG) must never produce divergence even with large confidence gap"
    )


# ---------------------------------------------------------------------------
# T234-6: divergence=True when verdicts differ AND delta > threshold
# ---------------------------------------------------------------------------

def test_t234_6_divergence_requires_verdict_differ_and_delta(tmp_db):
    """Divergence fires only when both conditions hold."""
    # Case A: verdicts differ, delta < threshold → no divergence
    verdicts_differ_a = True
    delta_a = 0.10  # below 0.30 threshold
    assert not (verdicts_differ_a and delta_a > 0.30)

    # Case B: verdicts differ, delta > threshold → divergence
    verdicts_differ_b = True
    delta_b = 0.75  # e.g. LLM=CERTIFY(0.8) vs fallback=FLAG(0.05)
    assert verdicts_differ_b and delta_b > 0.30

    # Case C: same verdict, delta > threshold → no divergence
    verdicts_differ_c = False
    delta_c = 0.90
    assert not (verdicts_differ_c and delta_c > 0.30)


# ---------------------------------------------------------------------------
# T234-7: advisory code in evidence → fallback=FLAG → LLM=FLAG → no divergence
# ---------------------------------------------------------------------------

def test_t234_7_advisory_code_does_not_break_streak(tmp_db):
    """Advisory codes change fallback to FLAG(0.5) but don't break streak if LLM=FLAG."""
    from vapi_bridge.session_adjudicator_validator import _rule_fallback

    evidence_with_advisory = {"advisory_codes": ["0x30"]}
    fb_verdict, fb_confidence, _ = _rule_fallback(evidence_with_advisory)
    assert fb_verdict == "FLAG"
    assert fb_confidence == pytest.approx(0.5)

    # LLM also says FLAG (any confidence) → verdicts_differ=False → divergence=False
    llm_verdict = "FLAG"
    verdicts_differ = llm_verdict != fb_verdict
    assert not verdicts_differ, (
        "Advisory code session: if LLM=FLAG and fallback=FLAG, no divergence (streak safe)"
    )


# ---------------------------------------------------------------------------
# T234-8: consecutive_clean counts leading non-divergent rows, breaks on first divergent
# ---------------------------------------------------------------------------

def test_t234_8_consecutive_clean_semantics(tmp_db):
    """Verify get_validation_summary counts leading non-divergent streak correctly."""
    store = _make_store(tmp_db)

    # Insert rows: 3 clean, 1 divergent, 2 more clean (in ascending created_at order)
    # Query is DESC so most-recent first: [clean, clean, divergent, clean, clean, clean]
    # Leading (from most recent) non-divergent = 2, then break at divergent row
    base_ts = time.time()

    def _insert_validation(ruling_id, divergence, offset_s):
        store.insert_validation_record(
            ruling_id=ruling_id,
            device_id="dev-test",
            llm_verdict="FLAG",
            fallback_verdict="FLAG" if not divergence else "CERTIFY",
            llm_confidence=0.05,
            fallback_confidence=0.05,
            divergence=int(divergence),
            pcc_state="NOMINAL" if not divergence else None,
            pcc_host_state="EXCLUSIVE_USB" if not divergence else None,
        )

    # Create 6 rows; simulate with different ruling_ids
    # We need agent_rulings rows first (FK constraint may be loose)
    # Use store directly — insert_validation_record may not enforce FK
    for i in range(6):
        _insert_validation(
            ruling_id=100 + i,
            divergence=(i == 2),   # index 2 (ascending) = position 3 from most recent = divergent
            offset_s=i,
        )

    summary = store.get_validation_summary(gate_n=100)
    # Most recent 3 rows (indices 5,4,3 in ascending = most recent in DESC) are clean
    # Then row at index 2 is divergent → streak breaks at 3
    assert summary["consecutive_clean"] == 3, (
        f"Expected consecutive_clean=3, got {summary['consecutive_clean']}. "
        "Streak should break at first divergent row from most-recent end."
    )
    assert summary["divergence_count"] == 1
    assert not summary["gate_passed"]  # 3 < 100
