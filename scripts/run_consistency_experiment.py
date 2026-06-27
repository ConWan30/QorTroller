"""Run the L9 x Trio-Retina consistency experiment (section-5) on synthetic data.

RESEARCH / provisional. Generates labeled sessions across the 5 classes, runs the
fusion engine, and writes a dated audit artifact (markdown + json) with the 5x6
confusion matrix, headline metrics, and the contextual-lift comparison.

    python scripts/run_consistency_experiment.py --synthetic --seed 0 --n-per-class 50

Sensitivity sweep on the load-bearing unknown (retina false-positive on elite play):

    python scripts/run_consistency_experiment.py --retina-fpr-proskill 0.30
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from l9_presence.adversarial.consistency_eval import run_experiment, to_markdown  # noqa: E402
from l9_presence.adversarial.real_sessions import (  # noqa: E402
    load_labeled_sessions_from_db,
    load_labels_from_json,
)
from l9_presence.adversarial.synthetic_sessions import (  # noqa: E402
    SynthParams,
    generate_labeled_sessions,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="L9 x Retina consistency experiment")
    ap.add_argument("--synthetic", action="store_true", default=True,
                    help="synthetic mode (Phase 1 default)")
    ap.add_argument("--real", action="store_true", default=False,
                    help="Phase 2 real-capture mode (requires --db + --sessions)")
    ap.add_argument("--db", default=None, help="bridge sqlite DB path (real mode)")
    ap.add_argument("--sessions", default=None, help="labels manifest JSON (real mode)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-per-class", type=int, default=50)
    ap.add_argument("--windows", type=int, default=8)
    ap.add_argument("--retina-tpr-cheat", type=float, default=0.85)
    ap.add_argument("--retina-fpr-proskill", type=float, default=0.15)
    ap.add_argument("--out-dir", default=str(_ROOT / "audits"))
    args = ap.parse_args()

    date = _dt.date.today().isoformat()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.real:
        if not args.db or not args.sessions:
            ap.error("--real requires --db <sqlite> and --sessions <labels.json>")
        labels = load_labels_from_json(args.sessions)
        sessions = load_labeled_sessions_from_db(args.db, labels)
        result = run_experiment(sessions, params=None, provenance="real")
        result["capture"] = {"mode": "real", "db": args.db, "sessions": args.sessions,
                             "single_subject": True, "n_session_labels": len(labels)}
        md_path = out_dir / f"consistency-experiment-real-{date}.md"
        json_path = out_dir / f"consistency-experiment-real-{date}.json"
        md_path.write_text(to_markdown(result, date), encoding="utf-8")
        json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        m = result["metrics"]
        print(f"[consistency-experiment] REAL machine_assist_catch = {m['machine_assist_catch_rate']}")
        print(f"[consistency-experiment] REAL false_accusation     = {m['false_accusation_rate']}")
        print(f"[consistency-experiment] wrote {md_path}")
        print("[consistency-experiment] N=1 single-subject: can KILL, cannot PASS (see protocol §0).")
        return 0

    params = SynthParams(
        retina_tpr_cheat=args.retina_tpr_cheat,
        retina_fpr_proskill=args.retina_fpr_proskill,
    )
    sessions = generate_labeled_sessions(
        seed=args.seed, n_per_class=args.n_per_class,
        windows_per_session=args.windows, params=params,
    )
    result = run_experiment(sessions, params)
    result["seed"] = args.seed
    result["n_per_class"] = args.n_per_class
    result["windows_per_session"] = args.windows

    md_path = out_dir / f"consistency-experiment-synthetic-{date}.md"
    json_path = out_dir / f"consistency-experiment-synthetic-{date}.json"
    md_path.write_text(to_markdown(result, date), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    m = result["metrics"]
    print(f"[consistency-experiment] machine_assist_catch_rate = {m['machine_assist_catch_rate']}")
    print(f"[consistency-experiment] false_accusation_rate     = {m['false_accusation_rate']}")
    print(f"[consistency-experiment] wrote {md_path}")
    print(f"[consistency-experiment] wrote {json_path}")
    print("[consistency-experiment] PROVISIONAL synthetic read — real PRO_SKILL capture is Phase 2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
