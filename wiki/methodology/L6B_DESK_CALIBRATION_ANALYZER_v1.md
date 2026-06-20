# L6B Desk Calibration — True-Latency Classifier & human_max Recommendation v1

| Field | Value |
|---|---|
| Status | **DRAFT** — operator review before production `human_max` change |
| Date | 2026-06-20 |
| Parent | `CCO_PHASE_B_DESIGN_v1.md` §5; F-L6B-CAL-005 |
| Code | `bridge/controller/l6b_reflex_analyzer.py`; `bridge/vapi_bridge/l6b_desk_session.py` |

---

## 1. Problem (empirical)

Desk/USB L6B calibration at **R2 force=200, rigid mode, hold=300ms** produced usable IMU peaks (56/59 ≥ 500 LSB) but the **legacy classifier** (`index × 8ms`, ignoring `probe_ts`) mis-bucketed slow human reflexes:

- **26 HUMAN / 26 REFLEX_OBSERVED** at legacy bands (80–280ms index)
- **26 INCONCLUSIVE**, of which **23 were slow (>280ms index)** — mostly index inflation, not absent reflex
- **3 HUMAN rows** had `true_latency_ms > 280` while legacy index said HUMAN (index understates wall time when poll jitter stretches gaps)
- **4 BOT** — all `true_latency ≈ 0.1ms`, `reflex_gap_ms ≈ 0` (mechanical actuator coupling, not neuromotor)

F-L6B-CAL-005 diagnostics already computed ground-truth `true_latency_ms` from `t_mono`; classification did not consume it until this amendment.

---

## 2. Candidate A — Classify on `true_latency_ms` (implemented)

**Rule:** When post-probe reports carry `t_mono ≥ probe_ts`, classify on:

```text
true_latency_ms = (crossing_t_mono - probe_ts) × 1000
```

where **crossing** = first frame with `|accel_mag - pre_mean| ≥ response_threshold_lsb` (500 LSB default).

**Fallback:** Reports without `t_mono` retain legacy `index × MS_PER_REPORT` (8ms) — bridge tests and pre-F-L6B-CAL-005 corpora unchanged.

**Storage:** `l6b_probe_log.latency_ms` = canonical (true preferred). Diagnostic table retains both `legacy_latency_ms` and `true_latency_ms`.

**Mechanical coupling guard:** If `true_latency_ms < human_min_ms` **and** `reflex_gap_ms < 50ms` (precursor→crossing), classify **INCONCLUSIVE** not HUMAN — separates motor spin-up from neuromotor loop.

---

## 3. Candidate B — Desk `human_max_ms = 350` (recommended for calibration only)

| Context | `human_max_ms` | Rationale |
|---------|----------------|-----------|
| Production / tournament default | **280** | Phase 63 neuromotor upper bound; unchanged unless operator amends |
| Desk/USB operator-fired sessions | **350** | Empirical desk corpus: median HUMAN `true_latency ≈ 230ms`; tail to ~320ms with USB poll jitter + cortical loop |

**Desk env (canonical actuator already validated):**

```env
L6B_PROBE_R2_FORCE=200
L6B_PROBE_MODE=rigid
L6B_PROBE_HOLD_MS=300
L6B_HUMAN_MAX_MS=350
```

`DeskProbeConfig.human_max_ms` defaults to **350** for `scripts/l6b_desk_reaction_session.py`. Bridge auto-probes keep config default **280** until operator sets env.

---

## 4. Corpus snapshot (desk-P1, force=200/rigid/300ms, pre-fix labels)

| Metric | Count |
|--------|------:|
| Total probes in `l6b_probe_log` | 59 |
| Legacy HUMAN / REFLEX_OBSERVED | 26 |
| Legacy INCONCLUSIVE (slow >280ms index) | 23 |
| Legacy BOT | 4 |
| Legacy NO_RESPONSE | 3 |
| Peaks ≥ 500 LSB | 56 (95%) |

**Post-fix replay** (`scripts/l6b_corpus_reclassify_report.py`, 2026-06-20):

| Subset | human_max | HUMAN / REFLEX_OBSERVED | INCONCLUSIVE | BOT | NO_RESPONSE | Total |
|--------|-----------|----------------------:|:------------:|:---:|:-----------:|------:|
| force=200 desk corpus | 350 | **38** | 14 | 4 | 3 | **59** |
| All probes (incl. force=128 era) | 350 | 38 | 35 | 4 | 57 | 134 |

Legacy labels on force=200 subset: 26 HUMAN → **38 HUMAN** (+12) after true-latency + desk max.

---

## 5. Operator gate item 2 (N≥50) — assessment

`CCO_PHASE_B_DESIGN_v1` §5 item 2: *Operator attests **N≥50** L6B calibration sessions.*

| Criterion | Verdict |
|-----------|---------|
| **Probe count N≥50** | **YES** — 59 desk probes logged @ force=200 |
| **DualSense-class hardware path** | **YES** — USB DualSense Edge, IMU + adaptive trigger |
| **Meaningful REFLEX_OBSERVED density** | **YES after fix** — 38/59 (64%) on force=200 corpus @ human_max=350 |
| **`L6B_ENABLED=true` production flip** | **NOT YET** — still requires operator attestation + Phase B merge per §5 |

**Conclusion:** Data volume **closes the N≥50 count gate**. Analyzer fix + desk `human_max=350` **closes the label-honesty gap** for slow human reflexes; operator may attest item 2 on probe count while treating REFLEX_OBSERVED rate as calibration quality (not a hard gate threshold in §5).

---

## 6. Stop / regression rails

- Production `L6B_ENABLED=false` default unchanged.
- Legacy-only reports (no `t_mono`) → byte-identical classification path.
- BOT discrimination unchanged for `true_latency < 15ms`.
- Do **not** widen production `human_max` to 350 without separate operator GO — desk calibration is a distinct posture (USB-only, operator-paced ENTER probes).

---

## 7. Citation

`L6B_DESK_CALIBRATION_ANALYZER_v1 §X [Tier 3 DRAFT; desk calibration 2026-06-20]`
