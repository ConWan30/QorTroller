---
type: ingredient
id: i-fcert007-followup-report
title: F-CERT-007 Follow-up Report (which N-gate governs developer_self) — verbatim
source: claude-code-investigation-2026-06-30
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

External evidence note (provenance only — VSD-INV-6). Verbatim text of the READ-ONLY F-CERT-007
Follow-up Report delivered by Claude Code on 2026-06-30. No paraphrase.

---

## F-CERT-007 Follow-up — Report

**SHOWN:**
- Call path: `scripts/poep_session_enroll.py:53` -> `single_subject_reflex_model(corpus_dir, player, a.min_n)`
  with `a.min_n` defaulting to **30** (`:47`, "developer-scoped data gate"). -> `l9_presence/poep_calibration.py:92`
  `single_subject_reflex_model(..., min_n=30)` filters sessions to one `player` (`:98`) and calls
  `population_reflex_model(sessions, min_n)`. -> `:43-48` `calibration_complete = len(rx) >= min_n` -> with
  min_n=30 the gate is **N>=30**. The verdict scorer `developer_self_liveness_verdict` (`:105-129`) re-checks
  `model["calibration_complete"]` (`:115`), i.e. the same N>=30 single-subject gate.
- The bridge reads this verdict: `poep_activation.read_session_poep_verdict` (`:54-73`) loads
  `~/.vapi/poep_session_verdict.json`, which `poep_session_enroll.py:75-80` writes from
  `developer_self_liveness_verdict` output -> the **single-subject** model's verdict.
- Live verdict file (`~/.vapi/poep_session_verdict.json`, read-only): `verdict=PRESENT`, `player=DEV`,
  `band=[161.8, 413.7]`, `n_reacted=10`, `n_in_band=7`, `in_band_fraction=0.7`, `session_path=DEV_05.poep.json`,
  `cert_scope=developer_self`, `channel=liveness_only`. This is the source the recorded proof's
  `poep_present=true` derived from (verdict ts `1782521615...` precedes the proof stream ts `1782523326...`).
- Measured band N (read-only compute over `poep_l9/`): DEV single-subject band = **52 in-band reactions,
  100% player "DEV"**, `calibration_complete=True`, `min_n=30`. The verdict's band `[161.8,413.7]` was built
  from `DEV_01..04` (fresh `DEV_05` excluded), N>=30 (PRESENT proves the gate passed); the population N>=50
  path (`poep_readiness`/`liveness_score`/`poep_verify`) is **not called** anywhere in this chain.
- `developer_self_cert_min_reflex_n` (config.py:2064, default 30): not imported or referenced in
  `poep_session_enroll.py` or `poep_calibration.py`. The N>=30 value comes from **two independent hardcoded
  literals** — argparse `--min-n` default (`enroll:47`) and the `min_n=30` function default
  (`poep_calibration:92`) — never the config field.

**ANSWER:**
- **Governing model: single-subject (min_n=30).** The population N>=50 L6B rule does not gate the
  `developer_self` enrollment path.
- **Measured N behind the recorded proof: 52 in-band reactions** (current DEV band; >=30 at enroll time when
  built from DEV_01..04) — **all single-subject (player "DEV")**. Note: 52 numerically exceeds 50 but is
  single-subject evidence, not across-humans population breadth; `per_player={'DEV': 52}`.
- **`developer_self_cert_min_reflex_n` status: confirmed-dead.** The effective gate is two hardcoded `30`
  literals; the config field is orphaned (matches Confirm-3 repo grep, now verified against the actual call
  chain).
- **Per-developer scoping: per-`player`-label, not per-identity.** `single_subject_reflex_model` filters by
  `s.player == player`; `enroll` defaults `--player DEV`. A second developer passing a distinct `--player`
  gets their own band (N=0 until they capture sessions) — isolated. A second developer reusing the default
  `"DEV"` label **pools into the shared band and inherits the first developer's count**. The verdict file is a
  single machine-global path (`~/.vapi/poep_session_verdict.json`), overwritten each enrollment. So isolation
  depends on the operator choosing a distinct label — it is not enforced by identity.

**GRADE: VERIFIED**

### Anomalies / drift surfaced (report only, not fixed)
1. **Numeric coincidence masks a semantic gap:** the DEV band is N=52, which trips past the *number* 50 but
   is 100% one subject. A reader seeing "N=52" could misread it as satisfying the population N>=50 rule; it
   does not — `per_player={'DEV':52}` is single-subject. The honesty rail that prevents this is
   `cert_scope=developer_self` + `population_certified=False`, not the N value.
2. **Triple-sourced N>=30, none authoritative:** the developer gate exists as (a) `enroll --min-n` default 30,
   (b) `single_subject_reflex_model(min_n=30)` default, (c) the dead `config.developer_self_cert_min_reflex_n=30`.
   Three copies of the same constant; the config field that *looks* canonical is the one not wired. Changing
   the operator-facing config would silently do nothing.
3. **Verdict carries no band-N:** `~/.vapi/poep_session_verdict.json` records `n_reacted`/`n_in_band` (this
   session) but not the band's calibration N — so the proof artifact alone cannot show what evidence base
   authorized it; it required reading the corpus. An auditor of the proof stream cannot see the
   N=52/single-subject fact without filesystem access to `poep_l9/`.
4. **Shared default label is a latent multi-developer hazard:** two developers on one machine both defaulting
   to `--player DEV` would silently share one band and one verdict file, with no identity binding distinguishing
   them.
5. **Band drift between enroll and now:** verdict band `[161.8,413.7]` (DEV_01..04) vs current `[159.5,429.3]`
   (DEV_01..05) — the live `read_session_poep_verdict` (max_age 7200s) would abstain once stale, but the band a
   future enroll builds differs from the one that authorized the recorded proof. Expected (corpus grew), noted
   for reproducibility.
