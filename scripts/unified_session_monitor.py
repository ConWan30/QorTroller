"""
unified_session_monitor.py — Read-only GIC + L6B synchronicity dashboard.

Polls bridge.db every N seconds and shows both counters advancing from the same
bridge play session. No bridge writes; no session-loop changes.

USAGE
-----
  python scripts/unified_session_monitor.py --player P1 --game "NCAA Football 26"
  python scripts/unified_session_monitor.py --interval 5 --grind-session-id grind_phase235_v1
  python scripts/unified_session_monitor.py --once   # single snapshot (smoke / CI)
"""

from __future__ import annotations

import argparse
import datetime
import signal
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.config import Config

L6B_TARGET_DEFAULT = 50
GIC_MILESTONE_100 = 100
POLL_INTERVAL_S = 5.0
DB_BUSY_TIMEOUT_MS = 5000
LOCK_RETRY_S = 1.0


@dataclass(frozen=True)
class GicSnapshot:
    grind_session_id: str
    chain_length: int
    latest_gic_hash: str
    latest_gic_ts_ns: int | None
    global_chain_length: int


@dataclass(frozen=True)
class L6bSnapshot:
    probe_count: int
    reflex_verdict_distribution: dict[str, int]
    classification_distribution: dict[str, int]
    latest_probe: dict | None
    target_n: int = L6B_TARGET_DEFAULT

    @property
    def gate_reached(self) -> bool:
        return self.probe_count >= self.target_n


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    """Open bridge.db for read-only polling with WAL-friendly busy timeout."""
    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
    return conn


def _query_with_retry(fn, *, retries: int = 3, delay_s: float = LOCK_RETRY_S):
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            last_exc = exc
            if attempt + 1 < retries:
                time.sleep(delay_s)
    assert last_exc is not None
    raise last_exc


def fetch_gic_snapshot(conn: sqlite3.Connection, grind_session_id: str) -> GicSnapshot:
    def _run() -> GicSnapshot:
        global_n = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM ruling_validation_log "
                "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != ''",
            ).fetchone()["n"],
        )
        if grind_session_id:
            scoped_n = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM ruling_validation_log "
                    "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                    "AND grind_session_id = ?",
                    (grind_session_id,),
                ).fetchone()["n"],
            )
            latest = conn.execute(
                "SELECT grind_chain_hash, gic_ts_ns FROM ruling_validation_log "
                "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                "AND grind_session_id = ? "
                "ORDER BY gic_ts_ns DESC LIMIT 1",
                (grind_session_id,),
            ).fetchone()
        else:
            scoped_n = global_n
            latest = conn.execute(
                "SELECT grind_chain_hash, gic_ts_ns FROM ruling_validation_log "
                "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                "ORDER BY gic_ts_ns DESC LIMIT 1",
            ).fetchone()
        latest_hash = (latest["grind_chain_hash"] if latest else "") or ""
        latest_ts = int(latest["gic_ts_ns"]) if latest and latest["gic_ts_ns"] is not None else None
        return GicSnapshot(
            grind_session_id=grind_session_id,
            chain_length=scoped_n,
            latest_gic_hash=latest_hash,
            latest_gic_ts_ns=latest_ts,
            global_chain_length=global_n,
        )

    return _query_with_retry(_run)


def fetch_l6b_snapshot(
    conn: sqlite3.Connection,
    *,
    device_id: str | None = None,
    target_n: int = L6B_TARGET_DEFAULT,
) -> L6bSnapshot:
    def _run() -> L6bSnapshot:
        _where = "WHERE device_id = ?" if device_id else ""
        _params: tuple = (device_id,) if device_id else ()
        probe_count = int(
            conn.execute(
                f"SELECT COUNT(*) AS n FROM l6b_probe_log {_where}",
                _params,
            ).fetchone()["n"],
        )
        reflex_rows = conn.execute(
            f"SELECT reflex_verdict, COUNT(*) AS n FROM l6b_probe_log {_where} "
            "GROUP BY reflex_verdict",
            _params,
        ).fetchall()
        class_rows = conn.execute(
            f"SELECT classification, COUNT(*) AS n FROM l6b_probe_log {_where} "
            "GROUP BY classification",
            _params,
        ).fetchall()
        latest = conn.execute(
            f"SELECT device_id, probe_ts_ms, classification, reflex_verdict, latency_ms "
            f"FROM l6b_probe_log {_where} ORDER BY id DESC LIMIT 1",
            _params,
        ).fetchone()
        reflex_dist: dict[str, int] = {}
        for row in reflex_rows:
            key = row["reflex_verdict"] if row["reflex_verdict"] is not None else "(null)"
            reflex_dist[key] = int(row["n"])
        class_dist: dict[str, int] = {}
        for row in class_rows:
            class_dist[str(row["classification"])] = int(row["n"])
        latest_dict = dict(latest) if latest else None
        return L6bSnapshot(
            probe_count=probe_count,
            reflex_verdict_distribution=reflex_dist,
            classification_distribution=class_dist,
            latest_probe=latest_dict,
            target_n=target_n,
        )

    return _query_with_retry(_run)


