#!/usr/bin/env python3
"""
QorTroller Protocol Watcher — Autonomous Agentic Monitoring Loop
================================================================

Runs as a background process alongside the bridge and daemon.
Every POLL_INTERVAL seconds it:

  1. Snapshots all key protocol metrics (GIC chain, PCC, separation,
     calibration, corpus, tournament gate, on-chain wallet + block)
  2. Stores the snapshot in agent_memory.db (snapshots table)
  3. Diffs against the previous snapshot
  4. Evaluates alert thresholds
  5. Posts any triggered alerts to the daemon brain via POST /chat
     — the brain reasons about the alert and stores its analysis
       in the shared conversation history

The daemon brain becomes a protocol-aware incident responder, not
just a query interface.

Usage:
  python protocol_watcher.py                  # default 5-min cadence
  python protocol_watcher.py --interval 60    # 60-second cadence (dev)
  python protocol_watcher.py --once           # single snapshot + diff, exit
  python protocol_watcher.py --status         # print last snapshot, exit

Architecture:
  protocol_watcher.py ──poll──▶ bridge:8000/operator/*
                      ──poll──▶ IoTeX RPC (direct)
                      ──alert──▶ daemon:8080/chat
                                  └──▶ deepseek-v4-flash reasons + stores
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

_DOTENV = os.path.join(os.path.dirname(__file__), "bridge", ".env")
if os.path.isfile(_DOTENV):
    with open(_DOTENV, "r", encoding="utf-8", errors="ignore") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                _k = _k.strip()
                _v = _v.strip().strip('"').strip("'")
                if _k and _k not in os.environ:
                    os.environ[_k] = _v

OPERATOR_API_KEY    = os.environ.get("OPERATOR_API_KEY", "")
BRIDGE_OPERATOR_URL = os.environ.get("VAPI_BRIDGE_OPERATOR_URL", "http://localhost:8000/operator")
DAEMON_URL          = os.environ.get("QORTROLLER_DAEMON_URL", "http://localhost:8080")
IOTEX_RPC           = "https://babel-api.testnet.iotex.io"
WALLET              = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
POLL_INTERVAL       = int(os.environ.get("WATCHER_INTERVAL", 300))  # seconds
DB_PATH             = os.path.join(os.path.dirname(__file__), "agent_memory.db")

# ── Alert thresholds ─────────────────────────────────────────────────────────

ALERTS = {
    # (metric_key, threshold, direction, message_template)
    "gic_chain_broken":       (True,  "eq",  "GIC chain integrity BROKEN — grind halted"),
    "separation_ratio_drop":  (0.05,  "gt",  "AIT separation ratio dropped {delta:.3f} in one cycle"),
    "calibration_threshold_shift": (0.10, "gt", "L4 anomaly threshold shifted {delta:.3f} — significant corpus change"),
    "wallet_drop":            (0.01,  "gt",  "Wallet decreased by {delta:.4f} IOTX — unexpected on-chain spend"),
    "pcc_degraded":           (True,  "eq",  "PCC capture state DEGRADED — grind session quality at risk"),
    "new_gic_links":          (5,     "ge",  "{count} new GIC links since last snapshot — good grind progress"),
    "gic_target_reached":     (True,  "eq",  "GIC_TARGET REACHED — {length} links complete. Run graduation sequence."),
    "tournament_gate_change": (True,  "eq",  "Tournament gate overall_pass changed to {value}"),
}

# ── Database ──────────────────────────────────────────────────────────────────

def _init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS protocol_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            ts_unix     REAL NOT NULL,
            snapshot    TEXT NOT NULL  -- JSON blob
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON protocol_snapshots(ts_unix DESC);
        CREATE TABLE IF NOT EXISTS watcher_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            alert_key   TEXT NOT NULL,
            message     TEXT NOT NULL,
            delta       REAL,
            posted_to_brain INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    return conn

def _save_snapshot(conn: sqlite3.Connection, snap: dict) -> int:
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    cur = conn.execute(
        "INSERT INTO protocol_snapshots (timestamp, ts_unix, snapshot) VALUES (?, ?, ?)",
        (ts, time.time(), json.dumps(snap, default=str))
    )
    conn.commit()
    return cur.lastrowid

def _get_last_snapshots(conn: sqlite3.Connection, n: int = 2) -> list[dict]:
    rows = conn.execute(
        "SELECT snapshot, timestamp FROM protocol_snapshots ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    return [{"data": json.loads(r[0]), "timestamp": r[1]} for r in rows]

def _save_alert(conn: sqlite3.Connection, key: str, message: str,
                delta: float | None = None) -> int:
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    cur = conn.execute(
        "INSERT INTO watcher_alerts (timestamp, alert_key, message, delta) VALUES (?, ?, ?, ?)",
        (ts, key, message, delta)
    )
    conn.commit()
    return cur.lastrowid

# ── Data collection ───────────────────────────────────────────────────────────

def _bget(path: str, timeout: float = 5.0) -> dict | None:
    """GET bridge operator endpoint with auth."""
    hdrs = {"x-api-key": OPERATOR_API_KEY} if OPERATOR_API_KEY else {}
    try:
        req = urllib.request.Request(
            f"{BRIDGE_OPERATOR_URL}{path}", headers=hdrs
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def _rpc(method: str, params: list) -> dict | None:
    """IoTeX JSON-RPC call."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1,
                          "method": method, "params": params}).encode()
    try:
        req = urllib.request.Request(
            IOTEX_RPC, data=payload,
            headers={"Content-Type": "application/json",
                     "User-Agent": "QorTroller-Watcher/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except Exception:
        return None

def collect_snapshot() -> dict:
    """Collect a full protocol state snapshot. Returns structured dict."""
    snap: dict = {"collected_at": datetime.datetime.utcnow().isoformat() + "Z"}

    # ── GIC chain ──────────────────────────────────────────────────────
    gic = _bget("/bridge/grind-chain-status")
    snap["gic"] = {
        "chain_length":    gic.get("chain_length", 0)       if gic else None,
        "chain_intact":    gic.get("chain_intact", None)    if gic else None,
        "grind_target":    gic.get("grind_target", 200)     if gic else None,
        "session_id":      gic.get("grind_session_id", "")  if gic else None,
        "latest_hash":     (gic.get("latest_gic_hash") or "")[:16] if gic else None,
        "latest_ts":       gic.get("latest_ts", 0)          if gic else None,
        "gameplay_ctx":    gic.get("latest_gameplay_context", "") if gic else None,
    }

    # ── PCC / capture health ───────────────────────────────────────────
    pcc = _bget("/bridge/capture-health")
    snap["pcc"] = {
        "capture_state":   pcc.get("capture_state", "UNKNOWN")         if pcc else None,
        "host_state":      pcc.get("host_state", "UNKNOWN")             if pcc else None,
        "poll_rate_hz":    pcc.get("poll_rate_hz", 0.0)                 if pcc else None,
        "grind_ready":     pcc.get("grind_ready", False)                if pcc else None,
        "consec_clean":    pcc.get("consecutive_clean_toward_target", 0) if pcc else None,
        "grind_target":    pcc.get("grind_target", 200)                 if pcc else None,
    }

    # ── AIT separation ─────────────────────────────────────────────────
    ait = _bget("/agent/ait-separation-status")
    snap["ait"] = {
        "ratio":           ait.get("separation_ratio", 0.0)   if ait else None,
        "n_sessions":      ait.get("n_sessions", 0)           if ait else None,
        "all_pairs_gt1":   ait.get("all_pairs_above_1", False) if ait else None,
        "p1vp2":           ait.get("pair_distances", {}).get("P1vP2") if ait else None,
        "p1vp3":           ait.get("pair_distances", {}).get("P1vP3") if ait else None,
        "p2vp3":           ait.get("pair_distances", {}).get("P2vP3") if ait else None,
    }

    # ── Separation ratio registry ───────────────────────────────────────
    sep = _bget(f"/agent/separation-ratio-status?api_key={OPERATOR_API_KEY}")
    snap["separation"] = {
        "pooled_ratio":    sep.get("pooled_ratio", 0.0)        if sep else None,
        "battery_ratio":   sep.get("battery_stratified_ratio", 0.0) if sep else None,
        "tournament_ready": sep.get("tournament_ready", False) if sep else None,
    }

    # ── Tournament gate ─────────────────────────────────────────────────
    tpf = _bget(f"/agent/tournament-preflight-status?api_key={OPERATOR_API_KEY}")
    snap["tournament"] = {
        "overall_pass":    tpf.get("overall_pass", False)     if tpf else None,
        "separation_ok":   tpf.get("separation_ok", False)    if tpf else None,
        "l4_ok":           tpf.get("l4_ok", False)            if tpf else None,
        "gate_ok":         tpf.get("gate_ok", False)          if tpf else None,
        "cert_ok":         tpf.get("cert_ok", False)          if tpf else None,
        "ait_ok":          tpf.get("ait_defensibility_ok", False) if tpf else None,
        "consec_clean":    tpf.get("conditions", {}).get("consecutive_clean") if tpf else None,
    }

    # ── Calibration thresholds ───────────────────────────────────────────
    try:
        cal_path = Path(__file__).parent / "calibration_profile_live.json"
        cal = json.loads(cal_path.read_text(encoding="utf-8"))
        snap["calibration"] = {
            "anomaly_threshold":    cal.get("thresholds", {}).get("l4_anomaly"),
            "continuity_threshold": cal.get("thresholds", {}).get("l4_continuity"),
            "total_records":        cal.get("total_records"),
            "confidence":           cal.get("confidence"),
            "generated_at":         cal.get("generated_at"),
        }
    except Exception:
        snap["calibration"] = None

    # ── Corpus snapshot ──────────────────────────────────────────────────
    corp = _bget("/agent/corpus-snapshot-status")
    snap["corpus"] = {
        "total_snapshots":  corp.get("total_snapshots", 0)      if corp else None,
        "latest_commit":    (corp.get("latest_commitment") or "")[:16] if corp else None,
        "corpus_n":         corp.get("corpus_n", 0)             if corp else None,
        "on_chain":         corp.get("on_chain_confirmed", False) if corp else None,
    }

    # ── Capture stagnation ────────────────────────────────────────────────
    stag = _bget("/agent/capture-stagnation-status")
    snap["stagnation"] = {
        "stagnant":   stag.get("stagnant", False) if stag else None,
        "sessions_since_new": stag.get("sessions_since_new_player") if stag else None,
    }

    # ── On-chain (direct RPC) ─────────────────────────────────────────────
    bal = _rpc("eth_getBalance", [WALLET, "latest"])
    blk = _rpc("eth_blockNumber", [])
    snap["chain"] = {
        "wallet_iotx": round(int(bal["result"], 16) / 1e18, 6) if bal and bal.get("result") else None,
        "block_number": int(blk["result"], 16) if blk and blk.get("result") else None,
    }

    return snap

# ── Diffing + alerting ────────────────────────────────────────────────────────

def diff_snapshots(prev: dict, curr: dict) -> list[dict]:
    """Compare two snapshots and return list of triggered alerts."""
    triggered = []

    def alert(key: str, message: str, delta: float | None = None):
        triggered.append({"key": key, "message": message, "delta": delta})

    # GIC chain integrity
    if (curr.get("gic", {}).get("chain_intact") is False and
            prev.get("gic", {}).get("chain_intact") is not False):
        alert("gic_chain_broken", "GIC chain integrity BROKEN — grind halted")

    # New GIC links
    prev_len = prev.get("gic", {}).get("chain_length") or 0
    curr_len = curr.get("gic", {}).get("chain_length") or 0
    if curr_len > prev_len:
        delta_links = curr_len - prev_len
        alert("new_gic_links",
              f"{delta_links} new GIC link(s) added — chain now {curr_len} links",
              float(delta_links))

    # GIC target reached
    target = curr.get("gic", {}).get("grind_target") or 200
    if curr_len >= target and prev_len < target:
        alert("gic_target_reached",
              f"GIC TARGET REACHED — {curr_len}/{target} links complete. Run graduation sequence.")

    # Separation ratio drift
    prev_ratio = prev.get("ait", {}).get("ratio") or 0.0
    curr_ratio = curr.get("ait", {}).get("ratio") or 0.0
    if prev_ratio and curr_ratio and abs(curr_ratio - prev_ratio) >= 0.05:
        direction = "dropped" if curr_ratio < prev_ratio else "rose"
        alert("separation_ratio_drop",
              f"AIT separation ratio {direction} from {prev_ratio:.3f} → {curr_ratio:.3f}",
              prev_ratio - curr_ratio)

    # L4 threshold shift
    prev_thr = (prev.get("calibration") or {}).get("anomaly_threshold") or 0.0
    curr_thr = (curr.get("calibration") or {}).get("anomaly_threshold") or 0.0
    if prev_thr and curr_thr and abs(curr_thr - prev_thr) >= 0.05:
        alert("calibration_threshold_shift",
              f"L4 anomaly threshold shifted {prev_thr:.4f} → {curr_thr:.4f}",
              curr_thr - prev_thr)

    # Wallet drop
    prev_bal = (prev.get("chain") or {}).get("wallet_iotx") or 0.0
    curr_bal = (curr.get("chain") or {}).get("wallet_iotx") or 0.0
    if prev_bal and curr_bal and (prev_bal - curr_bal) >= 0.01:
        alert("wallet_drop",
              f"Wallet decreased {prev_bal:.6f} → {curr_bal:.6f} IOTX "
              f"(−{prev_bal - curr_bal:.6f} IOTX)",
              prev_bal - curr_bal)

    # PCC degradation
    prev_pcc = (prev.get("pcc") or {}).get("capture_state") or ""
    curr_pcc = (curr.get("pcc") or {}).get("capture_state") or ""
    if curr_pcc == "DEGRADED" and prev_pcc == "NOMINAL":
        alert("pcc_degraded",
              f"PCC capture state degraded: NOMINAL → DEGRADED "
              f"(poll_rate={curr.get('pcc', {}).get('poll_rate_hz'):.0f} Hz)")

    # Tournament gate flip
    prev_pass = (prev.get("tournament") or {}).get("overall_pass")
    curr_pass = (curr.get("tournament") or {}).get("overall_pass")
    if prev_pass is not None and curr_pass is not None and prev_pass != curr_pass:
        alert("tournament_gate_change",
              f"Tournament gate overall_pass: {prev_pass} → {curr_pass}")

    return triggered

# ── Daemon notification ────────────────────────────────────────────────────────

def post_to_brain(message: str, timeout: float = 30.0) -> bool:
    """Post an alert message to the daemon brain via POST /chat."""
    payload = json.dumps({"message": message}).encode()
    try:
        req = urllib.request.Request(
            f"{DAEMON_URL}/chat", data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def build_alert_message(alerts: list[dict], snap: dict) -> str:
    """Build a structured alert message for the brain."""
    ts = snap.get("collected_at", "unknown time")
    gic_len = snap.get("gic", {}).get("chain_length", "?")
    gic_target = snap.get("gic", {}).get("grind_target", 200)
    ratio = snap.get("ait", {}).get("ratio", "?")
    wallet = snap.get("chain", {}).get("wallet_iotx", "?")
    block = snap.get("chain", {}).get("block_number", "?")

    lines = [
        f"[WATCHER ALERT — {ts}]",
        f"Protocol snapshot: GIC {gic_len}/{gic_target} | AIT ratio {ratio} | "
        f"Wallet {wallet} IOTX | Block {block:,}" if isinstance(block, int) else
        f"Protocol snapshot: GIC {gic_len}/{gic_target} | AIT ratio {ratio} | "
        f"Wallet {wallet} IOTX",
        "",
        f"{len(alerts)} alert(s) triggered:",
    ]
    for a in alerts:
        lines.append(f"  [{a['key']}] {a['message']}")

    lines += [
        "",
        "Analyze these alerts in context of the current protocol state. "
        "Are any of these unexpected? Does any require operator action? "
        "Summarize your assessment concisely.",
    ]
    return "\n".join(lines)

def build_periodic_summary(snap: dict) -> str:
    """Build a periodic summary message for the brain (no alerts)."""
    ts = snap.get("collected_at", "unknown time")
    gic = snap.get("gic", {})
    pcc = snap.get("pcc", {})
    ait = snap.get("ait", {})
    chain = snap.get("chain", {})
    cal = snap.get("calibration") or {}
    tournament = snap.get("tournament", {})

    pct = round((gic.get("chain_length") or 0) /
                max(gic.get("grind_target") or 200, 1) * 100, 1)
    block = chain.get("block_number", "?")

    return (
        f"[WATCHER PERIODIC — {ts}] All clear — no threshold alerts. "
        f"GIC: {gic.get('chain_length')}/{gic.get('grind_target')} ({pct}%, intact={gic.get('chain_intact')}). "
        f"PCC: {pcc.get('capture_state')}/{pcc.get('host_state')}. "
        f"AIT: {ait.get('ratio')} (n={ait.get('n_sessions')}). "
        f"L4 anomaly threshold: {cal.get('anomaly_threshold')}. "
        f"Tournament gate: {tournament.get('overall_pass')}. "
        f"Block: {block:,} | Wallet: {chain.get('wallet_iotx')} IOTX. "
        f"Acknowledge this snapshot."
    )

# ── Formatting ────────────────────────────────────────────────────────────────

def format_snapshot(snap: dict) -> str:
    """Human-readable snapshot summary."""
    gic = snap.get("gic", {})
    pcc = snap.get("pcc", {})
    ait = snap.get("ait", {})
    chain = snap.get("chain", {})
    cal = snap.get("calibration") or {}
    tpf = snap.get("tournament", {})
    corp = snap.get("corpus", {})

    target = gic.get("grind_target") or 200
    length = gic.get("chain_length") or 0
    pct = round(length / max(target, 1) * 100, 1)
    bar = "#" * min(int(pct / 5), 20) + "." * (20 - min(int(pct / 5), 20))

    lines = [
        "=" * 58,
        f"  QORTROLLER PROTOCOL SNAPSHOT  {snap.get('collected_at','')[:19]}",
        "=" * 58,
        f"  GIC Chain   : {length}/{target} links  [{bar}] {pct}%",
        f"  Intact      : {'YES' if gic.get('chain_intact') else 'BROKEN'}",
        f"  Head        : {gic.get('latest_hash', '')}...",
        f"  Session     : {gic.get('session_id', '')}",
        "-" * 58,
        f"  PCC State   : {pcc.get('capture_state')} / {pcc.get('host_state')}",
        f"  Poll rate   : {pcc.get('poll_rate_hz', 0):.0f} Hz",
        f"  Grind ready : {pcc.get('grind_ready')}",
        f"  Consec clean: {pcc.get('consec_clean', 0)} / {pcc.get('grind_target', 200)}",
        "-" * 58,
        f"  AIT ratio   : {ait.get('ratio')} (n={ait.get('n_sessions')})",
        f"  All pairs>1 : {ait.get('all_pairs_gt1')}",
        f"  P1vP2/P1vP3/P2vP3: {ait.get('p1vp2')}/{ait.get('p1vp3')}/{ait.get('p2vp3')}",
        "-" * 58,
        f"  L4 anomaly  : {cal.get('anomaly_threshold')}  (baseline 7.009)",
        f"  L4 continu. : {cal.get('continuity_threshold')}  (baseline 5.367)",
        f"  Corpus recs : {cal.get('total_records')} | conf: {cal.get('confidence')}",
        "-" * 58,
        f"  Tournament  : overall_pass={tpf.get('overall_pass')} "
        f"sep={tpf.get('separation_ok')} l4={tpf.get('l4_ok')} "
        f"gate={tpf.get('gate_ok')} cert={tpf.get('cert_ok')}",
        f"  Corpus snap : n={corp.get('corpus_n')} on_chain={corp.get('on_chain')}",
        "-" * 58,
        f"  Wallet      : {chain.get('wallet_iotx')} IOTX",
        f"  IoTeX block : {chain.get('block_number', '?'):,}"
        if isinstance(chain.get("block_number"), int)
        else f"  IoTeX block : {chain.get('block_number', '?')}",
        "=" * 58,
    ]
    return "\n".join(lines)

# ── Main loop ─────────────────────────────────────────────────────────────────

def run_once(conn: sqlite3.Connection, verbose: bool = True) -> list[dict]:
    """Take one snapshot, diff, evaluate alerts. Return triggered alerts."""
    if verbose:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Collecting snapshot...", end=" ")
        sys.stdout.flush()

    snap = collect_snapshot()
    _save_snapshot(conn, snap)

    if verbose:
        print("done.")
        print(format_snapshot(snap))

    prev_snapshots = _get_last_snapshots(conn, 2)
    if len(prev_snapshots) < 2:
        if verbose:
            print("  (no previous snapshot to diff against)")
        return []

    curr_data = prev_snapshots[0]["data"]
    prev_data = prev_snapshots[1]["data"]
    alerts = diff_snapshots(prev_data, curr_data)

    if alerts:
        print(f"\n  [{len(alerts)} ALERT(S)]")
        for a in alerts:
            print(f"    [{a['key']}] {a['message']}")

        for a in alerts:
            _save_alert(conn, a["key"], a["message"], a.get("delta"))

        # Post to daemon brain
        msg = build_alert_message(alerts, snap)
        print("\n  Posting alert to daemon brain...", end=" ")
        posted = post_to_brain(msg)
        print("OK" if posted else "FAILED (daemon may be offline)")
    elif verbose:
        print("  No threshold alerts triggered.")

    return alerts

def run_loop(interval: int, verbose: bool = True):
    """Run the monitoring loop indefinitely."""
    conn = _init_db(DB_PATH)
    print("=" * 58)
    print("  QorTroller Protocol Watcher")
    print(f"  Interval   : {interval}s ({interval//60}m {interval%60}s)")
    print(f"  Bridge     : {BRIDGE_OPERATOR_URL}")
    print(f"  Daemon     : {DAEMON_URL}")
    print(f"  DB         : {DB_PATH}")
    print("=" * 58)
    print()

    # Run immediately on start
    alerts = run_once(conn, verbose=verbose)
    # Post a startup summary to the brain
    post_to_brain(
        "[WATCHER STARTED] Protocol watcher is now running. "
        f"Polling every {interval}s. I will alert you when thresholds are "
        "crossed. First snapshot collected — standing by."
    )

    cycle = 1
    while True:
        next_run = time.time() + interval
        while time.time() < next_run:
            remaining = int(next_run - time.time())
            print(f"\r  Next snapshot in {remaining:3d}s  (cycle {cycle})", end="")
            sys.stdout.flush()
            time.sleep(min(5, remaining))

        print()
        cycle += 1
        try:
            run_once(conn, verbose=verbose)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  [ERROR] Snapshot failed: {e}")

def show_status():
    """Print the last snapshot and alert history."""
    conn = _init_db(DB_PATH)
    snaps = _get_last_snapshots(conn, 1)
    if not snaps:
        print("No snapshots yet. Run: python protocol_watcher.py --once")
        return
    print(format_snapshot(snaps[0]["data"]))
    print(f"\nSnapshot taken: {snaps[0]['timestamp']}")

    alerts = conn.execute(
        "SELECT timestamp, alert_key, message FROM watcher_alerts "
        "ORDER BY id DESC LIMIT 10"
    ).fetchall()
    if alerts:
        print(f"\nLast {len(alerts)} alert(s):")
        for ts, key, msg in alerts:
            print(f"  [{ts[:19]}] [{key}] {msg}")
    else:
        print("\nNo alerts logged yet.")
    conn.close()

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QorTroller Protocol Watcher")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL,
                        help="Poll interval in seconds (default: 300)")
    parser.add_argument("--once", action="store_true",
                        help="Take one snapshot and exit")
    parser.add_argument("--status", action="store_true",
                        help="Print last snapshot and alerts, then exit")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress snapshot output (alerts still printed)")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.once:
        conn = _init_db(DB_PATH)
        run_once(conn, verbose=not args.quiet)
        conn.close()
        return

    try:
        run_loop(args.interval, verbose=not args.quiet)
    except KeyboardInterrupt:
        print("\n\nWatcher stopped.")

if __name__ == "__main__":
    main()
