#!/usr/bin/env python3
"""EVENT-BIND increment 3 demo — PoSR recency catches the replay the crypto join can't.

Both sessions are FULLY splice-proof (shared record_hash anchors — EVENT-BIND says crypto-bound).
They differ only in the session's temporal beacon vs the reference block:
  (1) LIVE session      — fresh beacon  -> REPLAY_RESISTANT
  (2) REPLAYED session  — stale beacon  -> SPLICE_PROOF_ONLY (recency refuses the replay-resistant claim)

Shows that recency is the layer that closes the naive full-session replay EVENT-BIND alone cannot.
Offline, no rig, no chain. See docs/event-bind-design-2026-07-09.md §2 (honest limits).
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.event_bind import HidOnset, ScreenOutcome, bind_events
from l9_presence.event_bind_recency import ReplayResistance, replay_resistance

_A = "a" * 64


def _splice_proof_session():
    # both lobes share the anchor -> binding_is_cryptographic (splice closed)
    return bind_events([ScreenOutcome(1000.0, _A), ScreenOutcome(2000.0, _A)],
                       [HidOnset(1080.0, _A), HidOnset(2080.0, _A)])


def main() -> int:
    reference_block = 100_000            # the "now" (latest anchored beacon block)

    live = replay_resistance(_splice_proof_session(), {"block_number": 99_950}, reference_block)   # 50 behind
    replayed = replay_resistance(_splice_proof_session(), {"block_number": 40_000}, reference_block)  # 60k behind

    print("Both sessions are fully splice-proof (crypto-bound) — EVENT-BIND alone cannot tell them apart.\n")
    for label, rr in (("(1) LIVE session     ", live), ("(2) REPLAYED session ", replayed)):
        d = rr.to_dict()
        print(f"{label}: binding_is_cryptographic={d['binding_is_cryptographic']}  "
              f"recency={d['recency_verdict']} (beacon {d['beacon_block']} vs ref {d['reference_block']}, "
              f"staleness {d['staleness_blocks']})  ->  {d['verdict']}")

    ok = (live.verdict == ReplayResistance.REPLAY_RESISTANT
          and replayed.verdict == ReplayResistance.SPLICE_PROOF_ONLY)
    print(f"\nRecency separates the live session from the replay on FRESHNESS, "
          f"not on the crypto binding: {'YES' if ok else 'NO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
