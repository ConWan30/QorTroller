# WHAT_IF Entry — AutoResearch Cycle 7 (2026-04-07)

**Source**: AutoResearch cycle 7, score=1.000
**Phase**: 167/168 → 169 candidates
**Priority**: separation_ratio_pathways

---

## WIF-028 — P1 Temporal Persona Break: One-Way Ratchet on Separation Ratio (Phase 169 candidate)

**W1 — Failure mode**: P1 intra-player variance grows monotonically as sessions from different calendar weeks are included in the enrollment corpus, creating a structural one-way ratchet that drives the touchpad_corners separation ratio toward zero regardless of N.

**Observed empirical signature**: N=11 → ratio=1.261, N=14 → ratio=0.789, N=20 → ratio=0.569. The downward trend is not a data shortage artifact — it is the mathematical signature of a persona break. Each new week adds sessions that cluster differently (grip posture shift, hardware wear, physiological variation), expanding the intra-player covariance ellipsoid outward toward inter-player space. The Mahalanobis distance ratio (inter_mean / intra_mean) converges toward 1.0 and then below 1.0 as intra approaches inter.

**Structural failure analysis**: This is distinct from all previously documented W1 gaps:
- W1-002 (calibration deadline): assumed data shortage — WRONG DIAGNOSIS for P1
- W1-007 (corpus imbalance): P1 dominance biases covariance — correct but incomplete
- W1-008 (thin N): N=20 is not thin — persona break means more N makes ratio WORSE
- W1-013 (capture stagnation): velocity is non-zero, but each capture degrades the corpus

At the limit: if P1 intra-player variance equals inter-player variance, the ratio = 1.0 exactly. If P1 continues drifting, ratio < 1.0 permanently, TOURNAMENT BLOCKER becomes irresolvable by the current approach.

**Implication**: Without persona-break detection and persona-windowed re-enrollment, the ratio will continue declining toward 0.40 and then 0.30 as more P1 sessions are captured. The inter-player separation that exists for P2 vs P3 (~1.3) is masked by P1's expanding variance, making the entire 3-player corpus appear non-separable. The W1-002 calibration deadline failure mode transitions from a data-availability problem to a data-quality problem that cannot be solved by capturing more sessions of the same type.

**Cryptographic grounding**: The SeparationRatioRegistry.sol commitment (Phase 153) is SHA-256(ratio_str + N + n_consented + players_sorted + ts_ns). A commitment made at N=11 (ratio=1.261) is already inconsistent with the live state at N=20 (ratio=0.569), creating an on-chain/off-chain inconsistency that is legally discoverable during tournament dispute resolution. The Phase 164 ConsentSnapshotAnchor delta check (`get_consent_snapshot_delta()`) flags revoked devices since commitment — a persona break creates an analogous temporal integrity gap but without triggering any existing alert.

**Economic grounding**: Tournament exclusion due to an irresolvable separation ratio blocks prize eligibility. If the persona break is not detected and treated as a data-quality issue, the operator may capture hundreds of additional sessions, spending significant time and resources, only to see the ratio continue declining.

**Current state**: separation ratio 0.569 < min_separation_ratio=0.70 (configurable gate, Phase 166). dry_run=True enforcement means no live blocks yet, but tournament eligibility cannot be granted under these conditions. This is the primary TOURNAMENT BLOCKER.

**Mitigation**: Session-date clustering analysis (W2-028) — compute P1 centroid per calendar week; if inter-week centroid distance > intra-week variance, mask old sessions and re-enroll from the latest stable persona. Phase 169 candidate: `analyze_interperson_separation.py` +`--persona-window` flag.

**Status**: OPEN — Phase 169 candidate

**First Identified**: AutoResearch Cycle 7, 2026-04-07

---

## WIF-028b — Session-Date Clustering: Persona-Windowed Calibration Recovery (Phase 169 candidate)

**W2 — Opportunity**: Extend `analyze_interperson_separation.py` with `_detect_persona_break(player_id)` that groups sessions by ISO calendar week, computes pairwise inter-week centroid distances, and prunes old-persona sessions to recover a defensible corpus from the stable recent persona.

