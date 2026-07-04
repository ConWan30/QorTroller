"""HID-lobe capture wiring (dual-lobe fusion) — the device-clock R2-onset stream feeding the KAS HID lobe.

Pins: default-off is inert (no detector, push/flush no-op); when enabled, push_l2_raw detects a device-clock
rising edge and flush_hid_events writes ONE r2_onset row to the sink (drained, no duplicate). This exercises
the real RetinaGameCapture wiring (constructor flag -> HidOnsetDetector -> push_l2_raw -> jsonl), not the pure
module in isolation. The raw-reader ungate + consumption-tick flush call live in dualshock_integration (the
running loop); here we drive push_l2_raw / flush_hid_events directly, exactly as that loop does."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("cv2")   # RetinaGameCapture pulls the retina/killfeed CV stack

from vapi_bridge.qortroller_retina_capture import RetinaGameCapture  # noqa: E402


def _rows(path):
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


def test_hid_events_off_by_default_is_inert(tmp_path):
    rgc = RetinaGameCapture("Remote Play")                    # no hid_events flag
    assert rgc._hid_onset is None
    rgc.push_l2_raw(1000.0, 3_000_000, 200)                  # no detector -> pure no-op, never raises
    rgc.flush_hid_events()                                    # no-op


def test_hid_events_detects_device_clock_onset_and_flushes_once(tmp_path):
    sink = str(tmp_path / "hid.jsonl")
    rgc = RetinaGameCapture("Remote Play", hid_events_enabled=True, hid_events_log_path=sink)
    assert rgc._hid_onset is not None
    # raw-reader feed (as dualshock_integration does): low -> high (rising edge) -> high (no re-fire). ts at
    # 3000 ticks/ms keeps the device->wall anchor identity, so the onset ts == the wall ms (1010).
    for wall, l2 in [(1000.0, 0), (1010.0, 200), (1020.0, 200)]:
        rgc.push_l2_raw(wall, int(wall * 3000.0) & 0xFFFFFFFF, l2)
    rgc.flush_hid_events()
    rows = _rows(sink)
    assert len(rows) == 1 and rows[0]["type"] == "r2_onset"
    assert rows[0]["t_ms"] == 1010.0 and rows[0]["l2"] == 200 and rows[0]["input_caused"] is False
    rgc.flush_hid_events()                                    # already drained -> no duplicate row
    assert len(_rows(sink)) == 1
