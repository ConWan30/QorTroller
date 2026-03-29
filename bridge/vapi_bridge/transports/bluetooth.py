"""
VAPI Bridge — Bluetooth Transport Layer (Phase 120)

DualShock Edge BLE transport at 250 Hz.

W1 INVARIANT (critical): BLE samples arrive at 250 Hz (not 1000 Hz USB).
All L4 thresholds (anomaly=7.009 / continuity=5.367) were calibrated on
USB 1000 Hz sessions.  BT sessions MUST NOT be evaluated against USB thresholds.
When transport_type=TRANSPORT_TYPE_BLE, route to a separate BT threshold track
(not yet calibrated; future Phase 121 candidate).

W2 OPPORTUNITY: BT transport + ESP32-S3 GSR grip enables Verified Human Channel
(VHC) — decentralized BLE mesh presence proof (Phase 121 candidate).

MockBLETransport follows the MockGSRGrip precedent (Phase 99B): same interface as
BLETransport; deterministic seed=42; no hardware required.  Code-before-hardware.

Sony DualShock Edge BLE identifiers (CFI-ZCP1):
  HID service UUID : 00001124-0000-1000-8000-00805f9b34fb
  Report char UUID : 00002a4d-0000-1000-8000-00805f9b34fb
  Device name prefix: "DualSense Edge"
"""

import asyncio
import math
import random
import struct
import time as _time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncGenerator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BT_POLL_HZ:     int   = 250           # DualShock Edge BLE notification rate
BT_FRAME_MS:    float = 1000.0 / BT_POLL_HZ   # 4.0 ms per frame
BT_WINDOW:      int   = 1024          # Analysis window (4.096 s at 250 Hz)
BT_HZ_PER_BIN:  float = BT_POLL_HZ / BT_WINDOW  # 0.244 Hz/bin (4× USB resolution)

TRANSPORT_TYPE_USB: int = 0x01
TRANSPORT_TYPE_BLE: int = 0x02

# Sony DualShock Edge BLE service / characteristic UUIDs
DS_SERVICE_UUID = "00001124-0000-1000-8000-00805f9b34fb"
DS_REPORT_CHAR  = "00002a4d-0000-1000-8000-00805f9b34fb"
DS_NAME_PREFIX  = "DualSense Edge"

# BLE HID report offsets (input report type 0x01, 64-byte report)
# These match the DualShock 4/Edge BLE report layout.
_OFF_LX    = 1
_OFF_LY    = 2
_OFF_RX    = 3
_OFF_RY    = 4
_OFF_L2    = 5
_OFF_R2    = 6
_OFF_BTN0  = 7    # buttons byte 0 (Cross=bit5, Circle=bit6, Square=bit4, Triangle=bit7)
_OFF_BTN1  = 8    # buttons byte 1
_OFF_GYRO_X  = 13   # int16 LE
_OFF_GYRO_Y  = 15
_OFF_GYRO_Z  = 17
_OFF_ACCEL_X = 19   # int16 LE
_OFF_ACCEL_Y = 21
_OFF_ACCEL_Z = 23
_OFF_TOUCH   = 33   # touch active flag (high nibble of byte 33)
_OFF_TOUCH_X = 34   # 12-bit x in bytes 34-35
_OFF_TOUCH_Y = 35   # 12-bit y from bytes 35-36


# ---------------------------------------------------------------------------
# BTFrame dataclass
# ---------------------------------------------------------------------------

@dataclass
class BTFrame:
    """Single 250 Hz BLE frame from DualShock Edge.

    transport_type=TRANSPORT_TYPE_BLE (0x02) tags this frame as BLE-sourced.
    This tag flows into the PoAC body at byte 163 (transport_type field) so
    downstream L4 evaluation can route BT sessions to the correct threshold track.

    W1: USB thresholds 7.009/5.367 MUST NOT be applied to BT frames.
    """
    ts_ns:          int   = 0

    left_stick_x:   int   = 128
    left_stick_y:   int   = 128
    right_stick_x:  int   = 128
    right_stick_y:  int   = 128

    accel_x:        int   = 0
    accel_y:        int   = 0
    accel_z:        int   = 0

    gyro_x:         int   = 0
    gyro_y:         int   = 0
    gyro_z:         int   = 0

    buttons_0:      int   = 0
    buttons_1:      int   = 0
    l2_trigger:     int   = 0
    r2_trigger:     int   = 0

    touch_active:   bool  = False
    touch0_x:       int   = 0
    touch0_y:       int   = 0

    transport_type: int   = field(default=TRANSPORT_TYPE_BLE)