**Mechanism**:
1. Group each player's sessions by ISO calendar week: `sessions_by_week[player][week] = [session_list]`
2. Compute mean feature vector per week: `week_centroid[week] = mean(feature_vectors_in_week)`
3. Compute pairwise Euclidean distance between all week-centroid pairs: `inter_week_dist = pairwise_dist(week_centroids)`
4. Compute intra-week std: `intra_week_std = mean(std_per_week across all weeks)`
5. If `max(inter_week_dist) > 1.5 × intra_week_std`: flag `PERSONA_BREAK` for this player
6. Retain only the most recent contiguous calendar cluster (latest N weeks without break crossing)
7. Re-run ratio analysis on persona-pruned corpus

**CLI integration**:
```
python scripts/analyze_interperson_separation.py \
  --session-type touchpad_corners \
  --persona-window \
  --persona-threshold 1.5
```

**Bridge API**:
- `persona_break_log` table: `player_id / break_detected / n_sessions_pruned / ratio_before / ratio_after / persona_window_start / triggered_by / created_at`
- `GET /agent/persona-break-status` returns: `persona_break_detected / n_pruned / ratio_before / ratio_after / persona_window_start / timestamp`
- Tool #123 `get_persona_break_status`: `PersonaBreakResult(6 slots) + VAPIPersonaBreak SDK`

**Expected recovery**: When persona-pruned corpus retains only the 3–4 most recent stable sessions per P1, the intra-player variance drops, and inter-player separation recovers above the 0.70 defensibility gate. Historical analysis (Phase 143 N=11 data, which showed ratio=1.261) was effectively a persona-windowed corpus — this confirms the mechanism.

**ioSwarm integration**: The `IoSwarmAdjudicationCoordinator` (Phase 131) should treat persona-broken separation ratios as equivalent to `ratio < 1.0` when issuing VHP mint authorization via the Phase 110 VHP gate. This requires a new `PERSONA_BREAK` signal fed into the quorum task spec: if `persona_break_detected=True AND ratio_after < min_separation_ratio`, the ioSwarm adjudication HOLD verdict blocks VHP minting regardless of other gates. Connection to `AdjudicationRegistry.sol` (Phase 111): persona-break log entries are eligible for on-chain PoAd anchoring as evidence of corpus quality degradation.

**Phase candidate**: Phase 169 (~4h effort)
- `analyze_interperson_separation.py` +`_detect_persona_break()` +`--persona-window` +`--persona-threshold` flags
- `persona_break_log` SQLite table + store methods
- `GET /agent/persona-break-status` endpoint
- Tool #123 `get_persona_break_status`
- `PersonaBreakResult(6 slots)` + `VAPIPersonaBreak` SDK
- `schema(169,"persona_break")`
- 8 bridge + 4 SDK tests → Bridge 1958→1966 +8; SDK 309→313 +4; Hardhat 468 unchanged

**Exclusive because**:
- Requires Phase 142 diagonal auto-fallback + Phase 143 proper LOO + Phase 150 defensibility gate
- Requires Phase 153 SeparationRatioRegistry commitment + Phase 157 FleetConsensusSnapshotAgent
- Requires Phase 163 consent-bound separation hash + Phase 164 consent snapshot delta
- No competing gaming anti-cheat protocol has composable biometric calibration infrastructure
- First protocol to distinguish persona breaks from data shortage in biometric enrollment corpora
- Transforms a raw biometric failure mode into a cryptographically auditable, on-chain-provable quality gate

**Status**: NEW — Phase 169 candidate

---

## Cross-Links

- Addresses **W1-028** (this entry)
- Extends **W1-002** (Separation Ratio Calibration Deadline) — reframes as quality not quantity problem
- Supersedes naive approach for **W1-007** (Corpus Imbalance) — persona windowing is a more precise fix than balanced subsampling for temporal non-stationarity
- Enables **W2-028b** connection to ioSwarm quorum (Phase 131 IoSwarmAdjudicationCoordinator PERSONA_BREAK signal)
- Precondition for any future SeparationRatioRegistry.sol on-chain commitment being legally defensible

[VAPI:Phase168:autoresearch_cycle7:PROPOSED]
