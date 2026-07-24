"""First-class surprise-mode latency report (A2A-POEP-CORPUS-TOOLING T3).

Report-only. Does NOT freeze the reaction band or flip poep_enabled.

  python scripts/poep_latency_report.py --date 2026-07-16
  python scripts/poep_latency_report.py --db PATH --date 2026-07-16 --out audits/report.md

Prefer l6b_probe_log.player when stamped (T1). Legacy nights without player can pass
--cut UTC cut-points for handoff forensics only.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

try:
    from l9_presence.poep_live_verify import REACTION_BAND_MS
except Exception:  # noqa: BLE001
    REACTION_BAND_MS = (80.0, 450.0)

BAND_LO, BAND_HI = float(REACTION_BAND_MS[0]), float(REACTION_BAND_MS[1])
PEAK_FLOOR = 1000.0
MARGIN_MS = 15.0
TRAIN_FRAC = 0.70


def pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return round(s[0], 3)
    k = (len(s) - 1) * p
    lo = int(math.floor(k))
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 3)


def stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": round(statistics.mean(xs), 2),
        "stdev": round(statistics.stdev(xs), 2) if len(xs) > 1 else 0.0,
        "min": round(min(xs), 2),
        "p5": pct(xs, 0.05),
        "median": pct(xs, 0.50),
        "p95": pct(xs, 0.95),
        "max": round(max(xs), 2),
    }


def in_band(lat: float, peak: float, *, lo: float = BAND_LO, hi: float = BAND_HI,
            peak_floor: float = PEAK_FLOOR) -> bool:
    return lo <= lat <= hi and peak >= peak_floor


def held_out_split(ordered_lats: list[float], train_frac: float = TRAIN_FRAC
                   ) -> tuple[list[float], list[float]]:
    """Chronological verify-pass rows: first train_frac train, rest holdout."""
    n = len(ordered_lats)
    if n == 0:
        return [], []
    if n == 1:
        return list(ordered_lats), []
    n_train = max(1, int(math.floor(n * train_frac)))
    if n_train >= n:
        n_train = n - 1
    return ordered_lats[:n_train], ordered_lats[n_train:]


def draft_ceiling(p95_train: float, *, band_hi: float = BAND_HI,
                  margin_ms: float = MARGIN_MS) -> int:
    """min(band_hi, ceil(p95_train + margin)) — train-only, not a freeze."""
    return int(min(band_hi, math.ceil(float(p95_train) + margin_ms)))


def load_rows(db: Path, date: str, policy_ref: str) -> list[dict]:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    # player column may be absent on very old DBs — probe
    cols = {r[1] for r in conn.execute("PRAGMA table_info(l6b_probe_log)").fetchall()}
    has_player = "player" in cols
    sel = (
        "id, latency_ms, accel_delta_peak AS peak, classification, created_at, policy_ref"
        + (", player" if has_player else ", NULL AS player")
    )
    rows = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT {sel}
            FROM l6b_probe_log
            WHERE policy_ref = ?
              AND date(created_at) = ?
            ORDER BY id ASC
            """,
            (policy_ref, date),
        ).fetchall()
    ]
    conn.close()
    return rows


