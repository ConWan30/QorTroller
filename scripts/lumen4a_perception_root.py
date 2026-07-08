#!/usr/bin/env python3
"""LUMEN-4a -- roll a session's LIVE-captured trio-retina perception events into the
first non-null retina_perception_root CANDIDATE.

The discovery that shaped this runner: the retina perception pipeline (the installed
MachineFi/IoTeX `trio-retina` package's data model, fed by retina_controller_embedder)
ran LIVE during Match 14 -- 329 rows in retina_event_log, each carrying typed events
with 16-dim embeddings (model qortroller-controller-v1), a world-state snapshot, a
per-row state_commitment_hex, and a binding record_hash_hex into the SAME PoAC record
stream PoSP's fusion surface references. The evidence existed; it was never rolled into
the session root PoSP's events_roots slot was designed to carry (§2.3 named-roots rail).

This runner computes that root OFFLINE via the EXISTING
retina_state_commitment.compute_events_root (no new scheme, no new tag) and emits a
CANDIDATE artifact. RAILS: an ISSUED PoSP record is NEVER mutated -- the slot stays
honestly null on M13/M14's records; this artifact is the candidate a FUTURE session
carries live. Advisory throughout; zero rig; zero chain.

Usage:
    python scripts/lumen4a_perception_root.py \
        --db C:/Users/Contr/.vapi/bridge_match14.db \
        --archive retina_kf_archive/match14_rp_option_b_1783475385 \
        --posp audits/posp_record_match14_rp_option_b_2026-07-07.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge.vapi_bridge.retina_state_commitment import (   # noqa: E402
    EVENTS_ROOT_SCHEME_SHA256_V1, compute_events_root,
)

_SPAN_PAD_S = 120.0


def main() -> int:
    ap = argparse.ArgumentParser(description="LUMEN-4a perception-root candidate")
    ap.add_argument("--db", required=True, help="session bridge DB (retina_event_log)")
    ap.add_argument("--archive", required=True, help="session archive (manifest.json)")
    ap.add_argument("--posp", default=None, help="issued PoSP record (join-strength check)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    try:
        manifest = json.load(open(os.path.join(args.archive, "manifest.json"), encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: manifest: {exc}", file=sys.stderr)
        return 2

    start_s = float(manifest["started_at"]) - _SPAN_PAD_S
    end_s = start_s + 2 * _SPAN_PAD_S + 3600.0
    archived = manifest.get("archived_at")
    if archived:
        try:
            end_s = _dt.datetime.strptime(archived, "%Y-%m-%d %H:%M:%S").timestamp() + _SPAN_PAD_S
        except ValueError:
            pass

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=10)
    rows = con.execute(
        "SELECT events_json, record_hash_hex, state_commitment_hex, anomaly_count, "
        "created_at, source FROM retina_event_log "
        "WHERE created_at BETWEEN ? AND ? ORDER BY id", (start_s, end_s)).fetchall()
    con.close()

    events, kinds, rec_hashes = [], Counter(), set()
    n_commitments = 0
    for ev_json, rec_hash, state_c, _anom, _ts, _src in rows:
        try:
            for e in json.loads(ev_json) or []:
                events.append(e)
                kinds[str(e.get("type", "?"))] += 1
        except json.JSONDecodeError:
            continue
        if rec_hash:
            rec_hashes.add(rec_hash)
        if state_c:
            n_commitments += 1

    if not rows:
        print("No retina_event_log rows in the session span -- nothing to roll. "
              "(Honest: the perception pipeline did not run for this session/DB.)")
        return 1

    root_hex = compute_events_root(events).hex()

    # Join strength: how many perception rows bind (via record_hash_hex) into the SAME
    # PoAC stream the issued PoSP's fusion surface references (capped ref list).
    join = None
    if args.posp and os.path.isfile(args.posp):
        posp = json.load(open(args.posp, encoding="utf-8"))
        refs = set((posp.get("fusion") or {}).get("record_hashes") or [])
        join = {"posp_session_id": posp.get("session_id"),
                "session_id_match": posp.get("session_id") == manifest.get("session_id"),
                "posp_fusion_refs": len(refs),
                "perception_rows_bound_to_posp_refs": len(rec_hashes & refs),
                "posp_retina_perception_root_at_issue": (posp.get("events_roots") or {}
                                                         ).get("retina_perception_root")}

    try:
        import retina
        trio_ver = getattr(retina, "__version__", "installed")
    except ImportError:
        trio_ver = None

    doc = {
        "artifact": "retina-perception-root-candidate-v0",
        "status": "CANDIDATE -- NOT retro-inserted into any issued PoSP record "
                  "(issued records are immutable; a future session carries this live)",
        "advisory": True,
        "session_id": manifest.get("session_id"),
        "session_display": manifest.get("session_display"),
        "retina_perception_root": root_hex,
        "events_root_scheme": str(EVENTS_ROOT_SCHEME_SHA256_V1),
        "n_perception_rows": len(rows),
        "n_events": len(events),
        "n_per_row_state_commitments": n_commitments,
        "event_types": dict(kinds),
        "distinct_record_hash_bindings": len(rec_hashes),
        "posp_join": join,
        "pipeline": {"package": "trio-retina (MachineFi/IoTeX, Apache-2.0)",
                     "installed": trio_ver is not None, "version": trio_ver,
                     "embedder": "retina_controller_embedder (qortroller-controller-v1, dim=16)",
                     "captured": "LIVE during the session (retina_event_log)"},
    }

    sep = "-" * 64
    print(f"\n{sep}\n  Perception-root candidate -- {doc['session_display']}\n{sep}")
    print(f"  root       : {root_hex}")
    print(f"  scheme     : {doc['events_root_scheme']}")
    print(f"  rows/events: {len(rows)} rows -> {len(events)} events "
          f"({n_commitments} per-row state commitments)")
    print(f"  types      : {dict(kinds)}")
    print(f"  bindings   : {len(rec_hashes)} distinct PoAC record hashes")
    if join:
        print(f"  posp join  : session_id_match={join['session_id_match']} | "
              f"{join['perception_rows_bound_to_posp_refs']}/{join['posp_fusion_refs']} "
              f"capped fusion refs also carry perception rows | root at issue: "
              f"{join['posp_retina_perception_root_at_issue']}")
    print(f"  trio-retina: installed={doc['pipeline']['installed']}")

    out = args.out or os.path.join(
        "audits", f"retina_perception_root_candidate_{doc['session_display']}.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    print(f"  written    : {out}\n{sep}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
