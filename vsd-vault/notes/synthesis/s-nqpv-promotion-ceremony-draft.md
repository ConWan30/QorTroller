---
type: synthesis
id: s-nqpv-promotion-ceremony-draft
title: Draft Promotion Ceremony Text for NQPV Study + Config Flip (from advisory to regime that can certify)
created: 2026-06-26T21:10:00Z
modified: 2026-06-26T21:10:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 20
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-nqpv-arc-overall-assessment", "s-presence-oracle-liveness-readiness-checklist", "specs/nqpv-defensibility-study.md"]
---

# Draft Promotion Ceremony Text (NQPV / Presence Oracle Liveness)

This is a proposed operator ceremony script / gate text for flipping NQPV (and its required presence oracles) from default-off advisory to a state where the calibrated model + study harness output can be used for certification decisions.

## Ceremony Command (example)
```bash
python scripts/promote_nqpv_presence.py \
  --regime FULL \
  --harness-report audits/nqpv-harness-FULL-YYYYMMDD.json \
  --corpus-snapshot vsd-vault/corpus/snapshot-... \
  --confirm "I understand this promotes NQPV from advisory to a certified-enabling regime. Human-TAR must meet or exceed the best single oracle. Anti-GCAP rail verified. Presence oracles (PoEP + coupled-retina) are live."
```

## Exact Phrase (must match)
"I understand this promotes NQPV from advisory to a certified-enabling regime. Human-TAR must meet or exceed the best single oracle. Anti-GCAP rail verified. Presence oracles (PoEP + coupled-retina) are live."

## Pre-Ceremony Checklist (operator must attest)
- [ ] Readiness checklist (s-presence-oracle-liveness-readiness-checklist) fully green.
- [ ] Study harness report for the live-oracle regime shows:
  - Fused human-TAR >= best single-oracle human-TAR (anti-GCAP rail).
  - Acceptable FAR envelope.
  - ROC operating point selected (weights + threshold).
- [ ] Real human corpus breadth documented (N per player, players).
- [ ] Modeled vs real-adversary caveat recorded (if any).
- [ ] Public surface updated: advisory=False, certified=True in VAPIPresenceProof and /player/presence-proof.
- [ ] Configs staged: nqpv_cocapture_enabled, poep_liveness_enabled, any retina live flags.
- [ ] No blocking FSCA / invariant violations.
- [ ] Wallet / chain posture allows (or test with paused first).

## Post-Ceremony Actions
1. Flip config (env or bridge/.env).
2. Restart bridge (or hot-reload if supported).
3. Re-run harness on next N sessions as smoke.
4. Update CLAUDE.md / arc assessment with promotion date + evidence hashes.
5. Announce to operators / tournament consumers: "NQPV presence proof now carries certified signal when oracles live."

## Reversion
- Flip flags back to False.
- Revert public surface to advisory.
- Log reason in invariant_gate_log or equivalent.

**Rationale (from arc):** The study proved separation only in FULL live-oracle regime. Promotion must be gated on actual liveness + measured envelope, not simulation. Matches QorTroller verification-over-assertion principle.

This draft can be turned into a script + enforced in CI / operator tools.
