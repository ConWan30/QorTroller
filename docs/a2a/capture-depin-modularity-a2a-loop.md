# A2A-CDM — Capture-DePIN-Modularity agent-to-agent brainstorming loop

**A novel-environment, agent-to-agent (A2A) brainstorming loop.** Subject: **how the capture card +
the certified controller align, expand, and enhance QorTroller's DePIN / IoTeX modularity
configurations — interoperably, in sync.** This is *conceptual-framework* work (ideation), the
brainstorming twin of the build loops (CWL-1 / TPF-1). It produces a grounded framework, not code.

> **Novel environment:** `docs/a2a/` is a dedicated A2A collaboration workspace. The message medium is
> **dated round files** (async agent-to-agent exchange, operator-relayed). This directory is the loop's
> whole world — self-contained, reversible (`rm -rf docs/a2a/`), and touching nothing else.

## Agents + roles (the A2A division of labor)

| Agent | Role | Mandate each round |
|---|---|---|
| **grok** | **Expander** (novelty engine) | propose **≥3 novel** modularity / interoperability / node-topology configurations, each with a rationale + why it is novel. Bold by mandate — reach past what exists. |
| **Claude** | **Grounder / Integrator** | audit **every** grok proposal `claim ⊆ repo-reality`; tag each `{BUILDABLE-NOW / GATED:<gate> / REFUTED:<why>}`; integrate survivors into the running framework; pose the next open questions. |
| **Operator** | **Arbiter / Committer** | relay rounds between agents; resolve ties; **sole committer**. Neither agent commits, pushes, or seals autonomously. |

This mirrors the AH-1 pattern (grok designs, Claude audits) — formalized here into a repeating A2A round
loop for conceptual expansion instead of a one-shot brief.

## The A2A round protocol (the message loop)

```text
round-01-claude-open    : seed the framework + grounded baseline + open questions   [DONE]
round-02-grok-expand    : grok proposes >=3 novel configs against the open questions
round-03-claude-ground  : Claude audits -> tags -> integrates -> next questions
round-04-grok-expand    : ...
round-05-claude-ground  : ...
   ... until SATURATION or operator-interrupt ...
round-NN-synthesis      : Claude writes the final framework + the buildable-now shortlist
```

**Round message schema** (keeps the exchange structured + auditable):
- *Expand rounds (grok):* `## proposals` — each `{id · claim · rationale · why-novel}`.
- *Ground rounds (Claude):* `## verdicts` — each `{id · tag · evidence(repo path/fact) · integration-note}`, then `## open-questions` for the next expand round.

**Saturation criterion:** two consecutive expand rounds in which Claude tags **0 new BUILDABLE-NOW and 0
new distinct GATED** → declare saturation, write the synthesis round, stop.

## Honesty rails (hard — every round, both agents)

- **Ideation / doc only.** No wallet spend · no deploys · no chain writes · no FROZEN-v1 / 228B-PoAC /
  Solidity edits · no governance seals. **TGE frozen.**
- **`claim ⊆ reality` before BUILDABLE-NOW.** Anything past today's repo gets `GATED:<named gate>`
  (hardware / corpus breadth / ceremony / partner / operator) or `REFUTED:<why>` — never rounded up.
- **The separation law holds in every configuration.** Observation augments; only the controller
  (assertion) may claim humanity. Adding modules never lets a spoofable plane become the humanity gate.
- **Provenance-not-truth ceiling** for the capture witness holds in every config: it proves
  who/when/what-device captured a stream, never that the content is genuine gameplay.
- **Single-committer; no fabrication.** The operator commits. Neither agent writes the other's rounds —
  grok's expansions come from grok (operator-relayed); Claude's grounding comes from Claude.

## Subject scope (the framework's spine — do not drift off it)

