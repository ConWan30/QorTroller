#!/usr/bin/env python3
"""Poll A2A-PKG mailbox for new Claude→grok messages; print one line per event.

Used by the Grok session monitor so the operator stays in the loop.
Stdout is line-buffered; each new event is a single JSON object.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAILBOX = REPO / "docs" / "a2a" / "pkg" / "mailbox"
INBOX = MAILBOX / "inbox"
OUTBOX = MAILBOX / "outbox"
LEDGER = MAILBOX / "ledger.jsonl"
PKG = REPO / "docs" / "a2a" / "pkg"
INTERVAL_S = 5.0


def _seen_envelopes() -> set[str]:
    seen: set[str] = set()
    for d in (INBOX, OUTBOX):
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            try:
                e = json.loads(p.read_text(encoding="utf-8"))
                eid = e.get("envelope_id") or p.stem
                seen.add(str(eid))
            except (OSError, json.JSONDecodeError):
                seen.add(p.stem)
    return seen


def _seen_rounds() -> set[str]:
    if not PKG.is_dir():
        return set()
    return {p.name for p in PKG.glob("round-*.md")}


def _ledger_len() -> int:
    if not LEDGER.is_file():
        return 0
    try:
        return sum(1 for _ in LEDGER.open(encoding="utf-8") if _.strip())
    except OSError:
        return 0


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    seen_env = _seen_envelopes()
    seen_rounds = _seen_rounds()
    ledger_n = _ledger_len()
    _emit(
        {
            "event": "watch_started",
            "loop": "A2A-PKG",
            "watching": "claude→grok envelopes + new round-*.md + ledger",
            "baseline_envelopes": len(seen_env),
            "baseline_rounds": sorted(seen_rounds),
            "baseline_ledger_lines": ledger_n,
            "interval_s": INTERVAL_S,
        }
    )

    while True:
        time.sleep(INTERVAL_S)

        # New envelopes (prefer claude→grok for operator alerts)
        for d in (INBOX, OUTBOX):
            if not d.is_dir():
                continue
            for p in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime):
                try:
                    e = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                eid = str(e.get("envelope_id") or p.stem)
                if eid in seen_env:
                    continue
                seen_env.add(eid)
                frm = e.get("from_agent", "?")
                to = e.get("to_agent", "?")
                kind = "claude_to_grok" if frm == "claude" and to == "grok" else "envelope_new"
                _emit(
                    {
                        "event": kind,
                        "envelope_id": eid,
                        "from_agent": frm,
                        "to_agent": to,
                        "subject": e.get("subject"),
                        "body_path": e.get("body_path"),
                        "expected_reply_path": e.get("expected_reply_path"),
                        "channel": e.get("channel"),
                        "autonomous": e.get("operator_authorized_autonomous_fire"),
                        "dir": d.name,
                    }
                )

        # New round files
        for name in sorted(_seen_rounds() - seen_rounds):
            seen_rounds.add(name)
            path = PKG / name
            preview = ""
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                preview = " ".join(text.splitlines()[:3])[:240]
            except OSError:
                pass
            _emit(
                {
                    "event": "round_file_new",
                    "name": name,
                    "path": f"docs/a2a/pkg/{name}",
                    "bytes": path.stat().st_size if path.is_file() else 0,
                    "preview": preview,
                }
            )

        # Ledger growth (new posts/fires)
        n = _ledger_len()
        if n > ledger_n and LEDGER.is_file():
            try:
                lines = LEDGER.read_text(encoding="utf-8").strip().splitlines()
                for line in lines[ledger_n:]:
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("from_agent") == "claude" or ev.get("event") in (
                        "posted",
                        "fire_completed",
                        "reply_ack",
                        "deliver_start",
                    ):
                        _emit(
                            {
                                "event": "ledger",
                                "ledger_event": ev.get("event"),
                                "envelope_id": ev.get("envelope_id"),
                                "from_agent": ev.get("from_agent"),
                                "to_agent": ev.get("to_agent"),
                                "body_path": ev.get("body_path"),
                                "returncode": ev.get("returncode"),
                            }
                        )
            except OSError:
                pass
            ledger_n = n


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        _emit({"event": "watch_stopped"})
        raise SystemExit(0)
