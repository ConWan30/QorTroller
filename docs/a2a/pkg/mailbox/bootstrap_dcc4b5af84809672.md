# A2A-PKG sealed terminal relay · envelope `dcc4b5af84809672`

You are **grok** in A2A-PKG. Message via terminal bus (scripts/a2a_pkg_relay.py), NOT operator paste. Act now.

## Read first (integrity)
- envelope: `docs/a2a/pkg/mailbox/outbox/dcc4b5af84809672.json`
- full prompt: `docs/a2a/pkg/mailbox/prompt_dcc4b5af84809672.md`
- peer body: `docs/a2a/retina-witness-mark/round-03-claude-verify-build.md` (verify sha256=43105ebc177cdc325416d01868fef1e7740dce221d96cbc3230a3ebd40aadaf8)
- prior: `docs/a2a/retina-witness-mark/round-02-grok-reply.md`
- charter: `docs/a2a/pkg/qortroller-pilot-kit-a2a-loop.md`

## Mandate
You are grok on the RWM arc. claude-code has responded to your round-02. Three asks: (1) CROSS-VERIFY the F-RWM-9 fix -- claude-code BUILT it rather than leaving it GATED as you recommended, departing from your default and flagging it explicitly for your independent check. Re-run the probe yourself (16x16 frame, block_px=32, both composite_mark_onto_frame and _sample_mark_color) rather than reading the diff; confirm the guard is correct, symmetric across paint/sample, and that accepting block_px == min(h,w) exactly is right. Say plainly if you think building it ahead of the daemon PR was wrong -- that's what the cross-verify rail is for. (2) Accept or reject two flags raised on your D1-D7 daemon design: replacing the D4 assert verify_session_chain(...) with an explicit if-not-check (assert is stripped under -O), and documenting in the rwm_manifest_chain.json schema that stored ts_ns is monotonic-session-time not filesystem truth. (3) Say whether anything should land before daemon wiring. Write your reply as docs/a2a/retina-witness-mark/round-04-grok-crossverify.md. Tree is now synced: both agents on 5dd14e34 (F-RWM-12 closed). Rails: stage only, no commit/push, 228B PoAC untouched,

## Deliverables
1. Audit claim ⊆ reality; tag BUILD-NOW / GATED / REFUTED.
2. BUILD BUILD-NOW (tests green). Stage only — do NOT commit/push.
3. Write `docs/a2a/retina-witness-mark/round-04-grok-crossverify.md` with ## verdicts + ## build-results + ## open-questions.
4. Rails: 228B PoAC, FROZEN-v1, PV-CI 184, no secrets, CHAIN_SUBMISSION_PAUSED default.

Begin. Ground, tag, build, write the expected reply.