# A2A-POEP-P2 · Round 02 · Grok Design

**Role:** model designer + data-quality adversary  
**Inputs:** Claude round-01 grounded corpus (bridge.db `l6b_probe_log` + `l6b_probe_diagnostic`)  
**Rails held:** population model only · no liveness verdict · peak=0 is candidate-artifact · `poep_enabled=False`  
**Date scope:** design proposals only — no code, no enablement, no chain write

---

## 0. Data-quality red team (adversary pass first)

Before proposing a model, the corpus itself is contested.

### DQ-1 · “189 valid” is a classification count, not a calibration count
- **Claim under attack:** 189 `REFLEX_OBSERVED` / HUMAN-classified probes are usable calibration material.
- **Attack:** Classification is latency-primary. Registered Edge (`581a836c…`) contributes 26 in-band probes with **accel_peak median = 0**. Those are latency-only admissions with **no IMU corroboration**. If HUMAN was assigned on the 80–350 ms band alone, the headline mixes (a) biomechanically corroborated reflexes and (b) timing windows without motion evidence.
- **Honest restatement:** usable calibration N is not 189 and not even 102 in-band; the **IMU-corroborated floor is ≈76 (desk-P1)**. 189 is an upper-bound on *observed-latency events*, not on *reflex-band population samples*.

### DQ-2 · peak=0 is a candidate-artifact, not a physiological zero
- **Rails say:** peak=0 is candidate-artifact. Design must not treat 0 as “still human, just quiet.”
- **Attack surface:** If capture path (USB HID IMU ring empty, diagnostic path not wired, still-hold vs adaptive-trigger desync, wrong device stream) zeros accel, latency alone still lands in-band → **false calibration mass**.
- **Consequence:** Any model that pools registered-Edge peak=0 rows with desk-P1 peak≈1038 rows learns a **bimodal garbage mixture**, not a population distribution. Peak=0 rows are **quality-holdout / artifact class**, not negative examples of “weak human.”

### DQ-3 · Two populations, opposite signatures → not exchangeable
| Population | n in-band | latency med / sd | accel_peak med | Interpretation |
|---|---:|---|---:|---|
| Registered Edge `581a836c…` (VMDR on-chain) | 26 | 320 / 36 | **0** | Tight, slow, **IMU-dead** — capture-path suspect |
| desk-P1 | 76 | 208 / 71 | **1038** | Mid-band, wide, **IMU-live** — only clean population |

- **Attack:** Treating these as one “PoEP corpus” invents a fictional population. The on-chain device’s weaker signal is not “the real tournament fingerprint is quieter”; it is **evidence that registered-Edge L6b capture is incomplete or path-buggy**.
- **Constraint on claim:** Until registered-Edge in-band probes show non-zero IMU corroboration at N≥50, **PoEP cannot honestly claim a calibrated population model for the on-chain node**. Desk-mode can support a **lab / path-B population prior**, not a device-attested Edge model.

### DQ-4 · Diagnostic_json richness is unused and unvalidated
- 873 diagnostic rows with `true_latency_ms`, `precursor_gap_ms`, `reflex_gap_ms`, full feature vector — but round-01 does not report:
  - missingness rates per field
  - agreement between `true_latency_ms` and `l6b_probe_log` latency
  - whether peak=0 rows still have non-empty force-curve / grip micro-adjustment (if yes → IMU path broken but other sensors live; if no → total dead features)
- **Attack:** Building a multi-feature signature on un-audited JSON is cargo-cult. Gate 0 must be a **schema + completeness audit** before any LOO story.

### DQ-5 · HUMAN-only labels = no adversarial / null class in-band
- All 189 REFLEX_OBSERVED are HUMAN-classified. There is **no labeled bot / no-human / open-loop / timed-macro** class in the same band.
- **Attack:** You cannot estimate false-accept rate from a one-class corpus without constructing an **explicit null** (synthetic or hardware-open-loop). Latency band membership ≠ human. Macro bots can land in 80–350 ms by design.

### DQ-6 · N and independence
- desk-P1 n=76 > 50, but **independence is unproven**: same player, same desk session, possible burst capture → effective sample size << 76.
- Registered Edge n=26 **fails** the N≥50 gate even before IMU filtering.
- **Attack:** Claiming “N≥50 satisfied” without session/player clustering understates variance and inflates calibration confidence.

### DQ-7 · Band ceiling pile-up
- Registered Edge median **320 ms** with sd 36 near the **350 ms** ceiling → right-censoring risk, selection of slow tail only, or mis-aligned stimulus onset (latency clock starts late → values compress upward).
- **Attack:** A population model fit on ceiling-hugging Edge rows will not transfer to mid-band desk physiology (or vice versa).

**Red-team verdict:** Proceed with design, but **calibration corpus = IMU-corroborated subset only (desk-P1 primary)**. Registered-Edge peak=0 is **out of calibration pool** until capture is fixed. Headline 189 is **not** the design N.

---

## Q1 · Model definition

### Proposal `P2-Q1-RBM-v0` · PoEP Reflex-Band Population Model (RBM-v0)

| Field | Content