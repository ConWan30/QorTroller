"""Cross-channel latency-invariant calibration capture (READ-ONLY over a bridge log).

The coupling channels (geometric stick->pan, B1 trigger->flash, B2 trigger->RED-hitmarker) each emit a
per-channel lag in the bridge's `RGC diag:` status lines during live play. This tool harvests those into a
calibration corpus and (optionally) fits the agreement threshold via
l9_presence.cross_channel_latency.calibrate_tau_lag.

WORKFLOW (see docs/wgc-devcert-warzone-runbook.md):
  1. Run the bridge with retina game capture enabled, redirecting its log to a file, and PLAY a real
     coupled session -> harvest GENUINE sessions:
         python scripts/capture_latency_calibration.py --log bridge.log --out genuine.jsonl
  2. Do the same while SPECTATING active combat and firing along -> harvest FORGED negatives:
         python scripts/capture_latency_calibration.py --log spectate.log --out forged.jsonl
  3. Fit + report (FAR-safe threshold, or INSUFFICIENT_DATA below N_FLOOR=10/class):
         python scripts/capture_latency_calibration.py --calibrate --genuine genuine.jsonl --forged forged.jsonl

Pure parser functions (parse_rgc_diag / sample_to_channels / load_sessions) are unit-tested; the CLI is I/O.
No FROZEN-v1 / 228B PoAC / chain / IOTX. Advisory presence calibration only.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "bridge"))

# (channel name, coupling key, null key, lag key) in the RGC diag status dict
_CHANNELS = (
    ("geometric", "coupling_score", "negative_control", "lag_ms"),
    ("b1_flash", "th_coupling", "th_null", "th_lag_ms"),
    ("b2_killmark", "th2_coupling", "th2_null", "th2_lag_ms"),
)
_MARKER = "RGC diag: "


def parse_rgc_diag(text: str) -> list[dict]:
    """Extract every `RGC diag: {dict}` status snapshot from bridge log text (pure). Tolerant: a line
    whose dict fails to literal_eval is skipped, never raised."""
    out: list[dict] = []
    for line in text.splitlines():
        i = line.find(_MARKER)
        if i < 0:
            continue
        blob = line[i + len(_MARKER):].strip()
        try:
            d = ast.literal_eval(blob)
        except (ValueError, SyntaxError):
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def sample_to_channels(d: dict):
    """Build a list[ChannelLag] from one RGC diag status dict — only channels with a present
    (non-None) coupling AND lag. Pure. Returns [] if no channel is usable."""
    from l9_presence.cross_channel_latency import ChannelLag
    chans = []
    for name, ck, nk, lk in _CHANNELS:
        coup, lag = d.get(ck), d.get(lk)
        if coup is None or lag is None:
            continue
        chans.append(ChannelLag(channel=name, coupling=float(coup),
                                null=float(d.get(nk) or 0.0), lag_ms=float(lag)))
    return chans


def load_sessions(jsonl_path: str):
    """Load a captured corpus (one JSON list-of-channel-dicts per line) -> list[list[ChannelLag]]."""
    from l9_presence.cross_channel_latency import ChannelLag
    sessions = []
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows = json.loads(line)
            sessions.append([ChannelLag(**r) for r in rows])
    return sessions


def _harvest(log_path: str, out_path: str, min_channels: int) -> int:
    text = open(log_path, encoding="utf-8", errors="replace").read()
    n = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for d in parse_rgc_diag(text):
            chans = sample_to_channels(d)
            if len(chans) < min_channels:
                continue                       # need >=min coupled channels for an agreement sample
            out.write(json.dumps([c.__dict__ for c in chans]) + "\n")
            n += 1
    print(f"[capture] {log_path} -> {out_path}: {n} sessions (>= {min_channels} channels each)")
    return n


def _calibrate(genuine_path: str, forged_path: str) -> int:
    from l9_presence.cross_channel_latency import calibrate_tau_lag
    g = load_sessions(genuine_path)
    f = load_sessions(forged_path)
    res = calibrate_tau_lag(g, f)
    print(json.dumps(res.to_dict(), indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="cross-channel latency-invariant calibration capture")
    ap.add_argument("--log", help="bridge log file to harvest RGC diag lines from")
    ap.add_argument("--out", help="output JSONL corpus path (with --log)")
    ap.add_argument("--min-channels", type=int, default=2, help="min coupled channels per kept sample")
    ap.add_argument("--calibrate", action="store_true", help="fit the threshold from --genuine/--forged")
    ap.add_argument("--genuine", help="genuine-session corpus JSONL (with --calibrate)")
    ap.add_argument("--forged", help="forged/spectate-negative corpus JSONL (with --calibrate)")
    a = ap.parse_args()
    if a.calibrate:
        if not (a.genuine and a.forged):
            ap.error("--calibrate requires --genuine and --forged")
        return _calibrate(a.genuine, a.forged)
    if not (a.log and a.out):
        ap.error("provide --log and --out to harvest, or --calibrate with --genuine/--forged")
    _harvest(a.log, a.out, a.min_channels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
