"""Streamer perception v0 — capture-card → structured events (advisory).

Domain: QORTROLLER-STREAMER-PERCEPTION-v0
See docs/design/trio-retina-streamer-perception-v0.md

- No YOLO required
- No chain / FROZEN / L6
- Optical events are advisory only
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Protocol, Tuple

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


def clock_ns() -> int:
    """Shared monotonic clock field for cross-plane correlation (WP-S4)."""
    return time.monotonic_ns()


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
    session_head_ns: Optional[int] = None,
) -> Dict[str, Any]:
    """Build one event; ts_ns defaults to wall time, clock_ns to monotonic."""
    return {
        "v": SCHEMA_V,
        "domain": DOMAIN,
        "ts_ns": ts_ns if ts_ns is not None else now_ns(),
        "clock_ns": clock_ns(),
        "session_head_ns": session_head_ns,
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
    # WP-S3 session marker (off|qr|text)
    session_marker: str = "off"
    session_marker_qr_path: Optional[Path] = None
    # WP-S4 shared session clock head (set by runtime; None until start)
    session_head_ns: Optional[int] = None
    # WP-S5 presence-sync activity
    presence_touch_file: Optional[Path] = None
    presence_timeout_s: float = 5.0
    presence_poll_url: Optional[str] = None
    # Marker decode cadence
    marker_check_every_s: float = 5.0


def default_zones() -> List[ZoneSpec]:
    """CFB-ish HUD ROIs as fractions (tune per title/resolution)."""
    return [
        ZoneSpec("hud_scoreboard", 0.25, 0.0, 0.75, 0.12, threshold=10.0),
        ZoneSpec("hud_bottom", 0.15, 0.85, 0.85, 1.0, threshold=10.0),
    ]


class EventBus:
    """JSONL + optional in-process subscribers; WebSocket fanout is external.

    Thread-safe for multi-source capture (WP-S2).
    """

    def __init__(self, jsonl_path: Optional[Path] = None):
        self.jsonl_path = jsonl_path
        self._subs: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        self.events_emitted = 0
        if jsonl_path is not None:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._subs.append(fn)

    def emit(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self.events_emitted += 1
            if self.jsonl_path is not None:
                with self.jsonl_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event, separators=(",", ":")) + "\n")
            for fn in list(self._subs):
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


def _build_single_source(
    cfg: PerceptionConfig,
    *,
    backend: Optional[str] = None,
    synthetic: bool = False,
    opened: bool = False,
    device: Optional[int] = None,
    device_name: Optional[str] = None,
    source_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a source dict for a single device."""
    kind = classify_source_kind(
        device_name if device_name is not None else cfg.device_name,
        override=source_kind if source_kind is not None else cfg.source_kind,
        synthetic=synthetic,
    )
    dev = "synthetic" if synthetic else (device if device is not None else cfg.device)
    out: Dict[str, Any] = {
        "kind": kind,
        "device": dev,
        "backend": backend if backend is not None else cfg.backend,
        "width": cfg.width,
        "height": cfg.height,
        "fps_target": cfg.fps_target,
        "opened": opened,
    }
    name = device_name if device_name is not None else cfg.device_name
    if name:
        out["name"] = name
    return out


def build_source_dict(
    cfg: PerceptionConfig,
    *,
    backend: Optional[str] = None,
    synthetic: bool = False,
) -> Dict[str, Any]:
    """Build the event `source` object (WP-S1); primary source + secondary reserve."""
    out = _build_single_source(cfg, backend=backend, synthetic=synthetic)
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
            "note": "WP-S2 dual-open; secondary is reserved/config-only until opened",
        }
    return out


def make_marker_digest(session_id: Optional[str], session_head_ns: Optional[int]) -> str:
    """Short advisory digest for session marker overlay (WP-S3)."""
    body = f"{session_id or ''}:{session_head_ns or 0}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def render_marker_text(session_id: Optional[str], session_head_ns: Optional[int]) -> str:
    """Text the overlay should display and the decoder should look for."""
    return f"{session_id or ''}|{make_marker_digest(session_id, session_head_ns)}"


def generate_qr_file(text: str, path: Path) -> bool:
    """Generate a QR image if the qrcode package is installed (WP-S3, fail-open)."""
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path))
        return True
    except Exception:
        return False


def _try_decode_qr(gray) -> Optional[str]:
    """Fail-open QR decode using OpenCV QRCodeDetector."""
    try:
        import cv2

        det = cv2.QRCodeDetector()
        data, _bbox, _ = det.detectAndDecode(gray)
        if data:
            return str(data)
    except Exception:
        pass
    return None


