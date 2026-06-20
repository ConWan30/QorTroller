# Trio-Retina Integration Impact Assessment — QorTroller

**As of:** 2026-06-19  
**Scope:** Advisory perception sidecar integrated into bridge, adjudicator, FSCA, provenance DAG, and observability APIs. W3bstream/DA/PV-CI explicitly deferred (operator GO).

---

## 1. What Trio-Retina is in QorTroller terms

Trio-Retina is an **advisory perception layer** that runs over trailing HID windows (~120 frames at 1 kHz) from the certified DualSense Edge pipeline. It embeds controller dynamics into a world-state representation and emits trajectory-anomaly events. Each window can produce a **`VAPI-RETINA-STATE-v1`** commitment (`retina_state_commitment.py`) stored in `retina_event_log` with optional cross-links to PoAC `record_hash_hex`.

**Three commitment axes must not alias:**

| Axis | Domain tag / role |
|------|-------------------|
| TinyML world model | `world_model_hash` (L3 behavioral classifier) |
| Arc 7 PQ sidecar | `pq_commitment` (32-byte ML-DSA pointer, off-chain) |
| Retina perception | `VAPI-RETINA-STATE-v1` (HID-window state commitment) |

Retina does **not** grow the 228-byte PoAC wire frame. It is a read-only sidecar on ingestion and audit surfaces.

**Default posture:** `retina_perception_enabled=False` until operator enables after calibration audit.

---

## 2. Integration surfaces (shipped)

### 2.1 Ingestion (Phase B)

- `dualshock_integration.py` — optional `pitl_meta` retina keys when enabled
- `retina_controller_embedder.py` — pure embed + anomaly detection
- `retina_perception.py` — orchestration, persistence, evidence slice builder

### 2.2 Session adjudication (read-only enrichment)

- `session_adjudicator.py` — `_enrich_retina_evidence()` injects `evidence_json.retina` with per-record bindings (`record_hash`, `state_commitment`, `anomaly_count`, `event_count`)
- **No verdict math change** — LLM and rule fallback see richer context only

### 2.3 Fleet Signal Coherence (cross-oracle)

Two new **CONTRADICTION** rules (MEDIUM severity, `guard: retina_perception_enabled`):

1. **`RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY`** — retina anomalies present but L4 Mahalanobis below continuity threshold
2. **`L4_ANOMALY_WITHOUT_RETINA_SIGNAL`** — L4 above anomaly threshold (24h window) with no matching retina anomaly row

Total `CONTRADICTION_RULES`: **30** (unchanged by this observability goal).

Dry-run classifier: `classify_cross_oracle_window()` in `retina_perception.py` mirrors FSCA logic for replay audits.

### 2.4 Provenance DAG

- `corpus_curator_agent.py` — `POAC_RECORD` parent (`POAC_INGEST`) → `RETINA_STATE_COMMITMENT` child (`PERCEPTION_BINDING`)
- `provenance_nodes.poac_record_node_id()` — canonical node id shared with operator API
- `GET /agent/data-provenance-chain?record_hash=` — resolves parent + `retina_commitments[]` children

### 2.5 Operator / SDK / agent tooling (this goal)

| Surface | Purpose |
|---------|---------|
| `GET /agent/retina-evidence-slice` | Per-record bindings for external reviewers |
| `GET /bridge/retina-status` / `retina-alerts` / `retina-stream` | Dashboard + SSE (documented in OpenAPI) |
| `POST /operator/retina-event` | External webhook ingest |
| `VAPIRetinaEvidenceSlice` (SDK) | Programmatic evidence slice access |
| `VAPIProvenanceChain.get_chain(record_hash=...)` | Provenance without manual SHA256 node ids |
| BridgeAgent `get_retina_evidence_slice` | Distinct from aggregate `get_retina_perception_status` |

### 2.6 Frontend

- `useRetinaStatus` + `RetinaAdvisoryPanel` in Gamer view (advisory display only)

---

## 3. Impact now that integration is complete

### 3.1 Adjudicator — richer audit trail, same gates

SessionAdjudicator evidence packages now carry structured Retina bindings when enabled. This improves:

- LLM reasoning context (trajectory anomalies adjacent to L4/L5/GSR evidence)
- Post-hoc operator review without re-parsing raw `retina_event_log`
- Consistency between what FSCA sees and what the adjudicator logged

**Impact:** Operational forensics and explainability. **Not** a new enforcement lever — BLOCK/CERTIFY thresholds unchanged.

### 3.2 FSCA — multi-oracle disagreement detection

