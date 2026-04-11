# VAPI DataCuratorAgent — Claude Code Integration Prompt
# Phase 192 Implementation Directive
# Authority level: FULL — Claude Code is authorized to extend any
# referenced tool, file, or infrastructure defined herein if the
# extension is logically grounded and provably beneficial to VAPI protocol.
#
# Save this file to: VAPI-WORKFLOW.v2/VAPI_DATACURATOR_BRIEF.md
# Then execute: /vapi datacurator --init
# ============================================================

/vapi DATACURATOR_AGENT_PHASE_192

READ in this exact sequence before writing a single line of code:
  1. VAPI-WORKFLOW.v2/VAPI_MEMORY.md          — last 5 entries
  2. VAPI-WORKFLOW.v2/VAPI_AGENTS.md          — agents #23–30 sections
  3. VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md      — all FROZEN values
  4. VAPI-WORKFLOW.v2/VAPI_WHAT_IF.md         — WIF-028 through WIF-033
  5. VAPI-WORKFLOW.v2/VAPI_BIOMETRIC_PRIVACY.md — BP-001 through BP-007
  6. VAPI-WORKFLOW.v2/VAPI_CORPUS.md          — current corpus statistics
  7. bridge/vapi_bridge/store.py              — existing table schemas
  8. vapi_wiki_engine.py                      — FROZEN dict + phase_close sequence
  9. vapi_managed_agents.py                   — BUS_CHANNELS + FROZEN dict
  10. vapi_eval_harness.py                    — MANDATORY_INVARIANTS + KNOWN_GAPS
  11. vapi_autoresearch.py                    — CLAUDE-EDITABLE ZONE functions

Do NOT proceed to implementation until all 11 files are read.
FROZEN value violations are P0 STOP — check before every file write.

---
## IDENTITY

