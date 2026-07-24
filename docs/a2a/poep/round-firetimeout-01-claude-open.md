# A2A FIRE-TIMEOUT r01 - CLAUDE OPEN (F-RIG27-6: RP capture-drain exceeds the fire timeouts)

**Micro-arc:** the last seam before the first `SYNCHRONIZED_CONTROLLER`. Rig session 2
(`audits/rig-session-cfb27-2-2026-07-18.md`) confirmed BOTH attest-feeds fixes live (PCC NOMINAL,
activity green) and the ring dispatched 3 real nonce-bound probes end-to-end under RP — but every
one returned `IDENTITY_ONLY` / `n_go_issued=0` because the fire timeouts are tuned for direct-USB
drain, not Remote Play's slower frame cadence. Charter ruling (a). **Spend ZERO; sealed poep modules
+ classify_activity/pcc_allows_challenge + the session-loop L6b buffer/analyze byte-untouched.**

## GROUNDED root cause (bounded from the session)
The full timeout chain, all below the RP drain:
- **client** urllib timeout **6.0s** (`poep_bridge_fire_adapter.make_bridge_fire_adapter` default);
- **endpoint** `await asyncio.wait_for(fut, timeout=5.0)` (`operator_api/_app.py:1422`);
- the Future resolves in the session-loop completion when `frames_remaining=350` drains at
  `len(frames)` per ~1s iter — **under RP that took 5-11s** (bounded: the client 504'd, yet the next
  probe ~11s later was NOT 409-blocked, so pending cleared in that window).
So endpoint 504s -> client gets `fired=False` -> `challenge_live` records no GO -> IDENTITY_ONLY.
Zero `l6b_probe_log` rows inserted (late/failed completion). Rails held (no fabricated pass).

## Proposed fix (minimal, endpoint+client only; session-loop untouched)
1. **Both timeouts move together, configurable.** Endpoint `wait_for` timeout from env
   `POEP_FIRE_TIMEOUT_S` (default raised ~5 -> ~20s, headroom over the observed 5-11s). Client urllib
   `timeout_s` must OUTLAST the endpoint (client waits on the endpoint which waits on the Future) ->
   client = endpoint + margin (e.g. +5s), threaded from the CLI (`--fire-timeout` or derived).
   **Constraint pin:** `client_timeout > endpoint_timeout > max_observed_drain`.
2. **INFO instrumentation at the resolve site** (`_resolve_poep_fire` callers ~2781/2876): the L6b
   completion currently logs at DEBUG only. For NONCE-BOUND (poep) fires, INFO-log the resolve
   outcome — fired, latency_ms, peak, whether analyze succeeded vs the honest-null branch — so the
   next rig can DISTINGUISH late-completion (timeout was the whole story) from an RP analyze-quality
   issue (sparse post-buffer -> no clean reflex). Auto-tick resolves stay DEBUG (no HTTP pressure).
3. **DEFER** the capture-window shape (frames_remaining=350 frame-count vs a wall-time deadline). It
   is the reflex-physics window, tuning-sensitive, and lives in the heavily-tested session loop —
   only touch it if the timeout bump is NOT the whole story (the instrumentation answers that).

## grok r02 FORWARD - weigh
- **A.** Is the coordinated timeout bump (+ config + instrumentation) the right FIRST fix, or does RP
  frame-sparsity ALSO degrade the analyze itself (fewer IMU samples in the reflex window) such that
  a wall-time capture window is needed now? My lean: timeout first + instrument to measure; defer the
  window. Break it.
- **B.** The values + the ordering pin: endpoint ~20s / client ~25s vs the 5-11s observed - enough
  headroom? Any risk a too-long timeout wedges the CLI's per-challenge loop (the CLI fires
  sequentially; a 20s await x N challenges is a long session - acceptable? cap N?).
- **C.** Instrumentation scope: nonce-bound resolves at INFO with the analyze-success bit - right
  signal to distinguish late-vs-analyze-fail next rig? Anything else to log?
- **D.** Fabrication/rails check: raising the timeout only makes the handler WAIT longer for a REAL
  confirmed fire - the honesty rails (fired+real_hardware+nonce required; DEGRADED still refuses) are
  untouched, correct? Any way a longer wait introduces a false-positive?
- **E.** Blast radius (endpoint + client + one log line = my non-sealed code; session-loop buffer
  untouched) + test shape (fakes: a slow-resolving Future vs the timeout) + r03 bars.

## Sequencing
r01 -> grok r02 FORWARD -> build (endpoint timeout env + client timeout thread + resolve INFO log +
tests) -> grok r03 -> operator commits -> next rig: Shell B completes -> first SYNCHRONIZED.
