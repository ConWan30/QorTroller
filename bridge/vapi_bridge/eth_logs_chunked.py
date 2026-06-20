"""Chunked eth_getLogs scanner for IoTeX RPC range limits (F-COMPOSE-2).

IoTeX testnet rejects wide ``eth_getLogs`` ranges (~1000 blocks max). This module
iterates in conservative hops and returns an explicit scan outcome so callers can
distinguish "scanned cleanly, empty" from "RPC failed mid-scan".
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class LogScanOutcome(str, Enum):
    SCAN_COMPLETE_FOUND = "SCAN_COMPLETE_FOUND"
    SCAN_COMPLETE_EMPTY = "SCAN_COMPLETE_EMPTY"
    SCAN_FAILED = "SCAN_FAILED"


@dataclass(frozen=True)
class ChunkedLogScanResult:
    outcome: LogScanOutcome
    logs: tuple[Any, ...]
    error: str | None = None


def scan_event_logs_chunked(
    fetch_chunk: Callable[[int, int], list],
    *,
    from_block: int,
    to_block: int,
    chunk_size: int = 1000,
    max_retries: int = 2,
    retry_backoff_s: float = 0.25,
) -> ChunkedLogScanResult:
    """Scan ``from_block``..``to_block`` inclusive in ``chunk_size`` hops.

    ``fetch_chunk(start, end)`` must return logs for that inclusive block range.
    Returns FOUND if any logs accumulated, EMPTY if scan completed with zero logs,
    FAILED if any chunk exhausts retries (partial logs discarded for outcome).
    """
    if from_block > to_block:
        return ChunkedLogScanResult(LogScanOutcome.SCAN_COMPLETE_EMPTY, ())

    all_logs: list[Any] = []
    start = int(from_block)
    end_limit = int(to_block)

    while start <= end_limit:
        chunk_end = min(start + chunk_size - 1, end_limit)
        attempt = 0
        while True:
            try:
                chunk_logs = fetch_chunk(start, chunk_end)
                all_logs.extend(chunk_logs)
                break
            except Exception as exc:
                attempt += 1
                if attempt > max_retries:
                    return ChunkedLogScanResult(
                        LogScanOutcome.SCAN_FAILED,
                        (),
                        error=str(exc),
                    )
                time.sleep(retry_backoff_s * attempt)
        start = chunk_end + 1

    outcome = (
        LogScanOutcome.SCAN_COMPLETE_FOUND
        if all_logs
        else LogScanOutcome.SCAN_COMPLETE_EMPTY
    )
    return ChunkedLogScanResult(outcome, tuple(all_logs))
