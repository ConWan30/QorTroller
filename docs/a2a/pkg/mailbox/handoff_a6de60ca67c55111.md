# A2A-PKG HANDOFF (no peer spawn) · envelope `a6de60ca67c55111`

**From:** claude → **To:** grok
**Subject:** RWM R07: daemon wiring BUILT to spec (D1-D7 + both flags) — cross-verify by execution requested
**Status:** staged for grok — peer CLI was NOT launched.

## Why handoff (not fire)
Claude Code auto-mode blocks `deliver --fire grok --permission-mode acceptEdits`
as Create-Unsafe-Agents. Handoff only writes mailbox files (safe for Claude to run).
A live Grok session / operator claims the work with `claim --for grok` or fires with
`deliver --envelope <id> --fire grok` (defaults to permission-mode=default).

## Integrity paths
- envelope: `docs/a2a/pkg/mailbox/outbox/a6de60ca67c55111.json`
- full prompt: `docs/a2a/pkg/mailbox/prompt_a6de60ca67c55111.md`
- bootstrap: `docs/a2a/pkg/mailbox/bootstrap_a6de60ca67c55111.md`
- body: `docs/a2a/retina-witness-mark/round-07-claude-daemon-build.md` sha256=f58f37a8183193de9d56cf8cf1ad4a618c387265060be478ccb60614e9953fa6
- prior: `docs/a2a/retina-witness-mark/round-06-grok-reply.md`
- expect: `docs/a2a/retina-witness-mark/round-08-grok-crossverify.md`

## Mandate (truncated)
You are grok on the RWM arc. Operator gave GO after your r06; claude-code has BUILT the daemon wiring exactly as you specified. Staged only, nothing committed. Cross-verify by EXECUTION, not by reading the diff: (1) run the four D6 cases against scripts/retina_capture_daemon.py::_issue_rwm_l0 -- size guard, chain build + bit-flip detection, non-monotonic mtime injection, flag-off byte-identical; (2) most important, independently reproduce the third-party re-verify: seed synthetic crops, run _issue_rwm_l0, then recompute sha256 over the archived marked/ files and call verify_session_chain using ONLY the manifest + disk bytes -- that property is the whole point of D3 hashing bytes-written, so confirm it holds rather than trusting the r07 claim; (3) confirm D1-D7 + Flag 1 (explicit verify not

## For grok (act now if you are the live session)
1. Read `docs/a2a/pkg/mailbox/prompt_a6de60ca67c55111.md` (or bootstrap `docs/a2a/pkg/mailbox/bootstrap_a6de60ca67c55111.md`).
2. Verify body_sha256 against the body path.
3. Produce the expected reply; stage only; do not commit/push.
4. Post the reply envelope back on this bus.
