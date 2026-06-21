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
from l9_presence.adversarial.synthetic_sessions import (  # noqa: E402
    SynthParams,
    generate_labeled_sessions,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="L9 x Retina consistency experiment (synthetic)")
    ap.add_argument("--synthetic", action="store_true", default=True,
                    help="synthetic mode (the only mode in Phase 1; real capture is Phase 2)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-per-class", type=int, default=50)
    ap.add_argument("--windows", type=int, default=8)
    ap.add_argument("--retina-tpr-aimassist", type=float, default=0.85)
    ap.add_argument("--retina-fpr-proskill", type=float, default=0.15)
    ap.add_argument("--out-dir", default=str(_ROOT / "audits"))
    args = ap.parse_args()

    params = SynthParams(
        retina_tpr_aimassist=args.retina_tpr_aimassist,
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

    date = _dt.date.today().isoformat()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
