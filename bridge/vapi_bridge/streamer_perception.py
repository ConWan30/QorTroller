"""Streamer perception v0 — capture-card → structured events (advisory).

Domain: QORTROLLER-STREAMER-PERCEPTION-v0
See docs/design/trio-retina-streamer-perception-v0.md

- No YOLO required
- No chain / FROZEN / L6
- Optical events are advisory only
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

DOMAIN = "QORTROLLER-STREAMER-PERCEPTION-v0"
SCHEMA_V = 0

# WP-S1 — source.kind tags (docs/design/trio-retina-obs-sync-v0.md)
SOURCE_UVC_CARD = "uvc_card"
SOURCE_OBS_VIRTUAL = "obs_virtual"
SOURCE_UNKNOWN = "unknown"
SOURCE_SYNTHETIC = "synthetic"
SOURCE_KINDS = frozenset(
    {SOURCE_UVC_CARD, SOURCE_OBS_VIRTUAL, SOURCE_UNKNOWN, SOURCE_SYNTHETIC}
)

# Substrings matched against device friendly names (case-insensitive).
_OBS_NAME_MARKERS = (
    "obs virtual camera",
    "obs-virtualcam",
    "obs virtual cam",
    "obs-camera",
    "obs virtual",
    "virtualcam",
)


def now_ns() -> int:
    return time.time_ns()


def classify_source_kind(
    device_name: Optional[str] = None,
    *,
    override: Optional[str] = None,
    synthetic: bool = False,
) -> str:
    """Classify UVC source kind for event tagging (WP-S1).

    Priority: override > synthetic > name sniff > unknown.
    Never claims clean-game fidelity — operators still eye-check.
    """
    if override is not None and str(override).strip():
        o = str(override).strip().lower().replace("-", "_")
        aliases = {
            "uvc_card": SOURCE_UVC_CARD,
            "card": SOURCE_UVC_CARD,
            "capture_card": SOURCE_UVC_CARD,
            "obs_virtual": SOURCE_OBS_VIRTUAL,
            "obs": SOURCE_OBS_VIRTUAL,
            "obsvirtual": SOURCE_OBS_VIRTUAL,
            "obs_vcam": SOURCE_OBS_VIRTUAL,
            "unknown": SOURCE_UNKNOWN,
            "synthetic": SOURCE_SYNTHETIC,
        }
        if o in aliases:
            return aliases[o]
        if o in SOURCE_KINDS:
            return o
        raise ValueError(
            f"invalid source kind override '{override}'; "
            f"expected one of {sorted(SOURCE_KINDS)} or card|obs"
        )
    if synthetic:
        return SOURCE_SYNTHETIC
    if not device_name or not str(device_name).strip():
        return SOURCE_UNKNOWN
    n = str(device_name).strip().lower()
    for marker in _OBS_NAME_MARKERS:
        if marker in n:
            return SOURCE_OBS_VIRTUAL
    if "virtual camera" in n:
        return SOURCE_OBS_VIRTUAL
    return SOURCE_UVC_CARD


def make_event(
    etype: str,
    payload: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    source: Optional[Dict[str, Any]] = None,
    ts_ns: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "v": SCHEMA_V,
        "domain": DOMAIN,
        "ts_ns": ts_ns if ts_ns is not None else now_ns(),
        "session_id": session_id,
        "source": source or {},
        "type": etype,
        "payload": payload,
    }


@dataclass
class ZoneSpec:
    zone_id: str
    # Normalized ROI fractions of frame: x0,y0,x1,y1 in [0,1]
    x0: float
    y0: float
    x1: float
    y1: float
    # Mean absolute luma delta vs EMA baseline to fire "active"
    threshold: float = 12.0


@dataclass
class PerceptionConfig:
    device: int = 0
    width: int = 1280
    height: int = 720
    fps_target: float = 20.0
    process_scale: float = 0.5  # downscale for metrics
    backend: str = "auto"  # auto|msmf|dshow|any
    session_id: Optional[str] = None
    # WP-S1 source tagging
    device_name: Optional[str] = None  # friendly name if known (CLI / env / probe)
    source_kind: Optional[str] = None  # override: uvc_card|obs_virtual|unknown|synthetic
    # WP-S2 groundwork (not dual-loop yet): secondary UVC index reserved
    secondary_device: Optional[int] = None
    secondary_device_name: Optional[str] = None
    secondary_source_kind: Optional[str] = None
    motion_high: float = 8.0
    motion_idle: float = 2.0
    activity_hysteresis_s: float = 1.0
    stats_every_s: float = 2.0
    heartbeat_every_s: float = 5.0
    zones: List[ZoneSpec] = field(default_factory=list)
    jsonl_path: Optional[Path] = None
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765
    enable_ws: bool = True
    max_frames: int = 0  # 0 = unlimited
    snapshot: Optional[Path] = None  # save first full-res frame for eye-check


def default_zones() -> List[ZoneSpec]:
    """CFB-ish HUD ROIs as fractions (tune per title/resolution)."""
    return [
        ZoneSpec("hud_scoreboard", 0.25, 0.0, 0.75, 0.12, threshold=10.0),
        ZoneSpec("hud_bottom", 0.15, 0.85, 0.85, 1.0, threshold=10.0),
    ]


class EventBus:
    """JSONL + optional in-process subscribers; WebSocket fanout is external."""

    def __init__(self, jsonl_path: Optional[Path] = None):
        self.jsonl_path = jsonl_path
        self._subs: List[Callable[[Dict[str, Any]], None]] = []
        self.events_emitted = 0
        if jsonl_path is not None:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        self._subs.append(fn)

    def emit(self, event: Dict[str, Any]) -> None:
        self.events_emitted += 1
        if self.jsonl_path is not None:
            with self.jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, separators=(",", ":")) + "\n")
        for fn in self._subs:
            try:
                fn(event)
            except Exception:
                pass


def frame_mean_luma(gray) -> float:
    import numpy as np

    return float(np.mean(gray))


def frame_motion(prev_gray, gray) -> float:
    """Mean abs diff — cheap motion score."""
    import numpy as np

    if prev_gray is None:
        return 0.0
    return float(np.mean(np.abs(gray.astype("float32") - prev_gray.astype("float32"))))


def crop_zone(gray, zone: ZoneSpec):
    h, w = gray.shape[:2]
    x0 = max(0, min(w - 1, int(zone.x0 * w)))
    x1 = max(x0 + 1, min(w, int(zone.x1 * w)))
    y0 = max(0, min(h - 1, int(zone.y0 * h)))
    y1 = max(y0 + 1, min(h, int(zone.y1 * h)))
    return gray[y0:y1, x0:x1]


def open_capture(device: int, width: int, height: int, fps: float, backend: str):
    """Open UVC/capture-card index. Returns (cap, backend_name) or raises."""
    import cv2

    backend = (backend or "auto").lower()
    order: List[Tuple[str, Optional[int]]] = []
    if backend == "msmf":
        order = [("msmf", getattr(cv2, "CAP_MSMF", None))]
    elif backend == "dshow":
        order = [("dshow", getattr(cv2, "CAP_DSHOW", None))]
    elif backend == "any":
        order = [("any", None)]
    else:
        order = [
            ("msmf", getattr(cv2, "CAP_MSMF", None)),
            ("dshow", getattr(cv2, "CAP_DSHOW", None)),
            ("any", None),
        ]

    last_err = None
    for name, be in order:
        try:
            cap = cv2.VideoCapture(device, be) if be is not None else cv2.VideoCapture(device)
            if not cap.isOpened():
                cap.release()
                last_err = f"{name}: not opened"
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                last_err = f"{name}: first read failed"
                continue
            return cap, name, frame
        except Exception as e:
            last_err = f"{name}: {e}"
    raise RuntimeError(f"could not open capture device {device}: {last_err}")


def build_source_dict(
    cfg: PerceptionConfig,
    *,
    backend: Optional[str] = None,
    synthetic: bool = False,
) -> Dict[str, Any]:
    """Build the event `source` object (WP-S1)."""
    kind = classify_source_kind(
        cfg.device_name,
        override=cfg.source_kind,
        synthetic=synthetic,
    )
    out: Dict[str, Any] = {
        "kind": kind,
        "device": "synthetic" if synthetic else cfg.device,
        "backend": backend if backend is not None else cfg.backend,
        "width": cfg.width,
        "height": cfg.height,
        "fps_target": cfg.fps_target,
    }
    if cfg.device_name:
        out["name"] = cfg.device_name
    # Dual-path groundwork: announce secondary if configured (not opened yet)
    if cfg.secondary_device is not None:
        sk = classify_source_kind(
            cfg.secondary_device_name,
            override=cfg.secondary_source_kind,
        )
        out["secondary"] = {
            "kind": sk,
            "device": cfg.secondary_device,
            "name": cfg.secondary_device_name,
            "opened": False,
            "note": "WP-S2 dual-open not yet active; secondary is reserved/config-only",
        }
    return out


class StreamerPerceptionRuntime:
    """Main loop: grab frames → metrics → events."""

    def __init__(self, cfg: PerceptionConfig, bus: EventBus):
        self.cfg = cfg
        self.bus = bus
        self._activity = "idle"
        self._activity_since = 0.0
        self._zone_state: Dict[str, str] = {}
        self._zone_ema: Dict[str, float] = {}
        self.frames = 0
        self.t0 = 0.0
        self._source_cache: Optional[Dict[str, Any]] = None

    def _source(self) -> Dict[str, Any]:
        if self._source_cache is not None:
            return dict(self._source_cache)
        return build_source_dict(self.cfg)

    def emit(self, etype: str, payload: Dict[str, Any]) -> None:
        self.bus.emit(
            make_event(
                etype,
                payload,
                session_id=self.cfg.session_id,
                source=self._source(),
            )
        )

    def process_gray(self, gray, now: float) -> Tuple[float, float]:
        """Pure metrics path (testable without camera). Returns (motion, luma)."""
        if not hasattr(self, "_prev_gray"):
            self._prev_gray = None
        motion = frame_motion(self._prev_gray, gray)
        self._prev_gray = gray
        luma = frame_mean_luma(gray)

        # Activity with hysteresis (hold desired for activity_hysteresis_s)
        if motion >= self.cfg.motion_high:
            desired = "high"
        elif motion <= self.cfg.motion_idle:
            desired = "idle"
        else:
            desired = "low"

        if not hasattr(self, "_pending_activity"):
            self._pending_activity = self._activity
            self._pending_since = now

        if desired != self._pending_activity:
            self._pending_activity = desired
            self._pending_since = now

        hold = self.cfg.activity_hysteresis_s
        if (
            self._pending_activity != self._activity
            and (hold <= 0.0 or (now - self._pending_since) >= hold)
        ):
            prev = self._activity
            self._activity = self._pending_activity
            self.emit(
                "activity",
                {
                    "level": self._activity,
                    "prev": prev,
                    "motion": round(motion, 3),
                    "mean_luma": round(luma, 2),
                },
            )

        # Zones
        for z in self.cfg.zones:
            crop = crop_zone(gray, z)
            if crop.size == 0:
                continue
            z_luma = frame_mean_luma(crop)
            ema = self._zone_ema.get(z.zone_id)
            if ema is None:
                self._zone_ema[z.zone_id] = z_luma
                self._zone_state[z.zone_id] = "quiet"
                continue
            delta = abs(z_luma - ema)
            # slow EMA
            self._zone_ema[z.zone_id] = 0.95 * ema + 0.05 * z_luma
            state = "active" if delta >= z.threshold else "quiet"
            prev = self._zone_state.get(z.zone_id, "quiet")
            if state != prev:
                self._zone_state[z.zone_id] = state
                self.emit(
                    "zone",
                    {
                        "zone_id": z.zone_id,
                        "state": state,
                        "prev": prev,
                        "delta": round(delta, 3),
                        "luma": round(z_luma, 2),
                    },
                )

        return motion, luma

    def run(self) -> Dict[str, Any]:
        import cv2

        self.t0 = time.time()
        self.emit(
            "session_start",
            {
                "jsonl": str(self.cfg.jsonl_path) if self.cfg.jsonl_path else None,
                "ws": f"ws://{self.cfg.ws_host}:{self.cfg.ws_port}"
                if self.cfg.enable_ws
                else None,
                "advisory": True,
                "note": "optical events are not humanity or tournament proof",
            },
        )

        cap, backend_name, first = open_capture(
            self.cfg.device,
            self.cfg.width,
            self.cfg.height,
            self.cfg.fps_target,
            self.cfg.backend,
        )
        self.cfg.backend = backend_name
        # Resolve source.kind after open (WP-S1); name may come from CLI/env only
        self._source_cache = build_source_dict(self.cfg, backend=backend_name)
        # Eye-check hint — still mandatory; kind tag is not proof of clean game
        h0, w0 = first.shape[:2]
        if self.cfg.snapshot is not None:
            self.cfg.snapshot.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(self.cfg.snapshot), first)
            self.emit(
                "frame_stats",
                {
                    "n": 0,
                    "eye_check": f"operator must verify first frames are GAME not webcam; snapshot saved to {self.cfg.snapshot}",
                    "first_shape": [int(h0), int(w0)],
                    "mean_luma": round(frame_mean_luma(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)), 2),
                    "snapshot": str(self.cfg.snapshot),
                },
            )
        else:
            self.emit(
                "frame_stats",
                {
                    "n": 0,
                    "eye_check": "operator must verify first frames are GAME not webcam",
                    "first_shape": [int(h0), int(w0)],
                    "mean_luma": round(frame_mean_luma(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)), 2),
                },
            )

        period = 1.0 / max(self.cfg.fps_target, 1.0)
        last_stats = 0.0
        last_hb = 0.0
        n = 0
        try:
            while True:
                loop_t0 = time.time()
                ok, frame = cap.read()
                if not ok or frame is None:
                    time.sleep(0.01)
                    continue
                n += 1
                self.frames = n
                # downscale for metrics
                scale = self.cfg.process_scale
                if scale < 1.0:
                    frame_s = cv2.resize(
                        frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                    )
                else:
                    frame_s = frame
                gray = cv2.cvtColor(frame_s, cv2.COLOR_BGR2GRAY)
                now = time.time()
                motion, luma = self.process_gray(gray, now)

                if now - last_stats >= self.cfg.stats_every_s:
                    elapsed = max(now - self.t0, 1e-6)
                    self.emit(
                        "frame_stats",
                        {
                            "n": n,
                            "fps_meas": round(n / elapsed, 2),
                            "mean_luma": round(luma, 2),
                            "motion": round(motion, 3),
                            "activity": self._activity,
                        },
                    )
                    last_stats = now

                if now - last_hb >= self.cfg.heartbeat_every_s:
                    self.emit(
                        "heartbeat",
                        {"uptime_s": round(now - self.t0, 1), "frames": n},
                    )
                    last_hb = now

                if self.cfg.max_frames and n >= self.cfg.max_frames:
                    break

                # pace
                dt = time.time() - loop_t0
                sleep = period - dt
                if sleep > 0:
                    time.sleep(sleep)
        except KeyboardInterrupt:
            pass
        finally:
            cap.release()
            elapsed = max(time.time() - self.t0, 1e-6)
            summary = {
                "frames": n,
                "events": self.bus.events_emitted,
                "elapsed_s": round(elapsed, 2),
                "fps_meas": round(n / elapsed, 2),
            }
            self.emit("session_end", summary)
            return summary


# --- WebSocket server (optional dependency: websockets) ---------------------

class WsFanout:
    """Tiny broadcast hub for asyncio websockets."""

    def __init__(self):
        self.clients: set = set()
        self._queue: Deque[str] = deque(maxlen=256)

    async def register(self, ws) -> None:
        self.clients.add(ws)

    async def unregister(self, ws) -> None:
        self.clients.discard(ws)

    def publish_threadsafe(self, loop: asyncio.AbstractEventLoop, event: Dict[str, Any]) -> None:
        msg = json.dumps(event, separators=(",", ":"))
        self._queue.append(msg)

        async def _broadcast() -> None:
            dead = []
            for ws in list(self.clients):
                try:
                    await ws.send(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.clients.discard(ws)

        try:
            asyncio.run_coroutine_threadsafe(_broadcast(), loop)
        except Exception:
            pass


async def run_ws_server(host: str, port: int, fanout: WsFanout):
    try:
        import websockets
    except ImportError as e:
        raise RuntimeError(
            "websockets package required for --ws "
            "(pip install websockets) or pass --no-ws"
        ) from e

    async def handler(ws):
        await fanout.register(ws)
        try:
            # replay recent
            for msg in list(fanout._queue)[-32:]:
                try:
                    await ws.send(msg)
                except Exception:
                    break
            async for _ in ws:
                pass  # ignore client messages in v0
        finally:
            await fanout.unregister(ws)

    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever
