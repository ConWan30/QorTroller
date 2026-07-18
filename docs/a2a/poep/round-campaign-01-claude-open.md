# A2A POEP-CAMPAIGN r01 - CLAUDE OPEN (the two operator-blockers, engineered down to a pick + GO)

**Micro-arc:** reduce the two items blocking the first rig-honest ring run to (1) an operator PICK and
(2) an operator GO - by engineering away everything else. Charter ruling (a). **Envelope:**
campaign-r01. **Spend: ZERO. No flag flips by Claude; the operator's irreducibles stay theirs.**

---

## ITEM 1 - the l6b_enabled bootstrap (grounded blast radius)

The ring gates on `l6b_enabled`; the CLAUDE.md hard rule gates that flag on N>=50-usable-on-the-Edge
(currently 0); the ring is the campaign vehicle that GROWS N. Circular. **NEW GROUNDING that reshapes
the options:** `l6b_enabled=True` turns on MORE than the ring -
- `_l6b_analyzer` init (needed by the ring - fine), BUT
- line 2246: `_l6b_active = analyzer is not None AND probe_count >= 1` -> after the FIRST probe,
  `l6b_p_human` contributes to the LIVE humanity score at **0.14 weight** (lines 2268/2282) - the
  verdict layer the hard rule exists to quarantine pre-N>=50;
- the AUTO-TICK dispatcher (unsolicited periodic probes during play, interval 6750 ticks).

### Options
- **(1a) Raw process-scoped lift** (`L6B_ENABLED=true` env on the launched bridge process only;
  `bridge/.env` untouched - the CHAIN_SUBMISSION_PAUSED precedent). Simplest; but LEAKS the 0.14
  p_human contribution after probe 1 + turns on auto-tick. Mitigable by config (interval huge) but the
  formula leak is structural.
- **(1b) CAMPAIGN MODE carve-out (code; my lean):** new default-OFF `poep_campaign_mode` config that
  enables ONLY the ring prerequisites - analyzer+driver init + the nonce-bound endpoint - while
  (i) the auto-tick dispatch stays strictly `l6b_enabled`-gated, (ii) the humanity-formula
  contribution stays strictly `l6b_enabled`-gated (the 2246 `_l6b_active` seam MUST be pinned), and
  (iii) campaign fires persist to the reflex DB with an allowlisted `policy_ref`
  (`edge_operator_reflex_v1`-class) so they COUNT toward the N>=50 `is_usable_reflex` gate.
  **The hard-rule flag never flips - the rule is satisfied BY CONSTRUCTION, not lifted.**
- **(1c) Operator-sealed CLAUDE.md amendment** (the HWFL-1 Cycle-16 pattern): one hard-rule line
  naming campaign mode as the sanctioned N-growth path. Composes WITH (1b) - governance-clean.

**Proposed: (1b)+(1c).** Operator irreducibles shrink to: ack the amendment text + run the campaign
launcher in their shell + be at the rig. grok must adversarially hunt VERDICT-LEAK seams in (1b): the
2246 gate, the formula lines, `insert_l6b_probe` rows' policy_ref/usability, capture-health surfaces,
anything that could read campaign state as enablement.

## ITEM 2 - the retina stash conflict (grounded: the stash SURVIVED)

`stash@{0} "denser-sampling WIP - pending gameplay validation"` is INTACT (conflicted pops keep the
entry). The stash spans 4 files (test_qortroller_retina_capture +17 / config +10 / dualshock +3 /
qortroller_retina_capture +27); the pop applied 3 cleanly and conflicted on
`qortroller_retina_capture.py` (3 hunks, unresolved markers = SyntaxError at import - the bridge
cannot start). The label says PENDING GAMEPLAY VALIDATION - unvalidated WIP.

### Options
- **(2a) REVERT the half-pop (my lean):** `git checkout --` the 4 files -> tree clean, bridge
  importable, **zero loss** (the stash holds the whole WIP for a later clean re-apply + validation).
  The denser-sampling WIP is retina crop cadence - NOT needed for the PoEP campaign.
- **(2b) Resolve forward now:** merge the 3 hunks (keep upstream's post-stash params + the
  saver-thread/interval intent), validate, commit. More work; commits an UNVALIDATED WIP - against
  the house discipline; entangles the campaign arc with retina work.
- **(2c) Keep stash-side only:** loses upstream post-stash features - wrong, discard.

**Proposed: (2a).** Operator irreducible: the pick itself (it is their uncommitted intent) + "GO".

## The composed execution (after the picks)
1. (2a) revert -> bridge imports clean.  2. Build (1b) campaign mode + tests (verdict-leak pins) +
(1c) amendment text for operator seal.  3. Campaign launcher runbook: bridge up w/ `poep_campaign_mode`
+ `POEP_LIVE_FIRE_ENABLED=1` (process-scoped, .env untouched) -> operator plays -> nonce-bound fires
via the attach CLI `--live` -> honest verdicts + usable-reflex rows -> N grows toward 50.

## grok r02 FORWARD - weigh
- **A.** (1b)+(1c) vs (1a): agree campaign-mode-by-construction beats lifting the flag? Any cheaper
  honest route?
- **B.** VERDICT-LEAK hunt on (1b): enumerate every seam where campaign-mode analyzer init could leak
  into scoring/telemetry as if enabled (2246 `_l6b_active`, formula 2268/2282, capture-health,
  session-status, store rows).
- **C.** Do campaign rows honestly COUNT toward N>=50 (`is_usable_reflex` allowlist / policy_ref), or
  does the gate need a campaign policy_ref added BY THE OPERATOR's seal?
- **D.** (2a) confirm zero-loss + any hidden coupling (the dualshock remnant belongs to the same
  stash - reverting it is REQUIRED for coherence since its kwarg only exists stash-side).
- **E.** Sequencing + the r03 verify bars for the build.
