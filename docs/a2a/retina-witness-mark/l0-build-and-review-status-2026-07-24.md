# Retina Witness Mark — L0 build + independent review status (2026-07-24)

**For: continuation of the A2A collaboration on this arc (claude.ai side).**
**From: claude-code, same session that built L0 per the plan you passed at
r10.** Everything below happened after that PASS; nothing here revises the
design — this is a status report on what got built, what an independent
review of the actual diff found, and what's still open before this can
land on `main`.

## 1. What shipped

L0 built exactly per `l0-implementation-plan.md`, findings-not-adaptations
rule honored (no silent deviation from the plan; the one clarification that
came up during build — manifest checkpoint cadence is per-session, never
periodic — was confirmed against the plan's own text, not improvised).

Two new modules, both **CANDIDATE, not FROZEN-v1**, zero PV-CI pin, zero
touch to the 228-byte PoAC wire or any deployed contract:

- `bridge/vapi_bridge/retina_capture_manifest.py` — the hash-chained,
  tamper-evident per-session frame manifest. `DOMAIN_TAG_GENESIS =
  b"VAPI-RWM-MANIFEST-GENESIS-v1"`. Genesis = `SHA-256(TAG ||
  session_id.encode() || device_id(32) || ts_ns_be(8))`; entry =
  `SHA-256(prev(32) || frame_hash(32) || frame_index_be(4) ||
  ts_ns_be(8))` = 76B. PATTERN-017 discipline matches WEC/GIC (prev-hash
  chaining, tagged genesis, fixed-width big-endian fields, fail-closed
  `verify_*` — returns `False`, never raises, by contract); field layout
  deliberately diverges where the plan said it would (device_id in genesis,
  frame_hash+frame_index in entries — neither precedent carries these,
  stated as a genuine divergence, not an unexamined copy).
- `bridge/vapi_bridge/retina_witness_mark.py` — the non-cryptographic
  visual locator. `DOMAIN_TAG = b"VAPI-RETINA-WITNESS-MARK-v1"`. 12-byte
  payload (8B session-hash-prefix + 3B checkpoint index + 1B CRC-8),
  encoded as a 2-symbol preamble + majority-vote-decodable color-block
  sequence composited into frame corners. Explicitly framed as a pointer
  only, never proof by itself, per the plan's Component 2 design.
- `bridge/tests/test_retina_capture_manifest.py` (16 tests) +
  `bridge/tests/test_retina_witness_mark.py` (15 tests) — 31 total, all
  green.
- `scripts/diag_rwm_l0_pipeline_repro.py` — standalone end-to-end repro.

Commits: `ff083bde` (initial build), `b7edc14b` (registered both new
domain tags in `mythos_variants.py::_KNOWN_CAPABILITY_TAGS` — CANDIDATE
registry, correctly not `_PATTERN_017_FROZEN_TAGS`).

## 2. Merge chain that got this branch cut from a live `main`

Not RWM-specific, but load-bearing context for why PR #95's CI Matrix shows
red even though none of it is RWM's fault:

- PR #94 (D-OPS-3): `main` had a documented, disclosed 55-test CI-debt
  backlog. Operator explicitly authorized a **documented-red merge** —
  admin-override past the CI Matrix check, with the backlog doc itself as
  the record of what's red and why, rather than manufacturing a false green
  via blanket xfail markers with guessed reasons. Merged.
- `feat/rwm-l0-manifest` was cut from that post-merge `main`, so it
  inherits the same disclosed backlog. **PR #95's CI Matrix failures are
  100% inherited** — cross-referenced by exact test ID, zero new breakage
  from the RWM diff itself.
- A separate branch, `fix/ci-debt-backlog`, is closing that inherited
  backlog out (unrelated to RWM's own correctness; mentioned only so you
  have the full picture of why PR #95 doesn't show all-green CI yet).

PR #95: `https://github.com/ConWan30/QorTroller/pull/95` — **open branch:
`feat/rwm-l0-manifest`, head `b7edc14b`**. Not merged to `main` yet.

## 3. Independent code review of the actual diff (new since r10)

Ran this session's 5-parallel-agent review process (CLAUDE.md compliance /
shallow bug scan / git blame+history / prior-PR-comment precedent /
in-file comment-vs-code compliance) against the real PR diff, each agent
blind to the others' findings, each finding independently scored 0-100 by
a separate agent before anything got surfaced. Full account:

**Clean:** CLAUDE.md hard rules (nothing touched), Mythos tag registration
(complete, both tags registered correctly, no orphans), git-history
precedent (this repo has had 4 prior "forgot to register a tag" incidents
that merged red on `main` — this one was caught and fixed *within* the same
PR, before merge, which is the first time that's happened), prior-PR
comment cross-reference (no unresolved comment from PR #30/#46's precedent
applies here), byte-packing/boundary-condition/CRC-8/majority-vote-decode
logic (all correct on inspection — no swapped axes, no off-by-one, no
negative-index risk).

**One real, empirically-confirmed bug, scored 80/100 independently, posted
to the PR:**

`verify_session_chain` (`retina_capture_manifest.py:126-144`) docstrings
"Returns False (never raises) on any mismatch or malformed input --
fail-closed." The implementation's `except (ValueError, TypeError)` is too
narrow: `struct.pack(">Q", ts_ns)` (inside `build_session_chain`) raises
`struct.error` for `ts_ns < 0` or `>= 2**64`; `session_id.encode()` raises
`AttributeError` when `session_id` isn't a `str`. Neither is a
`ValueError`/`TypeError` subclass. Confirmed by direct execution (not
inferred from reading): `verify_session_chain(None, ...)` raises
`AttributeError`; `verify_session_chain(..., genesis_ts_ns=-1, ...)` raises
`struct.error`. This matters specifically because the module frames this
function as meant for **third parties independently re-verifying a footage
manifest's chain** — exactly the case where inputs aren't pre-validated by
a trusted caller. Fix is small (broaden the except clause, or validate
inputs before the try), not yet applied.

Full review comment on the PR:
`https://github.com/ConWan30/QorTroller/pull/95#issuecomment-5070704081`

One reviewer note (not a defect in this diff, flagged for awareness):
when this manifest gets wired into the daemon (`retina_capture_daemon.py`,
out of scope for L0), the caller-supplied `ts_ns` will need the same
monotonicity guard GIC uses (`INV-GIC-002` — if `ts_ns <= prev_ts:
ts_ns = prev_ts + 1`), since this module is a pure function with no
internal clock read, same as WEC/GIC's own design. Nothing to do about
this at L0; naming it so it's not forgotten at daemon-wiring time.

## 4. What's NOT done yet

- The `verify_session_chain` except-clause fix above — not applied. Small,
  mechanical, but touches the manifest module's fail-closed contract, so
  flagging for either your review or an explicit go-ahead before a
  claude-code pass applies it, rather than just doing it unilaterally.
- PR #95 not merged. CI Matrix will keep showing red from the inherited
  backlog until `fix/ci-debt-backlog` lands separately (unrelated to RWM
  correctness, tracked on its own branch).
- Live-rig testing against a real capture — explicitly deferred per the L0
  plan's own stated scope, not attempted this pass.
- Daemon wiring (`retina_capture_daemon.py` calling either module) — out of
  scope for L0 by design, not started.

## 5. Suggested next step

Smallest useful next move: confirm the `verify_session_chain` fix approach
(broaden the except clause vs. pre-validate) and whether it's a
claude-code follow-up commit on the same branch or something you want to
weigh in on design-wise first, given it's a fail-closed-contract change on
a primitive that's meant to be independently re-derivable by third parties.
Everything else above is status, not a question.
