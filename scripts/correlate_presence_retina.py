"""Runner: bind presence proofs (l6b_probe_log) to retina/PoAC records (retina_event_log).

Reads the live bridge SQLite DB, runs the pure +/-2 s temporal correlator
(l9_presence.adversarial.cocapture_binding), and writes a dated audit artifact.

This is the PROTOTYPE closure of the presence<->retina binding gap: it pairs the
already-captured probes (which carry no record_hash) to co-temporal retina rows
(which DO carry a PoAC record_hash). It states plainly that a temporal pair is a
correlation, not a cryptographic proof. The production closure (probe carries its
own record_hash) is handled going forward by scripts/presence_challenger.py.

Stdlib sqlite3 only -- no bridge import. Timestamp bases (confirmed against the DB):
  l6b_probe_log.probe_ts_ms : INTEGER ms   -> *1e6 ns
  retina_event_log.created_at: REAL epoch s -> *1e9 ns

  py scripts/correlate_presence_retina.py
  py scripts/correlate_presence_retina.py --since-ms 1782050000000 --window-ms 2000
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from l9_presence.adversarial.cocapture_binding import (  # noqa: E402
    ProbeRow,
    RetinaRow,
    correlate,
)

_DEFAULT_DB = os.path.expanduser("~/.vapi/bridge.db")
_DEFAULT_DEVICE = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"


def load_probes(conn: sqlite3.Connection, device_id: str, since_ms: int) -> list[ProbeRow]:
    rows = conn.execute(
        "SELECT device_id, probe_ts_ms, classification, latency_ms FROM l6b_probe_log "
        "WHERE device_id=? AND probe_ts_ms >= ? ORDER BY probe_ts_ms ASC",
        (device_id, since_ms),
    ).fetchall()
    out = []
    for dev, ts_ms, cls, lat in rows:
        rh = None
        # forward-compat: stamp present only after the challenger upgrade lands
        out.append(ProbeRow(device_id=dev, ts_ns=int(ts_ms) * 1_000_000,
                            classification=cls, latency_ms=lat, record_hash=rh))
    return out


def load_probes_with_hash(conn: sqlite3.Connection, device_id: str, since_ms: int) -> list[ProbeRow]:
    """Variant used when l6b_probe_log has gained a record_hash column."""
    rows = conn.execute(
        "SELECT device_id, probe_ts_ms, classification, latency_ms, record_hash "
        "FROM l6b_probe_log WHERE device_id=? AND probe_ts_ms >= ? ORDER BY probe_ts_ms ASC",
        (device_id, since_ms),
    ).fetchall()
    return [ProbeRow(device_id=d, ts_ns=int(t) * 1_000_000, classification=c,
                     latency_ms=l, record_hash=h) for d, t, c, l, h in rows]


def load_retina(conn: sqlite3.Connection, device_id: str, since_s: float) -> list[RetinaRow]:
    rows = conn.execute(
        "SELECT device_id, created_at, record_hash_hex, anomaly_count FROM retina_event_log "
        "WHERE device_id=? AND created_at >= ? ORDER BY created_at ASC",
        (device_id, since_s),
    ).fetchall()
    return [RetinaRow(device_id=d, ts_ns=int(float(ts) * 1_000_000_000),
                      record_hash=rh, anomaly_count=int(ac or 0))
            for d, ts, rh, ac in rows]


def _has_record_hash_column(conn: sqlite3.Connection) -> bool:
    cols = [c[1] for c in conn.execute("PRAGMA table_info(l6b_probe_log)").fetchall()]
    return "record_hash" in cols


def main() -> int:
    ap = argparse.ArgumentParser(description="Bind presence proofs to retina/PoAC records")
    ap.add_argument("--db", default=_DEFAULT_DB)
    ap.add_argument("--device", default=_DEFAULT_DEVICE)
    ap.add_argument("--since-ms", type=int, default=0,
                    help="only probes at/after this epoch-ms (default 0 = all)")
    ap.add_argument("--window-ms", type=float, default=2000.0,
                    help="temporal join window in ms (default 2000 = engine fusion window)")
    ap.add_argument("--out-dir", default="audits")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db, timeout=5.0)
    try:
        if _has_record_hash_column(conn):
            probes = load_probes_with_hash(conn, args.device, args.since_ms)
        else:
            probes = load_probes(conn, args.device, args.since_ms)
        retina = load_retina(conn, args.device, args.since_ms / 1000.0)
    finally:
        conn.close()

    rep = correlate(probes, retina, window_ns=int(args.window_ms * 1_000_000))
    d = rep.to_dict()

    os.makedirs(args.out_dir, exist_ok=True)
    date = time.strftime("%Y-%m-%d")
    md_path = os.path.join(args.out_dir, f"presence-retina-binding-{date}.md")
    json_path = os.path.join(args.out_dir, f"presence-retina-binding-{date}.json")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(rep.to_markdown() + "\n")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2)

    print(f"[correlate] probes={d['n_probes']} retina_rows={len(retina)} "
          f"bound={d['n_bound']} ({d['coverage'] * 100:.1f}%) "
          f"crypto={d['n_crypto_bound']} ({d['crypto_coverage'] * 100:.1f}%)")
    print(f"[correlate] HUMAN={d['n_human']} HUMAN-bound={d['n_human_bound']} "
          f"({d['human_coverage'] * 100:.1f}%)  offset_abs_dt_ms={d['offset_stats_ms']}")
    print(f"[correlate] wrote {md_path} + {json_path}")
    if d["binding_is_cryptographic"]:
        print("[correlate] BINDING IS CRYPTOGRAPHIC (production).")
    else:
        print("[correlate] TEMPORAL prototype only — NOT a cryptographic proof. "
              "Run an upgraded challenger session for record_hash-stamped probes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