You are implementing the VAPI DataCuratorAgent (Agent #35, Phase 192).
This agent is NOT a data management utility. It is a DATA COHERENCE LAYER —
the component that makes VAPI's entire causal chain from raw sensor byte
to on-chain tournament ruling queryable as a unified, legally defensible artifact.

The core insight driving every task in this agent:
  VAPI is the only protocol where a 228-byte PoAC sensor record at T=0
  is cryptographically traceable to a soulbound VHP credential and a
  tournament ruling at T=N. The DataCuratorAgent makes that full chain
  queryable, certifiable, and auditable without any human assembly required.

No other gaming or DePIN protocol can build this agent because none of
them have the 192-phase causal chain beneath it. Every task defined below
is exclusively enabled by VAPI's existing infrastructure.

---
## SYSTEM STATE AT PHASE 192

```
Bridge:    2082  |  SDK: 367  |  Hardhat: 498
Agents:    30    |  Tools: #135  |  Contracts: 43 LIVE
Separation ratio: 0.569 (N=20, TOURNAMENT BLOCKER, FROZEN gate=0.70)
FROZEN values (never modify, sourced from wiki_engine.py + managed_agents.py):
  separation_gate:           0.70
  epistemic_threshold:       0.65
  vhp_expiry_days:           90
  record_hash_slice:         raw[:164]  (SHA-256(raw[:164]) — NOT raw[:228])
  nPublic:                   5
  auto_activate:             False  (PERMANENT)
  ceremony_beacon:           "#41723255"
  adjudication_registry:     "0x44CF981f46a52ADE56476Ce894255954a7776fb4"
  l4_anomaly:                7.009
  l4_continuity:             5.367
```

---
## PHASE 192 IMPLEMENTATION SCOPE

DataCuratorAgent (Agent #35) implements SEVEN exclusive novel tasks.
Each task is a distinct subsystem that you will build, test, and wire
into the existing fleet in strict atomic order defined at the end of
this brief. Do not build tasks out of order. Each task depends on the
store schema additions of the task before it.

---
## TASK 1 — Provenance DAG Engine

### Purpose
Maintain a directed acyclic graph where each node is a database row and
each edge is a causal relationship. The full chain:

  calibration_sessions row N
    → (feature_extraction) → separation_ratio_snapshots row M
    → (defensibility_check) → separation_defensibility_log row K
    → (commitment) → SeparationRatioRegistry.sol commit hash H
    → (renewal_trigger) → biometric_renewal_log row R
    → (attestation) → re_enrollment_attestation_log row A
    → (badge_mint) → VHPReenrollmentBadge token T

### Store schema (store.py)
```sql
CREATE TABLE IF NOT EXISTS data_provenance_dag (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id          TEXT NOT NULL UNIQUE,
    node_type        TEXT NOT NULL,
    -- node_type values:
    --   CALIBRATION_SESSION | SEPARATION_SNAPSHOT | DEFENSIBILITY_LOG
    --   COMMITMENT_HASH | RENEWAL_LOG | ATTESTATION_LOG | BADGE_TOKEN
    --   RULING_LOG | CONSENT_SNAPSHOT | ERASURE_CERTIFICATE
    source_table     TEXT NOT NULL,
    source_row_id    INTEGER,
    source_hash      TEXT,          -- SHA-256 of the source row's key fields
    parent_node_id   TEXT,          -- NULL for root nodes (raw sessions)
    edge_type        TEXT,          -- FEATURE_EXTRACTION | DEFENSIBILITY_CHECK |
                                    -- COMMITMENT | RENEWAL | ATTESTATION | BADGE_MINT
                                    -- RULING | CONSENT | ERASURE
    phase_produced   INTEGER NOT NULL,
    player_id        TEXT,
    on_chain_ref     TEXT,          -- IoTeX tx hash or contract address if anchored
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_provenance_parent ON data_provenance_dag(parent_node_id);
CREATE INDEX IF NOT EXISTS idx_provenance_player ON data_provenance_dag(player_id);
CREATE INDEX IF NOT EXISTS idx_provenance_type   ON data_provenance_dag(node_type);
```

### Store methods
```python
def insert_provenance_node(self, node: dict) -> str:
    """Returns node_id. Idempotent — INSERT OR IGNORE on node_id UNIQUE."""

def get_provenance_chain(self, leaf_node_id: str) -> list[dict]:
    """
    Recursive walk from leaf_node_id to root(s) via parent_node_id.
    Returns ordered list of nodes from root → leaf.
    This is the forensic lineage answer to "what data produced this credential."
    Max depth: 20 hops (prevents infinite loop on corrupt graph).
    """

def get_provenance_subtree(self, root_node_id: str) -> list[dict]:
    """All descendants of a root node (e.g., all artifacts from one session)."""

def register_calibration_session(self, session_file: str, player_id: str,
                                  phase: int) -> str:
    """
    Called when a new calibration session is added to corpus.
    Creates a CALIBRATION_SESSION root node.
    node_id = SHA-256(session_file + player_id + created_at)
    """
```

### Config addition
```python
data_provenance_dag_enabled: bool = True
provenance_max_chain_depth:  int  = 20
```

### Operator API endpoint
```
GET /agent/data-provenance-chain?leaf_node_id=<id>
```
Response:
```json
{
  "leaf_node_id": "sha256:...",
  "chain_length": 7,
  "chain": [
    {
      "node_id": "sha256:...",
      "node_type": "CALIBRATION_SESSION",
      "source_table": "calibration_sessions",
      "edge_type": null,
      "player_id": "P2",
      "phase_produced": 143,
      "on_chain_ref": null
    },
    ...
    {
      "node_type": "BADGE_TOKEN",
      "on_chain_ref": "0x..."
    }
  ],
  "forensic_summary": "7-hop chain from P2 calibration session (Phase 143) to VHPReenrollmentBadge token 0x...",
  "timestamp": "2026-04-09T..."
}
```
**Tool #136**: `get_data_provenance_chain` (input: leaf_node_id str)

### AutoResearch integration
After each `phase_close` call in vapi_wiki_engine.py, DataCuratorAgent
auto-registers all new nodes produced by that phase into the DAG.
Add this call to `cmd_phase_close()` in vapi_wiki_engine.py:
```python
# After wiki pages are written:
_trigger_provenance_registration(phase)
```
Where `_trigger_provenance_registration(phase)` queries all tables
that had new rows inserted during `phase` (via `phase_produced` column
pattern) and calls the bridge `POST /agent/datacurator/register-phase-nodes`.

### WIF impact
This task directly closes the implicit gap in WIF-023 (N_consented staleness):
regulators can now query the full chain from consent snapshot → ratio commitment
as a single DAG traversal rather than a manual table join. File as TASK1_W2
in VAPI_WHAT_IF.md after implementation.

---
## TASK 2 — Corpus Entropy Monitor

### Purpose
Track whether the 13-dimensional feature space is being well-sampled or
whether sessions cluster (low entropy = brittle centroid). A low-entropy
corpus produces a separation ratio that collapses under small perturbation.
High entropy means the centroid is stable and the ratio is trustworthy.

### The math (implement exactly as specified)
```
For each player P and each feature dimension d (0..12):
  sessions_P_d = [session[d] for session in corpus if session.player == P]
  bins = np.histogram(sessions_P_d, bins=10)[0]
  p = bins / bins.sum()
  p = p[p > 0]  # remove zero bins
  entropy_P_d = -np.sum(p * np.log2(p))  # Shannon entropy in bits

per_player_entropy[P] = mean(entropy_P_d for d in 0..12)
corpus_entropy_score = mean(per_player_entropy.values())
# Score range: 0.0 (all sessions identical) → 3.32 (uniform over 10 bins)
# Flag threshold: corpus_entropy_score < 1.5 = CLUSTERING_WARNING
```

### Store schema
```sql
CREATE TABLE IF NOT EXISTS corpus_entropy_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    corpus_entropy_score  REAL NOT NULL,
    per_player_entropy    TEXT NOT NULL,   -- JSON: {"P1": 1.2, "P2": 2.8, "P3": 2.6}
    per_feature_entropy   TEXT NOT NULL,   -- JSON: {"0": 1.8, "1": 2.1, ...}
    low_entropy_features  TEXT NOT NULL,   -- JSON array of feature indices with entropy < 1.0
    clustering_warning    BOOLEAN NOT NULL DEFAULT 0,
    n_sessions_analyzed   INTEGER NOT NULL,
    session_type_filter   TEXT DEFAULT 'touchpad_corners',
    computed_at_ts        INTEGER NOT NULL,
    created_at            TEXT DEFAULT (datetime('now'))
);
```

### Config addition
```python
corpus_entropy_enabled:           bool  = True
corpus_entropy_warning_threshold: float = 1.5
corpus_entropy_poll_interval:     int   = 3600   # 1 hour
```

### Operator API endpoint
```
GET /agent/corpus-entropy-status
```
**Tool #137**: `get_corpus_entropy_status`

### MCP knowledge_server.py extension (AUTHORIZED)
You are authorized to extend `knowledge_server.py` with a new tool:
```python
"vapi_corpus_entropy": {
    "description": (
        "Returns current corpus entropy score and per-player entropy breakdown. "
        "Score < 1.5 = CLUSTERING_WARNING — sessions are not sampling the feature "
        "space well; centroid will be brittle. Score > 2.5 = WELL_SAMPLED — safe "
        "to report separation ratio as trustworthy."
    ),
    "schema": {
        "type": "object",
        "properties": {
            "session_type": {
                "type": "string",
                "default": "touchpad_corners"
            }
        }
    },
    "fn": vapi_corpus_entropy
}
```
This makes corpus entropy queryable from Claude Code's MCP context during
any session where separation ratio is discussed — Claude Code will automatically
have entropy context alongside ratio context.

### AutoResearch feed
In `vapi_autoresearch.py` `format_cycle_prompt()`, add corpus entropy to
the KNOWN GAPS section:
```python
entropy_row = store.get_latest_corpus_entropy()
if entropy_row:
    gap_summary += (
        f"\n  corpus_entropy: {entropy_row['corpus_entropy_score']:.2f} "
        f"({'CLUSTERING_WARNING' if entropy_row['clustering_warning'] else 'WELL_SAMPLED'})"
        f" — low_entropy_features: {entropy_row['low_entropy_features']}"
    )
```
This ensures every AutoResearch cycle is aware of whether the corpus is
well-sampled or clustering, and can generate W1/W2 entries grounded in
the actual current entropy state.

---
## TASK 3 — Proof-of-Erasure Certificate Engine

### Purpose
Issue cryptographic certificates proving GDPR Art.17 erasure happened
correctly across all affected tables. Committed to AdjudicationRegistry.sol
(same contract as PoAd — zero new infrastructure). The certificate is a
tournament-grade proof that a player's data was erased at a specific time,
affecting specific rows, producing a specific post-erasure ratio.

### Certificate computation
```python
def compute_erasure_certificate(
    device_id: str,
    player_id: str,
    erased_tables: dict[str, list[int]],  # {table_name: [row_ids]}
    post_erasure_ratio: float,
    ts_ns: int,
) -> str:
    """
    FROZEN: uses SHA-256 (same family as record_hash = SHA-256(raw[:164]))
    Certificate = SHA-256(
        device_id_bytes +
        sorted_table_row_hashes +  # sorted for determinism
        post_erasure_ratio_str.encode() +
        ts_ns_bytes
    )
    """
```

### Store schema
```sql
CREATE TABLE IF NOT EXISTS erasure_certificate_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_hash      TEXT NOT NULL UNIQUE,
    device_id             TEXT NOT NULL,
    player_id             TEXT NOT NULL,
    erased_tables_json    TEXT NOT NULL,   -- {table: [row_ids]}
    erased_row_count      INTEGER NOT NULL,
    post_erasure_ratio    REAL NOT NULL,
    on_chain_tx_hash      TEXT,           -- AdjudicationRegistry.sol tx
    anchored              BOOLEAN NOT NULL DEFAULT 0,
    ts_ns                 INTEGER NOT NULL,
    created_at            TEXT DEFAULT (datetime('now'))
);
```

### Integration with anonymize_device_records()
Extend the existing `anonymize_device_records()` call in store.py:
After all rows are anonymized, call:
```python
cert_hash = self.issue_erasure_certificate(
    device_id=device_id,
    player_id=player_id,
    erased_tables=erased_tables,
    post_erasure_ratio=new_ratio_after_recompute,
    ts_ns=int(time.time_ns()),
)
# Then anchor to AdjudicationRegistry.sol via existing chain.py:
await chain.anchor_erasure_certificate(cert_hash)
```

### Operator API endpoint
```
GET /agent/erasure-certificate?device_id=<id>
POST /agent/anchor-erasure-certificate  (triggers on-chain anchor)
```
**Tool #138**: `get_erasure_certificate`
**Tool #139**: `anchor_erasure_certificate`

### VAPI_WHAT_IF.md update (AUTHORIZED)
After Task 3 is implemented, append to VAPI_WHAT_IF.md:
```
## WIF-034 — Erasure Certificate Replay: Anchor hash reuse across
multiple erasure events for the same device_id.
W1: If device_id is re-enrolled after erasure, a new erasure cert
for the same device_id could share hash components with the original,
enabling an adversary to argue the first cert covers the second erasure.
Mitigation: certificate_hash must include erasure_sequence_number per
device_id (monotonic counter in erasure_certificate_log).
W2: Erasure certificate chain as GDPR Art.17 compliance oracle —
queryable by regulators as a proof that the full erasure lifecycle
was followed, from VAPI to IoTeX L1.
Status: OPEN — Phase 193 candidate.
```

---
## TASK 4 — Federated Corpus Quality Aggregator

### Purpose
FederationBus (Agent #11) correlates threat signals across bridges.
DataCuratorAgent extends this: anonymized corpus quality statistics
(N per session type, entropy score, stationarity status, centroid
velocity) are aggregated across federation nodes, enabling operators
to know whether their local corpus is representative of the federation
or an outlier before running a tournament.

### Privacy constraint (BP-007 EPHEMERAL_SESSIONS — IMMUTABLE)
Raw biometric data NEVER leaves a bridge. Only derived statistics:
N_sessions, entropy_score, stationarity_score, centroid_velocity_mean.
No feature vectors. No raw HID data. No player identifiers.
Bus messages carry only: {bridge_id_hash, session_type, n_sessions,
entropy_score, stationarity_score, centroid_velocity_mean, ts_ns}

### Store schema
```sql
CREATE TABLE IF NOT EXISTS federation_corpus_quality_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    bridge_id_hash          TEXT NOT NULL,   -- SHA-256(bridge_operator_address)
    session_type            TEXT NOT NULL,
    n_sessions              INTEGER NOT NULL,
    entropy_score           REAL NOT NULL,
    stationarity_score      REAL NOT NULL,   -- mean across players (not per-player)
    centroid_velocity_mean  REAL NOT NULL,
    federation_entropy_mean REAL,            -- computed after aggregation
    federation_outlier      BOOLEAN NOT NULL DEFAULT 0,
    outlier_sigma           REAL,            -- how many σ from federation mean
    received_at_ts          INTEGER NOT NULL,
    created_at              TEXT DEFAULT (datetime('now'))
);
```

### Bus channel extension (AUTHORIZED)
Add "corpus_quality" to BUS_CHANNELS in vapi_managed_agents.py:
```python
BUS_CHANNELS["corpus_quality"] = (
    "Anonymized corpus quality statistics for cross-bridge comparison. "
    "Contains only derived metrics — never raw biometric data (BP-007)."
)
```

### Config addition
```python
federated_corpus_quality_enabled: bool  = False  # Off until 2+ bridges active
corpus_outlier_sigma_threshold:   float = 2.0     # Flag if > 2σ from federation mean
```

### Operator API endpoint
```
GET /agent/federated-corpus-quality
```
**Tool #140**: `get_federated_corpus_quality`

### wiki_engine.py extension (AUTHORIZED)
In `cmd_agent_feed()`, after writing the separation ratio page, add:
```python
# Publish local corpus quality stats to federation bus
if cfg.federated_corpus_quality_enabled:
    _publish_corpus_quality_to_bus(latest_entropy, latest_stationarity)
```

---
## TASK 5 — Cross-Feature Temporal Correlation Engine

### Purpose
Per-player feature correlation matrices across sessions are themselves
biometric signatures — patterns stable within a player but different
between players. Two players with similar marginal distributions but
different feature correlation structures are separable in ways that
single-feature Mahalanobis distance misses. This makes the separation
ratio MORE defensible as N grows, not less.

### The math
```python
# For each player P:
# sessions_matrix_P = np.array([[f0, f1, ..., f12] for session in P_sessions])
# correlation_matrix_P = np.corrcoef(sessions_matrix_P.T)  # 13x13 matrix
# Stored as JSON-serialized flattened upper triangle (91 values)

def upper_triangle_json(corr_matrix: np.ndarray) -> str:
    n = corr_matrix.shape[0]
    vals = [corr_matrix[i][j] for i in range(n) for j in range(i+1, n)]
    return json.dumps([round(v, 6) for v in vals])

# Cross-player correlation distance:
# frobenius_distance(corr_P, corr_Q) = ||corr_P - corr_Q||_F
# High Frobenius distance = players are separable by correlation structure
# even if marginal distributions overlap
```

### Store schema
```sql
CREATE TABLE IF NOT EXISTS feature_correlation_log (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id            TEXT NOT NULL,
    session_type         TEXT NOT NULL DEFAULT 'touchpad_corners',
    n_sessions_used      INTEGER NOT NULL,
    correlation_upper_tri TEXT NOT NULL,  -- JSON: 91 values (13x13 upper triangle)
    high_correlation_pairs TEXT NOT NULL, -- JSON: [[i,j,corr] for |corr|>0.7]
    frobenius_vs_p1      REAL,            -- distance from P1's matrix
    frobenius_vs_p2      REAL,            -- distance from P2's matrix
    frobenius_vs_p3      REAL,            -- distance from P3's matrix
    correlation_separable BOOLEAN NOT NULL DEFAULT 0,
    -- correlation_separable=True when min(frobenius_distances) > 0.5
    computed_at_ts       INTEGER NOT NULL,
    created_at           TEXT DEFAULT (datetime('now'))
);
```

### Config addition
```python
correlation_engine_enabled:          bool  = True
correlation_separability_threshold:  float = 0.5   # Frobenius distance floor
correlation_high_pair_threshold:     float = 0.7   # |corr| above = noteworthy
```

### Operator API endpoint
```
GET /agent/feature-correlation-status?player_id=P1
```
**Tool #141**: `get_feature_correlation_status`

### Integration with analyze_interperson_separation.py (AUTHORIZED)
Add `--correlation-matrix` flag to the analyzer. When present:
  1. Compute per-player correlation matrices after separation ratio
  2. Call `POST /agent/datacurator/store-correlation-matrix`
  3. Log correlation_separable result alongside ratio in output

This enriches the separation analysis output: a player pair with
ratio=0.8 AND frobenius_distance=0.9 is MORE defensible than a pair
with ratio=1.2 AND frobenius_distance=0.1.

### VAPI_WHAT_IF.md update (AUTHORIZED)
After Task 5 is implemented, append:
```
## WIF-035 — Correlation Structure as Independent Biometric Gate
W1: Current tournament gate uses only Mahalanobis distance on marginal
distributions. Two players with identical marginal means but different
feature correlation structures pass/fail the same gate — the correlation
signal is invisible. An adversary who mimics P2's marginal distributions
but not their correlation pattern evades the current gate.
W2: correlation_separable=True as an independent tournament gate condition
alongside separation_ratio > gate. A player pair is tournament-eligible
only if BOTH Mahalanobis separation AND correlation Frobenius distance
exceed their respective thresholds. First dual-gate biometric tournament
credential in gaming DePIN.
Status: OPEN — Phase 194 candidate.
```

---
## TASK 6 — Data Readiness Certificate Engine

### Purpose
Pre-tournament data quality certification across all 8 quality dimensions
simultaneously. The certificate_hash is committed to AdjudicationRegistry.sol
as a pre-tournament checkpoint. When a ruling is later challenged, the
operator can prove the data was certified to a specific standard at a
specific timestamp before the tournament began.

### The 8 quality dimensions (check ALL in a single atomic pass)
```python
READINESS_DIMENSIONS = {
    "separation_ratio_above_gate": {
        "check": lambda: current_ratio >= FROZEN["separation_gate"],
        "current_value": current_ratio,
        "gate": 0.70,  # FROZEN
        "blocking": True,  # must be True for certificate to be CERTIFIED
    },
    "corpus_age_tbd_compliant": {
        # All sessions within vhp_expiry_days=90 of now (FROZEN)
        "check": lambda: max(session_ages) < 90,
        "blocking": False,  # advisory
    },
    "session_type_mix_adequate": {
        # touchpad_corners >= 10% of total corpus
        "check": lambda: touchpad_corners_pct >= 0.10,
        "blocking": False,
    },
    "centroid_stability_ok": {
        # No player has centroid_velocity > stationarity_threshold
        "check": lambda: not any_player_persona_break_detected,
        "blocking": True,
    },
    "consent_coverage_complete": {
        # All enrolled players have active consent
        "check": lambda: n_consented == n_enrolled,
        "blocking": True,
    },
    "biometric_ttl_valid": {
        # Latest commitment age < vhp_expiry_days (FROZEN=90)
        "check": lambda: commitment_age_days < 90,
        "blocking": True,
    },
    "corpus_entropy_adequate": {
        # corpus_entropy_score >= 1.5
        "check": lambda: entropy_score >= 1.5,
        "blocking": False,  # advisory — low entropy is a warning, not a block
    },
    "attestation_status_clean": {
        # No active re-enrollment attestation tokens pending consumption
        "check": lambda: active_attestations == 0,
        "blocking": False,  # advisory
    },
}
```

### Certificate hash (uses FROZEN SHA-256 family)
```python
certificate_hash = SHA-256(
    sorted_dimension_results_json.encode() +
    separation_ratio_str.encode() +
    ts_ns_bytes
)
```

### Store schema
```sql
CREATE TABLE IF NOT EXISTS data_readiness_certificate_log (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    certificate_hash       TEXT NOT NULL UNIQUE,
    certification_status   TEXT NOT NULL,   -- CERTIFIED | BLOCKED | ADVISORY_ONLY
    blocking_failures      TEXT NOT NULL,   -- JSON array of blocking dimension names
    advisory_warnings      TEXT NOT NULL,   -- JSON array of non-blocking warnings
    dimension_results      TEXT NOT NULL,   -- JSON: {dimension: {passed, value, gate}}
    separation_ratio       REAL NOT NULL,
    on_chain_tx_hash       TEXT,
    anchored               BOOLEAN NOT NULL DEFAULT 0,
    valid_until_ts         INTEGER NOT NULL, -- ts_ns + vhp_expiry_days*86400*1e9
    ts_ns                  INTEGER NOT NULL,
    created_at             TEXT DEFAULT (datetime('now'))
);
```

### Operator API endpoint
```
GET  /agent/data-readiness-certificate
POST /agent/anchor-data-readiness-certificate
```
**Tool #142**: `get_data_readiness_certificate`
**Tool #143**: `anchor_data_readiness_certificate`

---
## TASK 7 — Session Contribution Weight Table

### Purpose
Track the effective contribution weight of each session toward the current
centroid under TBD (Temporal Biometric Decay, τ_half=90 days, FROZEN).
This weight tells operators when adding a new session will meaningfully
shift the centroid versus when it will be drowned by corpus inertia.
It enables weighted centroid computation natively, without the
`--recency-window` hack in analyze_interperson_separation.py.

### Weight computation
```python
# FROZEN: TBD half-life = vhp_expiry_days = 90 days
LAMBDA = math.log(2) / 90   # decay rate from BP-001 TBD primitive

def session_contribution_weight(
    session_captured_at_ts: int,
    session_type: str,
    stationarity_score: float,  # from temporal_stationarity_log
    current_ts: int,
) -> float:
    """
    age_days = (current_ts - session_captured_at_ts) / 86400
    tbd_weight = e^(-LAMBDA * age_days)

    # Session type multiplier (touchpad_corners contributes more to tournament gate)
    type_multiplier = {
        "touchpad_corners":    1.0,   # primary tournament session type
        "mixed_biometric_probe": 0.9,
        "touchpad_freeform":   0.7,
        "resting_grip":        0.5,
        "gameplay":            0.3,   # free-form gameplay does not help ratio (Phase 143)
    }.get(session_type, 0.5)

    # Stationarity penalty: high stationarity_score = centroid drift = lower weight
    # stationarity_score > 0.35 = DRIFT (from Phase 178 temporal_stationarity_log)
    stationarity_multiplier = max(0.1, 1.0 - stationarity_score)

    return tbd_weight * type_multiplier * stationarity_multiplier
    """
```

### Store schema
```sql
CREATE TABLE IF NOT EXISTS session_contribution_weight_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_file            TEXT NOT NULL,
    player_id               TEXT NOT NULL,
    session_type            TEXT NOT NULL,
    session_captured_at_ts  INTEGER NOT NULL,
    age_days                REAL NOT NULL,
    tbd_weight              REAL NOT NULL,    -- e^(-λ*age)
    type_multiplier         REAL NOT NULL,
    stationarity_multiplier REAL NOT NULL,
    effective_weight        REAL NOT NULL,    -- tbd * type * stationarity
    centroid_influence_rank INTEGER,          -- rank 1=highest influence
    computed_at_ts          INTEGER NOT NULL,
    created_at              TEXT DEFAULT (datetime('now'))
);
```

### Config addition
```python
contribution_weight_enabled: bool = True
# No configurable λ — FROZEN to match BP-001 TBD half-life = vhp_expiry_days = 90
```

### Integration with analyze_interperson_separation.py (AUTHORIZED)
Add `--weighted-centroid` flag. When present, each session's contribution
to its player's centroid is multiplied by `effective_weight` before
averaging. Replace:
```python
centroid_P = sessions_P.mean(axis=0)
```
With:
```python
weights = np.array([store.get_session_weight(s) for s in P_sessions])
centroid_P = np.average(sessions_P, weights=weights, axis=0)
```
This produces a recency-aware, type-weighted, stationarity-penalized
centroid that is more robust than the unweighted mean — especially
critical for P1 where old sessions cluster near P2 and contaminate
the centroid with stale patterns.

### Operator API endpoint
```
GET /agent/session-contribution-weights?player_id=P1
```
**Tool #144**: `get_session_contribution_weights`

---
## AGENT ARCHITECTURE

### DataCuratorAgent (Agent #35)
```python
class DataCuratorAgent:
    NAME          = "DataCuratorAgent"
    AGENT_ID      = 35
    POLL_INTERVAL = 1800  # 30 minutes (all 7 tasks on unified cycle)

    TASK_SEQUENCE = [
        "_run_provenance_dag",        # Task 1
        "_run_corpus_entropy",        # Task 2
        "_run_erasure_certificates",  # Task 3 — only if pending erasures
        "_run_federation_quality",    # Task 4 — only if federated_corpus_quality_enabled
        "_run_correlation_engine",    # Task 5
        "_run_readiness_certificate", # Task 6
        "_run_contribution_weights",  # Task 7
    ]

    async def _run_once(self):
        for task in self.TASK_SEQUENCE:
            try:
                await getattr(self, task)()
            except Exception as e:
                # Each task is independently fail-open
                self._logger.warning(f"DataCuratorAgent task {task} failed: {e}")
                # Continue to next task — no task blocks another
                continue

        # Publish unified status to "curator" bus channel after all tasks
        await self._bus.publish("curator", {
            "event":       "curator_cycle_complete",
            "entropy_ok":   self._last_entropy_ok,
            "cert_status":  self._last_cert_status,
            "dag_nodes":    self._last_dag_nodes_registered,
            "provenance":   f"[VAPI:Phase192:DataCuratorAgent:MEASURED]",
        })
```

**Fail mode**: Each of the 7 tasks is independently fail-open. A failure
in Task 3 (erasure certificates) does not block Task 4 (federation quality).
The agent never blocks bridge operation.

**Poll interval**: 30 minutes. Tasks 1, 2, 5, 6, 7 run every cycle.
Task 3 only runs when pending_erasures > 0. Task 4 only when
federated_corpus_quality_enabled=True.

### Wiring in main.py
Initialize after AttestationBoundRenewalAgent (#30):
```python
# DataCuratorAgent depends on outputs of:
#   SeparationRatioMonitorAgent (#15) — snapshots
#   AgeWeightedRatioPersistenceAgent (#24) — TDI values
#   PersonaBreakDetectorAgent (#27) — stationarity scores
#   BiometricCredentialTTLAgent (#29, Phase 178) — TTL status
# All of these poll at intervals ≤ 30 minutes, so DataCuratorAgent
# always reads current data on its 30-minute cycle.
agents.append(DataCuratorAgent(store, config, bus, logger))
```

### Bus channel (AUTHORIZED — extend BUS_CHANNELS in vapi_managed_agents.py)
```python
BUS_CHANNELS["curator"] = (
    "DataCuratorAgent cycle results: entropy, readiness certificate status, "
    "provenance DAG registration events, erasure certificates. "
    "MA-003 OperatorOnboardingAgent subscribes for readiness reporting."
)
```

---
## VAPI_AGENTS.md ENTRY (append after Agent #30)

```markdown
## Agent 35: DataCuratorAgent — Phase 192

**Trigger**: Automatic 1800s poll (30-minute unified cycle across 7 tasks)

**Role**: Data Coherence Layer. Makes VAPI's causal chain from raw 228-byte
PoAC sensor record to on-chain tournament ruling queryable as a unified,
legally defensible artifact — without human assembly.

**Seven exclusive tasks**:
1. Provenance DAG — causal lineage from calibration session to VHP badge
2. Corpus Entropy Monitor — feature space coverage quality signal
3. Proof-of-Erasure Certificate — GDPR Art.17 cryptographic compliance artifact
4. Federated Corpus Quality Aggregator — cross-bridge anonymized corpus comparison
5. Cross-Feature Temporal Correlation Engine — 13×13 per-player correlation matrix
6. Data Readiness Certificate — 8-dimension pre-tournament certification artifact
7. Session Contribution Weight Table — TBD-decay weighted centroid computation

**Fail mode**: Each task independently fail-open. Agent never blocks bridge.

**Bus**: Publishes to "curator" channel after each 30-minute cycle.
MA-003 OperatorOnboardingAgent subscribes.

**Tools** (#136–#144):
  136: get_data_provenance_chain
  137: get_corpus_entropy_status
  138: get_erasure_certificate
  139: anchor_erasure_certificate
  140: get_federated_corpus_quality
  141: get_feature_correlation_status
  142: get_data_readiness_certificate
  143: anchor_data_readiness_certificate
  144: get_session_contribution_weights

**Exclusive**: Requires VAPI's 192-phase causal chain (Sessions → Features →
Ratio → Commitment → Consent → Renewal → Attestation → Badge) to exist.
No other gaming or DePIN protocol can build this agent.
```

---
## AUTHORIZED TOOL AND INFRASTRUCTURE EXTENSIONS

Claude Code has FULL AUTHORITY to make the following modifications
if, and only if, each modification is provably required by one of the
7 tasks above and does not violate any FROZEN invariant:

### knowledge_server.py (MCP)
ADD tools: `vapi_corpus_entropy`, `vapi_data_readiness_certificate`,
`vapi_provenance_chain`. These make curator outputs queryable from
Claude Code's MCP context during any session — no separate API call needed.
Register alongside existing tools in the `TOOLS` dict.

### vapi_wiki_engine.py
ADD: `_trigger_provenance_registration(phase)` call inside `cmd_phase_close()`.
ADD: corpus entropy to `cmd_agent_feed()` output alongside separation ratio.
ADD: `data_readiness_certificate` status to `wiki/concepts/` pages.
These are additive — no existing wiki_engine behavior is modified.

### vapi_autoresearch.py CLAUDE-EDITABLE ZONE
ADD to `get_priority_from_log()`:
```python
"corpus_entropy_health",    # surfaces when entropy_score < 1.5
"contribution_weight_audit",# surfaces when effective_weight of oldest sessions > 0.3
```
ADD to `select_skill_section_to_improve()`:
```python
"corpus_entropy_health":    "CALIBRATION",
"contribution_weight_audit": "CALIBRATION",
```
ADD `score_phase_192_readiness()` function checking that all 7 curator
task tables exist in the store schema before Phase 192 synthesis runs.

### vapi_eval_harness.py — DO NOT MODIFY
This file is IMMUTABLE. The eval harness is ground truth.
DataCuratorAgent tasks are validated by existing MANDATORY_INVARIANTS.
No additions to KNOWN_GAPS or MANDATORY_INVARIANTS are needed for this phase.

### analyze_interperson_separation.py
ADD flags: `--weighted-centroid`, `--correlation-matrix`.
These are additive — existing flags unchanged. Existing tests unchanged.
New tests cover weighted centroid output format only.

---
## ATOMIC IMPLEMENTATION ORDER

Execute in strict sequence. Do not skip steps. Do not reorder.

```
Step  1: bridge/vapi_bridge/config.py
          — add 7 config fields (one per task, listed in each task above)

Step  2: bridge/vapi_bridge/store.py
          — add 7 table schemas (in task order: provenance → entropy →
            erasure → federation → correlation → readiness → weights)
          — add schema(192, "data_provenance_dag") through schema(192, "session_contribution_weight")
          — add all store methods defined per task

Step  3: bridge/vapi_bridge/data_curator_agent.py  (NEW FILE)
          — DataCuratorAgent class with all 7 _run_* methods
          — fail-open per task, unified 30-min poll cycle

Step  4: bridge/vapi_bridge/main.py
          — wire DataCuratorAgent after AttestationBoundRenewalAgent (#30)
          — import DataCuratorAgent

Step  5: bridge/vapi_bridge/operator_api.py
          — add 9 endpoints (Tools #136–#144 per task)

Step  6: bridge/vapi_bridge/bridge_agent.py
          — add Tools #136–#144 input schemas and descriptions

Step  7: frontend/public/openapi.yaml
          — add 7 response schemas + 9 paths

Step  8: sdk/vapi_sdk.py
          — add 7 result dataclasses (slots=True):
            ProvenanceChainResult | CorpusEntropyResult | ErasureCertificateResult |
            FederatedCorpusQualityResult | FeatureCorrelationResult |
            DataReadinessCertificateResult | SessionContributionWeightResult

Step  9: analyze_interperson_separation.py
          — add --weighted-centroid and --correlation-matrix flags

Step 10: knowledge_server.py
          — add vapi_corpus_entropy, vapi_data_readiness_certificate,
            vapi_provenance_chain tools

Step 11: vapi_wiki_engine.py
          — add _trigger_provenance_registration() + corpus entropy to agent_feed

Step 12: vapi_autoresearch.py
          — extend get_priority_from_log() and select_skill_section_to_improve()
          — add score_phase_192_readiness()

Step 13: vapi_managed_agents.py
          — add "curator" and "corpus_quality" to BUS_CHANNELS

Step 14: bridge/tests/test_phase192_datacurator.py
          — minimum 14 tests (2 per task: schema + logic)
          — ACIM self-test count must still show 16/16 after wiring

Step 15: sdk/tests/test_phase192_datacurator_sdk.py
          — minimum 7 tests (1 per result dataclass)

Step 16: CLAUDE.md
          — Phase 192 COMPLETE
          — Bridge +14→2096 | SDK +7→374 | Agents 30→31 (35 is correct — gap implies phases 31-34 exist)
          — Tools 135→144

Step 17: VAPI-WORKFLOW.v2/VAPI_MEMORY.md
          — append Phase 192 session entry

Step 18: VAPI-WORKFLOW.v2/VAPI_WHAT_IF.md
          — append WIF-034 (erasure certificate replay — Task 3)
          — append WIF-035 (correlation structure as biometric gate — Task 5)

Step 19: VAPI-WORKFLOW.v2/VAPI_AGENTS.md
          — append Agent #35 block

Step 20: python vapi_wiki_engine.py sync_what_if
Step 21: python vapi_wiki_engine.py agent_feed
Step 22: python vapi_wiki_engine.py snapshot --anchor
Step 23: python vapi_wiki_engine.py phase_close 192
```

**Count verification before Step 16 (CLAUDE.md)**:
```bash
python -m pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -q 2>&1 | tail -1
# Must show: ≥2096 passed

python -m pytest sdk/tests/ -q 2>&1 | tail -1
# Must show: ≥374 passed

cd contracts && npx hardhat test 2>&1 | tail -3
# Must show: ≥498 passing (unchanged — no new contracts this phase)

curl -H "x-api-key: $OPERATOR_KEY" http://localhost:8080/agent/calibration-health
# Must show: {"passed_self_tests": 16, "failed_self_tests": 0}
```

If any count drops below floor: DO NOT update CLAUDE.md. Root-cause first.

---
## QUALITY GATES — DataCuratorAgent must pass all before phase_close

Gate 1 — Provenance chain is queryable:
  `GET /agent/data-provenance-chain?leaf_node_id=<any_recent_snapshot_id>`
  Response must include chain_length > 0 and forensic_summary.

Gate 2 — Corpus entropy computed:
  `GET /agent/corpus-entropy-status`
  Response must include corpus_entropy_score (any value accepted — this is
  a measurement, not a gate. Even 0.0 is valid — it means clustering).

Gate 3 — Readiness certificate generated:
  `GET /agent/data-readiness-certificate`
  Response must include certification_status and certificate_hash.
  Status BLOCKED is acceptable — the certificate is honest about blockers.

Gate 4 — Session weights computed:
  `GET /agent/session-contribution-weights`
  Response must include at least 1 session with effective_weight > 0.

Gate 5 — MCP tool queryable:
  From Claude Code session: call `vapi_corpus_entropy` via MCP.
  Must return a structured response without error.

Gate 6 — ACIM health preserved:
  `GET /agent/calibration-health`
  Must show: passed_self_tests=16, failed_self_tests=0.
  If ACIM fails: DataCuratorAgent polling broke a calibration invariant.
  Root-cause before merging.

---
## MEMORY.md ENTRY TO APPEND AFTER IMPLEMENTATION

```
### 2026-04-09: Phase 192 COMPLETE — DataCuratorAgent (Agent #35)

**What was done**:
DataCuratorAgent implemented with 7 exclusive tasks. Agent is the Data Coherence
Layer — makes VAPI's causal chain from raw session to on-chain artifact queryable
as a unified forensic artifact.

Task 1: Provenance DAG — data_provenance_dag table, 20-hop chain traversal
Task 2: Corpus Entropy — Shannon entropy across 13-dim feature space per player
Task 3: Proof-of-Erasure — SHA-256 certificates anchored to AdjudicationRegistry.sol
Task 4: Federated Corpus Quality — cross-bridge anonymized corpus comparison (disabled until 2+ bridges)
Task 5: Feature Correlation — 13×13 per-player correlation matrix, Frobenius separability
Task 6: Data Readiness Certificate — 8-dimension pre-tournament certification artifact
Task 7: Session Contribution Weights — TBD-decay × type × stationarity per session

Knowledge_server.py extended: vapi_corpus_entropy, vapi_data_readiness_certificate,
vapi_provenance_chain now queryable from MCP context in any Claude Code session.

AutoResearch cycle priority rotation updated: corpus_entropy_health,
contribution_weight_audit added as new priorities.

Wiki engine extended: provenance registration on phase_close,
corpus entropy in agent_feed output.

WIF-034 filed: erasure certificate replay (Phase 193 candidate)
WIF-035 filed: correlation structure as independent biometric gate (Phase 194 candidate)

**What we learned**:
- The --weighted-centroid flag on analyze_interperson_separation.py is the most
  immediately impactful change: P1's old sessions (clustering near P2) now receive
  TBD-decay weight < 0.3, reducing their centroid contamination without requiring
  --recency-window exclusion. The ratio may recover without P1 re-enrollment.
- Corpus entropy score answers a question the separation ratio cannot: "is the
  ratio trustworthy?" A ratio of 0.9 with entropy 2.8 is more defensible than a
  ratio of 1.1 with entropy 0.8.
- data_readiness_certificate anchored pre-tournament is the strongest possible
  operator defense in a legal challenge: the data was certified to a specific
  standard, at a specific timestamp, before the tournament began.

[PATTERN-016]: Before reporting separation_ratio as evidence:
  1. Check corpus_entropy_score — if < 1.5, ratio is brittle (CLUSTERING_WARNING)
  2. Check session_contribution_weights — if any player's top-weighted sessions
     are > 60 days old, ratio may recover with new captures rather than re-enrollment
  3. Check feature_correlation_log — if correlation_separable=True for all pairs,
     report dual-gate separability alongside ratio
  4. Generate data_readiness_certificate BEFORE any tournament authorization
```
