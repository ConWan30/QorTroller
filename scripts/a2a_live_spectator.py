#!/usr/bin/env python3
"""A2A live spectator — grok watches a QorTroller session (operator-requested 2026-07-13).

During a live session, this loop periodically composes an HONEST telemetry tick — the witness's own
readings (latest OCR'd feed lines from the killfeed sink, ring freshness, session identity), never
raw video — fires the grok CLI single-turn, and banks grok's spectator commentary to a session-local
log. grok is the SECOND WITNESS: it sees exactly what the retina read, comments live, and its whole
transcript is auditable afterward.

Rails: read-only on the session (never touches capture/daemon state); text telemetry only (game-feed
OCR lines — no images, no biometrics, no keys); fail-open (a missed tick never breaks the session);
the spectator log is a commentary artifact, NEVER evidence (grok's remarks carry no verdict
authority — the separation law: observation may suggest, only assertion may claim).

Usage (run alongside a live session):
    python scripts/a2a_live_spectator.py --label session_<stamp>            # auto-detects latest
    python scripts/a2a_live_spectator.py --interval 120 --max-ticks 20
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def latest_session_dir(root: Path) -> Path | None:
    dirs = sorted((root / "retina_kf_crops").glob("session_*"), key=lambda p: p.name, reverse=True)
    return dirs[0] if dirs else None


def read_sink_tail(capture_dir: Path, n: int = 8) -> list[dict]:
    """Last n killfeed events (killer/victim text) — the witness's own reads. Fail-open []."""
    try:
        lines = (capture_dir / "killfeed_events.jsonl").read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines[-n:]:
            d = json.loads(ln)
            d = d.get("data", d)
            out.append({"killer": d.get("killer", "?"), "victim": d.get("victim", "?")})
        return out
    except Exception:  # noqa: BLE001
        return []


def ring_freshness(capture_dir: Path) -> tuple[int, float]:
    try:
        crops = list(capture_dir.glob("panel_*.png"))
        if not crops:
            return 0, float("inf")
        newest = max(c.stat().st_mtime for c in crops)
        return len(crops), max(0.0, time.time() - newest)
    except Exception:  # noqa: BLE001
        return 0, float("inf")


def compose_tick(label: str, tick: int, events: list[dict], n_crops: int, age_s: float,
                 prev_events_n: int) -> str:
    ev = "\n".join(f"  {e['killer']} -> {e['victim']}" for e in events) or "  (none read yet)"
    fresh = "LIVE" if age_s < 30 else ("STALE" if age_s < 1e8 else "EMPTY")
    return f"""You are grok, LIVE SPECTATOR of a QorTroller capture-witness session ({label}, tick {tick}).
The operator (handle Qortrola30) is playing Warzone RIGHT NOW; the retina witness reads the killfeed
via OCR. Below is the witness's HONEST telemetry this tick (text reads only — you see what it read).

ring: {n_crops} crops, newest {age_s:.0f}s old [{fresh}] | feed events read so far: {len(events)} (was {prev_events_n})
latest reads (killer -> victim):
{ev}

Reply with a SHORT live-spectator comment (2-4 sentences): what you observe about the session's
health + the operator's activity AS EVIDENCED BY THE READS (never invent kills or events not shown;
if the operator's handle appears as killer, celebrate it — that's a witnessed kill). You are a
commentator, not a verdict authority. No tools. Just the comment."""


def fire_grok(prompt: str, timeout_s: int = 90) -> str:
    try:
        r = subprocess.run(["grok", "-p", prompt, "--output-format", "plain", "--disable-web-search"],
                           capture_output=True, text=True, timeout=timeout_s, encoding="utf-8")
        return (r.stdout or "").strip() or f"(grok empty, rc={r.returncode})"
    except Exception as exc:  # noqa: BLE001
        return f"(grok unavailable this tick: {exc})"


def main() -> int:
    ap = argparse.ArgumentParser(description="grok live-spectates a QorTroller session (read-only)")
    ap.add_argument("--label", default="", help="session dir name (default: latest session_*)")
    ap.add_argument("--interval", type=int, default=150, help="seconds between ticks (default 150)")
    ap.add_argument("--max-ticks", type=int, default=12, help="stop after N ticks (default 12)")
    a = ap.parse_args()

    cap = (_REPO / "retina_kf_crops" / a.label) if a.label else latest_session_dir(_REPO)
    if cap is None or not cap.exists():
        print(f"ABORT: no session dir found ({a.label or 'latest'})", file=sys.stderr)
        return 2
    log = cap / "a2a_spectator_log.md"
    log.write_text(f"# grok live-spectator log -- {cap.name}\n\n"
                   f"*Second AI witness; commentary only, never evidence. Started "
                   f"{time.strftime('%Y-%m-%d %H:%M')}.*\n\n", encoding="utf-8")
    print(f"[spectator] grok watching {cap.name} every {a.interval}s -> {log}")

    prev_n = 0
    for tick in range(1, a.max_ticks + 1):
        events = read_sink_tail(cap, n=8)
        n_crops, age_s = ring_freshness(cap)
        if age_s > 600:                                   # session looks over -> final tick + stop
            print("[spectator] ring stale >10min -- session over, stopping")
            break
        comment = fire_grok(compose_tick(cap.name, tick, events, n_crops, age_s, prev_n))
        prev_n = len(events)
        stamp = time.strftime("%H:%M:%S")
        with log.open("a", encoding="utf-8") as f:
            f.write(f"## tick {tick} · {stamp} · ring={n_crops} crops ({age_s:.0f}s) · reads={len(events)}\n\n"
                    f"{comment}\n\n")
        print(f"[spectator] tick {tick} @ {stamp}: {comment[:110]}...")
        if tick < a.max_ticks:
            time.sleep(a.interval)
    print(f"[spectator] done -> {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
