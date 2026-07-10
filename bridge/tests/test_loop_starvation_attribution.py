"""D1 loop-starvation attribution ring (bridge capture-lag fix, phase D1) tests.

Pins: flag default-OFF -> timed_block does NOT append (byte-identical) · attribution ON -> a slow
timed_block lands in the ring · top_blocks names the top offenders by dur (window-filtered) · the
timed_block WARNING-on-slow behavior is unchanged when off (only the ring append is gated) · the ring is
bounded · toggle via set_attribution_enabled. D1 is diagnostic-only: no fleet/data/loop mutation.
"""
from __future__ import annotations

import logging
import time

from bridge.vapi_bridge import loop_timing as lt


def _reset():
    lt._attribution_ring.clear()
    lt.set_attribution_enabled(False)


def test_flag_toggle_and_helper():
    lt.set_attribution_enabled(False)
    assert lt.attribution_enabled() is False
    lt.set_attribution_enabled(True)
    assert lt.attribution_enabled() is True
    _reset()


def test_t1_attribution_off_no_ring_append():
    _reset()
    log = logging.getLogger("t")
    with lt.timed_block("slow_site", warn_s=0.0, logger=log):    # "slow" but flag OFF => no ring append
        pass
    assert list(lt._attribution_ring) == []                       # byte-identical: nothing recorded


def test_t2_attribution_on_records_block():
    _reset()
    lt.set_attribution_enabled(True)
    log = logging.getLogger("t")
    with lt.timed_block("curator_tick", warn_s=100.0, logger=log):
        time.sleep(0.01)
    ring = list(lt._attribution_ring)
    assert len(ring) == 1 and ring[0]["label"] == "curator_tick"
    assert ring[0]["dur_s"] >= 0.0 and "tid" in ring[0] and "wall_ns" in ring[0]
    _reset()


def test_t2b_top_blocks_names_the_top_offender():
    _reset()
    lt.set_attribution_enabled(True)
    log = logging.getLogger("t")
    with lt.timed_block("fast", warn_s=100.0, logger=log):
        pass
    with lt.timed_block("SLOW_DB_site", warn_s=100.0, logger=log):
        time.sleep(0.02)
    top = lt.top_blocks(k=1)
    assert top and top[0]["label"] == "SLOW_DB_site"              # sorted by dur desc
    _reset()


def test_top_blocks_since_window_filter():
    _reset()
    lt.set_attribution_enabled(True)
    lt._attribution_ring.append({"label": "old", "dur_s": 9.0, "tid": 1, "wall_ns": 1000})
    lt._attribution_ring.append({"label": "new", "dur_s": 0.1, "tid": 1, "wall_ns": 5000})
    assert [b["label"] for b in lt.recent_blocks(since_wall_ns=2000)] == ["new"]   # old excluded by window
    assert lt.top_blocks(k=5, since_wall_ns=2000)[0]["label"] == "new"
    _reset()


def test_off_byte_identical_warning_still_fires(caplog):
    """Flag OFF: the WARNING-on-slow behavior is unchanged; ONLY the ring append is gated."""
    _reset()
    log = logging.getLogger("byteident")
    with caplog.at_level(logging.WARNING, logger="byteident"):
        with lt.timed_block("over_thresh", warn_s=0.0, logger=log, slow_word="SLOW DB"):
            pass
    assert any("SLOW DB: over_thresh" in r.getMessage() for r in caplog.records)   # warning still emitted
    assert list(lt._attribution_ring) == []                                        # but nothing recorded


def test_ring_is_bounded():
    _reset()
    lt.set_attribution_enabled(True)
    log = logging.getLogger("t")
    for i in range(lt._ATTRIBUTION_RING_MAX + 50):
        with lt.timed_block(f"s{i}", warn_s=100.0, logger=log):
            pass
    assert len(lt._attribution_ring) == lt._ATTRIBUTION_RING_MAX   # bounded deque, no unbounded growth
    _reset()


# --- D1.1 loop-thread tid filter ----------------------------------------------------------------
def test_loop_tid_set_and_get():
    lt.set_loop_tid(None)
    assert lt.loop_tid() is None
    lt.set_loop_tid(12345)
    assert lt.loop_tid() == 12345
    lt.set_loop_tid(None)


def test_top_blocks_loop_tid_filter_excludes_worker_tid():
    """D1.1: a big worker-thread block (different tid) is dropped when loop_tid_only is set, so it
    cannot mask the real loop-thread offender — the whole point of the filter."""
    _reset()
    lt._attribution_ring.append({"label": "worker_big", "dur_s": 9.0, "tid": 999, "wall_ns": 1000})
    lt._attribution_ring.append({"label": "loop_small", "dur_s": 0.1, "tid": 42, "wall_ns": 2000})
    assert [b["label"] for b in lt.top_blocks(k=5, loop_tid_only=42)] == ["loop_small"]  # worker excluded
    assert lt.top_blocks(k=1)[0]["label"] == "worker_big"          # unfiltered, the worker dominates
    _reset()


def test_recent_blocks_loop_tid_filter():
    _reset()
    lt._attribution_ring.append({"label": "a", "dur_s": 1.0, "tid": 7, "wall_ns": 1000})
    lt._attribution_ring.append({"label": "b", "dur_s": 1.0, "tid": 8, "wall_ns": 1000})
    assert {b["label"] for b in lt.recent_blocks(loop_tid_only=7)} == {"a"}
    assert len(lt.recent_blocks()) == 2                            # unfiltered sees both
    _reset()
