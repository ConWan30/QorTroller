# A2A-PKG — QorTroller Pilot Kit agent-to-agent BUILD loop (PKG-1)

**An A2A collaboration loop that BUILDS, not just brainstorms.** Subject: **package the QorTroller
bridge into an installable product** — the *dramatic transition* from today's developer rig (terminal
daemon + env flags + tribal knowledge) into an onboarding-wizard product that reflects what QorTroller
has now substantiated: live capture-card observation, the first self-verified `VAPI-RETINA-STATE-v3`
record from a real match, a SYNCHRONIZED PoSP, an on-chain-anchored FROZEN governance seal, and a live
WMP provenance bundle. **The install experience must carry that maturity — a proof appliance, not a
script pile.**

> **Novel environment:** `docs/a2a/pkg/` is this loop's dedicated A2A workspace (sibling of the
> A2A-CDM loop). Message medium = dated round files. **Relay channels (2026-07-12+):** (1) classic
> operator-paste; (2) **terminal A2A bus** — `scripts/a2a_pkg_relay.py` seals hash-bound envelopes
> under `docs/a2a/pkg/mailbox/` and can fire `claude`/`grok` CLI autonomously when the operator
> authorizes (`--autonomous`). Unlike A2A-CDM (ideation-only), **this loop ships code**: Claude
> builds increments between rounds; the rounds steer the build. Operator remains sole committer.
>
> **Claude → Grok delivery (2026-07-22):** Claude Code auto-mode blocks
> `deliver --fire grok --permission-mode acceptEdits` as *Create Unsafe Agents*. Claude MUST use
> the handoff path only (no peer spawn):
> `python scripts/a2a_pkg_relay.py deliver --envelope <id> --handoff`
> then Grok/operator claims with `claim --for grok`. Direct `fire=grok` defaults to
> `permission-mode=default`; `acceptEdits` requires explicit `--force-unsafe-fire` (operator only).

## Agents + roles

| Agent | Role | Mandate each round |
|---|---|---|
| **grok** | **Product designer** (novelty + UX vision) | design the install/onboarding/settings experience: ≥3 concrete proposals per round `{id · design · rationale · why-novel}`. Bold by mandate — design the product QorTroller's milestones deserve, not a wrapper on the rig. |
| **Claude** | **Grounder / Builder / Auditor** | audit every proposal `claim ⊆ repo-reality` → tag `{BUILD-NOW / GATED:<gate> / REFUTED:<why>}`; **build the BUILD-NOW increments** (tested, PV-CI-clean, staged); report build results into the next round; pose the next design questions. |
| **Operator** | **Arbiter / INSTALLER #1 / Committer** | relay rounds; resolve ties; **dogfood every increment as the first installer** (real feedback beats speculation); sole committer — neither agent commits/pushes/seals autonomously. |

## Phasing (the operator's mandate)

1. **Phase D — developer-savvy (NOW):** the operator is the only installer. Increments may assume a
   developer machine, but every increment must REPLACE a piece of tribal knowledge with a wizard,
   pack, or check (the operator should need the chat transcript less after every increment).
2. **Phase G — gamer-grade (LATER, gated):** a friend with zero terminal skill installs it. Reached
   only when Phase D is dogfooded stable. Per-gamer identity/consent is designed in Phase D,
   activated in Phase G.

## The round protocol

```text
round-01-claude-open    : grounded baseline (the REAL install surface today) + design questions  [DONE]
round-02-grok-design    : >=3 product/onboarding designs against the questions
round-03-claude-ground+build : audit -> tag -> BUILD the BUILD-NOW set -> results + next questions
round-04-grok-design    : ...
   ... until Phase D dogfood-stable or operator-interrupt ...
round-NN-synthesis      : final kit definition + the Phase G gate checklist
```

**Round schema** — *grok:* `## proposals` `{id · design · rationale · why-novel}`. *Claude:*
`## verdicts` `{id · tag · evidence · build-result(if built)}` + `## open-questions`.

**Saturation/stop:** Phase D is DONE when the operator completes a full session (install → wizard →
play → stop → verified artifacts) **without touching a terminal flag or asking the chat** — the
dogfood bar. Then synthesis + the Phase G gate list.

## Honesty rails (hard — every round, both agents)

- **Single-committer.** Operator commits/pushes. Claude stages + hands off; grok's designs arrive
  operator-relayed. Neither agent writes the other's rounds.
- **Cross-verified building (operator ruling (a), 2026-07-12, round-06 cycle).** EITHER agent may
  build increments, but staged work is accepted ONLY after the *other* agent independently verifies
  it (tests + PV-CI + rails audit) and records the verification in its round. Cross-verification is
  the rail; role purity is not. Surfaced when grok exceeded its designer mandate in round-06 and
  built the Q10–Q13 set — Claude's audit (30/30 tests, PV-CI 183, no secrets, nothing committed)
  validated the work, and the operator ruled to keep the pattern.
- **No secrets in the kit.** Never ship/copy `bridge/.env`, `BRIDGE_PRIVATE_KEY`, `~/.vapi` key
  material, or biometric `sessions/` data. Key handling in the kit is a DESIGN surface (per-gamer
  identity), never a copy-paste of the operator's keys.
- **`claim ⊆ reality`.** The kit's UI/wizard claims exactly what the pipeline proves — the honest
  verdicts (UNVERIFIABLE / PARTIAL / SYNCHRONIZED, honest-null v3) render AS-IS; packaging never
  rounds a verdict up. F-T66B-1 (own-kill recall) is disclosed in-product until fixed.
- **Rails untouched:** 228B PoAC wire · FROZEN-v1 formulas · PV-CI 183 · separation law + biometric
  floor · TGE frozen · `CHAIN_SUBMISSION_PAUSED=true` default in anything the kit configures.
  No deploys/spend from the kit; chain writes stay operator-fired + triple-gated.
- **Additive packaging.** The daemon/bridge keep working exactly as today for the dev path; the kit
  wraps, never forks.

## The novelty spine (align with where QorTroller stands NOW)

**Installation = node provisioning.** The onboarding wizard is not app setup — it is the birth
ceremony of a **capture-witness DePIN node** (the A2A-CDM thesis made tangible): the card GO-check is
the C0 smoke test; ROI calibration is R2; the controller identity check is the device-registry story;
the first session's KAS/PoSP/v3 artifacts are the node's first proofs. The kit's product identity:
**"install it, play one match, hold a cryptographic proof of your own gameplay"** — the exact thing
proven live 2026-07-12, packaged.

---
*A2A-PKG orchestrator — drafted 2026-07-12. Operator-paced; Phase D first (operator = installer #1);
Phase G gated on dogfood-stable. Rounds in `docs/a2a/pkg/round-*.md`. Nothing here commits itself.*
