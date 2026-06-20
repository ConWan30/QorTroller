#!/usr/bin/env python3
"""Optional trio-retina WebhookSink receiver (Phase C).

Listens on RETINA_WEBHOOK_PORT (default 8091) — NOT bridge/daemon 8080.
Forwards JSON payloads to the bridge ``POST /operator/retina-event`` endpoint.

Usage:
  python scripts/retina_webhook_receiver.py
  RETINA_WEBHOOK_PORT=8091 VAPI_BRIDGE_URL=http://127.0.0.1:8000 \\
    OPERATOR_API_KEY=your-key python scripts/retina_webhook_receiver.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer


def _bridge_url() -> str:
    return os.environ.get("VAPI_BRIDGE_URL", "http://127.0.0.1:8000").rstrip("/")


def _api_key() -> str:
    return os.environ.get("OPERATOR_API_KEY", os.environ.get("VITE_VAPI_API_KEY", ""))


def _forward_to_bridge(payload: dict) -> tuple[int, str]:
    key = _api_key()
    if not key:
        return 503, "OPERATOR_API_KEY not set"
    url = f"{_bridge_url()}/operator/retina-event?api_key={key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except Exception as exc:
        return 502, str(exc)


class RetinaWebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"invalid json")
            return
        code, body = _forward_to_bridge(payload)
        self.send_response(code if 200 <= code < 600 else 502)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"retina webhook receiver ok\n")


def main() -> None:
    port = int(os.environ.get("RETINA_WEBHOOK_PORT", "8091"))
    server = HTTPServer(("127.0.0.1", port), RetinaWebhookHandler)
    print(f"Retina webhook receiver on http://127.0.0.1:{port} -> {_bridge_url()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutdown")


if __name__ == "__main__":
    main()
