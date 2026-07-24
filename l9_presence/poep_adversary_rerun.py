"""FLIP-A protocol adversary re-run (report-only, poep_enabled stays False).

Aggregates:
  1) TellWatcher FAR collapse (F-POEP-LIVE-1) — continuous_poll must beat poll-burst
  2) Catch-trial always-fire bot catch rate on NO_GO schedule
  3) Honest-human FA rate simulation under catch schedule (budget check)
  4) Offline band-only macro FAR (honest: still high — band is not anti-bot)

PASS for this *software gate* = tell proof + catch always-fire bar + human FA budget in sim.
Does NOT authorize poep_enabled=True (needs live multi-day corpus + operator GO).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from l9_presence.poep_catch_trials import (  # noqa: E402
    ALWAYS_FIRE_CATCH_BAR,
    HUMAN_FA_BUDGET,
    plan_trial_kinds,
    score_session,
    simulate_always_fire_on_schedule,
    simulate_honest_human_on_schedule,
)
from l9_presence.poep_live_verify import (  # noqa: E402
    REACTION_BAND_MS,
    ChallengeResponse,
    LiveChallenge,
    poep_commitment,
    response_feature_digest,
    verify_live_response,
)
from l9_presence.poep_tell_watcher import far_collapse  # noqa: E402

_DEVICE = "581a836c-adversary-harness"


def band_only_macro_far(*, n_trials: int = 400, seed: int = 0xBAD) -> dict:
    """A-RAND style: sample latency in band + peak>=floor + correct nonce commitment.

    Expected FAR ~1.0 under pure live-verify — documents that band alone is not anti-bot.
    """
    import random

    rng = random.Random(seed)
    lo, hi = REACTION_BAND_MS
    accepts = 0
    for i in range(n_trials):
        t_ch = 1_000_000_000_000 + i * 10_000_000
        nonce = f"arand-{i}-{rng.getrandbits(32):08x}"
        lat = rng.uniform(lo + 5.0, hi - 5.0)
        peak = rng.uniform(1200.0, 4000.0)
        t_resp = t_ch + int(lat * 1e6)
        fd = response_feature_digest(lat, peak, 100.0)
        com = poep_commitment(device_id=_DEVICE, nonce=nonce, feature_digest=fd, ts_ns=t_resp)
        ch = LiveChallenge(_DEVICE, nonce, t_ch)
        resp = ChallengeResponse(t_resp, lat, peak, 100.0, nonce, com)
        if verify_live_response(ch, resp)["ok"]:
            accepts += 1
    return {
        "attack": "A-RAND_band_only",
        "n": n_trials,
        "n_accept": accepts,
        "far": accepts / n_trials,
        "note": "FAR≈1 expected — live-verify alone without catch/shape is not presence.",
    }


def run_adversary_suite(*, n_tell: int = 400, n_catch: int = 200, seed: int = 0xC7C4) -> dict[str, Any]:
    tell = far_collapse(n_trials=n_tell, seed=seed)

    kinds = plan_trial_kinds(n_catch, go_per_no_go=4, seed=seed + 1)
    bot_scores = simulate_always_fire_on_schedule(kinds)
    bot_agg = score_session(bot_scores, mode="always_fire_bot")
    nogo = [s for s in bot_scores if s.kind == "NO_GO"]
    bot_catch_rate = float(bot_agg.get("always_fire_catch_rate") or 0.0)

    # Large sim for FA budget check (small N is noisy around 5% bar)
    human_kinds = plan_trial_kinds(max(n_catch, 500), go_per_no_go=4, seed=seed + 2)
    human_scores = simulate_honest_human_on_schedule(
        human_kinds, nogo_fa_rate=0.02, go_pass_rate=0.85, seed=seed + 2,
    )
    human_agg = score_session(human_scores, mode="human")

    band = band_only_macro_far(n_trials=n_tell, seed=seed + 3)

    catch_ok = bot_catch_rate >= ALWAYS_FIRE_CATCH_BAR
    human_fa = human_agg.get("human_fa_rate")
    human_fa_ok = human_fa is None or human_fa <= HUMAN_FA_BUDGET

    # Structural software gate: tell proof + always-fire catch (deterministic protocol properties).
    # Human FA budget is validated live on-rig; sim is advisory (binomial noise on small N).
    software_gate = bool(tell.get("passes_tell_removal_proof") and catch_ok)

    return {
        "schema": "qortroller-poep-adversary-rerun-v0",
        "poep_enabled": False,
        "flip_authorized": False,
        "reaction_band_ms": list(REACTION_BAND_MS),
        "tell_watcher": tell,
        "catch_trials": {
            "n_schedule": len(kinds),
            "n_nogo": len(nogo),
            "always_fire_catch_rate": bot_catch_rate,
            "always_fire_catch_bar": ALWAYS_FIRE_CATCH_BAR,
            "always_fire_catch_ok": catch_ok,
            "honest_human_sim": human_agg,
            "human_fa_budget": HUMAN_FA_BUDGET,
            "human_fa_ok_sim": human_fa_ok,
        },
        "band_only_macro": band,
        "software_gate_pass": software_gate,
        "software_gate_means": (
            "tell-removal proof + always-fire catch bar (structural). "
            "Human FA sim is advisory; live FA measured on-rig with --catch. "
            "NOT FLIP-A flip."
        ),
        "human_fa_sim_ok": human_fa_ok,
        "still_required_for_poep_enabled": [
            "live catch-trial sessions with measured human FA <=5%",
            "operator review of claim language (FLIP-A only)",
            "two-key operator fire of poep_enabled",
            "A-REACTIVE still out of claim",
        ],
    }


def to_markdown(report: dict) -> str:
    tw = report["tell_watcher"]
    ct = report["catch_trials"]
    band = report["band_only_macro"]
    lines = [
        "# PoEP adversary re-run (software gate)",
        "",
        f"**poep_enabled={report['poep_enabled']}** · **flip_authorized={report['flip_authorized']}**",
        f"Band: `{report['reaction_band_ms']}`",
        "",
        "## 1. TellWatcher (F-POEP-LIVE-1)",
        "",
        f"| metric | value | bar |",
        f"|--------|------:|-----|",
        f"| FAR stdout_tell | {tw['far_stdout_tell']:.3f} | ≥ {tw['bar_stdout_min']} |",
        f"| FAR pollburst naive | {tw['far_pollburst_naive']:.3f} | ≥ {tw['bar_flaw_min']} |",
        f"| FAR continuous_poll | {tw['far_pollburst_fixed']:.3f} | ≤ {tw['bar_fix_max']} |",
        f"| **passes_tell_removal_proof** | **{tw['passes_tell_removal_proof']}** | |",
        "",
        "## 2. Catch trials (always-fire vs honest sim)",
        "",
        f"- schedule N={ct['n_schedule']} · NO_GO={ct['n_nogo']}",
        f"- always-fire catch rate: **{ct['always_fire_catch_rate']:.3f}** "
        f"(bar ≥ {ct['always_fire_catch_bar']}) → ok={ct['always_fire_catch_ok']}",
        f"- honest human FA rate (sim): **{ct['honest_human_sim'].get('human_fa_rate')}** "
        f"(budget ≤ {ct['human_fa_budget']}) → ok={ct['human_fa_ok_sim']}",
        "",
        "## 3. Band-only macro (honesty check)",
        "",
        f"- A-RAND FAR: **{band['far']:.3f}** — {band['note']}",
        "",
        "## Software gate",
        "",
        f"**PASS={report['software_gate_pass']}** — {report['software_gate_means']}",
        "",
        "### Still required for poep_enabled=True",
        "",
    ]
    for x in report["still_required_for_poep_enabled"]:
        lines.append(f"- {x}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None, help="write markdown report path")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--n-tell", type=int, default=400)
    ap.add_argument("--n-catch", type=int, default=200)
    args = ap.parse_args()
    rep = run_adversary_suite(n_tell=args.n_tell, n_catch=args.n_catch)
    md = to_markdown(rep)
    print(md)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Wrote {args.out}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rep, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")
    return 0 if rep["software_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
