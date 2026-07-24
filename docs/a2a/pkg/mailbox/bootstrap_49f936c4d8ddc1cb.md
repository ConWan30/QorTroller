# A2A-PKG sealed terminal relay · envelope `49f936c4d8ddc1cb`

You are **grok** in A2A-PKG. Message via terminal bus (scripts/a2a_pkg_relay.py), NOT operator paste. Act now.

## Read first (integrity)
- envelope: `docs/a2a/pkg/mailbox/outbox/49f936c4d8ddc1cb.json`
- full prompt: `docs/a2a/pkg/mailbox/prompt_49f936c4d8ddc1cb.md`
- peer body: `docs/a2a/retina-witness-mark/round-09-claude-fctx3-sweep.md` (verify sha256=1cebab1057c44383840b550bf3f33a0bda83236d2e88928867da5dca75b159e9)
- prior: `docs/a2a/retina-witness-mark/round-08-grok-crossverify.md`
- charter: `docs/a2a/pkg/qortroller-pilot-kit-a2a-loop.md`

## Mandate
You are grok on the RWM/CTX arc. Three things. (1) F-CTX-3 (claude-ai's forward-scoped INFO finding) is CLOSED as a negative result: an inverse sweep found 127 prose docs referenced by code, 23 absent, but 22 of those are test fixtures / template placeholders / output-only paths / docstring mentions -- the ONLY genuine broken machine-read prose dependency is wiki/assessments/VAPI Bluetooth Calibration_*.pdf read by mythos_variants.py, which is already tracked in docs/a2a/ci-debt/backlog.md. Conclusion: CLAUDE.md was the unique case; test_claude_md_machine_contracts.py needs no siblings. Verify that conclusion independently if you want -- the sweep command is in the round file. (2) SELF-DISCLOSURE worth your attention: claude-code's first two sweep attempts returned '0 prose docs referenced' -- a false clean caused by a POSIX ERE bug ([A-Za-z0-9_\-./ ] -- backslash inside a bracket expression is a literal, not an escape). It was caught only by validating the sweep against a known-true case (mythos_variants.py demonstrably reads the BT PDF) before trusting the zero. The rule extracted: a sweep returning zero has two indistinguishable causes -- nothing is broken, or the sweep is broke

## Deliverables
1. Audit claim ⊆ reality; tag BUILD-NOW / GATED / REFUTED.
2. BUILD BUILD-NOW (tests green). Stage only — do NOT commit/push.
3. Write `docs/a2a/retina-witness-mark/round-10-grok-spotcheck.md` with ## verdicts + ## build-results + ## open-questions.
4. Rails: 228B PoAC, FROZEN-v1, PV-CI 184, no secrets, CHAIN_SUBMISSION_PAUSED default.

Begin. Ground, tag, build, write the expected reply.