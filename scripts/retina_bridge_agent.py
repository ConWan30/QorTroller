#!/usr/bin/env python3
"""Retina Bridge Agent — local gameplay digest monitor.

This is NOT a Buzz agent. It runs alongside the QorTroller bridge and uses
Retina Visual Oracle to analyze gameplay frames, producing structured digests.

Operator-fired, fail-closed:
  - Requires RETINA_BRIDGE_AGENT_ENABLED=1
  - Requires NIM_API_KEY for the VLM
  - Outputs only digests to audits/retina_bridge_agent/
  - Never writes raw frames, video, keys, or social posts

Usage:
  $env:RETINA_BRIDGE_AGENT_ENABLED="1"
  $env:NIM_API_KEY="..."
  $env:RETINA_FRAME_SOURCE="video"
  $env:RETINA_VIDEO_PATH="C:\capture\session.mp4"
  $env:GAME_PROFILE_ID="ncaa_cfb_26"
  python scripts/retina_bridge_agent.py

Stop:
  python scripts/retina_bridge_agent.py --stop
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("retina_bridge_agent")

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = Path(os.environ.get("RETINA_AGENT_AUDIT_DIR", "audits/retina_bridge_agent"))
STOP_FILE = Path(os.environ.get("RETINA_AGENT_STOP_FILE", str(AUDIT_DIR / "STOP")))
INTERVAL_S = float(os.environ.get("RETINA_BRIDGE_AGENT_INTERVAL_S", "5"))
BRIDGE_BASE_URL = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8080").rstrip("/")


def _enabled() -> bool:
    return os.environ.get("RETINA_BRIDGE_AGENT_ENABLED", "0") == "1"


def _stop_requested() -> bool:
    return STOP_FILE.exists()


def _touch_stop() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FILE.touch()
    logger.info("[Retina Bridge Agent] stop signal written: %s", STOP_FILE)


def _get_session_id() -> str:
    """Use the bridge session id if available, else mint a local one."""
    try:
        import requests
        resp = requests.get(f"{BRIDGE_BASE_URL}/player/session-status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            sid = data.get("session_id") or data.get("session", {}).get("session_id")
            if sid:
                return str(sid)
    except Exception as exc:
        logger.debug("could not get session id from bridge: %s", exc)
    return f"local-{int(time.time() * 1e9)}"


def _bridge_up() -> bool:
    try:
        import requests
        resp = requests.get(f"{BRIDGE_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception as exc:
        logger.debug("bridge health check failed: %s", exc)
        return False


def _load_visual_oracle() -> Any:
    """Import and create a VisualOracle from the bridge module."""
    sys.path.insert(0, str(REPO_ROOT / "bridge"))
    from vapi_bridge.retina_visual_oracle import VisualOracle, VisualOracleConfig
    cfg = VisualOracleConfig()
    if not cfg.enabled:
        raise RuntimeError("VisualOracle not enabled (missing NIM_API_KEY or NIM_MODEL)")
    return VisualOracle(cfg)


def _frame_source(source: str):
    """Return a sync frame generator for the configured source."""
    if source == "video":
        path = os.environ.get("RETINA_VIDEO_PATH", "")
        if not path:
            raise RuntimeError("RETINA_VIDEO_PATH not set")
        import cv2
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(f"could not open video: {path}")

        def _gen():
            while cap.isOpened():
                ok, frame = cap.read()
                if not ok:
                    break
                yield frame
            cap.release()

        return _gen()

    if source == "dir":
        d = os.environ.get("RETINA_FRAME_DIR", "")
        if not d:
            raise RuntimeError("RETINA_FRAME_DIR not set")
        p = Path(d)
        files = sorted(p.glob("*.png")) + sorted(p.glob("*.jpg")) + sorted(p.glob("*.jpeg"))

        def _gen():
            for f in files:
                import cv2
                yield cv2.imread(str(f))

        return _gen()

    if source == "game":
        # Windows-only: attempt to use the bridge's RetinaGameCapture source.
        # This is a stub; real WGC/UVC integration lives in the bridge loop.
        raise NotImplementedError(
            "game source is not yet supported in retina_bridge_agent. "
            "Use the bridge's built-in VLM pipeline (vlm_session_manager) or a video/dir source."
        )

    raise RuntimeError(f"unknown frame source: {source}")


def _frame_hash(frame: Any) -> str:
    """SHA-256 hash of a frame (for digest identity, not pixel storage)."""
    try:
        import numpy as np
        h = hashlib.sha256(frame.tobytes()).hexdigest()
        return f"sha256:{h}"
    except Exception:
        return "sha256:unknown"


def _digest_observation(oracle: Any, frame: Any, frame_number: int) -> dict:
    """Run one frame through the oracle and return a scrubbed digest."""
    ctx = asyncio.get_event_loop().run_until_complete(oracle.analyze_frame(frame))
    # Cross-modal verify with empty motion/input features by default.
    verdict = oracle.verify(motion_features={}, input_features={})

    fields = {
        "timestamp_ns": int(time.time() * 1e9),
        "frame_number": frame_number,
        "frame_hash": _frame_hash(frame),
        "game_state": ctx.game_state.value if ctx else "unknown",
        "game_title": ctx.game_title if ctx else "",
        "screen_description": ctx.screen_description if ctx else "",
        "confidence": float(ctx.confidence) if ctx else 0.0,
        "frame_quality": ctx.frame_quality if ctx else "unknown",
        "cross_modal_match": bool(verdict.match) if verdict else False,
        "cross_modal_anomaly": bool(verdict.anomaly) if verdict else False,
        "cross_modal_anomaly_type": verdict.anomaly_type if verdict else "",
        "cross_modal_confidence": float(verdict.confidence) if verdict else 0.0,
        "model": oracle.config.nim_model,
    }

    # Add game-specific fields if present
    if ctx:
        for attr in [
            "football_home_score", "football_away_score", "football_quarter",
            "football_down", "football_yards_to_go", "football_possession",
            "football_clock_seconds", "football_play_type", "health", "ammo",
            "enemies_visible", "is_combat", "is_moving", "score", "round_info",
            "events", "has_screen_tearing", "has_lag_indicator",
        ]:
            val = getattr(ctx, attr, None)
            if val is not None and val != 0:
                fields[attr] = val

    return fields


def _write_summary(audit_file: Path, session_id: str, observations: list[dict]) -> None:
    if not observations:
        return
    gameplay = sum(1 for o in observations if o.get("game_state") == "gameplay")
    anomalies = sum(1 for o in observations if o.get("cross_modal_anomaly"))
    summary = {
        "session_id": session_id,
        "started_at_ns": observations[0].get("timestamp_ns"),
        "ended_at_ns": observations[-1].get("timestamp_ns"),
        "frame_count": observations[-1].get("frame_number", 0),
        "observation_count": len(observations),
        "gameplay_ratio": round(gameplay / len(observations), 4) if observations else 0.0,
        "anomaly_count": anomalies,
        "verdict": "pending",  # operator/EA sets final verdict from this data
        "commitment_root": "",  # operator/EA sets from PoAC chain
        "note": "Raw frames are not stored; this is a VLM digest only.",
    }
    summary_file = audit_file.with_suffix(".summary.json")
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("[Retina Bridge Agent] summary written: %s", summary_file)


def _main_loop() -> int:
    source = os.environ.get("RETINA_FRAME_SOURCE", "video")
    logger.info("[Retina Bridge Agent] starting; source=%s", source)

    session_id = _get_session_id()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_file = AUDIT_DIR / f"{session_id}.jsonl"
    observations: list[dict] = []

    oracle = _load_visual_oracle()
    sample_rate = max(1, int(oracle.config.frame_sample_rate))
    frame_number = 0

    while True:
        if _stop_requested():
            logger.info("[Retina Bridge Agent] stop requested")
            break

        if not _bridge_up():
            logger.info("[Retina Bridge Agent] bridge not reachable; waiting %ss", INTERVAL_S)
            time.sleep(INTERVAL_S)
            continue

        logger.info("[Retina Bridge Agent] bridge up; beginning capture for session %s", session_id)
        try:
            for frame in _frame_source(source):
                if _stop_requested():
                    break
                frame_number += 1
                if frame is None:
                    continue
                if frame_number % sample_rate != 0:
                    continue

                digest = _digest_observation(oracle, frame, frame_number)
                observations.append(digest)

                # Append to JSONL
                with audit_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(digest, ensure_ascii=False) + "\n")

                logger.debug(
                    "frame %s: state=%s confidence=%.2f",
                    frame_number,
                    digest.get("game_state"),
                    digest.get("confidence", 0.0),
                )

                # Small yield to keep loop responsive
                time.sleep(0.01)

                # Re-check bridge periodically
                if frame_number % (sample_rate * 60) == 0 and not _bridge_up():
                    logger.warning("[Retina Bridge Agent] bridge went down mid-capture")
                    break

        except StopIteration:
            logger.info("[Retina Bridge Agent] source exhausted")
        except Exception as exc:
            logger.error("[Retina Bridge Agent] capture error: %s", exc)
            time.sleep(INTERVAL_S)
            continue

        _write_summary(audit_file, session_id, observations)
        logger.info("[Retina Bridge Agent] capture ended; %s observations", len(observations))

        # For video/dir sources, exit after one pass; for game/live, loop.
        if source in ("video", "dir"):
            break

        time.sleep(INTERVAL_S)

    _write_summary(audit_file, session_id, observations)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true", help="Write stop signal and exit")
    args = parser.parse_args()

    if args.stop:
        _touch_stop()
        return 0

    if not _enabled():
        logger.error(
            "[Retina Bridge Agent] not enabled. Set RETINA_BRIDGE_AGENT_ENABLED=1 to start."
        )
        return 1

    if _stop_requested():
        STOP_FILE.unlink(missing_ok=True)

    return _main_loop()


if __name__ == "__main__":
    sys.exit(main())
