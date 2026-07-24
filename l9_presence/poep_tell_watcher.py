"""TellWatcher FAR harness for F-POEP-LIVE-1 (grok round-18 design + round-19 correction).

Round-18 shipped a naive model (stdout tell vs a blind uniform-delay guesser) that measured FAR 0.02 and
OVERSTATED the close. Round-19 caught the real residual: the first "silent" fire (sleep -> then a dense
pre-collection burst -> fire) still leaks a PRE-FIRE tell via USB poll cadence -- a `PollBurstWatcher`
that arms on the silence->burst transition gets FAR ~0.56, not chance. This harness models that bot
honestly and proves the ACTUAL fix (silent CONTINUOUS-poll fire: uniform cadence from arm to fire, no
burst transition) is what collapses it.

Three capture paths and the strongest modeled host-side macro against each:
  - stdout_tell      : the old `_fire_probe_sync` prints "Baseline IMU..." at a fixed offset before fire.
                       stdout_watcher learns t_challenge -> FAR ~1.0.
  - sleep_then_burst : the naive "silent" fix (sleep, THEN dense collect, THEN fire). No stdout, but a
                       PollBurstWatcher sees the poll burst start ~200-600ms before fire -> FAR ~0.56.
  - continuous_poll  : the real fix (poll uniformly from t_arm through fire; ring = last pre_count).
                       No burst transition -> the PollBurstWatcher has no signal, falls back to blind
                       delay-guessing -> FAR ~chance.

The bot is GENEROUS: it is GIVEN the nonce (commitment always validates), so the ONLY discriminator is
TIMING. A-REACTIVE (a bot watching the HID OUTPUT force command, which fires at the true onset) is NOT
modelled -- uncloseable for any host-timed proof, out of P-LIVE-0's claim.

Pure stdlib; deterministic under a seed (tests). The real capture draws its delay from `secrets`.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from l9_presence.poep_live_verify import (  # noqa: E402
    ChallengeResponse,
    LiveChallenge,
    poep_commitment,
    response_feature_digest,
    verify_live_response,
)

CAPTURES = ("stdout_tell", "sleep_then_burst", "continuous_poll")
BOTS = ("stdout_watcher", "poll_burst_watcher", "blind_guesser")

FAR_OLD_BAR = 0.90         # stdout-tell path: the macro should forge >= 90%
FAR_FLAW_MIN = 0.30        # naive sleep-then-burst path: the poll-burst macro must be DEMONSTRABLY able
                           # to exploit it (else the continuous-poll fix would be decorative, not load-bearing)
FAR_FIX_BAR = 0.15         # continuous-poll path: the poll-burst macro must collapse to ~chance
_DEVICE = "581a836c"       # placeholder device id (harness only)

# default pre-collection window (ring size in [pre_samples//2, 3*pre_samples//2) at ~8ms/poll -> ms)
_PRE_MS_MIN = 208.0        # 26 * 8ms  (cfg.pre_samples=50, poll=0.008)
_PRE_MS_MAX = 600.0        # 75 * 8ms


def _canned_response(nonce: str, t_response_ns: int, *, latency_ms: float = 150.0,
                     peak_lsb: float = 2000.0, precursor_gap_ms: float = 120.0) -> ChallengeResponse:
    """A macro's forged in-band 'reflex': canned scalars + a CORRECT commitment (bot has the nonce)."""
    fd = response_feature_digest(latency_ms, peak_lsb, precursor_gap_ms)
    com = poep_commitment(device_id=_DEVICE, nonce=nonce, feature_digest=fd, ts_ns=t_response_ns)
    return ChallengeResponse(t_response_ns=t_response_ns, latency_ms=latency_ms, peak_lsb=peak_lsb,
                             precursor_gap_ms=precursor_gap_ms, nonce=nonce, commitment=com)


def _pollburst_offset_ns(pre_ms_min: float, pre_ms_max: float) -> int:
    """The poll-burst bot's optimal fixed offset O from t_burst: centers [O-300,O-80] on the est_pre
    distribution the public cfg implies (O = mid(est_pre) + band_center)."""
    band_center_ms = 0.5 * (80.0 + 300.0)
    return int((0.5 * (pre_ms_min + pre_ms_max) + band_center_ms) * 1e6)