def fetch_session_deltas(
    conn: sqlite3.Connection,
    *,
    grind_session_id: str,
    gic_baseline: int,
    l6b_baseline: int,
    monitor_start_wall_ms: int,
    device_id: str | None = None,
) -> dict[str, int]:
    """Rows added since monitor start (count + classification buckets)."""

    def _run() -> dict[str, int]:
        if grind_session_id:
            gic_delta = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM ruling_validation_log "
                    "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                    "AND grind_session_id = ? AND gic_ts_ns >= ?",
                    (grind_session_id, monitor_start_wall_ms * 1_000_000),
                ).fetchone()["n"],
            )
        else:
            gic_delta = int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM ruling_validation_log "
                    "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != '' "
                    "AND gic_ts_ns >= ?",
                    (monitor_start_wall_ms * 1_000_000,),
                ).fetchone()["n"],
            )
        _l6b_where = "WHERE probe_ts_ms >= ?"
        _l6b_params: list = [monitor_start_wall_ms]
        if device_id:
            _l6b_where += " AND device_id = ?"
            _l6b_params.append(device_id)
        l6b_delta = int(
            conn.execute(
                f"SELECT COUNT(*) AS n FROM l6b_probe_log {_l6b_where}",
                tuple(_l6b_params),
            ).fetchone()["n"],
        )
        # Fallback if wall-clock skew: use count delta from baselines
        gic_now = fetch_gic_snapshot(conn, grind_session_id).chain_length
        l6b_now = fetch_l6b_snapshot(conn, device_id=device_id).probe_count
        gic_delta = max(gic_delta, max(0, gic_now - gic_baseline))
        l6b_delta = max(l6b_delta, max(0, l6b_now - l6b_baseline))

        human = inconclusive = reflex_observed = 0
        rows = conn.execute(
            f"SELECT classification, reflex_verdict FROM l6b_probe_log {_l6b_where}",
            tuple(_l6b_params),
        ).fetchall()
        for row in rows:
            if row["classification"] == "HUMAN":
                human += 1
            elif row["classification"] == "INCONCLUSIVE":
                inconclusive += 1
            if row["reflex_verdict"] == "REFLEX_OBSERVED":
                reflex_observed += 1
        return {
            "gic_delta": gic_delta,
            "l6b_delta": l6b_delta,
            "human": human,
            "inconclusive": inconclusive,
            "reflex_observed": reflex_observed,
        }

    return _query_with_retry(_run)


def _format_ts_ns(ts_ns: int | None) -> str:
    if ts_ns is None:
        return "-"
    try:
        dt = datetime.datetime.fromtimestamp(ts_ns / 1e9)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(ts_ns)


def _format_probe_ts_ms(ts_ms: int | None) -> str:
    if ts_ms is None:
        return "-"
    try:
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000.0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(ts_ms)


def render_dashboard(
    *,
    player: str,
    game: str,
    gic: GicSnapshot,
    l6b: L6bSnapshot,
    session_deltas: dict[str, int],
) -> str:
    gic_target_line = (
        "GIC_100 met; ongoing"
        if gic.chain_length >= GIC_MILESTONE_100
        else f"milestone {GIC_MILESTONE_100}"
    )
    latest_probe = l6b.latest_probe or {}
    probe_ts = _format_probe_ts_ms(latest_probe.get("probe_ts_ms"))
    probe_verdict = latest_probe.get("reflex_verdict") or latest_probe.get("classification") or "-"
    probe_lat = latest_probe.get("latency_ms")
    probe_lat_s = f"{probe_lat:.1f}" if probe_lat is not None else "-"
    gic_head = (gic.latest_gic_hash[:8] if gic.latest_gic_hash else "-")
    gic_ts = _format_ts_ns(gic.latest_gic_ts_ns)
    sid = gic.grind_session_id or "(all sessions)"
    lines = [
        "+- QorTroller Session Monitor --------------------------------+",
        f"| Player: {player:<12} Game: {game:<28}|",
        f"| GIC session: {sid:<42}|",
        f"| GIC Chain     N = {gic.chain_length:<6} ({gic_target_line})              |",
        f"| L6B Corpus    N = {l6b.probe_count:<3} / {l6b.target_n:<3}                         |",
        "|                                                             |",
        "| This session:                                               |",
        f"|   GIC entries:  +{session_deltas['gic_delta']:<4}                                      |",
        f"|   L6B probes:   +{session_deltas['l6b_delta']:<4}                                      |",
        f"|   HUMAN:        {session_deltas['human']:<4}  INCONCLUSIVE: {session_deltas['inconclusive']:<4}          |",
        f"|   REFLEX_OBSERVED: {session_deltas['reflex_observed']:<4}                                   |",
        "|                                                             |",
        f"| Last probe:  {probe_ts} {probe_verdict} {probe_lat_s} ms",
        f"| Last GIC:    {gic_ts} head={gic_head}...",
        "+-------------------------------------------------------------+",
    ]
    return "\n".join(lines)