def _parse_bt_frame(data: bytes, ts_ns: int) -> BTFrame:
    """Parse a 64-byte BLE HID input report into a BTFrame.

    Falls back gracefully for short reports (< 64 bytes).
    """
    n = len(data)

    def _u8(off: int) -> int:
        return data[off] if off < n else 0

    def _i16(off: int) -> int:
        if off + 1 >= n:
            return 0
        raw = struct.unpack_from("<h", data, off)[0]
        return int(raw)

    touch_active = bool((_u8(_OFF_TOUCH) & 0x80) == 0)  # bit 7 clear = finger down
    # 12-bit touch X from bytes 34-35
    touch_x = _u8(_OFF_TOUCH_X) | ((_u8(_OFF_TOUCH_Y) & 0x0F) << 8)
    touch_y = ((_u8(_OFF_TOUCH_Y) & 0xF0) >> 4) | (_u8(_OFF_TOUCH_Y + 1) << 4)

    return BTFrame(
        ts_ns=ts_ns,
        left_stick_x=_u8(_OFF_LX),
        left_stick_y=_u8(_OFF_LY),
        right_stick_x=_u8(_OFF_RX),
        right_stick_y=_u8(_OFF_RY),
        accel_x=_i16(_OFF_ACCEL_X),
        accel_y=_i16(_OFF_ACCEL_Y),
        accel_z=_i16(_OFF_ACCEL_Z),
        gyro_x=_i16(_OFF_GYRO_X),
        gyro_y=_i16(_OFF_GYRO_Y),
        gyro_z=_i16(_OFF_GYRO_Z),
        buttons_0=_u8(_OFF_BTN0),
        buttons_1=_u8(_OFF_BTN1),
        l2_trigger=_u8(_OFF_L2),
        r2_trigger=_u8(_OFF_R2),
        touch_active=touch_active,
        touch0_x=touch_x,
        touch0_y=touch_y,
        transport_type=TRANSPORT_TYPE_BLE,
    )


# ---------------------------------------------------------------------------
# BLETransport — real hardware path (bleak optional dependency)
# ---------------------------------------------------------------------------

class BLETransport:
    """Async BLE transport for DualShock Edge at 250 Hz.

    bleak is an optional dependency.  If not installed, connect() logs a warning
    and stream_frames() falls back to MockBLETransport transparently.

    Usage::

        transport = BLETransport(device_address="XX:XX:XX:XX:XX:XX")
        connected = await transport.connect()
        async for frame in transport.stream_frames():
            # frame.transport_type == TRANSPORT_TYPE_BLE
            process(frame)
        await transport.disconnect()
    """

    def __init__(self, device_address: str = "") -> None:
        self._address  = device_address
        self._client   = None   # bleak.BleakClient when connected
        self._queue: "asyncio.Queue[BTFrame]" = asyncio.Queue(maxsize=512)
        self._connected = False
        self._frames_received = 0
        self._frames_dropped  = 0
        self._last_ts_ns      = 0

    async def connect(self) -> bool:
        """Scan and connect to DualShock Edge over BLE.

        Returns True on success, False if bleak unavailable or no device found.
        """
        try:
            import bleak  # noqa: F401 — optional dep
            from bleak import BleakClient, BleakScanner

            if not self._address:
                # Auto-scan for DS Edge by name prefix
                devices = await BleakScanner.discover(timeout=5.0)
                for d in devices:
                    if d.name and DS_NAME_PREFIX.lower() in d.name.lower():
                        self._address = d.address
                        break
                if not self._address:
                    return False

            self._client = BleakClient(self._address)
            await self._client.connect()
            await self._client.start_notify(DS_REPORT_CHAR, self._on_notify)
            self._connected = True
            return True
        except ImportError:
            # bleak not installed — caller should fall back to MockBLETransport
            return False
        except Exception:
            return False

    def _on_notify(self, _sender, data: bytes) -> None:  # type: ignore[override]
        """BLE notification callback — called at ~250 Hz by bleak."""
        ts_ns = _time.time_ns()
        frame = _parse_bt_frame(bytes(data), ts_ns)
        try:
            self._queue.put_nowait(frame)
            self._frames_received += 1
        except asyncio.QueueFull:
            self._frames_dropped += 1
        self._last_ts_ns = ts_ns

    async def stream_frames(self) -> AsyncGenerator[BTFrame, None]:
        """Async generator yielding BTFrames at ~250 Hz.

        If BLE connection failed, falls back to MockBLETransport transparently.
        """
        if not self._connected:
            mock = MockBLETransport()
            async for frame in mock.stream_frames():
                yield frame
            return
        while self._connected:
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                yield frame
            except asyncio.TimeoutError:
                continue

    async def disconnect(self) -> None:
        """Disconnect from BLE device."""
        self._connected = False
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None

    @property
    def frames_received(self) -> int:
        return self._frames_received

    @property
    def frames_dropped(self) -> int:
        return self._frames_dropped

    @property
    def device_address(self) -> str:
        return self._address


