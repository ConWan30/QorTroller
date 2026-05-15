"""Phase 235-EVENTLOOP — Event-loop blocking fixes.

T235-EL-1: _synthesis_cycle has >= 6 asyncio.sleep(0) yield points between modes.
T235-EL-2: idx_records_inference_ts index exists in the DB schema.
T235-EL-3: CorpusDataCuratorAgent.run has asyncio.sleep(30) startup delay.
"""
import inspect
import sqlite3
import sys
import tempfile
import os
from pathlib import Path

import pytest

# sys.path setup — matches the convention used across bridge/tests.
# Without this, `from vapi_bridge.X` fails because pytest
# --import-mode=importlib does not add the test file's parent dirs.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# T235-EL-1 — Synthesis cycle yield points
# ---------------------------------------------------------------------------

def test_synthesis_cycle_has_yield_points():
    """_synthesis_cycle must have >= 6 asyncio.sleep(0) calls between mode awaits."""
    from vapi_bridge.insight_synthesizer import InsightSynthesizer
    src = inspect.getsource(InsightSynthesizer._synthesis_cycle)
    # Count occurrences of the exact yield pattern
    count = src.count("await asyncio.sleep(0)")
    assert count >= 6, (
        f"_synthesis_cycle has {count} asyncio.sleep(0) yield points; expected >= 6. "
        "Each sync-body mode must yield to the event loop to prevent HTTP timeouts."
    )


# ---------------------------------------------------------------------------
# T235-EL-2 — records(inference, timestamp_ms DESC) index
# ---------------------------------------------------------------------------

def test_records_inference_ts_index_exists():
    """idx_records_inference_ts must be created by _init_schema()."""
    # Use mkdtemp (not TemporaryDirectory) — WAL files cause PermissionError on Windows cleanup
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_idx.db")
    from vapi_bridge.store import Store
    store = Store(db_path=db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='index' AND name='idx_records_inference_ts'"
    ).fetchone()
    conn.close()

    assert row is not None, (
        "idx_records_inference_ts not found in sqlite_master. "
        "get_nominal_records_for_calibration will full-scan 192k+ rows at cold start."
    )
    assert "inference" in row[1].lower(), (
        f"Index SQL does not reference 'inference' column: {row[1]}"
    )
    assert "timestamp_ms" in row[1].lower(), (
        f"Index SQL does not reference 'timestamp_ms' column: {row[1]}"
    )


# ---------------------------------------------------------------------------
# T235-EL-3 — CorpusDataCuratorAgent startup delay
# ---------------------------------------------------------------------------

def test_curator_has_startup_delay():
    """CorpusDataCuratorAgent.run must sleep 30s before first _run_once call."""
    from vapi_bridge.corpus_curator_agent import CorpusDataCuratorAgent
    src = inspect.getsource(CorpusDataCuratorAgent.run)

    assert "asyncio.sleep(30)" in src, (
        "CorpusDataCuratorAgent.run does not contain asyncio.sleep(30). "
        "Without a startup delay the agent's 7 sync tasks compete with Uvicorn "
        "warmup and block HTTP request handling immediately at bridge start."
    )

    # Verify the sleep appears BEFORE the while True loop (i.e., before _run_once)
    sleep_pos = src.index("asyncio.sleep(30)")
    run_once_pos = src.index("_run_once")
    assert sleep_pos < run_once_pos, (
        "asyncio.sleep(30) must appear before the first _run_once call in run(). "
        f"sleep at char {sleep_pos}, _run_once at char {run_once_pos}."
    )
