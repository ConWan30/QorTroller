"""Phase 131 — IoSwarmLiveNodeClient.

Dispatches evaluation requests to real HTTP ioSwarm node endpoints when
``ioswarm_node_urls`` is configured; falls back to the appropriate
IoSwarmNodeEmulator when the URL list is empty (zero behavior change).

W1: per-node timeout via asyncio.wait_for(timeout=ioswarm_node_timeout_seconds).
    Timed-out nodes are skipped and their last_seen_ts is NOT updated.
    Quorum computed only from nodes that responded within the timeout window.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_EVAL_TYPE_MAP = {
    "renewal": "renewal",
    "adjudication_classj": "adjudication_classj",
    "adjudication_triage": "adjudication_triage",
    "vhp_mint": "vhp_mint",
}


class IoSwarmLiveNodeClient:
    """HTTP client for real ioSwarm operator nodes (Phase 131).

    When ``cfg.ioswarm_node_urls`` is empty this class returns ``is_emulator_mode() == True``
    and callers fall back to their local emulator. When URLs are configured,
    ``dispatch_evaluation`` fans out HTTP POSTs to all nodes concurrently with
    per-node timeout, collects results, and updates the node registry.
    """

    def __init__(self, cfg, store):
        self._cfg = cfg
        self._store = store

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_emulator_mode(self) -> bool:
        """True when no live node URLs are configured."""
        return not bool(self._get_node_urls())

    def _get_node_urls(self) -> list[str]:
        raw = getattr(self._cfg, "ioswarm_node_urls", "") or ""
        return [u.strip() for u in raw.split(",") if u.strip()]

    # ------------------------------------------------------------------
    # Evaluation dispatch
    # ------------------------------------------------------------------

    async def dispatch_evaluation(
        self, evaluation_type: str, payload: dict
    ) -> list[dict]:
        """Dispatch evaluation to all configured nodes concurrently.

        Returns list of response dicts from nodes that answered within
        ``ioswarm_node_timeout_seconds``. Returns empty list (not an error)
        if no nodes are reachable — callers must handle empty response by
        falling back to emulator.

        Each response dict has keys: node_id, staker_address, verdict, confidence.
        """
        urls = self._get_node_urls()
        if not urls:
            return []

        timeout = float(getattr(self._cfg, "ioswarm_node_timeout_seconds", 5.0))
        body = json.dumps(
            {
                "evaluation_type": evaluation_type,
                "payload": payload,
            }
        ).encode()

        tasks = [
            asyncio.wait_for(self._call_node(url, body), timeout=timeout)
            for url in urls
        ]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        now = time.time()
        for url, result in zip(urls, results_raw):
            if isinstance(result, Exception):
                log.debug(
                    "ioSwarm node %s did not respond within %.1fs: %s",
                    url, timeout, result,
                )
            else:
                results.append(result)
                try:
                    self._store.update_ioswarm_node_last_seen(
                        url, now, result.get("staker_address", "")
                    )
                except Exception:
                    pass
        return results

    async def _call_node(self, url: str, body: bytes) -> dict:
        """POST /evaluate on a single node. Raises on any error."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._http_post, url, body)
        return result

    def _http_post(self, base_url: str, body: bytes) -> dict:
        """Blocking HTTP POST to {base_url}/evaluate."""
        endpoint = base_url.rstrip("/") + "/evaluate"
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    # ------------------------------------------------------------------
    # Health polling (used by Phase 132 IoSwarmNodeHealthPoller)
    # ------------------------------------------------------------------

    async def poll_node_health(self) -> list[dict]:
        """Poll GET /status on all configured nodes. Returns per-node health dicts."""
        urls = self._get_node_urls()
        if not urls:
            return []
        timeout = float(getattr(self._cfg, "ioswarm_node_timeout_seconds", 5.0))
        tasks = [
            asyncio.wait_for(self._poll_single(url), timeout=timeout)
            for url in urls
        ]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        now = time.time()
        for url, result in zip(urls, results_raw):
            if isinstance(result, Exception):
                entry = {
                    "node_url": url, "healthy": False,
                    "latency_ms": -1.0, "staker_address": "",
                    "error_msg": str(result),
                }
            else:
                entry = result
                try:
                    self._store.update_ioswarm_node_last_seen(
                        url, now, result.get("staker_address", "")
                    )
                except Exception:
                    pass
            results.append(entry)
        return results

    async def _poll_single(self, url: str) -> dict:
        t0 = time.time()
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._http_get_status, url)
        latency_ms = (time.time() - t0) * 1000
        data["latency_ms"] = latency_ms
        data["node_url"] = url
        data["healthy"] = True
        return data

    def _http_get_status(self, base_url: str) -> dict:
        endpoint = base_url.rstrip("/") + "/status"
        with urllib.request.urlopen(endpoint) as resp:
            return json.loads(resp.read())
