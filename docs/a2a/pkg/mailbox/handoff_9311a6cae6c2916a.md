# A2A-PKG HANDOFF (no peer spawn) · envelope `9311a6cae6c2916a`

**From:** grok → **To:** claude
**Subject:** RWM R10: sole-agent spot-check — live archives verified; live_04 FROZEN content finding; runbook; tip d9182a8d
**Status:** staged for claude — peer CLI was NOT launched.

## Why handoff (not fire)
Claude Code auto-mode blocks `deliver --fire grok --permission-mode acceptEdits`
as Create-Unsafe-Agents. Handoff only writes mailbox files (safe for Claude to run).
A live Grok session / operator claims the work with `claim --for grok` or fires with
`deliver --envelope <id> --fire grok` (defaults to permission-mode=default).

## Integrity paths
- envelope: `docs/a2a/pkg/mailbox/outbox/9311a6cae6c2916a.json`
- full prompt: `docs/a2a/pkg/mailbox/prompt_9311a6cae6c2916a.md`
- bootstrap: `docs/a2a/pkg/mailbox/bootstrap_9311a6cae6c2916a.md`
- body: `docs/a2a/retina-witness-mark/round-10-grok-spotcheck.md` sha256=980aed4f975c2122ef9bdeb1721d95a42b455e2ccccf51c0cd5d2113e481cb23
- prior: `docs/a2a/retina-witness-mark/round-09-claude-fctx3-sweep.md`
- expect: `docs/a2a/retina-witness-mark/round-11-next.md`

## Mandate (truncated)
You are Claude in A2A-PKG (Grounder/Builder). Audit every proposal claim ⊆ repo-reality; tag {BUILD-NOW / GATED:<gate> / REFUTED:<why>}; BUILD the BUILD-NOW set (tested, PV-CI-clean, staged — do NOT commit/push); write the expected reply round file. Rails: 228B PoAC, FROZEN-v1, PV-CI 183, no secrets, CHAIN_SUBMISSION_PAUSED default, additive packaging, single-committer=operator.

## For claude (act now if you are the live session)
1. Read `docs/a2a/pkg/mailbox/prompt_9311a6cae6c2916a.md` (or bootstrap `docs/a2a/pkg/mailbox/bootstrap_9311a6cae6c2916a.md`).
2. Verify body_sha256 against the body path.
3. Produce the expected reply; stage only; do not commit/push.
4. Post the reply envelope back on this bus.
