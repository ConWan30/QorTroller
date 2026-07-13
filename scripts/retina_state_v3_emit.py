"""TRA-1 T6.6a - session-close VAPI-RETINA-STATE-v3 emit (daemon hook; default-off, fail-open).

At session close the daemon (``retina_capture_daemon._issue_posp``) can ADDITIVELY emit the FROZEN
``VAPI-RETINA-STATE-v3`` record from the session's live-captured, CONFORMANT ``retina.event/0.1``
events (the SAME ``retina_event_log`` source LUMEN-4b rolls). Writes
``audits/retina_state_v3_<label>_<date>.json``.

Rails:
  * Gated by ``RETINA_STATE_V3_EMIT_ENABLED`` (default OFF -> byte-identical daemon behavior).
  * FAIL-OPEN: never blocks PoSP issuance (any error -> None + a diagnostic print).
  * Does NOT modify the PoSP ``retina_perception_root`` / the M14-anchored LUMEN-4a root - switching
    the PoSP to the standard ordered root is a separate operator decision (dual-consumer regression).
  * Honest null: no conformant events -> no record (never fabricated), matching LUMEN-4a.

OBSERVATION-plane only. No PoAC / 228B / ASSERTION-plane / chain contact; the v3 formula is FROZEN.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional, Sequence

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bridge.vapi_bridge.retina_event_std import separation_law_problems, validate_event
from bridge.vapi_bridge.retina_session_worldstate import worldstate_from_observation
from bridge.vapi_bridge.retina_state_v3_record import build_retina_state_v3_record

_SPAN_PAD_S = 120.0


def emit_enabled() -> bool:
    """True iff RETINA_STATE_V3_EMIT_ENABLED is set truthy (default OFF)."""
    return os.environ.get("RETINA_STATE_V3_EMIT_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def read_session_events(db_path: Optional[str], start_s: float, end_s: float) -> list[dict]:
    """Read the session's live-captured events from ``retina_event_log`` (same source + span shape as
    LUMEN-4b). Fail-open -> [] on missing DB / any error."""
    try:
        if not db_path or not os.path.isfile(db_path):
            return []
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        try:
            rows = con.execute(
                "SELECT events_json FROM retina_event_log WHERE created_at BETWEEN ? AND ? ORDER BY id",
                (float(start_s), float(end_s))).fetchall()
        finally:
            con.close()
        events: list[dict] = []
        for (ev_json,) in rows:
            try:
                for e in json.loads(ev_json) or []:
                    if isinstance(e, dict):
                        events.append(e)
            except (json.JSONDecodeError, TypeError):
                continue
        return events
    except Exception:  # noqa: BLE001 - fail-open
        return []


def conformant_events(events: Sequence[dict]) -> list[dict]:
    """Keep only events passing retina.event/0.1 conformance + the separation law (the v3 record can
    only be built over a conformant stream; non-conformant rows are dropped, never forced)."""
    return [e for e in events if not (validate_event(e) + separation_law_problems(e))]


def read_killfeed_event_sink(capture_dir: Optional[str]) -> list[dict]:
    """Read the session's killfeed kill events from ``{capture_dir}/killfeed_events.jsonl`` (written by
    the daemon's rapidocr tick, T6.6b) - the OBSERVATION source for the session v3 record, NOT the
    controller-perception ``retina_event_log``. Deduped: the lingering feed repeats each kill across
    ticks, so keep the FIRST occurrence of each (killer, victim) in t-order. (v1 limitation: an
    identical re-kill of the same victim collapses; refine with real live timestamps.) Fail-open -> []."""
    try:
        if not capture_dir:
            return []
        sink = os.path.join(capture_dir, "killfeed_events.jsonl")
        if not os.path.isfile(sink):
            return []
        raw: list[dict] = []
        with open(sink, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    if isinstance(e, dict):
                        raw.append(e)
                except json.JSONDecodeError:
                    continue
        raw.sort(key=lambda e: float(e.get("t", 0.0) or 0.0))
        seen: set = set()
        out: list[dict] = []
        for e in raw:
            key = (str(e.get("killer", "")), str(e.get("victim", "")))
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
        return out
    except Exception:  # noqa: BLE001 - fail-open
        return []


def emit_session_v3_record(events: Sequence[dict], *, device_id: str, ts_ns: int, label: str,
                           out_dir: Optional[Path] = None, controller_id: Any = None,
                           input_locus: Optional[Sequence[float]] = None, chain_fn=None) -> Optional[Path]:
    """Build + write the v3 record from the session's CONFORMANT events. Returns the artifact path, or
    None (honest null) when there are no conformant events. WorldState = the session observation + the
    controller ONLY when a live input locus is supplied (dual-connection-blind -> omitted)."""
    ce = conformant_events(events)
    if not ce:
        return None
    ws = worldstate_from_observation(ts_ns / 1e9, controller_id=controller_id, input_locus=input_locus)
    record = build_retina_state_v3_record(device_id, ts_ns, ce, ws, chain_fn=chain_fn)
    out_dir = out_dir or (_REPO / "audits")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"retina_state_v3_{label}_{date.today().isoformat()}.json"
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return out


def maybe_emit_session_v3(label: str, stamp, kas_rec: dict, db_path: Optional[str], *,
                          out_dir: Optional[Path] = None) -> Optional[Path]:
    """Daemon hook (called from ``_issue_posp`` when RETINA_STATE_V3_EMIT_ENABLED). Reads the session's
    events + emits the v3 record. Fail-open -> None (never blocks PoSP issuance)."""
    try:
        if not emit_enabled():
            return None
        capture_dir = os.environ.get("RETINA_KILLFEED_CAPTURE_DIR", "retina_kf_crops")
        if not os.path.isabs(capture_dir):
            capture_dir = str(_REPO / capture_dir)
        events = read_killfeed_event_sink(capture_dir)   # T6.6b: killfeed sink, NOT retina_event_log
        device_id = str(kas_rec.get("device_id") or kas_rec.get("session_id") or "unknown")
        ts_ns = int(float(stamp) * 1e9)
        out = emit_session_v3_record(events, device_id=device_id, ts_ns=ts_ns, label=label, out_dir=out_dir)
        if out:
            print(f"[daemon] retina-state-v3: emitted {out.name} "
                  f"({len(conformant_events(events))} conformant events)")
        else:
            print("[daemon] retina-state-v3: no conformant events -> honest null (no record)")
        return out
    except Exception as e:  # noqa: BLE001 - never block PoSP issuance
        print(f"[daemon] retina-state-v3 emit failed (non-fatal): {e!r}")
        return None
