"""
AlertRouter — Phase 37: "The Protocol Acts on Its Memory"

Polls protocol_insights every 30 seconds and dispatches high-severity events
to operator webhooks. Zero external dependencies (stdlib urllib.request only).

Design constraints:
  - Tracks _last_id to avoid re-dispatching previously seen insights
  - Severity filter: only dispatches when insight severity >= alert_severity_threshold
  - All webhook calls are non-fatal — exceptions are logged as warnings
  - /health endpoint is never rate-limited by this component (passthrough concern)
  - Three payload formats: slack, pagerduty, generic (dict)
  - No-op when alert_webhook_url is empty string
"""
import asyncio
import ipaddress
import json
import logging
import socket
import time
import urllib.request
from urllib.error import URLError
from urllib.parse import urlparse

log = logging.getLogger(__name__)


def _validate_webhook_url(url: str) -> tuple[bool, str]:
    """SSRF guard. Returns (ok, reason). Rejects non-http(s), loopback, private,
    link-local, multicast, reserved ranges. Hostnames are resolved and ALL
    returned addresses must be public."""
    if not isinstance(url, str) or len(url) > 2048:
        return False, "invalid_url_type_or_length"
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"unparseable: {exc}"
    if parsed.scheme not in ("http", "https"):
        return False, f"scheme_not_allowed: {parsed.scheme}"
    if not parsed.hostname:
        return False, "no_hostname"
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        return False, f"dns_failed: {exc}"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False, "invalid_resolved_ip"
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False, f"non_public_ip: {ip}"
    return True, "ok"

# Severity ranking — higher number = more severe
_SEVERITY_ORDER: dict[str, int] = {
    "critical": 3,
    "medium":   2,
    "low":      1,
}


class AlertRouter:
    """Polls store.get_recent_insights() and dispatches qualifying events to webhooks.

    Args:
        cfg:   BridgeConfig instance; uses alert_webhook_url, alert_webhook_format,
               alert_severity_threshold.
        store: Store instance; uses get_recent_insights(limit).

    Invariants:
        - run() is a long-lived coroutine; cancel it to stop
        - All dispatch failures are logged as warnings, never re-raised
        - _last_id monotonically increases — insights are never re-dispatched
        - No-op (polling continues, no dispatches) when webhook_url is empty
    """

    _POLL_INTERVAL_S: float = 30.0

    def __init__(self, cfg, store):
        self._cfg   = cfg
        self._store = store
        self._last_id: int = 0

    async def run(self) -> None:
        """Main poll loop. Runs until cancelled."""
        log.info(
            "AlertRouter started (threshold=%s format=%s webhook=%s)",
            getattr(self._cfg, "alert_severity_threshold", "medium"),
            getattr(self._cfg, "alert_webhook_format", "generic"),
            "configured" if getattr(self._cfg, "alert_webhook_url", "") else "not-configured",
        )
        while True:
            try:
                await asyncio.sleep(self._POLL_INTERVAL_S)
            except asyncio.CancelledError:
                log.info("AlertRouter: shutdown requested")
                return
            try:
                await self._poll_and_dispatch()
            except asyncio.CancelledError:
                log.info("AlertRouter: shutdown during dispatch")
                return
            except Exception as exc:
                log.warning("AlertRouter: poll/dispatch error (non-fatal): %s", exc)

    async def _poll_and_dispatch(self) -> None:
        """Fetch recent insights and dispatch those above threshold with new IDs."""
        webhook_url = getattr(self._cfg, "alert_webhook_url", "")
        threshold   = getattr(self._cfg, "alert_severity_threshold", "medium")

        try:
            insights = self._store.get_recent_insights(limit=50)
        except Exception as exc:
            log.warning("AlertRouter: store.get_recent_insights failed: %s", exc)
            return

        for insight in insights:
            insight_id = insight.get("id", 0)
            if insight_id <= self._last_id:
                continue
            self._last_id = max(self._last_id, insight_id)

            if not webhook_url:
                continue  # track IDs but do not dispatch

            severity = insight.get("severity", "low")
            if not self._meets_threshold(severity, threshold):
                continue

            await self._dispatch(webhook_url, insight)

    def _meets_threshold(self, severity: str, threshold: str) -> bool:
        """Return True if severity rank >= threshold rank."""
        return _SEVERITY_ORDER.get(severity, 0) >= _SEVERITY_ORDER.get(threshold, 2)

    async def _dispatch(self, webhook_url: str, insight: dict) -> None:
        """Format and POST insight to the configured webhook (non-fatal)."""
        ok, reason = _validate_webhook_url(webhook_url)
        if not ok:
            log.warning("AlertRouter: SSRF guard rejected webhook (%s): %s",
                        reason, webhook_url)
            return
        fmt = getattr(self._cfg, "alert_webhook_format", "generic")
        try:
            payload = self._format_payload(insight, fmt)
            body    = json.dumps(payload).encode("utf-8")
            loop    = asyncio.get_event_loop()

            def _send():
                req = urllib.request.Request(
                    webhook_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        status = resp.getcode()
                        if status < 200 or status >= 300:
                            log.warning(
                                "AlertRouter: webhook returned non-2xx status=%d insight_id=%s",
                                status, insight.get("id"),
                            )
                except URLError as exc:
                    log.warning(
                        "AlertRouter: webhook delivery failed (insight_id=%s): %s",
                        insight.get("id"), exc,
                    )

            await loop.run_in_executor(None, _send)
        except Exception as exc:
            log.warning(
                "AlertRouter: dispatch error (insight_id=%s): %s",
                insight.get("id"), exc,
            )

    def _format_payload(self, insight: dict, fmt: str) -> dict:
        """Format insight dict into webhook-specific payload structure."""
        severity     = insight.get("severity", "low")
        insight_type = insight.get("insight_type", "unknown")
        content      = insight.get("content", "")
        device_id    = insight.get("device_id", "")
        created_at   = insight.get("created_at", time.time())

        summary = (
            f"[VAPI {severity.upper()}] {insight_type}"
            + (f" device={device_id[:16]}" if device_id else "")
            + f": {content[:200]}"
        )

        if fmt == "slack":
            return {
                "text": summary,
                "attachments": [
                    {
                        "color": "#FF0000" if severity == "critical" else "#FFA500",
                        "fields": [
                            {"title": "Severity",     "value": severity,      "short": True},
                            {"title": "Type",         "value": insight_type,  "short": True},
                            {"title": "Device",       "value": device_id[:32] if device_id else "—", "short": True},
                            {"title": "Time",         "value": str(int(created_at)), "short": True},
                        ],
                    }
                ],
            }
        if fmt == "pagerduty":
            return {
                "summary":  summary,
                "severity": severity if severity in ("critical", "medium", "low") else "info",
                "source":   "vapi-bridge",
                "custom_details": {
                    "insight_type": insight_type,
                    "device_id":    device_id,
                    "content":      content,
                    "created_at":   created_at,
                },
            }
        # generic (default)
        return {
            "vapi_alert": {
                "severity":     severity,
                "insight_type": insight_type,
                "device_id":    device_id,
                "content":      content,
                "created_at":   created_at,
                "id":           insight.get("id"),
            }
        }
