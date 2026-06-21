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


def artifact_from_npz(path: str, class_label: str = "HUMAN_CLEAN") -> SessionArtifact:
    """Load a recorded witness/cocapture .npz into a SessionArtifact (provenance=real).

    Recorded sessions carry the HID + camera streams but no per-frame OCR (hud_texts=[]),
    so the discrete-coherence channel reads INSUFFICIENT until an OCR pass is added — the
    continuous coupling channel still scores. capture_governor telemetry is carried through."""
    import numpy as np
    d = np.load(path, allow_pickle=True)

    def col(k: str) -> list[float]:
        return [float(x) for x in d[k].tolist()] if k in d.files else []

    telemetry = {}
    if "capture_governor" in d.files:
        try:
            telemetry = json.loads(str(d["capture_governor"]))
        except Exception:
            telemetry = {}
    return SessionArtifact(
        in_ts=col("in_ts"), in_sx=col("in_sx"), in_sy=col("in_sy"),
        mo_ts=col("mo_ts"), mo_yaw=col("mo_yaw"), mo_pitch=col("mo_pitch"),
        in_fire=col("in_fire"), hud_texts=[], class_label=class_label,
        provenance="real", capture_telemetry=telemetry,
    )


def _foreign_from(a: SessionArtifact, seed: int = 1729) -> SessionArtifact:
    """Decoupled 'foreign' camera for make_replay: the session's own camera time-SHUFFLED, so
    it no longer tracks the real stick at any causal lag (this is the negative-control op, and
    unlike a time-roll it decouples robustly even for periodic stick signals)."""
    rng = random.Random(seed)
    yaw = list(a.mo_yaw); rng.shuffle(yaw)
    pitch = list(a.mo_pitch); rng.shuffle(pitch)
    return SessionArtifact(in_ts=a.in_ts, in_sx=a.in_sx, in_sy=a.in_sy,
                           mo_ts=a.mo_ts, mo_yaw=yaw, mo_pitch=pitch)

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


def _build_result(rows: list[dict], provenance: str, **meta) -> dict:
    """5-class x fusion_verdict confusion over evaluated rows."""
    classes = sorted({r["class_label"] for r in rows})
    verdicts = sorted({r["fusion_verdict"] for r in rows})
    confusion = {c: {v: 0 for v in verdicts} for c in classes}
    for r in rows:
        confusion[r["class_label"]][r["fusion_verdict"]] += 1
    return {
        "schema": "vapi-fusion-v2-calibration-v1",
        "calibration": "UNCALIBRATED",
        "provenance": provenance,
        "classes": classes,
        "verdicts": verdicts,
        "confusion_fusion_verdict": confusion,
        "rows": rows,
        **meta,
    }


def run_synthetic(seed: int, n_per_class: int) -> dict:
    rows = []
    for k in range(n_per_class):
        for a in _labelled_artifacts(seed + k):
            rows.append(evaluate_artifact(a).to_dict())
    return _build_result(rows, "synthetic", n_per_class=n_per_class, seed=seed)


def run_from_session(path: str, *, injection_strength: float = 2.0) -> dict:
    """Real-session path (the N=1 unlock): load one recorded .npz, derive the four
    self-adversarial classes from it, and tabulate the per-oracle confusion."""
    base = artifact_from_npz(path, "HUMAN_CLEAN")
    arts = [
        base,
        make_replay(base, _foreign_from(base)),
        make_relay(base),
        make_headless(base),
        make_injection(base, strength=injection_strength),
    ]
    rows = [evaluate_artifact(a).to_dict() for a in arts]
    return _build_result(rows, "real_derived", source_session=os.path.basename(path),
                         capture_telemetry=base.capture_telemetry)


def to_markdown(d: dict) -> str:
    lines = [
        "# Fusion v2 Calibration — synthetic self-adversarial run",
        "",
        "**UNCALIBRATED — provisional read on synthetic + real-derived data.** N=1 falsifies, "
        "does not validate. Thresholds proposed here require real labelled co-capture before promotion.",
        "",
        f"- provenance: {d['provenance']}" + (
            f"  seed: {d['seed']}  n_per_class: {d['n_per_class']}"
            if d.get("seed") is not None else f"  source_session: {d.get('source_session', '?')}"),
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
    ap.add_argument("--from-session", default="",
                    help="path to a recorded witness/cocapture .npz; derive the 4 adversary "
                         "classes from this real session and tabulate the confusion (N=1 unlock)")
    ap.add_argument("--injection-strength", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-per-class", type=int, default=10)
    ap.add_argument("--out-dir", default="audits")
    args = ap.parse_args()

    if args.from_session:
        if not os.path.exists(args.from_session):
            print(f"[fusion-v2] session not found: {args.from_session}")
            return 2
        d = run_from_session(args.from_session, injection_strength=args.injection_strength)
    else:
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