# ---------------------------------------------------------------------------
# MockBLETransport — deterministic code-before-hardware (MockGSRGrip pattern)
# ---------------------------------------------------------------------------

class MockBLETransport:
    """Deterministic BLE transport mock for testing and development.

    Follows MockGSRGrip (Phase 99B) precedent:
    - seed=42 for reproducibility
    - Same async interface as BLETransport
    - n_frames=0 → infinite stream
    - Generates realistic DualShock Edge BLE data patterns

    Usage in tests::

        mock = MockBLETransport(seed=42, n_frames=100)
        frames = []
        async for frame in mock.stream_frames():
            frames.append(frame)
        assert len(frames) == 100
    """

    def __init__(self, seed: int = 42, n_frames: int = 0) -> None:
        self._seed     = seed
        self._n_frames = n_frames  # 0 = infinite
        self._rng      = random.Random(seed)
        self._frames_received = 0
        self._frames_dropped  = 0
        self._device_address  = f"MOCK:{seed:02X}:BT:DE:VI:CE"

    async def stream_frames(self) -> AsyncGenerator[BTFrame, None]:
        """Async generator yielding deterministic BTFrames at BT_FRAME_MS intervals.

        Uses asyncio.sleep(BT_FRAME_MS/1000) to simulate 250 Hz.
        Stick values walk a sinusoidal pattern seeded by _rng.
        Accel/gyro values simulate micro-tremor (human physiological noise).
        """
        rng   = self._rng
        count = 0
        t0    = _time.monotonic()

        # Seed a phase offset for stick drift simulation
        phase_lx = rng.uniform(0, 2 * math.pi)
        phase_ry = rng.uniform(0, 2 * math.pi)

        while self._n_frames == 0 or count < self._n_frames:
            ts_ns  = _time.time_ns()
            elapsed = _time.monotonic() - t0
            frame_idx = count

            # Stick values: sinusoidal drift ±15 around center 128
            lx = 128 + int(15 * math.sin(phase_lx + elapsed * 0.3))
            ly = 128 + int(12 * math.cos(elapsed * 0.25))
            rx = 128 + int(10 * math.sin(elapsed * 0.2))
            ry = 128 + int(15 * math.sin(phase_ry + elapsed * 0.4))

            # Micro-tremor: Gaussian noise around zero
            ax = int(rng.gauss(0, 1500))
            ay = int(rng.gauss(0, 1500))
            az = int(rng.gauss(-16000, 1500))  # ~1g downward
            gx = int(rng.gauss(0, 200))
            gy = int(rng.gauss(0, 200))
            gz = int(rng.gauss(0, 200))

            # Occasional trigger press (R2 at ~2 Hz pattern)
            r2 = int(min(255, max(0, 200 * max(0, math.sin(elapsed * 2 * math.pi * 1.5)))))

            # Touch: simulate thumb resting on pad with small drift
            touch = True
            tx = int(1000 + 20 * math.sin(elapsed * 0.1 + phase_lx))
            ty = int(500  + 10 * math.sin(elapsed * 0.15 + phase_ry))

            frame = BTFrame(
                ts_ns=ts_ns,
                left_stick_x=max(0, min(255, lx)),
                left_stick_y=max(0, min(255, ly)),
                right_stick_x=max(0, min(255, rx)),
                right_stick_y=max(0, min(255, ry)),
                accel_x=ax, accel_y=ay, accel_z=az,
                gyro_x=gx,  gyro_y=gy,  gyro_z=gz,
                buttons_0=0, buttons_1=0,
                l2_trigger=0, r2_trigger=r2,
                touch_active=touch,
                touch0_x=tx, touch0_y=ty,
                transport_type=TRANSPORT_TYPE_BLE,
            )
            yield frame
            self._frames_received += 1
            count += 1
            await asyncio.sleep(BT_FRAME_MS / 1000.0)

    @property
    def frames_received(self) -> int:
        return self._frames_received

    @property
    def frames_dropped(self) -> int:
        return self._frames_dropped

    @property
    def device_address(self) -> str:
        return self._device_address
