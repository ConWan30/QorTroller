"""Replay calibration HID sessions through the Retina controller embedder.

Compares Retina advisory anomaly counts against L4 Mahalanobis and L5 rhythm
proxies on the same sliding windows. Writes ``logs/retina_replay_<session>.jsonl``.

With ``--write-audit``, also writes ``audits/retina_cross_oracle_<date>.md`` and
``audits/retina_cross_oracle_latest.json`` (FSCA dry-run classifier vs L4).

Usage:
  python scripts/replay_retina_calibration.py
  python scripts/replay_retina_calibration.py --session sessions/hw_005.json
  python scripts/replay_retina_calibration.py --synthetic --aimbot-snap-at 100
  python scripts/replay_retina_calibration.py --write-audit
  python scripts/replay_retina_calibration.py --sessions-dir sessions/human \
      --max-frames 3000 --write-audit   # real 30k-frame captures, bounded
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "controller"))
sys.path.insert(0, str(ROOT / "bridge"))

from vapi_bridge.retina_controller_embedder import (  # noqa: E402
    DEFAULT_WINDOW,
    EVT_TRAJECTORY_ANOMALOUS,
    embed_controller_window,
    snaps_from_session_json,
    synthetic_snaps,
    write_events_jsonl,
)
from vapi_bridge.retina_perception import (  # noqa: E402
    RULE_L4_ANOMALY_WITHOUT_RETINA,
    RULE_RETINA_TRAJECTORY_WITHOUT_L4,
    classify_cross_oracle_window,
)

DEFAULT_L4_ANOMALY = 7.009
DEFAULT_L4_CONTINUITY = 5.367


class _Snap:
    def __init__(self, d: dict):
        for k, v in d.items():
            setattr(self, k, v)


def _load_snaps(path: Path | None, synthetic: bool, aimbot_at: int | None, macro: bool) -> list[dict]:
    if path is not None:
        if not path.is_file():
            raise FileNotFoundError(path)
        with open(path, encoding="utf-8") as fh:
            return snaps_from_session_json(json.load(fh))
    return synthetic_snaps(400, aimbot_snap_at=aimbot_at, macro_flat=macro)


def _l4_distance_per_window(snaps: list[dict], window: int) -> list[float]:
    try:
        from tinyml_biometric_fusion import BiometricFeatureExtractor, BiometricFusionClassifier
    except ImportError:
        return []
    clf = BiometricFusionClassifier()
    extractor = BiometricFeatureExtractor()
    distances: list[float] = []
    for end in range(window, len(snaps) + 1, window // 2 or 1):
        chunk = [_Snap(s) for s in snaps[end - window : end]]
        frame = extractor.extract(chunk, window_frames=window)
        for _ in range(5):
            clf.update_fingerprint(frame)
        d = getattr(clf, "last_distance", None)
        if d is None:
            r = clf.classify(frame)
            if r is not None:
                d = getattr(clf, "last_distance", 0.0)
        distances.append(float(d or 0.0))
    return distances


def _l4_distance(snaps: list[dict], window: int) -> list[float]:
    return _l4_distance_per_window(snaps, window)


def _l5_cv_proxy(snaps: list[dict], window: int) -> list[float]:
    """Inter-frame stick delta CV as L5 rhythm proxy when oracle unavailable offline."""
    cvs: list[float] = []
    for end in range(window, len(snaps) + 1, window // 2 or 1):
        chunk = snaps[end - window : end]
        deltas = []
        for i in range(1, len(chunk)):
            dx = chunk[i]["right_stick_x"] - chunk[i - 1]["right_stick_x"]
            dy = chunk[i]["right_stick_y"] - chunk[i - 1]["right_stick_y"]
            deltas.append((dx * dx + dy * dy) ** 0.5)
        if len(deltas) < 2:
            continue
        import numpy as np

        arr = np.array(deltas, dtype=np.float64)
        mean = float(arr.mean())
        cvs.append(float(arr.std() / mean) if mean > 1e-6 else 0.0)
    return cvs


def _post_webhook(url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:500]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:500]
    except Exception as exc:
        return 0, str(exc)[:200]


def _retina_pass(snaps: list[dict], window: int, source_id: str) -> dict:
    total_events = 0
    trajectory = 0
    windows = 0
    all_events = []
    per_window_anomalies: list[int] = []
    for end in range(window, len(snaps) + 1, window // 2 or 1):
        chunk = snaps[end - window : end]
        result = embed_controller_window(chunk, source_id=source_id, start_t=(end - window) / 1000.0)
        win_traj = sum(1 for e in result.events if e.type == EVT_TRAJECTORY_ANOMALOUS)
        total_events += len(result.events)
        trajectory += win_traj
        per_window_anomalies.append(win_traj)
        all_events.extend(result.events)
        windows += 1
    return {
        "windows": windows,
        "total_events": total_events,
        "trajectory_anomalies": trajectory,
        "per_window_anomalies": per_window_anomalies,
        "events": all_events,
    }


def _cross_oracle_summary(
    l4_per_window: list[float],
    retina_per_window: list[int],
    *,
    l4_anomaly: float,
    l4_continuity: float,
) -> dict:
    n = min(len(l4_per_window), len(retina_per_window))
    rule1 = rule2 = agree = 0
    windows: list[dict] = []
    for i in range(n):
        fired = classify_cross_oracle_window(
            l4_per_window[i],
            retina_per_window[i],
            l4_anomaly_threshold=l4_anomaly,
            l4_continuity_threshold=l4_continuity,
        )
        if RULE_RETINA_TRAJECTORY_WITHOUT_L4 in fired:
            rule1 += 1
        if RULE_L4_ANOMALY_WITHOUT_RETINA in fired:
            rule2 += 1
        if not fired:
            agree += 1
        windows.append({
            "window_index": i,
            "l4_mahalanobis": round(l4_per_window[i], 4),
            "retina_anomaly_count": retina_per_window[i],
            "fsca_would_fire": fired,
        })
    return {
        "windows_analyzed": n,
        "rule1_retina_without_l4": rule1,
        "rule2_l4_without_retina": rule2,
        "agreement_windows": agree,
        "agreement_rate": round(agree / n, 4) if n else 0.0,
        "l4_anomaly_threshold": l4_anomaly,
        "l4_continuity_threshold": l4_continuity,
        "per_window": windows,
    }


def _write_audit_artifact(audit_root: Path, sessions: list[dict]) -> Path:
    audit_root.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    md_path = audit_root / f"retina_cross_oracle_{today}.md"
    json_path = audit_root / "retina_cross_oracle_latest.json"
    total_windows = sum(s.get("cross_oracle", {}).get("windows_analyzed", 0) for s in sessions)
    total_r1 = sum(s.get("cross_oracle", {}).get("rule1_retina_without_l4", 0) for s in sessions)
    total_r2 = sum(s.get("cross_oracle", {}).get("rule2_l4_without_retina", 0) for s in sessions)
    total_agree = sum(s.get("cross_oracle", {}).get("agreement_windows", 0) for s in sessions)
    agg_rate = round(total_agree / total_windows, 4) if total_windows else 0.0

    real = [s for s in sessions if s.get("session") != "synthetic"]
    is_real = bool(real)
    capped = [s for s in real if s.get("max_frames") and s.get("frames_available", 0) > s.get("frames", 0)]
    l4_all_zero = all((s.get("l4_mean_distance") or 0.0) == 0.0 for s in sessions)
    if is_real:
        provenance = (
            f"Real `hw_*.json` replay: {len(real)} session(s), "
            f"{sessions[0].get('frames', 0)} frames/session"
            + (f" (capped from up to {max(s.get('frames_available', 0) for s in real)} available)" if capped else "")
            + ". Advisory dry-run — not a substitute for live tournament adjudication."
        )
    else:
        provenance = "Synthetic replay — not a substitute for live tournament adjudication."

    lines = [
        f"# Retina cross-oracle calibration audit ({today})",
        "",
        "Dry-run FSCA classifier vs L4 Mahalanobis on replay windows.",
        provenance,
        "",
        "## Aggregate",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Data provenance | {'real hw_*.json' if is_real else 'synthetic'} |",
        f"| Sessions | {len(sessions)} |",
        f"| Windows | {total_windows} |",
        f"| RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY | {total_r1} |",
        f"| L4_ANOMALY_WITHOUT_RETINA_SIGNAL | {total_r2} |",
        f"| Agreement rate | {agg_rate} |",
        "",
        "## Caveats",
        "",
        "- Agreement rate reflects mutual quiescence: both oracles stayed quiet on this data,",
        "  which is the expected/clean outcome for genuine human captures (no adversarial input).",
        "  It is NOT validation against spoofed/aimbot trajectories — use `--synthetic --aimbot-snap-at`",
        "  or `--macro-flat` for adversarial cross-oracle checks.",
    ]
    if l4_all_zero:
        lines += [
            "- L4 mahalanobis is ~0 across all windows. Two contributing effects: (1) calibration",
            "  captures here are still-hold/neutral-stick probes, so L5/trajectory signal is naturally",
            "  near zero; (2) the replay L4 proxy updates the fingerprint with the same window it then",
            "  measures (self-referential), so distance trends to ~0 on smooth sequential windows.",
            "  Treat the L4 arm as a structural sanity check, not a live Mahalanobis verdict.",
        ]
    lines += [
        "",
        "## Per session",
        "",
    ]
    for s in sessions:
        co = s.get("cross_oracle", {})
        lines.append(f"### {s.get('session', '?')}")
        lines.append(
            f"- windows={co.get('windows_analyzed', 0)} "
            f"rule1={co.get('rule1_retina_without_l4', 0)} "
            f"rule2={co.get('rule2_l4_without_retina', 0)} "
            f"agreement={co.get('agreement_rate', 0.0)}"
        )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload = {
        "as_of": today,
        "data_provenance": "real_hw_json" if is_real else "synthetic",
        "sessions": sessions,
        "aggregate": {
            "windows": total_windows,
            "rule1": total_r1,
            "rule2": total_r2,
            "agreement_rate": agg_rate,
            "l4_all_zero": l4_all_zero,
            "agreement_is_mutual_quiescence": True,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Retina calibration replay + L4/L5 comparison")
    parser.add_argument("--session", type=Path, default=None, help="Path to hw_*.json session")
    parser.add_argument("--sessions-dir", type=Path, default=ROOT / "sessions", help="Scan dir for hw_*.json")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic HID when no session file")
    parser.add_argument("--aimbot-snap-at", type=int, default=None)
    parser.add_argument("--macro-flat", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "logs")
    parser.add_argument(
        "--webhook-url",
        default="",
        help="Optional bridge POST /operator/retina-event URL (with api_key query)",
    )
    parser.add_argument(
        "--write-audit",
        action="store_true",
        help="Write audits/retina_cross_oracle_*.md + retina_cross_oracle_latest.json",
    )
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=ROOT / "audits",
        help="Directory for cross-oracle audit artifacts",
    )
    parser.add_argument(
        "--l4-anomaly-threshold",
        type=float,
        default=DEFAULT_L4_ANOMALY,
    )
    parser.add_argument(
        "--l4-continuity-threshold",
        type=float,
        default=DEFAULT_L4_CONTINUITY,
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help=(
            "Cap frames per session before embed/L4 passes (0 = all). "
            "embed_controller_window dynamics check is O(n^2); real hw_*.json "
            "captures are ~30k frames, so cap to keep replay tractable."
        ),
    )
    args = parser.parse_args()

    paths: list[Path] = []
    if args.session:
        paths = [args.session]
    elif not args.synthetic:
        paths = sorted(args.sessions_dir.glob("hw_*.json"))[:3]
        if not paths:
            print("No hw_*.json found — falling back to synthetic HID", file=sys.stderr)
            args.synthetic = True

    if args.synthetic and not paths:
        paths = [Path("synthetic")]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for path in paths:
        label = path.stem if path != Path("synthetic") else "synthetic"
        snaps = _load_snaps(None if path == Path("synthetic") else path, args.synthetic, args.aimbot_snap_at, args.macro_flat)
        frames_available = len(snaps)
        if args.max_frames and len(snaps) > args.max_frames:
            snaps = snaps[: args.max_frames]
        if len(snaps) < args.window:
            print(f"SKIP {label}: only {len(snaps)} frames (need {args.window})")
            continue

        retina = _retina_pass(snaps, args.window, source_id=f"replay_{label}")
        out_path = args.out_dir / f"retina_replay_{label}.jsonl"
        write_events_jsonl(retina["events"], str(out_path))

        if args.webhook_url and retina["events"]:
            _ev_dicts = [
                e.to_dict() if hasattr(e, "to_dict") else dict(e)
                for e in retina["events"][-20:]
            ]
            _payload = {
                "device_id": f"replay_{label}",
                "events": _ev_dicts,
                "anomaly_count": retina["trajectory_anomalies"],
            }
            _code, _body = _post_webhook(args.webhook_url, _payload)
            print(f"webhook {label}: HTTP {_code} {_body[:120]}", file=sys.stderr)

        l4 = _l4_distance(snaps, args.window)
        l5 = _l5_cv_proxy(snaps, args.window)
        cross_oracle = _cross_oracle_summary(
            l4,
            retina.get("per_window_anomalies", []),
            l4_anomaly=args.l4_anomaly_threshold,
            l4_continuity=args.l4_continuity_threshold,
        )
        row = {
            "session": label,
            "frames": len(snaps),
            "frames_available": frames_available,
            "max_frames": args.max_frames,
            "jsonl": str(out_path),
            "retina_windows": retina["windows"],
            "retina_events": retina["total_events"],
            "retina_trajectory_anomalies": retina["trajectory_anomalies"],
            "l4_windows": len(l4),
            "l4_mean_distance": round(sum(l4) / len(l4), 4) if l4 else None,
            "l5_mean_cv": round(sum(l5) / len(l5), 4) if l5 else None,
            "cross_oracle": cross_oracle,
        }
        summary.append(row)
        print(json.dumps(row))

    if not summary:
        return 1
    summary_path = args.out_dir / "retina_replay_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {summary_path}")
    if args.write_audit:
        audit_md = _write_audit_artifact(args.audit_dir, summary)
        print(f"Wrote {audit_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
