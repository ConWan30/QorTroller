"""F-COMPOSE-2 — chunked eth_getLogs scanner tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.eth_logs_chunked import (
    ChunkedLogScanResult,
    LogScanOutcome,
    scan_event_logs_chunked,
)


class TestScanEventLogsChunked:
    def test_accumulates_logs_across_three_chunks(self):
        calls: list[tuple[int, int]] = []

        def fetch(start: int, end: int) -> list:
            calls.append((start, end))
            if start == 1000:
                return [{"block": 1000}]
            if start == 2000:
                return [{"block": 2000}, {"block": 2001}]
            if start == 3000:
                return [{"block": 3000}]
            return []

        result = scan_event_logs_chunked(
            fetch,
            from_block=1000,
            to_block=3500,
            chunk_size=1000,
        )
        assert result.outcome == LogScanOutcome.SCAN_COMPLETE_FOUND
        assert len(result.logs) == 4
        assert calls == [(1000, 1999), (2000, 2999), (3000, 3500)]

    def test_empty_scan_complete_empty(self):
        result = scan_event_logs_chunked(
            lambda _s, _e: [],
            from_block=43947835,
            to_block=43948834,
            chunk_size=1000,
        )
        assert result.outcome == LogScanOutcome.SCAN_COMPLETE_EMPTY
        assert result.logs == ()
        assert result.error is None

    def test_chunk_failure_after_retries_is_scan_failed(self):
        calls = {"n": 0}

        def fetch(start: int, end: int) -> list:
            calls["n"] += 1
            if start >= 2000:
                raise RuntimeError("range exceeds the limit")
            return []

        result = scan_event_logs_chunked(
            fetch,
            from_block=1000,
            to_block=2999,
            chunk_size=1000,
            max_retries=2,
            retry_backoff_s=0.0,
        )
        assert result.outcome == LogScanOutcome.SCAN_FAILED
        assert "range exceeds" in (result.error or "")
        assert calls["n"] >= 3  # first chunk OK + retries on second chunk

    def test_chunk_size_1000_hop_count(self):
        from_block = 43947835
        to_block = 43947835 + 2500 - 1  # 2500 blocks => 3 hops at size 1000
        hops: list[tuple[int, int]] = []

        def fetch(start: int, end: int) -> list:
            hops.append((start, end))
            return []

        scan_event_logs_chunked(
            fetch,
            from_block=from_block,
            to_block=to_block,
            chunk_size=1000,
        )
        assert len(hops) == 3
        assert hops[0] == (from_block, from_block + 999)
        assert hops[1] == (from_block + 1000, from_block + 1999)
        assert hops[2] == (from_block + 2000, to_block)
