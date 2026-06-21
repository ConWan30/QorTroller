"""Fusion v2 calibration runner — replay labelled artifacts through the oracle panel and
tabulate a 5-class x per-oracle confusion (Fusion v2 Phase 3/4 end-to-end).

--synthetic (default): builds a base LIVE artifact, derives the four self-adversarial classes
(replay / relay / headless / injection), runs each through evaluate_artifact, and writes the
confusion + per-oracle verdicts to audits/fusion-v2-calibration-<date>.{md,json}. This is the
artifact that PROPOSES calibrated thresholds — it is UNCALIBRATED until real co-capture, and
N=1 falsifies, not validates.

  py scripts/run_fusion_v2_experiment.py --synthetic --seed 0 --n-per-class 10
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge.vapi_bridge.oracle_panel import SessionArtifact, evaluate_artifact  # noqa: E402
from bridge.vapi_bridge.self_adversary import (  # noqa: E402
    make_headless, make_injection, make_relay, make_replay,
)

_HUD = [
    (2000.0, "1ST & 10"), (3000.0, "2ND & 6"),
    (5000.0, "2ND & 6"), (6000.0, "3RD & 2"),
    (8000.0, "3RD & 2"), (9000.0, "1ST & 10"),
]


def _streams(n=600, rate_hz=60.0, coupled=True, seed=0):
    rng = random.Random(seed)
    dt = 1000.0 / rate_hz
    ts = [i * dt for i in range(n)]
    sx = [128 + 60.0 * math.sin(2 * math.pi * 0.8 * t / 1000.0) for t in ts]
    sy = [128 + 8.0 * math.sin(2 * math.pi * 0.3 * t / 1000.0) for t in ts]
    lag = int(round(40.0 / dt))
    yaw = [rng.gauss(0, 0.4) for _ in range(n)]
    if coupled:
        for i in range(lag, n):
            yaw[i] += (sx[i - lag] - 128) * 1.5
    pitch = [rng.gauss(0, 0.4) for _ in range(n)]
    return ts, sx, sy, yaw, pitch


def _live(seed=0):
    ts, sx, sy, yaw, pitch = _streams(coupled=True, seed=seed)
    fire = [200.0 if any(ot <= t < ot + 300 for ot in (1000.0, 4000.0, 7000.0)) else 0.0 for t in ts]
    return SessionArtifact(in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch,
                           in_fire=fire, hud_texts=_HUD, class_label="HUMAN_CLEAN")


def _foreign(seed=0):
    ts, sx, sy, yaw, pitch = _streams(coupled=False, seed=seed + 7919)
    return SessionArtifact(in_ts=ts, in_sx=sx, in_sy=sy, mo_ts=ts, mo_yaw=yaw, mo_pitch=pitch)


def _labelled_artifacts(seed: int):
    base = _live(seed)
    return [
        base,
        make_replay(_live(seed), _foreign(seed)),
        make_relay(_live(seed)),
        make_headless(_live(seed)),
        make_injection(_live(seed), strength=2.0, seed=seed),
    ]


def run_synthetic(seed: int, n_per_class: int) -> dict:
    rows = []
    for k in range(n_per_class):
        for a in _labelled_artifacts(seed + k):
            rows.append(evaluate_artifact(a).to_dict())
    # 5-class x fusion_verdict confusion
    classes = sorted({r["class_label"] for r in rows})
    verdicts = sorted({r["fusion_verdict"] for r in rows})
    confusion = {c: {v: 0 for v in verdicts} for c in classes}
    for r in rows:
        confusion[r["class_label"]][r["fusion_verdict"]] += 1
    return {
        "schema": "vapi-fusion-v2-calibration-v1",
        "calibration": "UNCALIBRATED",
        "provenance": "synthetic",
        "n_per_class": n_per_class,
        "seed": seed,
        "classes": classes,
        "verdicts": verdicts,
        "confusion_fusion_verdict": confusion,
        "rows": rows,
    }


def to_markdown(d: dict) -> str:
    lines = [
        "# Fusion v2 Calibration — synthetic self-adversarial run",
        "",
        "**UNCALIBRATED — provisional read on synthetic + real-derived data.** N=1 falsifies, "
        "does not validate. Thresholds proposed here require real labelled co-capture before promotion.",
        "",
        f"- provenance: {d['provenance']}  seed: {d['seed']}  n_per_class: {d['n_per_class']}",
        "",
        "## Confusion — class_label x fusion_verdict",
        "",
        "| class \\ verdict | " + " | ".join(d["verdicts"]) + " |",
        "|---|" + "|".join(["---"] * len(d["verdicts"])) + "|",
    ]
    for c in d["classes"]:
        row = d["confusion_fusion_verdict"][c]
        lines.append(f"| {c} | " + " | ".join(str(row[v]) for v in d["verdicts"]) + " |")
    lines += [
        "",
        "## Honest read",
        "- HUMAN_CLEAN should concentrate on LIVE_COHERENT.",
        "- HUMAN_RELAY (replay/relay) should concentrate on REPLAY_OR_RELAY.",
        "- HUMAN_INPUT_MACRO (injection) should lift INJECTION_SUSPECT as residual passes threshold.",
        "- BOT_FULL (headless) has no rendered channel — coupling None; coherence INSUFFICIENT/ORPHAN_INPUT.",
        "- Off-diagonal mass is the measured separation gap the real experiment must close.",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fusion v2 calibration runner")
    ap.add_argument("--synthetic", action="store_true", default=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-per-class", type=int, default=10)
    ap.add_argument("--out-dir", default="audits")
    args = ap.parse_args()

    d = run_synthetic(args.seed, args.n_per_class)
    os.makedirs(args.out_dir, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    md_path = os.path.join(args.out_dir, f"fusion-v2-calibration-{date}.md")
    json_path = os.path.join(args.out_dir, f"fusion-v2-calibration-{date}.json")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(to_markdown(d) + "\n")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in d.items() if k != "rows"}, fh, indent=2)

    print(f"[fusion-v2] classes={d['classes']}")
    for c in d["classes"]:
        print(f"[fusion-v2] {c}: {d['confusion_fusion_verdict'][c]}")
    print(f"[fusion-v2] wrote {md_path} + {json_path}  (UNCALIBRATED)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
