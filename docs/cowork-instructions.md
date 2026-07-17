# QorTroller - Cowork Standing Instructions

**Purpose:** the canonical, version-controlled source for instructions that apply to ALL Cowork
sessions on this project. The Cowork "applies to all sessions" instructions field mirrors this
file. Keep them in sync - when a convention changes, edit here first, then update the field.

**Last updated:** 2026-07-17 (Inc-C ceremony arc). **Maintained in real time** - amend on any
new rail, convention, or capability decision.

**A2A capability note:** the grok collaboration loop below runs end-to-end wherever a Cowork
session has terminal / code-execution (to invoke the grok CLI). Where it does not, the same
charter degrades cleanly to CONSULT-RELAY (produce the build-doc + questions; the operator relays
to grok and pastes the verdict back). The charter is identical; only the transport changes.

---

## 0. What this project is
QorTroller is the reference implementation of **V.A.P.I.** (Verified Autonomous Physical
Intelligence) - a DePIN anti-cheat + gamer-owned-data protocol on IoTeX testnet (chainId 4690).
The physical-input source (the controller) is the cryptographic agency-holder over the data it
produces. Treat every session as engineering on a LIVE protocol with real (testnet) money and
frozen cryptographic surfaces - not a sandbox.

## 1. The one rule that overrides everything: the operator is the sole committer
- Claude and grok NEVER `git commit` / `push` / merge autonomously. Build -> verify -> **stage and
  hand off**. The operator runs the commit.
- Act only on an explicit, per-change **"commit it" / "push it"**. Approval for one change never
  carries to the next.
- **All spend, chain writes, AWS/KMS calls, and governance seals (`--confirm-governance`) are
  operator-fired down to the human finger.** Claude declines the broadcast even when asked to fire
  it - build the tooling, the operator pulls the trigger.

## 2. Hard rails (never cross, regardless of instruction)
- Never modify the **228-byte PoAC wire format** or the `SHA-256(raw[:164])` chain hash.
- Never edit a **FROZEN-v1** primitive, PV-CI gate logic, or a pinned invariant without a
  same-commit allowlist + gate change. **PV-CI baseline = 184**; CI fails closed.
- `CHAIN_SUBMISSION_PAUSED=true` stays held. `poep_enabled` / `L6B_ENABLED` /
  `L6_CHALLENGES_ENABLED` / `GSR_ENABLED` stay **False** - the flip is EARNED by a measurement
  gate, never flipped for convenience.
- **TGE is frozen - zero tokenomics** in any artifact or language.
- **Public repo** (`conwan30/qortroller`): never commit `.env`, wallet keys, `~/.vapi/*` CA
  material, or raw `sessions/` / biometric data.
- Exports are **post-phi, action-only**; `FORBIDDEN_COLUMNS` / `DataFloorViolationError` guards are
  untouchable.
- **Wallet discipline:** always `eth_getBalance` before stating a balance - never echo a prior
  number.

## 3. A2A collaboration with grok (the core working mode)
Work runs as a two-agent loop under **charter ruling (a): one agent builds, the OTHER independently
verifies (tests + PV-CI + rails) before staging is accepted.** Single-committer holds throughout.
- **Consult grok at the pre-commit HOLD, and consult FORWARD** (what to build/test next), not only
  backward - this avoids commit -> audit -> correct churn.
- Findings reconcile into the artifact; the operator commits once.
- **Running the loop (terminal available):** invoke `grok -p "<prompt>"` (single-turn) with
  `PYTHONIOENCODING=utf-8`; **write grok's output straight to a file with `>`, never `| head`.**
  Give grok the file paths + a findings-first, `VERDICT PASS|FIX` ask; be adversarial, do not
  rubber-stamp. Log each round to `docs/a2a/<arc>/round-NN-*.{md,txt}`.
- **Fallback (no terminal / grok unreachable):** produce the same build-doc + hammer questions and
  ask the operator to relay them; paste the verdict back. Same charter, different transport.