Before Retina, L4 Mahalanobis was the primary continuous biometric oracle on the HID path. Retina adds a **dynamics-shaped** signal (trajectory embedding anomalies) that can disagree with L4 on the same window.

When both oracles agree, FSCA stays quiet. When they disagree, MEDIUM contradictions surface for operator triage — without auto-suspending credentials or blocking tournament P0 gates.

**Impact:** Earlier visibility into aim-assist / macro-like trajectory patterns that L4 alone might miss (or vice versa: L4 spikes without Retina signal).

### 3.3 Provenance — PoAC ↔ perception binding

The provenance stack already tracks GIC (cognitive continuity), WEC (operational continuity), VAME, and CORPUS-SNAPSHOT. Retina adds **per-record perception commitments** as first-class DAG children of `POAC_RECORD` nodes.

**Impact:** A third-party auditor can walk `record_hash` → `RETINA_STATE_COMMITMENT` without manual node-id computation. Supports grind-run forensic packages and partner handoff (Rung 3 assembler candidate input).

### 3.4 Observability closure

Prior gap: bridge had retina endpoints but **no OpenAPI/SDK parity** for evidence slices or record-hash provenance lookup. This goal closes that gap so SDK consumers, CI harnesses, and external reviewers use the same shapes as SessionAdjudicator.

**Impact:** Reduces integration friction for IoTeX Halo / partner demos; aligns with QorTroller brand discipline (verifiable, fail-open, advisory-first).

---

## 4. What Trio-Retina does NOT do

- **No tournament P0 gate** — AIT/L4 separation ratio and `all_pairs_p0_ok` unchanged
- **No humanity formula weight** — Retina is not in `humanity_probability`
- **No PoAC byte growth** — 228-byte frame frozen (INV-ARC7-001 discipline applies to PQ, not Retina inline)
- **No replacement for biometric separation** — AIT ratio=1.199 remains the tournament blocker clearance path
- **No automatic credential suspension** — FSCA surfaces MEDIUM contradictions; enforcement agents unchanged
- **No W3bstream mechanical validation yet** — see `docs/retina-w3bstream-integration.md` (operator GO)

---

## 5. Enablement path (recommended)

1. Run `python scripts/replay_retina_calibration.py --write-audit` on calibration corpus + synthetic aimbot replay
2. Review `audits/retina_cross_oracle_*.md` — target acceptable agreement rate and bounded rule1/rule2 false-positive rates
3. Collect N≥10 sessions per player with Retina enabled on real hardware (not synthetic-only)
4. Set `RETINA_PERCEPTION_ENABLED=true` in `bridge/.env` only after audit sign-off
5. Monitor FSCA `RETINA_*` contradictions for 1–2 grind cycles before treating signals as operational

**Calibration artifact (synthetic smoke, 2026-06-19):** 5 windows, agreement rate 0.6, rule1=2 (retina without L4), rule2=0. Synthetic L4 distances were 0.0 (cold classifier) — treat as infrastructure smoke, not production FP estimate.

---

## 6. Deferred high-leverage path

| Item | Blocker |
|------|---------|
| W3bstream applet `retina_commitment` validation | PV-CI ceremony + operator GO |
| DA sidecar upload for retina payloads | Arc 7 DA pattern reuse; deploy-hold |
| Humanity formula / tournament weighting | Requires Stage A empirical unknowns on trajectory separability |

---

## 7. Honest limits

1. **Synthetic replay ≠ live aimbot** — `replay_retina_calibration.py` uses embedder + L4 proxy; real adversaries may differ
2. **L4 cold-start in offline replay** — Mahalanobis distances at 0.0 inflate rule1 counts in synthetic runs; live bridge uses warmed fingerprints
3. **Stage A sensor-stack gates** — Hall/TMR stick fingerprinting and adaptive-trigger discriminators remain MEASUREMENT-PENDING per Sensor Stack v2.1
4. **Advisory default** — Retina-enabled FSCA rules are guarded; disabled by default prevents silent fleet noise

---

## 8. Summary verdict

Trio-Retina is **load-bearing for multi-oracle honesty and forensic provenance**, not for core tournament eligibility. With adjudicator enrichment, FSCA cross-oracle rules, provenance DAG bindings, and SDK/OpenAPI parity, QorTroller can now:

- Explain *why* trajectory and L4 signals disagreed on a specific PoAC record
- Expose the same evidence to operators, agents, and external SDK consumers
- Anchor perception commitments in the grind audit trail without touching FROZEN-v1 wire formats

**Recommended operator action:** Review cross-oracle audit artifact, then pilot `RETINA_PERCEPTION_ENABLED=true` on a single device grind before fleet-wide enablement.