Capture card + controller as **composable DePIN modules on IoTeX**, held coherent across **three sync
axes** — *identity* (session_id), *time* (PoSR temporal beacons), *content* (F3 `poac_chain_root`
cross-verify) — arranged in **modularity tiers** (minimal → standard → mesh), plugging into the **IoTeX
interoperability fabric** (W3bstream · ioID · DA · Realms · MachineFi). Round-01 grounds all of this.

## Round ledger

| round | agent | status |
|---|---|---|
| 01 | Claude — open | **DONE** (`round-01-claude-open.md`) |
| 02 | grok — expand | **DONE** (`round-02-grok-expand.md` — 23 proposals, rails held) |
| 03 | Claude — ground | **DONE** (`round-03-claude-ground.md` — 0 refuted; 4 gate-sharpenings [TGE, CONSENT-v2, privacy-legal, W3bstream-live]; Q4-P3 core found already-shipped; **D-CDM-1** fork-semantics → operator; 3 desk build candidates; NOT saturated) |
| 04 | grok — expand | **DONE** (`round-04-grok-expand.md` — 21 precision proposals; all Round-03 gates honored) |
| 05 | Claude — ground | **DONE** (`round-05-claude-ground.md` — 0 refuted; consent surface is THREE-layered [v1 bitmask + Arc-4 dimensions + LIVE WM registry] → v2 must reconcile; Q3-P3 gates split [action-SKU consent leg LIVE]; credits anti-cosplay rail; D-CDM-2 minor [reject ROLE_UNKNOWN]; **Grounder CONCURS with grok on D-CDM-1** [fail-closed joined + plane-local verifiable + multi-status]; 5-item buildable-NOW backlog; **recommendation: pivot to build**, then Round 06 = adversarial pass on built artifacts, Round 07 = synthesis) |
| — | **operator arbitration** | **D-CDM-1 DECIDED 2026-07-12: fail-closed-joined** (grok Q4-P3 + Grounder concurrence adopted); **pivot-to-build chosen** |
| — | **build pivot (Claude)** | **①–⑤ BUILT 2026-07-12:** ④ CONTENT_FORK terminal fail-closed in `tri_plane_manifest.py` (+ artifact-free fork rail; plane-split escape proven by test) · ③ `consumer_status()` multi-status surface (never a single boolean) · ② provenance-DAG index + `verify_provenance_dag.py` (real M17 index VERIFIED cold; omission ceiling pinned in output) · ① ModuleHello v0 spec (`docs/module-hello-v0-spec-2026-07-12.md`; D-CDM-2 resolved: reject `ROLE_UNKNOWN`) · ⑤ token-free economics + anti-cosplay rails (`docs/depin-economics-under-tge-freeze-2026-07-12.md`). 33 tests; PV-CI 182 |
| 06 | grok — adversarial | **DONE** (`round-06-grok-adversarial.md` — 26 attacks across T1–T4; 2 flagged as likely real gaps) |
| 07 | Claude — synthesis | **DONE — LOOP CLOSED** (`round-07-claude-synthesis.md`). Executed all desk forges: **2 CONFIRMED REAL GAPS found + FIXED** — F-CDM-1 (T1-A2: D-CDM-1 was plane-field-honest not artifact-root-honest; forking artifacts + stripped plane roots verified green → artifact-derived roots now authoritative) · F-CDM-2 (T3-A3: DAG was a hash-locker not a timeline; PoSP under a lied session_id verified green → session_id equality now enforced). T2-A1 also fixed (consumer_status label-skim). Rest = confirmed holds or documented ceilings. 44 tests; PV-CI 182. **SATURATED.** |

**LOOP CLOSED at Round 07.** Carried forward (named, gated): CONSENT-v2 ceremony · ModuleHello wire + trust-floor tests (→ CWL-1) · DAG v0.5 countersign+count-commitment · stake/slash (→ TGE).

---

*A2A-CDM loop — opened 2026-07-12. Operator-paced + operator-relayed; ideation only; reversible
(`rm -rf docs/a2a/`). grok expands, Claude grounds, the operator decides. Federation, never conflation.*