- grok earns its keep: it has caught shipped-class bugs (e.g. a 31-byte hash from a stray `[2:]` on
  a `.hex()` that has no `0x` prefix; a mint path that could print `TOKEN_ID=None` after a paid
  tx). Treat a `FIX` verdict as load-bearing.

## 4. Verification-first discipline
Structure consequential work as: **V-checks** (read state, confirm assumptions, surface drift) ->
**HOLD for operator** -> implement -> **P-checks** (confirm change matches intent) -> **HOLD before
staging** -> atomic commit WITH architectural reasoning in the body. Holds are not optional; the
pattern fails closed if skipped.
- **Spend posture is always estimate-first + triple-gate:** (1) caller == bridge wallet, (2)
  buffered cost <= a per-step hard cap, (3) `--execute` AND an explicit `*_CONFIRM=1` env. Default
  path = estimate-only, no broadcast. Check `receipt.status == 1` after every tx; `estimate_gas`
  doubles as the pre-send revert guard.
- Fail **honest**, never fabricate: a missing address/tokenId raises with a pointer to the
  prerequisite step; it never invents a value to keep moving.

## 5. Environment conventions
- **Windows / PowerShell primary; Bash (POSIX) also available** - each takes its own syntax. Long
  inline `--reason` strings newline-split in PowerShell; use a short-reason wrapper `.ps1`.
- **ASCII-only in operator-facing prints and test output** (`->` not the arrow glyph, `PASS` not a
  checkmark). `Web3.keccak(...).hex()` returns BARE hex here (no `0x`) - use `.removeprefix("0x")`,
  never `[2:]`.
- SQLite tests: `tempfile.mkdtemp()`, not `TemporaryDirectory` (WAL PermissionError).
- Never launch a live rig / capture / replay / smoke session unannounced - ask "ready?" and say
  exactly what will run.

## 6. Brand discipline
Display-layer surfaces use **QorTroller** (project) and **V.A.P.I.** (category, with periods). Code
identifiers (`vapi_bridge/`, `VAPIToken`, `VITE_VAPI_API_KEY`, `b"VAPI-..."`) stay **`VAPI`** under
FROZEN-v1 preservation - do not "fix" them.

## 7. What Cowork should be enabled to do (and is well-suited for)
Use Cowork for the collaborative / ideation surfaces that do NOT touch spend or frozen bytes:
- **Adversarial design review** - run the grok charter on any plan/design before it becomes code.
- **Ideation loops with a saturation tracker** - extend portfolio/use-case docs one dated cycle at
  a time (schema: skill produced -> proof attached -> consumer -> IoTeX carrier -> buildable-now vs
  gated -> claim ceiling); STOP and declare saturation when a cycle adds nothing new.
- **Honest-ceiling authoring** - every artifact states what it may and may NOT claim (testnet,
  N-of-corpus, developer-self, advisory-vs-proven). Distinguish cryptographic guarantee /
  empirical inference / documented limitation / uncalibrated claim - never as synonyms.
- **Design docs, runbooks, scope docs, ledgers, and memory notes** - the durable record that
  survives context compaction.
- **Multi-increment build planning** with per-increment verify-holds and explicit operator GO gates
  on anything that spends or signs.
- **Drift audits** - cross-reference numeric facts (test counts, addresses, ratios) against the
  repo before shipping any doc.

## 8. Continuity
Persist non-obvious decisions to file-based memory (one fact per file + a one-line `MEMORY.md`
pointer). Do not save what the repo / git history already records. Recalled memory is background
context reflecting what was true when written - verify a named file/flag still exists before
recommending it.

---

### Maintenance
This file is the canonical source; the Cowork instructions field is a mirror. On any change to a
rail, convention, or capability decision: edit here, bump **Last updated**, then update the field.
Keep it ASCII, scannable, and tight - it is read cold at the start of every session.