def print_operator_gate_checklist() -> None:
    print()
    print("=" * 60)
    print("  CCO PHASE B — OPERATOR GATE (before L6B_ENABLED=true in prod)")
    print("  Source: wiki/methodology/CCO_PHASE_B_DESIGN_v1.md section 5")
    print("=" * 60)
    print()
    print("  [ ] 1. Phase B implementation merged; tests pass with L6B_ENABLED=false.")
    print("  [ ] 2. Operator attests N>=50 L6B calibration probes in l6b_probe_log.")
    print("  [ ] 3. DualSense-class hardware validated (IMU + adaptive trigger path).")
    print("  [ ] 4. poep_enabled remains false; REFLEX_OBSERVED does not imply")
    print("         tournament eligibility.")
    print()
    print("  Do NOT flip production L6B_ENABLED until all boxes are operator-signed.")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--player", "-p", default="P1", help="Player label (display only)")
    parser.add_argument("--game", "-g", default="NCAA Football 26", help="Game title (display only)")
    parser.add_argument("--target", "-t", type=int, default=L6B_TARGET_DEFAULT, help="L6B gate N")
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL_S, help="Poll interval seconds")
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    parser.add_argument("--device-id", default=None, help="Filter L6B rows to one device")
    parser.add_argument("--grind-session-id", default=None, help="GIC session scope (default: Config)")
    parser.add_argument("--no-prompt", action="store_true", help="Skip ENTER prompt")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    args = parser.parse_args()

    cfg = Config()
    db_path = Path(args.db or cfg.db_path)
    grind_sid = args.grind_session_id if args.grind_session_id is not None else cfg.grind_session_id

    if not db_path.exists():
        print(f"ERROR: bridge DB not found: {db_path}")
        return 1

    print("QorTroller Unified Session Monitor (read-only)")
    print(f"DB: {db_path}")
    print(f"GIC scope: {grind_sid or '(all stamped links)'}")
    print()

    conn = connect_readonly(db_path)
    try:
        gic0 = fetch_gic_snapshot(conn, grind_sid)
        l6b0 = fetch_l6b_snapshot(conn, device_id=args.device_id, target_n=args.target)
        if gic0.chain_length == 0 and gic0.global_chain_length > 0 and grind_sid:
            print(
                f"  WARN F-SYNC-003: GIC scope '{grind_sid}' has 0 links but DB has "
                f"{gic0.global_chain_length} global stamped links. "
                "Set GRIND_SESSION_ID in bridge/.env to match the active grind."
            )
            print()

        monitor_start_ms = int(time.time() * 1000)
        gic_baseline = gic0.chain_length
        l6b_baseline = l6b0.probe_count

        if args.once:
            deltas = fetch_session_deltas(
                conn,
                grind_session_id=grind_sid,
                gic_baseline=gic_baseline,
                l6b_baseline=l6b_baseline,
                monitor_start_wall_ms=monitor_start_ms,
                device_id=args.device_id,
            )
            print(
                render_dashboard(
                    player=args.player,
                    game=args.game,
                    gic=gic0,
                    l6b=l6b0,
                    session_deltas=deltas,
                )
            )
            return 2 if l6b0.gate_reached else 0

        if not args.no_prompt:
            input("Press ENTER to start live monitoring (Ctrl-C to end)...")

        done = False

        def _handle_sigint(_sig, _frame):
            nonlocal done
            done = True

        signal.signal(signal.SIGINT, _handle_sigint)

        while not done:
            gic = fetch_gic_snapshot(conn, grind_sid)
            l6b = fetch_l6b_snapshot(conn, device_id=args.device_id, target_n=args.target)
            deltas = fetch_session_deltas(
                conn,
                grind_session_id=grind_sid,
                gic_baseline=gic_baseline,
                l6b_baseline=l6b_baseline,
                monitor_start_wall_ms=monitor_start_ms,
                device_id=args.device_id,
            )
            print("\033[2J\033[H", end="")  # clear screen
            print(
                render_dashboard(
                    player=args.player,
                    game=args.game,
                    gic=gic,
                    l6b=l6b,
                    session_deltas=deltas,
                )
            )
            print(f"\n  Poll every {args.interval:.0f}s — Ctrl-C to stop.")
            if l6b.gate_reached:
                print()
                print(f"  L6B TARGET REACHED: N={l6b.probe_count} >= {args.target}")
                print_operator_gate_checklist()
                return 0
            time.sleep(args.interval)
    finally:
        conn.close()

    print("\nMonitor stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
