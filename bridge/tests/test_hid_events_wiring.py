"""HID-lobe capture wiring (dual-lobe fusion) — the device-clock R2-onset stream feeding the KAS HID lobe.

Pins: default-off is inert (no detector, push/flush no-op); when enabled, push_r2_raw detects a device-clock
rising edge and flush_hid_events writes ONE r2_onset row to the sink (drained, no duplicate). This exercises
the real RetinaGameCapture wiring (constructor flag -> HidOnsetDetector -> push_r2_raw -> jsonl), not the pure
module in isolation. The raw-reader ungate + consumption-tick flush call live in dualshock_integration (the
running loop); here we drive push_r2_raw / flush_hid_events directly, exactly as that loop does.

FOUND 2026-07-05 (Phase C C-1.1 live rig validation): push_l2_raw used to ALSO feed _hid_onset with the L2
value (raw offset 5), so 'r2_onset' events fired on L2 presses and never on real R2 presses (raw offset 6)
— confirmed live before the fix (L2 presses produced onsets immediately; R2 presses produced none). Fixed
by giving the HID lobe its own ingestion point, push_r2_raw, fed the real R2 byte. See qortroller_retina_
capture.py's push_l2_raw/push_r2_raw docstrings and dualshock_integration.py's raw reader thread."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("cv2")   # RetinaGameCapture pulls the retina/killfeed CV stack

from bridge.vapi_bridge.qortroller_retina_capture import RetinaGameCapture  # noqa: E402


def _rows(path):
    import os
    if not os.path.exists(path):     # nothing was ever drained -> zero rows (append_near_boundary_jsonl
        return []                    # never created the file, since there was nothing to append)
    return [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]


def test_hid_events_off_by_default_is_inert(tmp_path):
    rgc = RetinaGameCapture("Remote Play")                    # no hid_events flag
    assert rgc._hid_onset is None
    rgc.push_l2_raw(1000.0, 3_000_000, 200)                  # no source -> pure no-op, never raises
    rgc.push_r2_raw(1000.0, 3_000_000, 200)                  # no detector -> pure no-op, never raises
    rgc.flush_hid_events()                                    # no-op


def test_push_l2_raw_never_feeds_the_r2_onset_detector(tmp_path):
    # the regression pin for the 2026-07-05 finding: L2 traffic (even a clean rising edge, even with the
    # HID lobe enabled) must NEVER produce an r2_onset — only push_r2_raw may.
    sink = str(tmp_path / "hid.jsonl")
    rgc = RetinaGameCapture("Remote Play", hid_events_enabled=True, hid_events_log_path=sink)
    assert rgc._hid_onset is not None
    for wall, l2 in [(1000.0, 0), (1010.0, 200), (1020.0, 200)]:
        rgc.push_l2_raw(wall, int(wall * 3000.0) & 0xFFFFFFFF, l2)
    rgc.flush_hid_events()
    assert _rows(sink) == []


def test_hid_onset_count_none_when_lobe_off_monotonic_when_on(tmp_path):
    # D-HIDW-1 (2026-07-05): hid_onset_count() is the consumption loop's raw-path R2 edge source for
    # inline-window opening + classify-burst arming (match 8: 111 raw onsets vs windows_total=0 on the
    # pydualsense path). Off-lobe -> None (legacy pydualsense-only behavior); on-lobe -> monotonic count
    # that survives flush_hid_events (JSONL drain and edge detection must not race each other).
    rgc_off = RetinaGameCapture("Remote Play")
    assert rgc_off.hid_onset_count() is None
    sink = str(tmp_path / "hid.jsonl")
    rgc = RetinaGameCapture("Remote Play", hid_events_enabled=True, hid_events_log_path=sink)
    assert rgc.hid_onset_count() == 0
    for wall, r2 in [(1000.0, 0), (1010.0, 200), (1020.0, 200)]:   # one rising edge
        rgc.push_r2_raw(wall, int(wall * 3000.0) & 0xFFFFFFFF, r2)
    assert rgc.hid_onset_count() == 1
    rgc.flush_hid_events()                                    # JSONL drain must not consume the counter
    assert rgc.hid_onset_count() == 1
    for wall, r2 in [(1030.0, 0), (1040.0, 200)]:             # release -> second edge
        rgc.push_r2_raw(wall, int(wall * 3000.0) & 0xFFFFFFFF, r2)
    assert rgc.hid_onset_count() == 2


def test_hid_events_detects_device_clock_onset_on_r2_and_flushes_once(tmp_path):
    sink = str(tmp_path / "hid.jsonl")
    rgc = RetinaGameCapture("Remote Play", hid_events_enabled=True, hid_events_log_path=sink)
    assert rgc._hid_onset is not None
    # raw-reader feed (as dualshock_integration does): low -> high (rising edge) -> high (no re-fire), on
    # R2. ts at 3000 ticks/ms keeps the device->wall anchor identity, so the onset ts == the wall ms (1010).
    for wall, r2 in [(1000.0, 0), (1010.0, 200), (1020.0, 200)]:
        rgc.push_r2_raw(wall, int(wall * 3000.0) & 0xFFFFFFFF, r2)
    rgc.flush_hid_events()
    rows = _rows(sink)
    assert len(rows) == 1 and rows[0]["type"] == "r2_onset"
    assert rows[0]["t_ms"] == 1010.0 and rows[0]["input_caused"] is False
    # NOTE: the persisted field is still named "l2" (legacy label predating this fix, kept to avoid an
    # on-disk schema change) — it now correctly carries the R2 raw value. Renaming it is a separate,
    # not-yet-made decision, flagged here rather than silently changed.
    assert rows[0]["l2"] == 200
    rgc.flush_hid_events()                                    # already drained -> no duplicate row
    assert len(_rows(sink)) == 1
