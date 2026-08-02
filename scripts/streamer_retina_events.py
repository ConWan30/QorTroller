#!/usr/bin/env python3
"""Streamer perception v0 - capture card -> JSONL + WebSocket events.

Design: docs/design/trio-retina-streamer-perception-v0.md

Usage:
  # List-friendly defaults (device 0 = first UVC / capture card index)
  python scripts/streamer_retina_events.py --device 0 --duration 60

  # No WebSocket (JSONL only)
  python scripts/streamer_retina_events.py --no-ws --max-frames 300

  # Synthetic self-test (no camera)
  python scripts/streamer_retina_events.py --synthetic --max-frames 90

OBS: add Browser Source -> tools/obs_streamer_perception_overlay.html
     (or serve file URL) with WS default ws://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

from vapi_bridge.streamer_perception import (  # noqa: E402
    EventBus,
    PerceptionConfig,
    StreamerPerceptionRuntime,
    WsFanout,
    build_source_dict,
    default_zones,
    make_event,
    run_ws_server,
)


def _session_id_from_env() -> str | None:
    for k in ("VSS_SESSION_ID", "GRIND_SESSION_ID", "STREAMER_SESSION_ID"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    # optional root .env grind id
    envp = ROOT / ".env"
    if envp.is_file():
        for line in envp.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("GRIND_SESSION_ID="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def _run_synthetic(cfg: PerceptionConfig, bus: EventBus) -> dict:
    """Generate synthetic frames (motion burst) without a camera."""
    import numpy as np

    rt = StreamerPerceptionRuntime(cfg, bus)
    rt.t0 = time.time()
    src = build_source_dict(cfg, synthetic=True)
    rt._source_cache = src
    bus.emit(
        make_event(
            "session_start",
            {"synthetic": True, "jsonl": str(cfg.jsonl_path)},
            session_id=cfg.session_id,
            source=src,
        )
    )
    h, w = 180, 320
    prev = None
    n = cfg.max_frames or 60
    t0 = time.time()
    for i in range(n):
        # idle then high motion (advance clock so hysteresis can fire)
        if i < n // 3:
            frame = np.zeros((h, w), dtype=np.uint8) + 40
        elif i < 2 * n // 3:
            noise = np.random.randint(0, 80, (h, w), dtype=np.uint8)
            frame = noise
        else:
            frame = np.zeros((h, w), dtype=np.uint8) + 40
            frame[20:60, 20:100] = 200  # zone flash
        now = t0 + i * 0.05  # 20 Hz synthetic clock
        rt.process_gray(frame, now)
        if i % 15 == 0:
            bus.emit(
                make_event(
                    "frame_stats",
                    {"n": i, "synthetic": True},
                    session_id=cfg.session_id,
                    source=src,
                )
            )
        time.sleep(0.01)
    summary = {
        "frames": n,
        "events": bus.events_emitted,
        "synthetic": True,
        "source_kind": src.get("kind"),
    }
    bus.emit(
        make_event("session_end", summary, session_id=cfg.session_id, source=src)
    )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Streamer Retina events v0")
    ap.add_argument("--device", type=int, default=int(os.environ.get("RETINA_UVC_INDEX", "0")))
    ap.add_argument(
        "--device-name",
        default=os.environ.get("RETINA_UVC_DEVICE_NAME", "") or None,
        help="Friendly device name for WP-S1 kind sniff (or set RETINA_UVC_DEVICE_NAME)",
    )
    ap.add_argument(
        "--source-kind",
        default=os.environ.get("RETINA_SOURCE_KIND", "") or None,
        help="Override source.kind: uvc_card|obs_virtual|unknown|synthetic",
    )
    ap.add_argument(
        "--secondary-device",
        type=int,
        default=None,
        help="WP-S2 groundwork: reserve secondary UVC index (not dual-opened yet)",
    )
    ap.add_argument(
        "--secondary-device-name",
        default=None,
        help="Friendly name for secondary source kind sniff",
    )
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps", type=float, default=20.0)
    ap.add_argument("--backend", default=os.environ.get("RETINA_UVC_BACKEND", "auto"))
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--out", default="", help="JSONL path")
    ap.add_argument("--ws-port", type=int, default=8765)
    ap.add_argument("--no-ws", action="store_true")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--duration", type=float, default=0.0, help="Stop after N seconds (0=until Ctrl+C)")
    ap.add_argument("--synthetic", action="store_true", help="No camera; synthetic motion")
    ap.add_argument("--no-zones", action="store_true")
    ap.add_argument("--snapshot", default="", help="Save first full-res frame to this PNG path for eye-check")
    args = ap.parse_args()

    out = Path(args.out) if args.out else (
        ROOT / "logs" / f"streamer_perception_{int(time.time())}.jsonl"
    )
    session_id = args.session_id or _session_id_from_env()
    cfg = PerceptionConfig(
        device=args.device,
        device_name=args.device_name or None,
        source_kind=args.source_kind or None,
        secondary_device=args.secondary_device,
        secondary_device_name=args.secondary_device_name,
        width=args.width,
        height=args.height,
        fps_target=args.fps,
        backend=args.backend,
        session_id=session_id,
        zones=[] if args.no_zones else default_zones(),
        jsonl_path=out,
        ws_port=args.ws_port,
        enable_ws=not args.no_ws and not args.synthetic,
        max_frames=args.max_frames,
        snapshot=Path(args.snapshot) if args.snapshot else None,
    )

    bus = EventBus(cfg.jsonl_path)
    fanout = WsFanout()
    loop_holder: dict = {}

    if cfg.enable_ws:
        def _ws_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop_holder["loop"] = loop
            try:
                loop.run_until_complete(run_ws_server(cfg.ws_host, cfg.ws_port, fanout))
            except Exception as e:
                print(f"[streamer-perception] WS server stopped: {e}", file=sys.stderr)

        t = threading.Thread(target=_ws_thread, name="ws-fanout", daemon=True)
        t.start()
        time.sleep(0.3)
        bus.subscribe(
            lambda ev: fanout.publish_threadsafe(loop_holder["loop"], ev)
            if loop_holder.get("loop")
            else None
        )
        print(f"[streamer-perception] WebSocket ws://{cfg.ws_host}:{cfg.ws_port}")

    src_preview = build_source_dict(cfg, synthetic=bool(args.synthetic))
    print(f"[streamer-perception] JSONL -> {out}")
    print(f"[streamer-perception] source.kind={src_preview.get('kind')} device={src_preview.get('device')}")
    if src_preview.get("name"):
        print(f"[streamer-perception] source.name={src_preview.get('name')}")
    if src_preview.get("secondary"):
        print(f"[streamer-perception] secondary reserved (not opened): {src_preview['secondary']}")
    print("[streamer-perception] advisory only - not humanity/tournament proof")
    print("[streamer-perception] EYE-CHECK: confirm feed is GAME not webcam (kind tag is not proof)")

    if args.duration > 0 and not args.synthetic:
        # approximate max frames from duration
        cfg.max_frames = int(args.duration * args.fps) or 1

    if args.synthetic:
        summary = _run_synthetic(cfg, bus)
    else:
        try:
            rt = StreamerPerceptionRuntime(cfg, bus)
            if args.duration > 0:
                # hard stop thread via max_frames already set
                pass
            summary = rt.run()
        except Exception as e:
            print(f"[streamer-perception] FAIL: {e}", file=sys.stderr)
            return 1

    print(json_dumps := __import__("json").dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
