"""BT DualSense Edge observer — Phase 1 research path.

Topology (Phase 0 proven):
  - PS5 Bluetooth off; Edge USB → PS5 (gameplay)
  - Edge Bluetooth → Windows (this observer)

Rules:
  - READ-only by default (no L6 / haptic write unless explicitly enabled later)
  - No chain spend, no enablement flips
  - Honest: BT report rate is not USB ~1000 Hz grind physics
  - Bus is Bluetooth Classic HID (path UUID 00001124-...), not BLE

Report: DualSense BT full input is typically 78 bytes, report id 0x31.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

EDGE_VID = 0x054C
EDGE_PID = 0x0DF2  # DualSense Edge CFI-ZCP1
BT_HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"

# Face / shoulder bits (DualSense common layout after report id)
# buttons0 (payload[7]): dpad nibble + face
BTN_SQUARE = 0x10
BTN_CROSS = 0x20
BTN_CIRCLE = 0x40
BTN_TRIANGLE = 0x80
# buttons1 (payload[8])
BTN_L1 = 0x01
BTN_R1 = 0x02
BTN_L2 = 0x04
BTN_R2 = 0x08
BTN_CREATE = 0x10
BTN_OPTIONS = 0x20
BTN_L3 = 0x40
BTN_R3 = 0x80
# buttons2 (payload[9])
BTN_PS = 0x01
BTN_TOUCHPAD = 0x02
BTN_MUTE = 0x04


@dataclass
class EdgeSample:
    """One decoded HID frame (digest-friendly)."""

    ts_ns: int
    report_id: int
    lx: int
    ly: int
    rx: int
    ry: int
    l2: int
    r2: int
    dpad: int
    buttons: list[str] = field(default_factory=list)
    # Optional IMU (present on 0x31 full reports; scaled raw)
    gyro_x: Optional[int] = None
    gyro_y: Optional[int] = None
    gyro_z: Optional[int] = None
    accel_x: Optional[int] = None
    accel_y: Optional[int] = None
    accel_z: Optional[int] = None
    raw_len: int = 0
    bus: str = "bluetooth_hid"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def path_is_bluetooth(path: Any) -> bool:
    if path is None:
        return False
    s = path.decode("utf-8", "replace") if isinstance(path, bytes) else str(path)
    return BT_HID_UUID in s.lower() or "bth" in s.lower() or "bluetooth" in s.lower()


def enumerate_edge_devices() -> list[dict[str, Any]]:
    """Return hidapi dicts for Edge devices (any bus)."""
    import hid

    out = []
    for d in hid.enumerate():
        if d.get("vendor_id") == EDGE_VID and d.get("product_id") == EDGE_PID:
            path = d.get("path")
            out.append(
                {
                    "path": path,
                    "product": d.get("product_string"),
                    "interface": d.get("interface_number"),
                    "usage_page": d.get("usage_page"),
                    "usage": d.get("usage"),
                    "is_bluetooth": path_is_bluetooth(path),
                }
            )
    return out


def pick_bt_edge_path(prefer_bluetooth: bool = True) -> Optional[bytes]:
    """Choose an Edge path; prefer Bluetooth HID when present."""
    devs = enumerate_edge_devices()
    if not devs:
        return None
    if prefer_bluetooth:
        bt = [d for d in devs if d["is_bluetooth"]]
        if bt:
            p = bt[0]["path"]
            return p if isinstance(p, bytes) else str(p).encode()
    p = devs[0]["path"]
    return p if isinstance(p, bytes) else str(p).encode()


def _i16(lo: int, hi: int) -> int:
    v = lo | (hi << 8)
    return v - 0x10000 if v & 0x8000 else v


def decode_edge_report(data: bytes, ts_ns: Optional[int] = None) -> Optional[EdgeSample]:
    """Decode DualSense/Edge input report (0x01 USB-style or 0x31 BT full)."""
    if not data:
        return None
    rid = data[0]
    # Payload after report id
    if rid in (0x01, 0x31):
        p = data[1:]
    else:
        # Some stacks strip report id
        p = data
        rid = 0
    if len(p) < 10:
        return None

    lx, ly, rx, ry = p[0], p[1], p[2], p[3]
    l2, r2 = p[4], p[5]
    b0, b1, b2 = p[7], p[8], p[9]
    dpad = b0 & 0x0F
    names: list[str] = []
    if b0 & BTN_SQUARE:
        names.append("square")
    if b0 & BTN_CROSS:
        names.append("cross")
    if b0 & BTN_CIRCLE:
        names.append("circle")
    if b0 & BTN_TRIANGLE:
        names.append("triangle")
    if b1 & BTN_L1:
        names.append("L1")
    if b1 & BTN_R1:
        names.append("R1")
    if b1 & BTN_L2:
        names.append("L2")
    if b1 & BTN_R2:
        names.append("R2")
    if b1 & BTN_CREATE:
        names.append("create")
    if b1 & BTN_OPTIONS:
        names.append("options")
    if b1 & BTN_L3:
        names.append("L3")
    if b1 & BTN_R3:
        names.append("R3")
    if b2 & BTN_PS:
        names.append("PS")
    if b2 & BTN_TOUCHPAD:
        names.append("touchpad")
    if b2 & BTN_MUTE:
        names.append("mute")

    gyro_x = gyro_y = gyro_z = None
    accel_x = accel_y = accel_z = None
    # Full report IMU: common offsets in DualSense USB payload @ 15..26 (0-based after rid)
    # For 0x31, same relative offsets in p[] as USB after rid.
    if len(p) >= 28:
        # gyro at p[15:21], accel at p[21:27] (little-endian int16) — widely used mapping
        gyro_x = _i16(p[15], p[16])
        gyro_y = _i16(p[17], p[18])
        gyro_z = _i16(p[19], p[20])
        accel_x = _i16(p[21], p[22])
        accel_y = _i16(p[23], p[24])
        accel_z = _i16(p[25], p[26])

    return EdgeSample(
        ts_ns=ts_ns if ts_ns is not None else time.time_ns(),
        report_id=rid,
        lx=lx,
        ly=ly,
        rx=rx,
        ry=ry,
        l2=l2,
        r2=r2,
        dpad=dpad,
        buttons=names,
        gyro_x=gyro_x,
        gyro_y=gyro_y,
        gyro_z=gyro_z,
        accel_x=accel_x,
        accel_y=accel_y,
        accel_z=accel_z,
        raw_len=len(data),
    )


class BtEdgeObserver:
    """Read-only DualSense Edge HID observer (BT preferred)."""

    def __init__(self, prefer_bluetooth: bool = True):
        self.prefer_bluetooth = prefer_bluetooth
        self._h = None
        self.path: Optional[bytes] = None
        self.is_bluetooth = False

    def open(self) -> None:
        import hid

        path = pick_bt_edge_path(prefer_bluetooth=self.prefer_bluetooth)
        if not path:
            raise RuntimeError(
                "DualSense Edge not found (VID 054C PID 0DF2). "
                "Pair over BT and/or check USB."
            )
        self.path = path
        self.is_bluetooth = path_is_bluetooth(path)
        h = hid.device()
        h.open_path(path)
        # Nonblocking poll loop; dual-home streams can idle then burst.
        h.set_nonblocking(True)
        self._h = h

    def close(self) -> None:
        if self._h is not None:
            try:
                self._h.close()
            except Exception:
                pass
            self._h = None

    def __enter__(self) -> "BtEdgeObserver":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def read_raw(self, size: int = 128) -> Optional[bytes]:
        if self._h is None:
            raise RuntimeError("observer not open")
        try:
            data = self._h.read(size)
        except OSError:
            # Transient BT stack glitch — caller may continue
            return None
        if not data:
            return None
        return bytes(data)

    def read_sample(self) -> Optional[EdgeSample]:
        raw = self.read_raw()
        if not raw:
            return None
        return decode_edge_report(raw)

    def iter_samples(
        self,
        duration_s: float,
        *,
        idle_sleep_s: float = 0.0005,
    ) -> Iterator[EdgeSample]:
        """Yield decoded samples for duration_s seconds."""
        t_end = time.time() + duration_s
        while time.time() < t_end:
            s = self.read_sample()
            if s is not None:
                yield s
            else:
                time.sleep(idle_sleep_s)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")


def run_session(
    duration_s: float,
    out_path: Path,
    *,
    prefer_bluetooth: bool = True,
    summary_every_s: float = 1.0,
) -> dict[str, Any]:
    """Capture a timed session to JSONL; return summary stats."""
    n = 0
    n_btn = 0
    t0 = time.time()
    last_summary = t0
    batch: list[dict[str, Any]] = []
    meta = {
        "event": "session_start",
        "ts_ns": time.time_ns(),
        "duration_s": duration_s,
        "prefer_bluetooth": prefer_bluetooth,
        "domain": "QORTROLLER-BT-EDGE-OBSERVER-v0",
        "note": "research observer; not USB grind physics; no L6 write",
    }
    write_jsonl(out_path, [meta])

    with BtEdgeObserver(prefer_bluetooth=prefer_bluetooth) as obs:
        bus = "bluetooth" if obs.is_bluetooth else "other"
        write_jsonl(
            out_path,
            [
                {
                    "event": "device_open",
                    "ts_ns": time.time_ns(),
                    "is_bluetooth": obs.is_bluetooth,
                    "bus": bus,
                }
            ],
        )
        for sample in obs.iter_samples(duration_s):
            n += 1
            if sample.buttons or sample.l2 > 8 or sample.r2 > 8:
                n_btn += 1
            batch.append({"event": "sample", **sample.to_dict()})
            if len(batch) >= 64:
                write_jsonl(out_path, batch)
                batch.clear()
            now = time.time()
            if now - last_summary >= summary_every_s:
                elapsed = max(now - t0, 1e-6)
                print(
                    f"[bt-obs] t={elapsed:.1f}s reports={n} "
                    f"rate≈{n / elapsed:.0f}Hz active_frames={n_btn} "
                    f"bt={obs.is_bluetooth}",
                    flush=True,
                )
                last_summary = now
        if batch:
            write_jsonl(out_path, batch)

    elapsed = max(time.time() - t0, 1e-6)
    summary = {
        "event": "session_end",
        "ts_ns": time.time_ns(),
        "reports": n,
        "active_frames": n_btn,
        "elapsed_s": elapsed,
        "rate_hz": n / elapsed,
        "out_path": str(out_path),
    }
    write_jsonl(out_path, [summary])
    return summary
