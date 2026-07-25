#!/usr/bin/env python3
"""Autonomous watcher: poll active RWM capture until stop, then post-check.

Prints one JSON line per event (line-buffered). Exits after stop+check.

Mid-session honesty:
  - eye_check_prompt: first new panel crop path so operator can open it (live_05 lesson)
  - frozen_ring_alert: after diversity_alert_at crops, unique recent content == 1
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# Ensure we always resolve paths from this file's repo root (not caller's cwd).

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / "retina_daemon.state.json"
_CROPS = _REPO / "retina_kf_crops"
_ARCHIVE = _REPO / "retina_kf_archive"


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _crop_count() -> int:
    if not _CROPS.is_dir():
        return 0
    return sum(1 for _ in _CROPS.glob("panel_*.png"))


def _newest_panel() -> Path | None:
    if not _CROPS.is_dir():
        return None
    files = list(_CROPS.glob("panel_*.png"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _newest_archive_for(label: str, started_at: int) -> Path | None:
    if not _ARCHIVE.is_dir():
        return None
    # exact label_started_at first
    exact = _ARCHIVE / f"{label}_{started_at}"
    if exact.is_dir():
        return exact
    cands = sorted(
        (d for d in _ARCHIVE.glob(f"{label}_*") if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
    )
    return cands[-1] if cands else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Watch active RWM capture; mid-session diversity alerts")
    ap.add_argument(
        "--diversity-alert-at",
        type=int,
        default=10,
        help="After this many panel crops, unique==1 over recent sample triggers frozen_ring_alert (default 10)",
    )
    ap.add_argument(
        "--sample-limit",
        type=int,
        default=20,
        help="How many most-recent crops to hash for the diversity probe (default 20)",
    )
    ap.add_argument(
        "--interval-s",
        type=float,
        default=15.0,
        help="Poll interval seconds (default 15)",
    )
    args = ap.parse_args(argv)

    diversity_alert_at = max(1, int(args.diversity_alert_at))
    sample_limit = max(2, int(args.sample_limit))
    interval_s = max(1.0, float(args.interval_s))

    if not _STATE.is_file():
        _emit({"event": "no_active_session", "state": str(_STATE)})
        return 2

    st = json.loads(_STATE.read_text(encoding="utf-8"))
    label = st.get("label", "session")
    started_at = int(st.get("started_at", 0))
    pid = st.get("pid")
    _emit({
        "event": "watch_started",
        "label": label,
        "started_at": started_at,
        "pid": pid,
        "port": st.get("port"),
        "interval_s": interval_s,
        "diversity_alert_at": diversity_alert_at,
        "sample_limit": sample_limit,
    })

    diversity_alerted = False
    eye_check_emitted = False
    last_n = _crop_count()
    last_report = time.time()
    _emit({"event": "ring_baseline", "panel_count": last_n, "diversity_alert_at": diversity_alert_at})

    while _STATE.is_file():
        time.sleep(interval_s)
        n = _crop_count()
        now = time.time()

        # First-crop eye-check: emit absolute path once so operator can open the PNG
        # before finishing a frozen/menu ROI session (live_04/05 class).
        if not eye_check_emitted and n > 0:
            newest = _newest_panel()
            if newest is not None:
                eye_check_emitted = True
                _emit({
                    "event": "eye_check_prompt",
                    "panel_count": n,
                    "path": str(newest.resolve()),
                    "detail": (
                        "OPEN this crop now — confirm it shows live gameplay (not menu/static UI). "
                        "If frozen or wrong ROI, retarget UVC/source before session ends."
                    ),
                })

        if n != last_n or (now - last_report) >= 60:
            evt = {
                "event": "ring_progress",
                "panel_count": n,
                "delta": n - last_n,
                "elapsed_s": int(now - last_report) if n == last_n else int(interval_s),
            }
            # Cheap diversity probe: hash last sample_limit crops only
            if n >= 5:
                try:
                    sys.path.insert(0, str(_REPO / "bridge"))
                    from vapi_bridge.rwm_panel_diversity import panel_stats_for_dir
                    stats = panel_stats_for_dir(_CROPS, sample_limit=sample_limit)
                    evt["unique_recent"] = stats["unique"]
                    evt["unique_label"] = stats["label"]
                    if (
                        not diversity_alerted
                        and n >= diversity_alert_at
                        and stats["frozen"]
                    ):
                        diversity_alerted = True
                        _emit({
                            "event": "frozen_ring_alert",
                            "panel_count": n,
                            "unique_recent": stats["unique"],
                            "diversity_alert_at": diversity_alert_at,
                            "detail": (
                                f"last-{sample_limit} panel crops are byte-identical — retarget UVC/ROI "
                                "or unpause game; session will FROZEN_RING at stop"
                            ),
                        })
                except Exception as e:  # noqa: BLE001 — never kill the watcher
                    evt["diversity_error"] = repr(e)[:120]
            _emit(evt)
            last_n = n
            last_report = now

    _emit({"event": "session_stopped", "final_ring_count": _crop_count()})
    time.sleep(2)  # let archive + RWM finish writing

    arch = _newest_archive_for(label, started_at)
    if arch is None:
        # wait a bit more for archive dir
        for _ in range(10):
            time.sleep(1)
            arch = _newest_archive_for(label, started_at)
            if arch is not None:
                break

    if arch is None:
        _emit({"event": "no_archive_found", "label": label, "started_at": started_at})
        return 1

    _emit({"event": "archive_found", "session_dir": str(arch), "name": arch.name})

    # wait for rwm_manifest if still writing
    chain = arch / "rwm_manifest_chain.json"
    for i in range(120):
        if chain.is_file():
            break
        time.sleep(1)
    else:
        _emit({"event": "rwm_chain_missing", "session_dir": str(arch)})
        # still run post-check for honest-null
        pass

    cmd = [
        sys.executable,
        str(_REPO / "scripts" / "rwm_post_session_check.py"),
        "--session-dir",
        str(arch),
    ]
    _emit({"event": "post_check_start", "cmd": cmd})
    proc = subprocess.run(cmd, cwd=str(_REPO), capture_output=True, text=True)
    _emit({
        "event": "post_check_done",
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-500:],
    })

    # optional: diversity-strict note already in stdout
    if proc.returncode == 0 and chain.is_file():
        # small escrow dogfood sample (local audits, not committed)
        try:
            man = json.loads(chain.read_text(encoding="utf-8"))
            n_frames = len(man.get("frames") or [])
            if n_frames >= 4:
                idxs = sorted({0, n_frames // 4, n_frames // 2, n_frames - 1})
                reveal = ",".join(str(i) for i in idxs)
                out = _REPO / "audits" / f"rwm_escrow_{arch.name}.json"
                ecmd = [
                    sys.executable,
                    str(_REPO / "scripts" / "rwm_dispute_escrow.py"),
                    "build",
                    "--archive", str(arch),
                    "--reveal", reveal,
                    "--reason", f"autonomous dogfood escrow after {arch.name}",
                    "--case-id", arch.name[:40],
                    "--out", str(out),
                ]
                ep = subprocess.run(ecmd, cwd=str(_REPO), capture_output=True, text=True)
                _emit({
                    "event": "escrow_dogfood",
                    "returncode": ep.returncode,
                    "stdout_tail": (ep.stdout or "")[-800:],
                    "out": str(out) if ep.returncode == 0 else None,
                })
        except Exception as e:  # noqa: BLE001
            _emit({"event": "escrow_dogfood_error", "error": repr(e)[:200]})

    _emit({"event": "watch_complete", "post_check_rc": proc.returncode})
    return 0 if proc.returncode in (0, 2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
