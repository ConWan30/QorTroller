# A2A-STREAM-2 — StreamView novelty enhancement loop (the gamer environment learns it's a node)

**Chartered 2026-07-13 (operator: enhance the StreamView via A2A novelty brainstorming before
playing).** Sibling loop on the shared bus. The StreamView (PKG rounds 10–14) was built BEFORE
VALID-1 and DEPIN-1 existed — the gamer environment renders witness respiration + ceremony + receipt
but knows nothing about: the node's identity (node_id spine), its DePIN contribution ledger, the
match self-scorecard, kills-seen, or the fresh-trigger pulse. STREAM-2 closes that gap with NOVELTY
as the explicit mandate — design what a **capture-witness DePIN node's live face** should be, not a
dashboard clone.

## Grounded gap (claim ⊆ reality)
`~/.qortroller/ui/*.json` snapshots carry `node_state/freshness_class/session_id_display` but NOT:
`node_id` (leg 1) · ledger entries/anchored state (leg 3) · scorecard recall/verdicts (VALID-1) ·
kills-seen (sink) · `_kf_fresh_fires` (HARD-1 watcher). StreamView reads only those snapshots
(noMock: missing → UNKNOWN). All the new data EXISTS in artifacts the CLI already reads.

## Roles (ruling (a))
grok = novelty designer (≥3 proposals `{id · design · rationale · why-novel}`) + may BUILD;
Claude = grounder + cross-verifier (+ builder where grok doesn't); operator = arbiter + sole
committer + first eyes on the result.

## Rails (standing + UI-specific, all inherited from PKG rounds 10–14)
Honest pixels: noMock (missing snapshot → UNKNOWN, never fabricated LIVE); freshness-class not
counts; verdicts AS-IS with dignity; F-T66B-1 disclosure wherever authorship renders; `anchored`
renders false/PENDING until a real tx (the leg-3 rail extends to pixels — never paint "on-chain"
for a local entry); node_id claim language (DEVICE on-chain, node_id derived); named exports +
lazy-load via named import; brand tokens (void-black/orange/cyan); zero live-bridge dependence for
offline surfaces; no keys/consent authority in the UI. Data flows CLI → snapshot JSON → view
(the UI never computes truth). Additive; single-committer.

## Stop criterion
One or two rounds: design → build → cross-verify → Vitest green → the operator SEES it (their
dogfood is the final judge). No endless polish before the operator has played once.

---
*STREAM-2 charter — 2026-07-13. Rounds in `docs/a2a/stream2/round-*.md`; envelopes on the shared bus.*
