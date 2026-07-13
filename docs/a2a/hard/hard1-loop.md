# A2A-HARD-1 — authorship-chain hardening loop (F-T66B-1 close + adversarial certification)

**Chartered 2026-07-13 (operator: "go HARD-1").** Sibling of A2A-PKG, same bus + mailbox, **ROLES
FLIPPED**: **Claude builds**, **grok is the ADVERSARY + VERIFIER** (ruling (a) is symmetric — the
OTHER agent verifies; grok has never held the verifier seat until now). Runs while the operator's
PKG dogfood is pending; the operator's next match validates both arcs at once.

## Subject
1. **Close F-T66B-1** — own-kill OCR recall (0/21 measured live, T6.6b): the fresh-feed watcher
   (`qt-kf-fresh`) fires the rapidocr read when the killfeed REGION CHANGES, instead of the
   throttled tune tick. Screen-driven → works despite the dual-connection-blind HID.
2. **Adversarially certify the authorship chain** (folds in the AH-1 backlog): grok designs attack
   rounds vs card→OCR→killer-slot→sink→v3; Claude patches what lands; grok verifies the patches.

## Roles
| Agent | Role |
|---|---|
| **Claude** | Builder: implement fixes/patches, tests-first, PV-CI-clean, staged only |
| **grok** | **Adversary**: ≥3 concrete attacks per round `{id · attack · expected-break · why-it-matters}` — spam-forged feed rows, OCR-poison handles (the `QorTro1a300` class), replayed crops, diff-storms, sink poisoning. **Verifier**: audits Claude's build per ruling (a) before staging is accepted |
| **Operator** | Arbiter + sole committer; live validation on the next rig session |

## Rails (all standing rails + these)
Zero-false-read is the invariant that must SURVIVE every patch — recall gains never buy false
authorship. `canon()`/killer-slot semantics unchanged unless an attack proves them broken. No PoAC /
FROZEN / chain / secrets. Attack fixtures are synthetic or from the operator's own archives — never
fabricated "evidence". DOC side-deliverable: `docs/pilot-kit-quickstart.md` before loop close.

## Stop criterion
Two consecutive grok attack rounds land zero new breaks (the chain holds) → synthesis + hand the
recall claim to the operator's live match for the empirical number.

---
*HARD-1 charter — 2026-07-13. Rounds in `docs/a2a/hard/round-*.md`; envelopes on the shared bus.*
