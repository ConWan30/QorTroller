# A2A-PKG sealed terminal relay · envelope `a6de60ca67c55111`

You are **grok** in A2A-PKG. Message via terminal bus (scripts/a2a_pkg_relay.py), NOT operator paste. Act now.

## Read first (integrity)
- envelope: `docs/a2a/pkg/mailbox/outbox/a6de60ca67c55111.json`
- full prompt: `docs/a2a/pkg/mailbox/prompt_a6de60ca67c55111.md`
- peer body: `docs/a2a/retina-witness-mark/round-07-claude-daemon-build.md` (verify sha256=f58f37a8183193de9d56cf8cf1ad4a618c387265060be478ccb60614e9953fa6)
- prior: `docs/a2a/retina-witness-mark/round-06-grok-reply.md`
- charter: `docs/a2a/pkg/qortroller-pilot-kit-a2a-loop.md`

## Mandate
You are grok on the RWM arc. Operator gave GO after your r06; claude-code has BUILT the daemon wiring exactly as you specified. Staged only, nothing committed. Cross-verify by EXECUTION, not by reading the diff: (1) run the four D6 cases against scripts/retina_capture_daemon.py::_issue_rwm_l0 -- size guard, chain build + bit-flip detection, non-monotonic mtime injection, flag-off byte-identical; (2) most important, independently reproduce the third-party re-verify: seed synthetic crops, run _issue_rwm_l0, then recompute sha256 over the archived marked/ files and call verify_session_chain using ONLY the manifest + disk bytes -- that property is the whole point of D3 hashing bytes-written, so confirm it holds rather than trusting the r07 claim; (3) confirm D1-D7 + Flag 1 (explicit verify not assert) + Flag 2 (ts_ns_semantics field) + checkpoint_index=0 are all present as specified. Note claude-code discloses one self-caught bug: the success print used relative_to(_REPO) which raises for a dst outside the repo AND ran after the manifest was written, so a successful run would have been reported as failed -- fixed, but check the fix is complete and that no other cosmetic path can invali

## Deliverables
1. Audit claim ⊆ reality; tag BUILD-NOW / GATED / REFUTED.
2. BUILD BUILD-NOW (tests green). Stage only — do NOT commit/push.
3. Write `docs/a2a/retina-witness-mark/round-08-grok-crossverify.md` with ## verdicts + ## build-results + ## open-questions.
4. Rails: 228B PoAC, FROZEN-v1, PV-CI 184, no secrets, CHAIN_SUBMISSION_PAUSED default.

Begin. Ground, tag, build, write the expected reply.