---
type: synthesis
id: s-nqpv-persistence-presence-liveness-scope
title: NQPV promotion prerequisite scope — persist the nqpv_* sidecar (dedicated co-capture table, mirroring retina_*_log) + the presence-oracle liveness split (PoEP config-gated, coupled-retina screen witness hardware-gated); the study harness re-runs unchanged once the rows carry live presence oracles
created: 2026-06-26T17:55:00Z
modified: 2026-06-26T17:55:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the ONE remaining prerequisite for promoting the NQPV calibrated model from advisory ->
certifying, surfaced by the cycle-31/32 study build ([[s-nqpv-study-corpus-harness-built]]): the
study harness PASSES only when the PRESENCE oracles are live, but today's regimes FAIL because (a) the
nqpv_* co-capture is not persisted to a queryable place and (b) the presence oracles (PoEP +
coupled-retina screen witness) are not live. This note designs (a), and honestly splits (b) into
config-gated vs hardware-gated. It is a SCOPE note; the build + the schema decision are operator-gated.

THE TWO HALVES (independent; (a) is agent-buildable now, (b) is not fully):

(a) PERSISTENCE WIRING -- agent-buildable now.
  The live-loop co-capture hook already derives nqpv_* fields onto the PITL meta sidecar
  (cocapture_fields_from_pitl_meta, default-off NQPV_COCAPTURE_ENABLED), but
  main.IngestService.on_record maps only a FIXED set of pitl_* columns onto the persisted record, so
  the nqpv_* keys are dropped before insert_record. Today's only queryable oracle is l4_l5_l6_ok
  (derived from persisted pitl_humanity_prob). Two designs:
    - Option A: ALTER records ADD COLUMN nqpv_cco_tier / nqpv_l4l5l6_ok / nqpv_poep_present /
      nqpv_retina_coupled_verdict. REJECTED-LEANING: bloats the already-5.4GB / ~925k-row hot records
      table (the ambient-floor finding [[s-ambient-floor-s1-s3-findings]]); the columns are sparse
      (only populated when co-capture is on); couples NQPV's research surface to the core PoAC table.
    - Option B (RECOMMENDED): a DEDICATED nqpv_cocapture_log table mirroring the retina_*_log
      precedent exactly -- `id AUTOINCREMENT PK, device_id TEXT, record_hash_hex TEXT, nqpv_cco_tier
      TEXT, nqpv_l4l5l6_ok INTEGER, nqpv_poep_present INTEGER, nqpv_retina_controller_signal TEXT,
      nqpv_retina_coupled_verdict TEXT, created_at REAL` + `idx_..._created_at DESC`. Insert one row
      per co-captured record from on_record (or the live loop) ONLY when nqpv_cocapture_enabled.
      Keeps the hot records table byte-identical; matches the existing retina logging discipline;
      bounded/prunable like the other telemetry logs.
  THE LOADER ALREADY CONSUMES OPTION B: nqpv_corpus_loader.load_from_rows normalizes the co-capture
  sidecar shape (the nqpv_* keys), and a thin new store boundary get_nqpv_cocapture_rows(limit) feeds
  it -- NO loader change. tri-state INTEGER bools (NULL = abstain) round-trip through the existing
  _as_bool. So (a) = one CREATE TABLE + migration + one insert method + one get method + the on_record
  mapping + tests. Mechanical; no FROZEN/PoAC/chain touch.

(b) PRESENCE-ORACLE LIVENESS -- partly config, partly hardware-gated.
  - PoEP (nqpv_poep_present): PoEP exists (l9_presence/) but is default-OFF (poep_enabled=False)
    behind its own L6B N>=50 neuromuscular-reflex calibration gate (a CLAUDE.md hard rule). Making
    nqpv_poep_present live = run PoEP per session + thread its present/absent verdict into the
    co-capture meta. Gated on the L6B corpus, NOT on this wiring. Until then it abstains honestly.
  - Coupled-retina / screen witness (nqpv_retina_coupled_verdict = COUPLED_CLEAN/LIVE_COHERENT):
    structurally HARDWARE-GATED -- the screen lobe needs a camera observing the display (the capture
    rig, [[project_l9_retina_fusion_capture_rig]], PRs held). The controller-lobe signal we DO capture
    is metadata only and must never be promoted to the coupled verdict (the loader enforces this).
  HONEST CONSEQUENCE: shipping (a) alone moves the study from "l4l5l6 only" to "cco + l4l5l6" live
  (the COCAPTURE regime), which the harness already PROVED still FAILS (replay carries real HW +
  physics). So (a) is necessary plumbing but does NOT by itself unlock certification -- (b) is the
  load-bearing unlock. The value of (a) now is a real persisted corpus to dry-run the harness against
  + readiness for the moment (b) lands.

WHAT STAYS UNCHANGED: the harness, loader, synth, and calibrated model re-run with ZERO code change
once the co-capture rows carry live presence oracles -- the operating point is then set by the
measured ROC + the mandatory anti-GCAP rail (fused human-TAR >= best single-oracle TAR). The
sharpening (COUPLED_CLEAN-as-presence) is already shipped and not contingent on any of this.

HONESTY RAILS / BOUNDARIES: measurement-first; NQPV stays default-off advisory until an operator-gated
promotion after a regime that actually separates. No FROZEN-v1 / 228B PoAC / chain / IOTX. The schema
decision (Option A vs B) is the operator's; this note RECOMMENDS B with reasons. Related:
[[s-nqpv-study-corpus-harness-built]], [[s-nqpv-defensibility-study-scope]], [[l9-presence-arc]].