def _try_decode_text(gray) -> Optional[str]:
    """Fail-open text OCR from the top-left marker region (WP-S3).

    Prefers rapidocr, falls back to pytesseract. Returns None if neither is installed.
    """
    h, w = gray.shape[:2]
    # Marker overlay is expected in the top-left region
    crop = gray[0 : max(1, h // 4), 0 : max(1, w // 3)]
    if crop.size == 0:
        return None
    try:
        from rapidocr import RapidOCR

        ocr = RapidOCR()
        result, _ = ocr(crop)
        if result:
            return str(result[0][1]).strip()
    except Exception:
        pass
    try:
        import pytesseract  # type: ignore[import-untyped]

        text = pytesseract.image_to_string(crop, config="--psm 6").strip()
        return text if text else None
    except Exception:
        pass
    return None


def decode_session_marker(
    gray,
    expected_marker: Optional[str],
    *,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Attempt to read the session marker from a frame (WP-S3).

    Returns an advisory result: method, decoded string, and match status.
    Never raises. No deps => method='none'.
    """
    if not expected_marker:
        return {"method": "none", "decoded": None, "match": None, "note": "no marker configured"}
    decoded = _try_decode_qr(gray)
    method = "qr" if decoded is not None else "none"
    if decoded is None:
        decoded = _try_decode_text(gray)
        method = "text" if decoded is not None else "none"
    match = None
    if decoded is not None:
        # Accept either the full marker text or just the session_id portion
        match = decoded == expected_marker or (
            session_id is not None and decoded == session_id
        )
    return {
        "method": method,
        "decoded": decoded,
        "match": match,
        "expected_prefix": session_id,
    }


class PresenceProvider(Protocol):
    """WP-S5: supplies the wall-clock timestamp of the most recent certified controller input."""

    def last_input_ts(self) -> Optional[float]: ...


class TouchFilePresenceProvider:
    """Presence from a touch-file mtime updated by the bridge or a companion process."""

    def __init__(self, path: Path, timeout_s: float = 5.0):
        self.path = Path(path)
        self.timeout_s = timeout_s

    def last_input_ts(self) -> Optional[float]:
        try:
            if not self.path.exists():
                return None
            return self.path.stat().st_mtime
        except Exception:
            return None


class StaticPresenceProvider:
    """Test/bridge hook: a fixed timestamp."""

    def __init__(self, last_input_ts: Optional[float]):
        self._ts = last_input_ts

    def last_input_ts(self) -> Optional[float]:
        return self._ts


class StreamerPerceptionRuntime:
    """Main loop: grab frames → metrics → events."""

    def __init__(
        self,
        cfg: PerceptionConfig,
        bus: EventBus,
        *,
        source: Optional[Dict[str, Any]] = None,
        presence_provider: Optional[PresenceProvider] = None,
    ):
        self.cfg = cfg
        self.bus = bus
        self._activity = "idle"
        self._activity_since = 0.0
        self._zone_state: Dict[str, str] = {}
        self._zone_ema: Dict[str, float] = {}
        self.frames = 0
        self.t0 = 0.0
        self._source_cache: Optional[Dict[str, Any]] = source
        self._cap: Optional[Any] = None
        self.session_head_ns = 0
        self._marker_text: Optional[str] = None
        self._marker_digest: Optional[str] = None
        self._last_marker_check = 0.0
        self.presence_provider = presence_provider

    def _source(self) -> Dict[str, Any]:
        if self._source_cache is not None:
            return dict(self._source_cache)
        return _build_single_source(self.cfg)

    def _compute_marker(self) -> None:
        if self.cfg.session_marker == "off":
            return
        if self.session_head_ns == 0:
            return
        self._marker_digest = make_marker_digest(self.cfg.session_id, self.session_head_ns)
        self._marker_text = render_marker_text(self.cfg.session_id, self.session_head_ns)

    def emit(self, etype: str, payload: Dict[str, Any]) -> None:
        self.bus.emit(
            make_event(
                etype,
                payload,
                session_id=self.cfg.session_id,
                source=self._source(),
                session_head_ns=self.session_head_ns or None,
            )
        )

    def _presence_status(self, now: float) -> Tuple[bool, Optional[float]]:
        """Return (sync_ok, seconds_since_last_input) for the current wall time.

        If no presence provider is configured, optical activity cannot claim
        controller-backed confidence (fail-closed).
        """
        if self.presence_provider is None:
            return False, None
        last = self.presence_provider.last_input_ts()
        if last is None:
            return False, None
        ago = now - last
        return ago <= self.cfg.presence_timeout_s, ago

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
            presence_sync_ok, last_ago = self._presence_status(now)
            self.emit(
                "activity",
                {
                    "level": self._activity,
                    "prev": prev,
                    "motion": round(motion, 3),
                    "mean_luma": round(luma, 2),
                    "presence_sync_ok": presence_sync_ok,
                    "last_controller_s_ago": round(last_ago, 3) if last_ago is not None else None,
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
                presence_sync_ok, last_ago = self._presence_status(now)
                self.emit(
                    "zone",
                    {
                        "zone_id": z.zone_id,
                        "state": state,
                        "prev": prev,
                        "delta": round(delta, 3),
                        "luma": round(z_luma, 2),
                        "presence_sync_ok": presence_sync_ok,
                        "last_controller_s_ago": round(last_ago, 3) if last_ago is not None else None,
                    },
                )

        return motion, luma

    def open(self) -> Tuple[Any, str]:
        """Open the capture, run per-source eye-check, emit session_start.

        Returns (cap, backend_name). Raises on primary open failure.
        """
        import cv2

        if self.cfg.session_head_ns is not None:
            self.session_head_ns = self.cfg.session_head_ns
        else:
            self.session_head_ns = clock_ns()
            self.cfg.session_head_ns = self.session_head_ns

        self.t0 = time.time()
        self._compute_marker()

        cap, backend_name, first = open_capture(
            self.cfg.device,
            self.cfg.width,
            self.cfg.height,
            self.cfg.fps_target,
            self.cfg.backend,
        )
        self.cfg.backend = backend_name
        # Resolve source.kind after open (WP-S1); name may come from CLI/env only
        self._source_cache = _build_single_source(self.cfg, backend=backend_name, opened=True)
        self._cap = cap

        # Session start carries the source that is actually opened
        session_payload: Dict[str, Any] = {
            "jsonl": str(self.cfg.jsonl_path) if self.cfg.jsonl_path else None,
            "ws": f"ws://{self.cfg.ws_host}:{self.cfg.ws_port}"
            if self.cfg.enable_ws
            else None,
            "advisory": True,
            "note": "optical events are not humanity or tournament proof",
        }
        if self._marker_text:
            session_payload["marker_text"] = self._marker_text
            session_payload["marker_kind"] = self.cfg.session_marker
        if self.presence_provider is not None:
            session_payload["presence_sync_enabled"] = True
            session_payload["presence_timeout_s"] = self.cfg.presence_timeout_s
        self.emit("session_start", session_payload)

        # Eye-check hint — still mandatory; kind tag is not proof of clean game
        h0, w0 = first.shape[:2]
        first_mean_luma = round(
            frame_mean_luma(cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)), 2
        )
        eye_check: Dict[str, Any] = {
            "n": 0,
            "eye_check": "operator must verify first frames are GAME not webcam",
            "first_shape": [int(h0), int(w0)],
            "mean_luma": first_mean_luma,
        }
        if self.cfg.snapshot is not None:
            self.cfg.snapshot.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(self.cfg.snapshot), first)
            eye_check["snapshot"] = str(self.cfg.snapshot)
            eye_check[
                "eye_check"
            ] = f"operator must verify first frames are GAME not webcam; snapshot saved to {self.cfg.snapshot}"
        self.emit("frame_stats", eye_check)

        return cap, backend_name

    def _check_marker(self, gray, now: float) -> None:
        if self.cfg.session_marker == "off":
            return
        if not self._marker_text:
            return
        if now - self._last_marker_check < self.cfg.marker_check_every_s:
            return
        self._last_marker_check = now
        result = decode_session_marker(gray, self._marker_text, session_id=self.cfg.session_id)
        self.emit(
            "session_marker",
            {
                "expected": self._marker_text,
                "session_id": self.cfg.session_id,
                "decoded": result.get("decoded"),
                "match": result.get("match"),
                "method": result.get("method"),
            },
        )

    def run_loop(self, cap: Optional[Any] = None) -> Dict[str, Any]:
        """Process frames from an already-opened capture (or self._cap)."""
        import cv2

        if cap is None:
            cap = self._cap
        if cap is None:
            raise RuntimeError("run_loop called with no open capture")

        period = 1.0 / max(self.cfg.fps_target, 1.0)
        last_stats = 0.0
        last_hb = 0.0
        n = 0
        summary: Dict[str, Any] = {}
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

                # WP-S3: optional session marker decode
                if n % 5 == 0:
                    self._check_marker(gray, now)

                if now - last_stats >= self.cfg.stats_every_s:
                    elapsed = max(now - self.t0, 1e-6)
                    presence_sync_ok, last_ago = self._presence_status(now)
                    self.emit(
                        "frame_stats",
                        {
                            "n": n,
                            "fps_meas": round(n / elapsed, 2),
                            "mean_luma": round(luma, 2),
                            "motion": round(motion, 3),
                            "activity": self._activity,
                            "presence_sync_ok": presence_sync_ok,
                            "last_controller_s_ago": round(last_ago, 3) if last_ago is not None else None,
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
            try:
                cap.release()
            except Exception:
                pass
            elapsed = max(time.time() - self.t0, 1e-6)
            summary = {
                "frames": n,
                "events": self.bus.events_emitted,
                "elapsed_s": round(elapsed, 2),
                "fps_meas": round(n / elapsed, 2),
            }
            self.emit("session_end", summary)
            return summary

    def run(self) -> Dict[str, Any]:
        """Open + run a single source."""
        self.open()
        return self.run_loop()


class DualStreamerRuntime:
    """WP-S2: open and run primary + optional secondary UVC sources concurrently."""

    def __init__(
        self,
        cfg: PerceptionConfig,
        bus: EventBus,
        *,
        presence_provider: Optional[PresenceProvider] = None,
    ):
        self.cfg = cfg
        self.bus = bus
        self.presence_provider = presence_provider
        self.primary_rt: Optional[StreamerPerceptionRuntime] = None
        self.secondary_rt: Optional[StreamerPerceptionRuntime] = None
        self.primary_cap: Optional[Any] = None
        self.secondary_cap: Optional[Any] = None
        self.threads: List[threading.Thread] = []
        self.results: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def _secondary_cfg(self) -> PerceptionConfig:
        """Make a secondary source config from the primary."""
        import copy

        cfg2 = copy.copy(self.cfg)
        cfg2.device = self.cfg.secondary_device
        cfg2.device_name = self.cfg.secondary_device_name
        cfg2.source_kind = self.cfg.secondary_source_kind
        cfg2.secondary_device = None
        cfg2.secondary_device_name = None
        cfg2.secondary_source_kind = None
        cfg2.snapshot = None  # avoid overwriting primary snapshot
        return cfg2

    def open_sources(self) -> None:
        """Open primary; try secondary and fail-closed if it cannot open."""
        # Mint one shared session clock head (WP-S4); reuse if already set by CLI/marker
        head = self.cfg.session_head_ns or clock_ns()
        self.cfg.session_head_ns = head

        self.primary_rt = StreamerPerceptionRuntime(
            self.cfg, self.bus, presence_provider=self.presence_provider
        )
        self.primary_cap, _ = self.primary_rt.open()

        if self.cfg.secondary_device is not None:
            cfg2 = self._secondary_cfg()
            cfg2.session_head_ns = head
            self.secondary_rt = StreamerPerceptionRuntime(
                cfg2, self.bus, presence_provider=self.presence_provider
            )
            try:
                self.secondary_cap, _ = self.secondary_rt.open()
            except Exception as exc:
                sec_source = _build_single_source(cfg2, opened=False)
                self.bus.emit(
                    make_event(
                        "source_secondary_failed",
                        {"error": str(exc), "device": cfg2.device, "name": cfg2.device_name},
                        session_id=self.cfg.session_id,
                        source=sec_source,
                        session_head_ns=head,
                    )
                )
                self.secondary_rt = None
                self.secondary_cap = None

    def _run_source(self, rt: StreamerPerceptionRuntime, cap: Any) -> None:
        try:
            summary = rt.run_loop(cap)
            with self._lock:
                self.results.append(summary)
        except Exception as exc:
            # Emit a source-level failure so the session does not silently die
            self.bus.emit(
                make_event(
                    "source_failed",
                    {"error": str(exc)},
                    session_id=rt.cfg.session_id,
                    source=rt._source(),
                    session_head_ns=rt.session_head_ns or self.cfg.session_head_ns,
                )
            )

    def run(self) -> Dict[str, Any]:
        self.open_sources()

        t1 = threading.Thread(
            target=self._run_source,
            args=(self.primary_rt, self.primary_cap),
            name="perception-primary",
        )
        t1.start()
        self.threads.append(t1)

        if self.secondary_rt is not None and self.secondary_cap is not None:
            t2 = threading.Thread(
                target=self._run_source,
                args=(self.secondary_rt, self.secondary_cap),
                name="perception-secondary",
            )
            t2.start()
            self.threads.append(t2)

        for t in self.threads:
            t.join()

        primary = self.results[0] if self.results else {"frames": 0, "events": 0}
        secondary = self.results[1] if len(self.results) > 1 else None
        total_frames = primary.get("frames", 0) + (
            secondary.get("frames", 0) if secondary else 0
        )
        total_events = primary.get("events", 0) + (
            secondary.get("events", 0) if secondary else 0
        )
        summary = {
            "frames": total_frames,
            "events": total_events,
            "sources_opened": 1 + (1 if secondary else 0),
            "primary": primary,
            "secondary": secondary,
        }
        # One combined session_end is enough; each source already emitted its own
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
