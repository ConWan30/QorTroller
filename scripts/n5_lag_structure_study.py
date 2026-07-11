#!/usr/bin/env python3
"""LUMEN-3 / N5 increment-1 study runner -- lag-structure coherence on real corpora.

Classes (fixed before running):
  GENUINE   : M13 (HDMI) + M14 (Remote Play) session window jsonls -- real matches,
              real input causing real screen effects (426 windows, 3 channels)
  DECOUPLED : a1spectate session windows -- operator spectating: screen active, stick
              moving, NO causation (213 windows, same channels/instrument)

Applies the PRE-REGISTERED bar in l9_presence/predictive_coupling.py (stated before any
class statistic was computed). Honest on both outcomes.

Usage: python scripts/n5_lag_structure_study.py
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.predictive_coupling import assess_separation  # noqa: E402

_GENUINE = ["match13_hdmi_direct_1783385280.jsonl", "match14_rp_option_b_1783475385.jsonl"]
_DECOUPLED = ["a1spectate_1783118822.jsonl"]


def _load_windows(paths) -> list:
    out = []
    for p in paths:
        fp = os.path.join(_REPO, p)
        if not os.path.isfile(fp):
            print(f"  MISSING: {p}", file=sys.stderr)
            continue
        for line in open(fp, encoding="utf-8"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            for w in (d if isinstance(d, list) else [d]):
                if isinstance(w, dict) and "channel" in w:
                    out.append(w)
    return out


def main() -> int:
    genuine = _load_windows(_GENUINE)
    decoupled = _load_windows(_DECOUPLED)
    print(f"genuine windows: {len(genuine)} ({'+'.join(_GENUINE)})")
    print(f"decoupled windows: {len(decoupled)} ({'+'.join(_DECOUPLED)})\n")

    result = assess_separation(genuine, decoupled)
    for ch in result["channels"]:
        g, d = ch["genuine"], ch["decoupled"]
        print(f"  {ch['channel']:<12} separates={ch['separates']}  ({ch['note']})")
        print(f"     genuine  : n_inf={g['n_informative']:<4} median={g['median_lag_ms']} "
              f"consistency={g['consistency']} -> {g['verdict']}")
        print(f"     decoupled: n_inf={d['n_informative']:<4} median={d['median_lag_ms']} "
              f"consistency={d['consistency']} -> {d['verdict']}")

    print(f"\n  PRE-REGISTERED BAR: {result['pre_registered_bar']}")
    print(f"  RESULT: separates_any = {result['separates_any']}")

    out = os.path.join(_REPO, "audits", "n5_lag_structure_result.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"classes": {"genuine": _GENUINE, "decoupled": _DECOUPLED,
                               "n_genuine": len(genuine), "n_decoupled": len(decoupled)},
                   **result}, fh, indent=2)
    print(f"  written -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
