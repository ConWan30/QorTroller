"""LUMEN-1 -- Game-State Buffer: the offline meaning-plane seed.

Builds a session-id-joined `SceneEventStream` from a session's manifest-committed crop
archive plus the session's persisted evidence logs. This is the trio model's OBSERVATION
plane made concrete for archives: rich, fallible, ADVISORY structuring that may SUGGEST
(where to look, what persisted, what clustered) and may never ASSERT (no verdict here
touches KAS/PoSP/presence_score -- the assertion plane is elsewhere by design).

Event vocabulary (v0, closed):
  SCENE_CHANGE          consecutive-crop gray-delta >= threshold (a row appeared/left)
                        -- the offline twin of the live `_killer_fresh_row` gate
                        (qortroller_retina_capture.py, fresh-diff threshold 6.0)
  SCENE_STABLE_SEGMENT  a run of low-delta crops (the panel held still)
  KILL_ROW_CLUSTER      lifted from a v2 precision scan (OCR stays the scan's job --
                        the buffer never re-runs OCR; separation of instruments)
  INPUT_WINDOW          a live R2 window span (from retina_kf_composite.jsonl)

Every event is commitment-referenced (crop SHA-256s from the manifest), never
raw-pixel-carrying. Rails: advisory=True on the stream; developer_self scope inherited;
no flags, no bridge imports; cv2/numpy used only in the thin IO helper -- the
segmentation core is pure and injectable for tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

SCENE_SCHEMA = "qortroller-scene-stream-v0"      # schema string only -- not a domain tag

SCENE_CHANGE = "SCENE_CHANGE"
SCENE_STABLE_SEGMENT = "SCENE_STABLE_SEGMENT"
KILL_ROW_CLUSTER = "KILL_ROW_CLUSTER"
INPUT_WINDOW = "INPUT_WINDOW"

DEFAULT_FRESH_DIFF = 6.0     # mirrors _SESSION_ANCHOR_FRESH_DIFF (live fresh-row gate)
# F-LUMEN-1 CALIBRATED (2026-07-08 study, audits/f-lumen-1-panel-threshold-study): the 6.0
# killer-slot threshold is ~8x below the PANEL-scale delta MEDIAN (p50~47 on BOTH M14-RP and
# M13-HDMI — cross-topology stable), which is why panel streams read ~92% SCENE_CHANGE.
# 63.0 = the cross-topology p75: ~25% ambient change rate (stable segments exist) with ~60%
# kill-onset sensitivity (kills sit at delta ~68-72). SCENE_CHANGE is generic structure, NOT
# a kill detector (OCR owns kills) — consumers wanting a different operating point read the sweep.
PANEL_FRESH_DIFF = 63.0
MIN_STABLE_RUN = 3           # crops; shorter runs are transitions, not segments


@dataclass(slots=True)
class SceneEvent:
    ts_ns: int
    kind: str
    span_ms: Optional[list]          # [start_ms, end_ms] or None for point events
    crop_shas: list
    confidence: Optional[float]
    source: str

    def to_dict(self) -> dict:
        return {"ts_ns": self.ts_ns, "kind": self.kind, "span_ms": self.span_ms,
                "crop_shas": self.crop_shas, "confidence": self.confidence,
                "source": self.source}


@dataclass
class SceneEventStream:
    schema: str
    session_id: Optional[str]
    session_display: Optional[str]
    events: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    advisory: bool = True

    def counts(self) -> dict:
        out: dict = {}
        for e in self.events:
            out[e.kind] = out.get(e.kind, 0) + 1
        return out

    def to_jsonl(self) -> str:
        head = json.dumps({"schema": self.schema, "session_id": self.session_id,
                           "session_display": self.session_display,
                           "advisory": self.advisory, "counts": self.counts(),
                           "notes": self.notes}, sort_keys=True)
        lines = [head] + [json.dumps(e.to_dict(), sort_keys=True) for e in self.events]
        return "\n".join(lines) + "\n"


def compute_crop_deltas(paths: list) -> list:
    """IO helper: mean-abs-gray delta between consecutive crops (the ONLY cv2/numpy
    touch). Returns [(ts_ns_of_second_crop, delta_float), ...]. Shape mismatches
    (resolution change mid-session) yield delta=None -- honestly skipped downstream."""
    import cv2
    import numpy as np
    out: list = []
    prev = prev_ts = None
    for ts_ns, path in paths:
        g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if g is None:
            continue
        if prev is not None:
            if g.shape == prev.shape:
                out.append((ts_ns, float(np.mean(np.abs(
                    g.astype("int16") - prev.astype("int16"))))))
            else:
                out.append((ts_ns, None))
        prev, prev_ts = g, ts_ns
    return out


def segment_scene(deltas: list, *, fresh_diff: float = DEFAULT_FRESH_DIFF,
                  min_stable_run: int = MIN_STABLE_RUN) -> list:
    """PURE segmentation core over a (ts_ns, delta) series. Emits SCENE_CHANGE point
    events (delta >= fresh_diff) and SCENE_STABLE_SEGMENT span events (runs of
    >= min_stable_run low-delta crops). None deltas (shape breaks) end any run."""
    events: list = []
    run_start = run_last = None
    run_len = 0

    def _flush():
        nonlocal run_start, run_last, run_len
        if run_start is not None and run_len >= min_stable_run:
            events.append(SceneEvent(
                ts_ns=run_start, kind=SCENE_STABLE_SEGMENT,
                span_ms=[round(run_start / 1e6, 1), round(run_last / 1e6, 1)],
                crop_shas=[], confidence=None, source="gray_delta_v0"))
        run_start = run_last = None
        run_len = 0

    for ts_ns, delta in deltas:
        if delta is None:
            _flush()
            continue
        if delta >= fresh_diff:
            _flush()
            events.append(SceneEvent(ts_ns=ts_ns, kind=SCENE_CHANGE, span_ms=None,
                                     crop_shas=[], confidence=round(float(delta), 2),
                                     source="gray_delta_v0"))
        else:
            if run_start is None:
                run_start = ts_ns
            run_last = ts_ns
            run_len += 1
    _flush()
    return events


def build_scene_stream(*, manifest: dict, deltas: Optional[list] = None,
                       scan: Optional[dict] = None, windows: Optional[list] = None,
                       fresh_diff: float = DEFAULT_FRESH_DIFF) -> SceneEventStream:
    """Assemble the stream. All inputs optional-but-honest: a missing source is a note,
    never a fabricated event. `scan` must be a v2 precision scan for this SAME session
    (session join enforced via the archive/display match -- mismatch = note + skip,
    the buffer never asserts a join it cannot check)."""
    notes: list = []
    stream = SceneEventStream(schema=SCENE_SCHEMA,
                              session_id=(manifest or {}).get("session_id"),
                              session_display=(manifest or {}).get("session_display"),
                              notes=notes)
    if not manifest:
        notes.append("no manifest -- stream is unjoined (session_id None)")

    events: list = []
    if deltas:
        events.extend(segment_scene(deltas, fresh_diff=fresh_diff))
    else:
        notes.append("no crop deltas supplied -- SCENE_CHANGE/STABLE events absent")

    if scan:
        display = (manifest or {}).get("session_display") or ""
        arch = str(scan.get("archive") or "").replace("\\", "/")
        if display and display not in arch:
            notes.append(f"scan archive {arch!r} != session {display!r} -- clusters SKIPPED")
        elif scan.get("scan_version") != "rp-ocr-precision-v2":
            notes.append("scan is not v2 (no per-read provenance) -- clusters SKIPPED")
        else:
            for c in (scan.get("clusters") or []):
                reads = c.get("reads") or []
                ts = [r["ts_ns"] for r in reads if r.get("ts_ns")]
                if not ts:
                    continue
                events.append(SceneEvent(
                    ts_ns=min(ts), kind=KILL_ROW_CLUSTER,
                    span_ms=[round(min(ts) / 1e6, 1), round(max(ts) / 1e6, 1)],
                    crop_shas=[r.get("sha256") for r in reads],
                    confidence=round(sum(r.get("conf", 0.0) for r in reads) / len(reads), 3),
                    source="rp-ocr-precision-v2"))
    else:
        notes.append("no scan supplied -- KILL_ROW_CLUSTER events absent")

    for w in (windows or []):
        events.append(SceneEvent(ts_ns=int(float(w[0]) * 1e6), kind=INPUT_WINDOW,
                                 span_ms=[float(w[0]), float(w[1])], crop_shas=[],
                                 confidence=None, source="retina_kf_composite"))
    if not windows:
        notes.append("no live windows supplied -- INPUT_WINDOW events absent")

    events.sort(key=lambda e: e.ts_ns)
    stream.events = events
    return stream


def verify_stream_references(stream: SceneEventStream, manifest: dict) -> dict:
    """LUMEN-2 join check: every event crop_sha must resolve in the manifest, and the
    stream's session_id must equal the manifest's. Returns {ok, dangling, note}."""
    man_shas = {f.get("sha256") for f in (manifest or {}).get("files") or []}
    dangling = [s for e in stream.events for s in e.crop_shas if s not in man_shas]
    sid_ok = stream.session_id == (manifest or {}).get("session_id")
    return {"ok": sid_ok and not dangling, "dangling": dangling,
            "note": ("session_id mismatch" if not sid_ok else
                     f"{len(dangling)} dangling sha(s)" if dangling else "all refs resolve")}


# =====================================================================================
# LUMEN-1 / A2 (TRL-1) -- OCR-recall aid: the buffer RAISES WHERE TO LOOK.
#
# Under sparse RP sampling the throttled kill-row OCR misses rows. Bursts of SCENE_CHANGE
# (a row appeared / left) mark the temporal windows worth the OCR budget; a KILL_ROW_CLUSTER
# overlapping boosts the priority. recall_priority() ranks those windows so the OCR spends
# its budget where a row most likely appeared.
#
# HARD RAILS (the certificate-path discipline, TRL-1 rail 7 / the alignment doc N1):
#   * ADVISORY ONLY -- ranks WHERE TO LOOK. Never opens a classification window, never
#     lowers the K=3 authored-kill floor, never changes canon(), never feeds presence_score.
#     OCR still owns the read; this only allocates the read budget.
#   * CONSUMPTION-GATED -- the priorities reach the live authorship / certificate path ONLY
#     after the zero-false-read gate AND the C1 adversarial pairing RE-PASS on the card feed
#     (the B8 lesson: a better reader can dissolve an accidental defense). That re-gate is
#     RIG/CARD-gated, not a desk step. authorship_recall_priority() returns [] until then --
#     so this ships the aid + the rail while the certificate-path wiring stays deferred.

RECALL_CLUSTER_WINDOW_MS = 750.0


def recall_priority(stream: SceneEventStream, *, top_k: int = 8,
                    cluster_window_ms: float = RECALL_CLUSTER_WINDOW_MS) -> list:
    """ADVISORY ranked OCR-recall windows [{ts_ns, priority}, ...] by SCENE_CHANGE
    density (KILL_ROW_CLUSTER overlap boosts). Non-max-suppressed to distinct windows.
    For logging / OCR scheduling -- NOT the certificate path (that is
    authorship_recall_priority, which is gated)."""
    changes = sorted(e.ts_ns for e in stream.events if e.kind == SCENE_CHANGE)
    if not changes:
        return []
    win_ns = cluster_window_ms * 1e6
    clusters = [tuple(e.span_ms) for e in stream.events
                if e.kind == KILL_ROW_CLUSTER and e.span_ms]

    def _boost(ts_ns):
        ts_ms = ts_ns / 1e6
        return 2 if any(s <= ts_ms <= e for s, e in clusters) else 1

    scored = [(ts, sum(1 for t in changes if abs(t - ts) <= win_ns / 2) * _boost(ts))
              for ts in changes]
    scored.sort(key=lambda x: (x[1], x[0]), reverse=True)
    hints: list = []
    used: list = []
    for ts, pr in scored:
        if all(abs(ts - u) > win_ns for u in used):
            hints.append({"ts_ns": ts, "priority": pr})
            used.append(ts)
        if len(hints) >= top_k:
            break
    return hints


def authorship_recall_priority(stream: SceneEventStream, *,
                               consumption_regated: bool = False, top_k: int = 8) -> list:
    """The CERTIFICATE-PATH consumer. Returns [] unless consumption_regated -- i.e. the
    zero-false-read gate + C1 adversarial pairing have RE-PASSED on the card feed (a
    rig/card-gated step). Until then the recall aid cannot influence authorship, by
    construction."""
    if not consumption_regated:
        return []
    return recall_priority(stream, top_k=top_k)
