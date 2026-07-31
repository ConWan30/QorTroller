# Buzz × QorTroller — Phase 5 Claim Register (v0)

**Status:** DESIGN (WP-A) — binding for public language  
**Date:** 2026-07-31  
**Parent:** `docs/design/buzz-phase5-product-claims-scope.md`  
**Also constrains:** README claim ceilings, `#announcements`, organizer one-pagers

---

## 0. Purpose

This register is the **only** allowed mapping from public phrases to
enablement gates. If a phrase is not in this table, it is not allowed
in product-facing copy until a new row is added under operator review.

**Hard rule:** no free-text “tournament-ready” / “tournament-grade” /
“certified fair” without a closed gate row cited in the same document
or post.

---

## 1. Gate legend

| Gate | One-line meaning |
|---|---|
| **G5-OPS** | Phase 4 ACP live ops acceptance signed off |
| **G5-VER** | Independent verifier path: stranger re-checks a sealed package |
| **G5-MULTI** | ≥2 distinct gamer ioID claims on a real sealed match |
| **G5-SEP** | Inter-person separation batteries all pass (`all_pairs_above_1`) |
| **G5-L6** | L6 haptic CR enabled after N≥50 calibration + ceremony |
| **G5-L6B** | Live PoEP / L6B presence after measured corpus + ceremony |
| **G5-FRR** | Field FRR/FAR proxies published with hold-out policy |

Until a gate is closed, treat it as **open**.

---

## 2. Allowed phrases (current)

| Phrase (public / organizer / Buzz) | Minimum closed gates | Notes |
|---|---|---|
| “Candidate presence digests on Buzz” | none (Phase 1–3) | Default honest floor |
| “Session postcard with honesty flags” | none | Must include `poep_enabled` / `l6b_enabled` / `candidate_ok` as-is |
| “Operator EA status bot on `#rig-ops`” | none | Path A bot; not ACP |
| “Operator ACP surface (`@EA`) for engineering hygiene” | **G5-OPS** | Never cite as population evidence |
| “Match result pinned with cryptographic pointer” | none | Pointer ≠ population certification |
| “Gamer self-asserted ioID claim on Buzz” | none | Claim only; proof stays in QorTroller / IoTeX |
| “Third party can re-verify this sealed match package” | **G5-VER** | Must link the exact verify command |
| “Multi-gamer sealed session (N≥2 ioIDs)” | **G5-MULTI** | Distinct wallets/npubs required |
| “Inter-person separation demonstrated on required batteries” | **G5-SEP** | Cite corpus + ratios |
| “L6 challenge-response enabled on this build” | **G5-L6** | Ceremony-attested only |
| “Live PoEP / L6B presence enabled on this build” | **G5-L6B** | Ceremony-attested only |
| “Field FRR/FAR proxies published for enabled stack” | **G5-FRR** | Report must be pinned |
| “Tournament-grade presence claims” | **G5-SEP + G5-L6/L6B + G5-FRR + G5-MULTI + G5-VER** | All five required; G5-OPS recommended |

---

## 3. Forbidden phrases (until gates close)

Do **not** use these without the corresponding closed gates and a
register update:

- “Tournament-ready” / “tournament-grade” (needs full set above)
- “100% fair” / “cheat-proof forever”
- “Population certified from developer-self data alone”
- “Ban is cryptographic truth” (social adjudication ≠ proof)
- “EA / ACP proved the gamer is human” (EA is steward, not gamer)
- Any implication that digests on Nostr contain biometric substrate

---

## 4. How to cite this register

In `#announcements`, organizer docs, or README claim sections:

```text
Claim: <exact phrase from §2>
Gates: <G5-… list>
Register: docs/design/buzz-phase5-claim-register.md (v0)
```

If the phrase is not in §2, **do not publish** — open a design PR to
add a row first.

---

## 5. Current gate status (honest snapshot, 2026-07-31)

| Gate | Status |
|---|---|
| G5-OPS | **Open** — code landed; ops checklist pending operator sign-off |
| G5-VER | **Open** — WMP/PORT-CERT tooling exists; product runbook not yet signed |
| G5-MULTI | **Open** — single-operator / dev-self demos only |
| G5-SEP | **Partial** — AIT cleared; touchpad_corners still a blocker |
| G5-L6 | **Open** — default-OFF; N below threshold |
| G5-L6B | **Open** — advisory / operator-gated |
| G5-FRR | **Open** — not published at product scope |

Therefore the **maximum allowed public language today** is the “none”
and Phase 1–3 rows in §2. Everything stronger is blocked.

---

## 6. Relationship to ACP (Phase 4)

A green `@EA invariant status` or `@EA health` reply is **engineering
hygiene**, not a claim-register event. It does not close G5-SEP,
G5-L6, G5-L6B, G5-MULTI, G5-FRR, or G5-VER.

---

## 7. Change control

- Adding a phrase or lowering a gate requirement is a **governance**
  change: design PR + operator review.
- Closing a gate requires the evidence named in
  `buzz-phase5-product-claims-scope.md` §3, pinned and linked from
  this register’s status table in a follow-up commit.

---

**End of Phase 5 Claim Register (v0)**
