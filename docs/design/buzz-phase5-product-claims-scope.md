# Buzz × QorTroller — Phase 5 Product Claims Scope (v0)

**Status:** PROPOSED (enablement-gated — no implementation until gates clear)  
**Date:** 2026-07-31  
**Parent document:** `docs/design/buzz-qortroller-gamer-mvp-v0.md`  
**Depends on:** Phase 1–3 landed; Phase 4 code landed (`de50a6d`); Phase 4 ops acceptance  
**Authors:** Operator (Con) + Grok

---

## 0. Purpose

Phase 5 is the first phase that is allowed to move language from
**“candidate presence on Buzz”** toward **“tournament-grade”** claims.

It is deliberately thin on code and heavy on **enablement evidence**.
Nothing in this phase may ship as a product claim until the gates in §3
are met and operator-attested.

Parent doc one-liner (still binding):

> Population band, multi-gamer FRR, L6B/N seals, independent verifier path.  
> Only then does language move from “candidate presence on Buzz” toward “tournament-grade.”

---

## 1. What Phase 5 is (and is not)

### Is

- A **claim-enablement** phase: gather the empirical and cryptographic
  evidence required to support stronger public language.
- A **verifier-path** phase: make it possible for a stranger to re-check
  a sealed match package without trusting the operator’s machine.
- A **multi-gamer** phase: leave developer-self scope only after real
  N>1 evidence exists.

### Is not

- A token launch.
- A ban-enforcement product.
- A guarantee of “100% fair forever.”
- Permission to post raw biometrics on Nostr.
- Permission for the ACP gateway (or Devin/Grok) to spend chain or
  mutate FROZEN surfaces.

---

## 2. Core principle (still binding)

> Buzz is the social/ops plane.  
> QorTroller is the truth plane.  
> Nostr carries only pointers, status, and operator signals — never the biometric substrate.

Phase 5 may **link** to richer offline artifacts (scorecards, verifier
bundles) via consent-gated pointers. It must not put the substrate on
the bus.

---

## 3. Enablement gates (must all clear before tournament-grade language)

These gates are derived from the existing claim ceilings already
stated in the public README and protocol invariants. They are not new
inventions for Buzz — they are the same bars the rest of QorTroller
already refuses to cross.

| Gate ID | Requirement | Current honest state (as of Phase 3/4) | Clears when |
|---|---|---|---|
| **G5-SEP** | Inter-person separation: `separation_ratio > 1.0` **and** `all_pairs_above_1=True` across the required batteries | AIT cleared (~1.199); touchpad_corners still a blocker | All required batteries pass, operator-attested corpus pinned |
| **G5-L6** | L6 haptic challenge-response enabled only after calibration N≥50 (RIGID_MAX) | Default-OFF; N below threshold | N≥50 corpus + env flip under operator ceremony |
| **G5-L6B / PoEP** | Live PoEP / L6B presence verdicts only after measured corpus + operator attestation | Advisory / operator-gated | N≥50 (or documented equivalent) + env flip; FRR proxy recorded |
| **G5-MULTI** | Multi-gamer evidence (N_players ≥ 2 independent wallets/ioIDs) on real matches | Developer-self / single-operator demos | At least one sealed multi-gamer session with distinct ioID claims |
| **G5-FRR** | Field false-reject / false-accept proxies published for the enabled stack | Not yet published at product scope | Operator-attested measurement report + hold-out policy |
| **G5-VER** | Independent verifier path: stranger re-checks a sealed package with public tools only | PORT-CERT / WMP verify scripts exist; not yet a Phase-5 product surface | One public “verify this match” runbook + fixture that exits 0 on real data |
| **G5-OPS** | Phase 4 ACP ops acceptance complete | Code landed; live `#rig-ops` acceptance open | §1 operational checklist in Phase 4 addendum signed off |

**Hard rule:** if any gate is open, public language stays at **candidate /
advisory / developer-self**. No silent upgrade of claim grade.

---

## 4. Work packages (only after the relevant gates are in reach)

### WP-A — Claim register (docs first)

- Single table of allowed public phrases vs required gates.
- Every Buzz `#announcements` or organizer-facing doc must cite the
  register. No free-text “tournament-ready” without a gate row.

### WP-B — Multi-gamer sealed session

- Two distinct gamer npubs + ioID claims (reuse `buzz_ioid_claim.py`).
- One real match producing postcards in `#matches` for both.
- Pin workflow exercised; scorecards offline; digests only on Nostr.

### WP-C — Independent verifier path

- Package a sealed match (commitment roots + PORT-CERT / WMP-style
  verify scripts) so a third party can run one command and get
  `OVERALL: VERIFIED` without operator keys.
- Document the exact command and the honesty flags that must appear.

### WP-D — L6B / PoEP enablement ceremony

- Calibration corpus to N threshold.
- Operator ceremony to flip enablement flags (env + recorded attestation).
- ACP `list_ceremony_steps` remains checklist-only; humans fire the flips.

### WP-E — FRR / separation publication

- Measurement report (ratios, pairs, hold-outs, failure modes).
- Update claim register only after the report is pinned.

### WP-F — Buzz product surface (last)

- Organizer-facing one-pager that is allowed to say what the register
  permits — nothing more.
- `#announcements` posts stay admin-only and cite gate IDs.

---

## 5. Explicit non-goals (Phase 5)

- No TGE / token.
- No automatic ban as cryptographic truth.
- No ACP (Grok or Devin) gaining commit or spend authority.
- No raw HID / IMU / L4 / frames / full PoAC on Nostr.
- No collapsing gamer identity into the EA bot key.
- No claiming population certification from developer-self data.

---

## 6. Relationship to Phase 4 ACP

Phase 4 is an **operator convenience surface**. It does not satisfy any
Phase 5 enablement gate by itself.

Allowed Phase 4 uses during Phase 5 prep:

- `@EA invariant status` / `@EA health` / `@EA run pytest …` for
  engineering hygiene.
- `@EA ceremony steps` as a **checklist reminder** only.
- `@EA diagnose …` → Devin queue for investigation — still no auto-merge.

Forbidden Phase 4 uses:

- Treating a green `@EA` reply as population evidence.
- Using ACP to flip L6 / PoEP enablement without the human ceremony.

---

## 7. Acceptance for entering Phase 5 implementation

Before any Phase 5 *code* beyond measurement scripts:

1. Phase 4 ops acceptance checklist signed off by the operator.
2. Claim register (WP-A) merged as design-only.
3. Operator names which gate will be pursued first (recommended order:
   G5-OPS → G5-VER → G5-MULTI → G5-SEP / G5-L6 / G5-L6B → G5-FRR).
4. No public “tournament-grade” language until the corresponding gates
   are closed and cited.

---

## 8. Suggested first concrete step

**Do not start multi-gamer or L6 enablement yet.**

First:

1. Finish Phase 4 live ops acceptance (`ACP_OPERATOR_PUBKEYS`, dry-run,
   four `#rig-ops` commands).
2. Land WP-A claim register as a short design doc.
3. Rehearse WP-C independent verifier on an existing sealed match
   (PORT-CERT / WMP scripts already in-tree).

Only after those three should multi-gamer or enablement ceremonies be
scheduled.

**Progress (2026-07-31):** (2) landed — `docs/design/buzz-phase5-claim-register-v0.md`.
(3) rehearsed and **G5-VER closed for the M17 sealed match** —
`docs/design/buzz-phase5-wpc-verifier-rehearsal.md`. (1) still open: it is
operator-local, and `--preflight` on the ACP gateway is the readiness check for it.

---

**End of Phase 5 Product Claims Scope (v0)**