def group_by_player(
    rows: list[dict], cuts: list[datetime] | None
) -> tuple[dict[str, list[dict]], str]:
    """Prefer non-empty player column; else optional --cut; else UNLABELED.

    Returns (buckets, source) where source is column | cuts | unlabeled.
    """
    labeled = defaultdict(list)
    n_with = 0
    for r in rows:
        pl = (r.get("player") or "").strip()
        if pl:
            labeled[pl].append(r)
            n_with += 1
    if n_with > 0 and n_with >= max(1, len(rows) // 2):
        for r in rows:
            pl = (r.get("player") or "").strip()
            if not pl:
                labeled["UNLABELED"].append(r)
        return dict(labeled), "column"

    if cuts:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            t = datetime.fromisoformat(r["created_at"])
            idx = 0
            for c in cuts:
                if t >= c:
                    idx += 1
                else:
                    break
            buckets[f"P{idx + 1}"].append(r)
        return dict(buckets), "cuts"

    return {"UNLABELED": list(rows)}, "unlabeled"


def build_report(
    rows: list[dict],
    *,
    date: str,
    policy_ref: str,
    cuts: list[datetime] | None = None,
) -> tuple[dict, str]:
    by_player, player_source = group_by_player(rows, cuts)

    report: dict = {
        "schema": "qortroller-poep-surprise-latency-report-v0",
        "date": date,
        "policy_ref": policy_ref,
        "band_ms": [BAND_LO, BAND_HI],
        "peak_floor_lsb": PEAK_FLOOR,
        "held_out_rule": f"per-player chronological verify-pass: train={TRAIN_FRAC:.0%}, holdout rest",
        "ceiling_draft_rule": f"min({BAND_HI}, ceil(p95_train+{MARGIN_MS}))",
        "poep_enabled": False,
        "band_frozen": False,
        "player_source": player_source,
        "n_rows": len(rows),
        "players": {},
        "pooled": {},
        "held_out": {},
    }

    all_verify: list[float] = []
    all_train: list[float] = []
    hold_lats: list[float] = []

    lines = [
        f"# PoEP surprise latency report — {date}",
        "",
        f"**Report-only.** `poep_enabled=False`. Band **not frozen**. "
        f"Band source: `REACTION_BAND_MS={BAND_LO}/{BAND_HI}`.",
        "",
        f"- rows: **{len(rows)}** · policy `{policy_ref}` · player_source: **{player_source}**",
        "",
        "## Per-player (verify-pass proxy)",
        "",
        "| player | n_all | n_verify | mean | median | p5 | p95 | min | max |",
        "|--------|------:|---------:|-----:|-------:|---:|----:|----:|----:|",
    ]
    if player_source == "unlabeled":
        lines.insert(
            6,
            "- **WARNING: UNLABELED** — pass `--cut` for legacy handoffs or re-capture with `--player`.",
        )

    for pl in sorted(by_player.keys()):
        rs = by_player[pl]
        ordered = []
        for r in sorted(rs, key=lambda x: x["id"]):
            lat = float(r["latency_ms"] or 0)
            peak = float(r["peak"] or 0)
            if in_band(lat, peak):
                ordered.append(lat)
        st = stats(ordered)
        all_verify.extend(ordered)
        train, hold = held_out_split(ordered)
        all_train.extend(train)
        hold_lats.extend(hold)
        report["players"][pl] = {
            "n_all": len(rs),
            "n_verify": len(ordered),
            "latency": st,
            "held_out": {"n_train": len(train), "n_holdout": len(hold),
                         "train": stats(train), "holdout": stats(hold)},
        }
        lines.append(
            f"| {pl} | {len(rs)} | {st.get('n', 0)} | {st.get('mean', '—')} | "
            f"{st.get('median', '—')} | {st.get('p5', '—')} | {st.get('p95', '—')} | "
            f"{st.get('min', '—')} | {st.get('max', '—')} |"
        )

    st_all = stats(all_verify)
    report["pooled"] = {"n_verify": st_all.get("n", 0), "latency": st_all}
    st_train = stats(all_train)
    p95 = float(st_train.get("p95") or 0.0)
    draft = draft_ceiling(p95) if st_train.get("n", 0) else int(BAND_HI)
    report["held_out"] = {
        "train": st_train,
        "holdout": stats(hold_lats),
        "p95_train": p95,
        "ceiling_draft_ms": draft,
        "margin_ms": MARGIN_MS,
    }

    lines += [
        "",
        "## Pooled verify-pass",
        "",
        f"- **N = {st_all.get('n', 0)}** · mean **{st_all.get('mean')}** · median **{st_all.get('median')}** · "
        f"p5 **{st_all.get('p5')}** · p95 **{st_all.get('p95')}**",
        "",
        "## Held-out (train-only draft ceiling)",
        "",
        f"- train N **{st_train.get('n', 0)}** p95 **{st_train.get('p95')}** → draft hi **{draft} ms**",
        f"- holdout N **{len(hold_lats)}** (FRR@current band = 0 by construction on verify-pass holdout)",
        "",
        "## Verdict",
        "",
        "1. Report-only — does **not** authorize `poep_enabled=True` or freeze the band.",
        "2. Prefer captures with `player` stamped (T1) for multi-op tables.",
        "3. Next rig night: multi-day corpus + catch trials + adversarial FAR before any flip.",
        "",
    ]
    return report, "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(Path.home() / ".vapi" / "bridge.db"))
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (created_at date in DB)")
    ap.add_argument("--policy-ref", default="edge_operator_reflex_v1")
    ap.add_argument("--out", default=None, help="markdown path (json written alongside)")
    ap.add_argument(
        "--cut",
        action="append",
        default=[],
        help="Legacy handoff UTC datetime ISO (repeatable), e.g. 2026-07-16T22:38:00",
    )
    args = ap.parse_args()

    db = Path(args.db)
    if not db.is_file():
        print(f"ERROR: DB not found: {db}", file=sys.stderr)
        return 1

    cuts = [datetime.fromisoformat(c) for c in args.cut] if args.cut else None
    # Special-case known 2026-07-16 pilot if unlabeled and no cuts
    rows = load_rows(db, args.date, args.policy_ref)
    if not cuts and args.date == "2026-07-16":
        # only apply default cuts if player column empty on majority
        n_lab = sum(1 for r in rows if (r.get("player") or "").strip())
        if n_lab < max(1, len(rows) // 2):
            cuts = [
                datetime.fromisoformat("2026-07-16 22:38:00"),
                datetime.fromisoformat("2026-07-16 22:51:00"),
            ]
            # also restrict to evening pilot for that night's multi-op tables
            evening = datetime.fromisoformat("2026-07-16 21:00:00")
            rows = [r for r in rows if datetime.fromisoformat(r["created_at"]) >= evening]

    report, md = build_report(rows, date=args.date, policy_ref=args.policy_ref, cuts=cuts)
    out = Path(args.out) if args.out else (
        REPO / "audits" / f"poep-surprise-latency-report-{args.date}.md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(md)
    print(f"Wrote {out}")
    print(f"Wrote {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