def simulate_far(*, capture: str, bot: str, n_trials: int = 400, seed: int = 0xB07,
                 min_delay_s: float = 3.0, max_delay_s: float = 12.0,
                 pre_ms_min: float = _PRE_MS_MIN, pre_ms_max: float = _PRE_MS_MAX,
                 react_offset_ms: float = 150.0) -> dict:
    """Per (capture, bot) adversarial FAR = fraction of forged responses that pass `verify_live_response`."""
    if capture not in CAPTURES:
        raise ValueError(f"unknown capture {capture!r}")
    if bot not in BOTS:
        raise ValueError(f"unknown bot {bot!r}")
    rng = random.Random(seed)
    min_ns, max_ns = int(min_delay_s * 1e9), int(max_delay_s * 1e9)
    off_ns = int(react_offset_ms * 1e6)
    burst_off_ns = _pollburst_offset_ns(pre_ms_min, pre_ms_max)
    accepts = 0
    for i in range(n_trials):
        t_arm = 1_000_000_000_000 + i * 60_000_000_000
        true_delay = rng.randint(min_ns, max_ns)
        t_challenge = t_arm + true_delay
        est_pre_ns = int(rng.uniform(pre_ms_min, pre_ms_max) * 1e6)   # pre-collection window this trial
        nonce = f"nonce-{i}-{rng.getrandbits(48):012x}"               # bot is GIVEN this (generous)

        if bot == "stdout_watcher":
            if capture == "stdout_tell":
                t_fire = t_challenge + off_ns                        # learned t_challenge from stdout
            else:
                t_fire = t_arm + rng.randint(min_ns, max_ns) + off_ns  # no stdout -> blind guess
        elif bot == "poll_burst_watcher":
            if capture == "sleep_then_burst":
                t_burst = t_challenge - est_pre_ns                   # poll burst starts est_pre before fire
                t_fire = t_burst + burst_off_ns
            elif capture == "stdout_tell":
                t_burst = t_challenge - est_pre_ns                   # a burst exists here too
                t_fire = t_burst + burst_off_ns
            else:  # continuous_poll: uniform polling from arm -> no burst transition -> blind fallback
                t_fire = t_arm + rng.randint(min_ns, max_ns) + off_ns
        else:  # blind_guesser
            t_fire = t_arm + rng.randint(min_ns, max_ns) + off_ns

        resp = _canned_response(nonce, t_fire)
        ch = LiveChallenge(_DEVICE, nonce, t_challenge)              # 3-field: the timing discriminator
        if verify_live_response(ch, resp)["ok"]:
            accepts += 1
    return {"capture": capture, "bot": bot, "n": n_trials, "n_accept": accepts, "far": accepts / n_trials}


def far_collapse(*, n_trials: int = 400, seed: int = 0xB07,
                 min_delay_s: float = 3.0, max_delay_s: float = 12.0) -> dict:
    """The three load-bearing measurements + the PASS condition for the F-POEP-LIVE-1 tell-removal proof."""
    kw = dict(n_trials=n_trials, seed=seed, min_delay_s=min_delay_s, max_delay_s=max_delay_s)
    stdout = simulate_far(capture="stdout_tell", bot="stdout_watcher", **kw)["far"]
    naive = simulate_far(capture="sleep_then_burst", bot="poll_burst_watcher", **kw)["far"]
    fixed = simulate_far(capture="continuous_poll", bot="poll_burst_watcher", **kw)["far"]
    passes = (stdout >= FAR_OLD_BAR) and (naive >= FAR_FLAW_MIN) and (fixed <= FAR_FIX_BAR)
    return {
        "far_stdout_tell": stdout,                 # old path, stdout macro       (~1.0)
        "far_pollburst_naive": naive,              # sleep-then-burst, poll macro (~0.56 -- the flaw)
        "far_pollburst_fixed": fixed,              # continuous-poll, poll macro  (~chance -- the fix)
        "bar_stdout_min": FAR_OLD_BAR,
        "bar_flaw_min": FAR_FLAW_MIN,
        "bar_fix_max": FAR_FIX_BAR,
        "passes_tell_removal_proof": passes,
        "n_trials": n_trials,
        "delay_window_s": [min_delay_s, max_delay_s],
        "claim": "the CONTINUOUS-poll silent fire (not merely removing the stdout print) is what collapses "
                 "the poll-burst pre-tell macro from ~0.56 (naive sleep-then-burst) to ~chance; stdout-tell "
                 "macro forges ~1.0. A-REACTIVE (HID force-command watcher) is out of claim; "
                 "poep_enabled stays False.",
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    print(json.dumps(far_collapse(), indent=2))
