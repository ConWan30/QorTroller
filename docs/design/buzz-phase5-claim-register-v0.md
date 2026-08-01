# Buzz × QorTroller — Phase 5 Claim Register (v0)

**Status:** DESIGN-ONLY (WP-A of `docs/design/buzz-phase5-product-claims-scope.md`)
**Date:** 2026-07-31
**Parent documents:** `docs/design/buzz-phase5-product-claims-scope.md`, `docs/design/buzz-qortroller-gamer-mvp-v0.md`
**Binding rule:** if a gate in the scope doc is open, the phrases it guards are not sayable.

---

## 0. What this is

Phase 5 §4 WP-A asks for "a single table of allowed public phrases vs required
gates". This is that table. Every organizer-facing sentence — Buzz posts, the
one-pager, README language, a pitch deck line — resolves to a row here.

Two directions of use:

- **Writing:** find the claim grade you want, check its gates, and if any is
  open, drop to the grade below.
- **Reviewing:** for any published sentence, name the row it came from. A
  sentence with no row is not approved language, regardless of how true it feels.

The register does not invent new ceilings. It restates the ones the README,
the protocol invariants, and the scope doc already enforce, in the form a
non-engineer can apply to a sentence.

---

## 1. Claim grades

| Grade | Meaning | Who may say it |
|---|---|---|
| **G0 — mechanical** | A thing the software did, stated as a fact about the software | anyone, no gate |
| **G1 — candidate** | A verdict the system produced, explicitly labelled candidate/advisory | anyone, no gate |
| **G2 — verifiable** | A stranger can re-check the artifact themselves | requires G5-VER |
| **G3 — measured** | A population/error claim backed by a published measurement | requires the measurement gates |
| **G4 — tournament-grade** | Suitable for competitive integrity decisions | requires **all** gates |

Current permitted ceiling: **G1**, plus G2 for the artifacts named in §3.

---

## 2. The register

| # | Phrase (or equivalent) | Grade | Gates required | Sayable today |
|---|---|---|---|---|
| R-01 | "The session produced a signed PoSP record with verdict `SYNCHRONIZED`." | G0 | — | yes |
| R-02 | "The match digest is anchored on IoTeX testnet in tx `0x…`." | G0 | — | yes |
| R-03 | "`@EA` reports PV-CI green at N invariants." | G0 | — | yes |
| R-04 | "Candidate presence was observed for this session." | G1 | — | yes |
| R-05 | "L6B / PoEP verdicts are advisory and default-OFF." | G1 | — | yes (and must accompany any L6B mention) |
| R-06 | "Anyone can re-verify this match certificate with public tools: `python scripts/portcert_full_verify.py`." | G2 | G5-VER | **yes** — rehearsed, see §3 |
| R-07 | "Two independent gamers completed a sealed, pinned match." | G2 | G5-MULTI | no — developer-self only |
| R-08 | "Inter-person separation exceeds 1.0 across the required batteries." | G3 | G5-SEP | no — touchpad_corners open |
| R-09 | "Measured false-reject rate is X% at the published threshold." | G3 | G5-FRR | no — not published |
| R-10 | "Humanity is cryptographically proven for this session." | G4 | all | no |
| R-11 | "Tournament-grade anti-cheat." | G4 | all | no |
| R-12 | "Cheating cannot exist on QorTroller." | G4 | all | no — aspirational framing only, never as a product claim |

### VSS stream seat rows (draft — VSS-5)

Source: `docs/design/buzz-vss-stream-seat-scope-v0.md` §10. These rows are
**draft** until promoted in a reviewed commit. The gate column names the
VSS work package(s) that must be shipped before the phrase is sayable.

| # | Phrase (or equivalent) | Grade | Gates required | Sayable today |
|---|---|---|---|---|
| R-VSS-01 | "Stream seat is OPEN while capture and retina oracle process report up." | G0 | VSS-1..3 | yes — VSS-1..3 shipped |
| R-VSS-02 | "Seat events are digests + media URL pointers on Buzz." | G0 | VSS-2 | yes — VSS-2 shipped |
| R-VSS-03 | "Only human community members can open a seat; agents may view." | G1 | VSS-7 | yes — VSS-7 shipped (bot OPEN ban enforced) |
| R-VSS-04 | "Stream is humanity-proven / tournament-grade." | G4 | **Forbidden** until Phase 5 gates | **no — never at this scope** |
| R-VSS-05 | "Seat carries honesty ribbon (flags as-is)." | G0 | F1 / VSS-2..3 | yes — VSS-2..3 shipped |
| R-VSS-06 | "This room is watching sealed session `<session_id>`." | G0 | F2 when bind is real | no — F2 bind not yet live |
| R-VSS-07 | "Gamer self-asserted ioID claim accompanies this seat." | G1 | Optional only | yes — but only if ioid_token actually present |

### Phrases that are never sayable

Independent of gates, because no evidence can support them at this scope:

- "100% fair" / "unhackable" / "impossible to cheat"
- "Certified" for any population the corpus does not contain
- Any claim implying a ban decision is cryptographic truth (bans are human decisions informed by evidence)
- "Stream is humanity-proven" or "tournament-grade stream" (R-VSS-04 — oracle process health ≠ population cert)
- "Verified human live" for any stream seat (the seat is eligibility-gated, not proof-graded)
- "Cheating-proof stream" or any variant implying the seat prevents cheating

---

## 3. G5-VER — the one gate that closed

WP-C was rehearsed on the M17 sealed match: a fresh non-Windows clone now
reaches `OVERALL: VERIFIED` with public tooling and no operator keys. Full
transcript, command, and honesty flags: `docs/design/buzz-phase5-wpc-verifier-rehearsal.md`.

R-06 is therefore sayable **for the M17 certificate specifically**, and for any
later match certificate that reaches the same verdict by the same command. It
is not a claim about matches that have not been through that command.

Every other gate in scope-doc §3 remains open. No grade above G1 (outside R-06)
is unlocked by this.

---

## 4. Usage rules

1. **Cite the row.** An `#announcements` post or organizer doc making a claim
   above G0 names the row ID in the drafting thread. Not in the public text —
   in the review.
2. **Ceilings travel with the claim.** R-04 without "candidate" is R-10. The
   qualifier is part of the phrase, not a footnote.
3. **No silent upgrades.** A gate closing does not retroactively upgrade
   published language; the register is edited first, in a reviewed commit.
4. **`@EA` output is G0.** A green reply from the ACP gateway is a statement
   about the repository, never about a population. Phase 4 §6 forbids treating
   it as evidence.

---

## 5. Relationship to the enablement gates

| Gate | Rows it unlocks |
|---|---|
| G5-SEP | R-08 |
| G5-L6 / G5-L6B | qualifier removal on R-05 |
| G5-MULTI | R-07 |
| G5-FRR | R-09 |
| G5-VER | R-06 (**closed** — see §3) |
| G5-OPS | none directly; it is the Phase 4 acceptance precondition |
| all of the above | R-10, R-11, R-VSS-04 |

### VSS work package gates

| WP | Rows it unlocks |
|---|---|
| VSS-1..3 | R-VSS-01, R-VSS-05 (shipped) |
| VSS-2 | R-VSS-02 (shipped) |
| VSS-7 | R-VSS-03 (shipped — bot OPEN ban enforced) |
| F2 bind live | R-VSS-06 (not yet live) |
| Phase 5 all gates | R-VSS-04 (forbidden until then) |

---

**End of Phase 5 Claim Register (v0)**
