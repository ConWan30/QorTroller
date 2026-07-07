"""Tests for scripts/issue_kas_records.parse_log — the C3 provenance tail on the candidate_cut log line.

sess_ab finding: the KAS event_trail is reconstructed by parsing the daemon log, whose candidate_cut line used
to carry ONLY event/regime/sha — so the certificate landed engine/match/raw = None even though the cut was
v6-driven. The producer now logs the C3 tail; parse_log must extract it, and old logs (no tail) must still
parse cleanly. Pure: writes a temp log file, no daemon/cv2/bridge-runtime."""
from __future__ import annotations

import os
import sys
import tempfile

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (os.path.join(_REPO, "scripts"), os.path.join(_REPO, "bridge"), _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import issue_kas_records as ikr  # noqa: E402


def _write_log(lines):
    d = tempfile.mkdtemp()   # mkdtemp, not TemporaryDirectory (Windows file-handle gotcha)
    path = os.path.join(d, "retina_daemon_t_1.log")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def test_candidate_cut_c3_tail_is_parsed_into_the_trail():
    path = _write_log([
        "2026-07-03 23:23:53 [INFO] x: session-anchor: candidate_cut regime=CANDIDATE sha=bd0f6fc0 "
        "engine=rapidocr_ppocrv6_small match=exact raw=Qortrola30",
        "2026-07-03 23:24:09 [INFO] x: session-anchor: promoted regime=PROMOTED sha=bd0f6fc0",
    ])
    _span, events, _h, _c = ikr.parse_log(path)
    cut = next(e for e in events if e["event"] == "candidate_cut")
    assert cut["engine"] == "rapidocr_ppocrv6_small"   # ACTUAL live model id — not None (the sess_ab gap)
    assert cut["match_kind"] == "exact" and cut["raw_read"] == "Qortrola30"
    # promoted line has no C3 tail -> no phantom keys
    prom = next(e for e in events if e["event"] == "promoted")
    assert "engine" not in prom


def test_static_feed_path_maps_dash_to_none():
    # the legacy template catch logs engine=static_feed_v1 with match/raw absent -> "-" placeholders -> None
    path = _write_log([
        "2026-07-03 23:23:53 [INFO] x: session-anchor: candidate_cut regime=CANDIDATE sha=aa11 "
        "engine=static_feed_v1 match=- raw=-",
    ])
    _s, events, _h, _c = ikr.parse_log(path)
    cut = events[0]
    assert cut["engine"] == "static_feed_v1" and cut["match_kind"] is None and cut["raw_read"] is None


def test_old_style_line_without_c3_still_parses():
    # backward compat: pre-fix logs (no C3 tail) must parse — the group is optional, no engine key emitted
    path = _write_log([
        "2026-07-03 23:23:53 [INFO] x: session-anchor: candidate_cut regime=CANDIDATE sha=old999",
    ])
    _s, events, _h, _c = ikr.parse_log(path)
    assert events[0]["event"] == "candidate_cut" and "engine" not in events[0]


def test_spacey_misread_raw_is_captured_rest_of_line():
    # raw is the LAST field (rest-of-line), so an OCR misread with a space can't break the parse or leak
    path = _write_log([
        "2026-07-03 23:23:53 [INFO] x: session-anchor: candidate_cut regime=CANDIDATE sha=bb22 "
        "engine=tesseract_row_v1 match=fuzzy raw=Qor trola 30",
    ])
    _s, events, _h, _c = ikr.parse_log(path)
    assert events[0]["engine"] == "tesseract_row_v1" and events[0]["raw_read"] == "Qor trola 30"
