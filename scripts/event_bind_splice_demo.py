#!/usr/bin/env python3
"""EVENT-BIND splice demonstration — makes the novelty tangible.

Builds two identical-timing corpora and binds each:
  (1) GENUINE co-capture  — outcome & onset share the live PoAC record_hash  -> RECORD_HASH_PRODUCTION
  (2) SPLICE              — kill-outcomes from capture A + trigger-onsets from capture B,
                            timestamps ALIGNED so a temporal ∩ would call it authored -> TEMPORAL_PROTOTYPE

The two reports differ ONLY in the anchors, not the timing — showing that a shared cryptographic
record_hash is what makes per-event authorship splice-proof, a class the temporal join cannot resist.

Offline, no rig, no chain. See docs/event-bind-design-2026-07-09.md.
"""
from __future__ import annotations

import os
import sys

# the report markdown carries Unicode (Δt, ±); make console printing UTF-8-safe on Windows cp1252
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.event_bind import HidOnset, ScreenOutcome, bind_events

_A = "a" * 64      # capture-A record_hashes (per-kill unique in reality; simplified here)
_B = "b" * 64      # capture-B record_hashes


def _corpus(onset_anchor):
    # three authored kills at 1s/2s/3s; trigger onsets 80 ms later (well inside any window)
    outcomes = [ScreenOutcome(t_ms=t, record_hash=_A, kill_id=f"k{i}")
                for i, t in enumerate((1000.0, 2000.0, 3000.0))]
    onsets = [HidOnset(t_ms=t + 80.0, record_hash=onset_anchor)
              for t in (1000.0, 2000.0, 3000.0)]
    return outcomes, onsets


def main() -> int:
    print("=" * 78)
    print("(1) GENUINE co-capture — both lobes stamped with the SAME live record_hash")
    print("=" * 78)
    out, ons = _corpus(_A)
    genuine = bind_events(out, ons)
    print(genuine.to_markdown())
    print()

    print("=" * 78)
    print("(2) SPLICE — kill-outcomes (capture A) + trigger-onsets (capture B), timestamps ALIGNED")
    print("     a temporal ∩ would call these authored; EVENT-BIND refuses the crypto claim")
    print("=" * 78)
    out, ons = _corpus(_B)               # SAME timing as (1) — only the onset anchor differs
    splice = bind_events(out, ons)
    print(splice.to_markdown())
    print()

    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"  genuine : binding_is_cryptographic = {genuine.binding_is_cryptographic}  "
          f"(crypto {genuine.n_crypto}/{genuine.n_outcomes})")
    print(f"  splice  : binding_is_cryptographic = {splice.binding_is_cryptographic}  "
          f"(crypto {splice.n_crypto}/{splice.n_outcomes}, temporal {splice.n_temporal})")
    ok = genuine.binding_is_cryptographic and not splice.binding_is_cryptographic \
        and genuine.n_bound == splice.n_bound        # SAME temporal coverage — only anchors differ
    print(f"\n  EVENT-BIND separates genuine from splice on the ANCHOR, not the clock: "
          f"{'YES' if ok else 'NO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
