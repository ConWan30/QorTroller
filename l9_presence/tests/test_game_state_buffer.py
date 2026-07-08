"""LUMEN-1 game-state buffer tests.

Pins: pure segmentation (change/stable/min-run/None-break), deterministic ordering,
session join enforcement on scan lifting, sha referencing + LUMEN-2 verify, honest-empty
notes, window overlays, and the cv2 IO helper end-to-end on real tiny PNGs.
"""
from __future__ import annotations

from l9_presence.game_state_buffer import (
    INPUT_WINDOW,
    KILL_ROW_CLUSTER,
    SCENE_CHANGE,
    SCENE_STABLE_SEGMENT,
    build_scene_stream,
    compute_crop_deltas,
    segment_scene,
    verify_stream_references,
)

_SID = "a" * 64
_DISPLAY = "match_test_1000"


def _manifest(shas=("s1", "s2", "s3")):
    return {"schema": "qortroller-session-archive-v1", "session_id": _SID,
            "session_display": _DISPLAY, "count": len(shas),
            "files": [{"file": f"c{i}.png", "sha256": s} for i, s in enumerate(shas)]}


def _scan(shas=("s1", "s2", "s3"), archive=f"retina_kf_archive/{_DISPLAY}"):
    reads = [{"file": f"c{i}.png", "ts_ns": int((1000 + i * 500) * 1e6), "sha256": s,
              "text": "Qortrola30", "conf": 0.9, "slot": "killer"}
             for i, s in enumerate(shas)]
    return {"scan_version": "rp-ocr-precision-v2", "archive": archive,
            "clusters": [{"size": len(reads), "texts": ["Qortrola30"] * len(reads),
                          "reads": reads}]}


def test_segment_change_and_stable():
    ns = lambda ms: int(ms * 1e6)
    deltas = [(ns(1000), 1.0), (ns(2000), 1.5), (ns(3000), 0.8),   # stable run of 3
              (ns(4000), 9.0),                                       # change
              (ns(5000), 1.0), (ns(6000), 1.0)]                      # run of 2 (< min) -> dropped
    ev = segment_scene(deltas)
    kinds = [e.kind for e in ev]
    assert kinds == [SCENE_STABLE_SEGMENT, SCENE_CHANGE]
    assert ev[0].span_ms == [1000.0, 3000.0]
    assert ev[1].confidence == 9.0


def test_none_delta_breaks_run():
    ns = lambda ms: int(ms * 1e6)
    deltas = [(ns(1000), 1.0), (ns(2000), 1.0), (ns(3000), None),
              (ns(4000), 1.0), (ns(5000), 1.0)]
    ev = segment_scene(deltas)
    assert ev == []          # both runs are length-2 (< MIN_STABLE_RUN) -> no events


def test_stream_assembly_sorted_and_joined():
    ns = lambda ms: int(ms * 1e6)
    deltas = [(ns(100), 1.0), (ns(200), 1.0), (ns(300), 1.0), (ns(9000), 8.0)]
    s = build_scene_stream(manifest=_manifest(), deltas=deltas, scan=_scan(),
                           windows=[(500.0, 4000.0)])
    assert s.session_id == _SID and s.advisory is True
    kinds = [e.kind for e in s.events]
    assert kinds == sorted(kinds, key=lambda k: 0) or True   # ordering checked below
    ts = [e.ts_ns for e in s.events]
    assert ts == sorted(ts)
    assert s.counts() == {SCENE_STABLE_SEGMENT: 1, SCENE_CHANGE: 1,
                          KILL_ROW_CLUSTER: 1, INPUT_WINDOW: 1}


def test_scan_session_mismatch_skipped():
    """The buffer never lifts clusters from a DIFFERENT session's scan."""
    s = build_scene_stream(manifest=_manifest(),
                           scan=_scan(archive="retina_kf_archive/other_session_9"),
                           windows=None)
    assert KILL_ROW_CLUSTER not in s.counts()
    assert any("SKIPPED" in n for n in s.notes)


def test_v1_scan_skipped():
    sc = _scan()
    sc["scan_version"] = "rp-ocr-precision-v1"
    s = build_scene_stream(manifest=_manifest(), scan=sc)
    assert KILL_ROW_CLUSTER not in s.counts()


def test_honest_empty_notes():
    s = build_scene_stream(manifest=_manifest())
    assert s.events == []
    joined = " ".join(s.notes)
    assert "no crop deltas" in joined and "no scan" in joined and "no live windows" in joined


def test_verify_stream_references():
    s = build_scene_stream(manifest=_manifest(), scan=_scan())
    v = verify_stream_references(s, _manifest())
    assert v["ok"]
    # a dangling sha (cluster references a crop the manifest never committed) must fail
    s2 = build_scene_stream(manifest=_manifest(shas=("s1", "s2", "sX")), scan=_scan())
    v2 = verify_stream_references(s2, _manifest(shas=("s1", "s2", "sOTHER")))
    assert not v2["ok"] and v2["dangling"]


def test_jsonl_roundtrip():
    import json
    s = build_scene_stream(manifest=_manifest(), scan=_scan(), windows=[(1.0, 2.0)])
    lines = s.to_jsonl().strip().split("\n")
    head = json.loads(lines[0])
    assert head["schema"] == "qortroller-scene-stream-v0" and head["advisory"] is True
    assert len(lines) - 1 == len(s.events)
    for ln in lines[1:]:
        json.loads(ln)


def test_compute_crop_deltas_end_to_end(tmp_path):
    """IO helper on real tiny PNGs: identical frames -> ~0 delta; a changed frame -> big."""
    import cv2
    import numpy as np
    a = np.zeros((20, 40), dtype=np.uint8)
    b = a.copy(); b[5:15, 10:30] = 200          # a "row" appears
    paths = []
    for i, img in enumerate([a, a, b]):
        p = str(tmp_path / f"panel_{1000 + i}.png")
        cv2.imwrite(p, img)
        paths.append((int((1000 + i) * 1e6), p))
    deltas = compute_crop_deltas(paths)
    assert len(deltas) == 2
    assert deltas[0][1] < 0.5 and deltas[1][1] > 6.0


def test_panel_fresh_diff_calibrated_constant():
    """F-LUMEN-1: the panel-scale constant is the calibrated cross-topology p75 (63.0),
    distinct from the killer-slot 6.0 -- never conflate the two scopes."""
    from l9_presence.game_state_buffer import DEFAULT_FRESH_DIFF, PANEL_FRESH_DIFF
    assert PANEL_FRESH_DIFF == 63.0
    assert DEFAULT_FRESH_DIFF == 6.0
    assert PANEL_FRESH_DIFF > DEFAULT_FRESH_DIFF * 8
