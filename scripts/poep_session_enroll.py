"""PoEP session-start enrollment (developer-self cert, Stage 2).

Run this BEFORE starting the bridge for a developer-self-cert play session. It:
  1. builds your DEV single-subject reflex band from poep_l9/DEV_*.poep.json (the campaign output);
  2. runs a SHORT liveness enrollment (react to the buzzes, controller still; force_trials=0 -> the
     device-auth channel is deferred per the DEV_01/02 slope=0 finding -- LIVENESS-ONLY v0);
  3. scores the fresh session against the band (developer_self_liveness_verdict);
  4. writes the session verdict to ~/.vapi/poep_session_verdict.json, which the bridge reads at startup
     (when developer_self_cert_enabled + poep_liveness_enabled) -> meta["poep_present"] goes live for the
     session via poep_activation.poep_present_signal.

PoEP is enrollment-mode/SESSION-level: this verdict is established still at session start and stays live
through the match (gameplay confounds mid-game reflex measurement). Stop the bridge first (pydualsense
contention). LIVENESS-ONLY: cert_scope stays developer_self; population_certified never True.
"""
from __future__ import annotations

import argparse
import json
import os
import time

from l9_presence.poep import PoEPConfig, PoEPRecorder, load_poep_session
from l9_presence.poep_calibration import (
    developer_self_liveness_verdict,
    single_subject_reflex_model,
)

DEFAULT_VERDICT_PATH = os.path.expanduser("~/.vapi/poep_session_verdict.json")


def _write_verdict(path: str, verdict: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description="PoEP session-start enrollment (developer-self cert)")
    ap.add_argument("--player", default="DEV", help="developer profile (single-subject band)")
    ap.add_argument("--challenges", type=int, default=10, help="reflex challenges this session")
    ap.add_argument("--corpus-dir", default="poep_l9")
    ap.add_argument("--min-n", type=int, default=30, help="developer-scoped data gate")
    ap.add_argument("--min-in-band-fraction", type=float, default=0.5)
    ap.add_argument("--out", default=DEFAULT_VERDICT_PATH)
    a = ap.parse_args()

    # 1. Build the DEV band from EXISTING sessions (scored-against band excludes the fresh session).
    model = single_subject_reflex_model(a.corpus_dir, a.player, a.min_n)
    if not model.get("calibration_complete"):
        verdict = {"status": "calibration_incomplete", "player": a.player,
                   "n_reactions": model.get("n_reactions", 0), "min_n": a.min_n,
                   "ts_ns": time.time_ns(), "channel": "liveness_only"}
        _write_verdict(a.out, verdict)
        print(f"DEV band NOT calibrated (N={verdict['n_reactions']} < {a.min_n}). "
              f"Run the campaign (l9_presence.poep enroll --player {a.player}) first. "
              f"Wrote abstain verdict -> {a.out}")
        return 1

    print(f"DEV band ready: mean={model.get('latency_mean_ms')}ms "
          f"band=[{model.get('band_lo_ms')}, {model.get('band_hi_ms')}]ms. "
          f"Hold the controller STILL and react to each buzz.\n")

    # 2. Short liveness enrollment (force_trials=0 -> liveness-only).
    cfg = PoEPConfig(player=a.player, challenges=a.challenges, force_trials=0, out_dir=a.corpus_dir)
    summary = PoEPRecorder(cfg).enroll()

    # 3. Score the fresh session against the (pre-existing) band.
    fresh = load_poep_session(summary["path"])
    reactions = [c.get("features", {}) for c in fresh.challenge_records]
    v = developer_self_liveness_verdict(reactions, model, min_in_band_fraction=a.min_in_band_fraction)
    v.update({"player": a.player, "device_id": fresh.device_id, "ts_ns": time.time_ns(),
              "session_path": summary["path"], "cert_scope": "developer_self"})

    # 4. Write the session verdict for the bridge to read at startup.
    _write_verdict(a.out, v)
    print(f"\nsession verdict: {v.get('verdict', v.get('status'))} "
          f"(in_band_fraction={v.get('in_band_fraction')}, n_reacted={v.get('n_reacted')}) "
          f"-> {a.out}")
    print("Start the bridge with DEVELOPER_SELF_CERT_ENABLED=true + POEP_LIVENESS_ENABLED=true to go live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
