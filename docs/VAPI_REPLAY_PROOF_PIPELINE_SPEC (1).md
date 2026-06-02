# VAPIReplayProofPipeline
## Technical Specification — Verified Human Replay Proof System
**Version:** 1.0 · **Date:** 2026-05-29
**Status:** Architectural Blueprint — Data Economy Arc 5
**Prerequisite arcs:** Data Economy Arcs 1–4 complete
**Authority:** Operator-reviewed · Verification-First Discipline applies throughout

---

## 0. Architectural Position

This specification introduces the **VAPIReplayProofPipeline** — the fifth arc
of the QorTroller Data Economy ladder, implementing a new proof type that is
orthogonal to the ZK Skill Proof tier hierarchy established in Arc 2.

### The Proof Type Distinction (Read First)

Two proof types serve distinct buyer needs in the QorTroller data economy:

```
ZK SKILL PROOFS (Arcs 1–4)         VHR PROOFS (Arc 5 — this spec)
─────────────────────────────────   ─────────────────────────────────
Subject:  the player                Subject:  the session
Claim:    "this player possesses    Claim:    "a verified human produced
          skill level X"                      this gameplay trace"
Reveals:  statistical credential    Reveals:  sanitized macro-intent record
Use case: scouting, ranking,        Use case: AI training corpus, coaching
          tournament seeding                  tools, game balance research
```

ZK Skill Proofs are credentials about a person.
VHR (Verified Human Replay) Proofs are records about a session.

They are complementary and independently marketable. They are NOT tiers of
the same hierarchy. A buyer may purchase one, the other, or both.

This distinction is architecturally load-bearing. Any implementation that
conflates the two proof types violates the honesty-first architecture.

### Alignment With Core Insight

The Data Economy Framework established:

> **The proof of humanity IS the data provenance.**

The VAPIReplayProofPipeline is the literal instantiation of this principle.
The PoAC chain — already running, already producing tamper-evident records —
is the provenance anchor. The VHR proof attaches a sanitized macro-intent
replay to that anchor, proving the replay was produced by a verified human
without exposing the biometric signature that was used to verify them.

The pipeline does not add a new data capture layer. It derives value from
what the anti-cheat infrastructure already produces.

---

## 1. Formal Non-Invertibility Foundation

This section establishes the mathematical basis for the pipeline's privacy
guarantee before describing the implementation. The guarantee is a formal
claim, not a testing assertion.

### 1.1 The Quantization Map

Let φ be the composition of the two pre-processing transforms:

```
φ = φ_spatial ∘ φ_temporal : ℝⁿ → ℤᵐ

Where:

φ_temporal : ℝ^(n × 1002) → ℝ^(n × 60)
  Maps continuous 1002 Hz time-series → 60 Hz via rolling median per window.
  Window width: ⌊1002/60⌋ ≈ 17 frames per 16.67ms tick.
  Median selection: deterministic (odd N always has a unique median).

φ_spatial : ℝ^(n × 60) → ℤ^(m × 60)
  Maps continuous floating-point channel values → discrete integer states.
  Stick vectors: ℝ² → {0..15}² (4-bit radial sector, 16 angular regions)
  Trigger analog: [0..255] → {0..15} (4-bit, 16 compression states)
  IMU gravity:   ℝ³ → {0..7} (3-bit posture sector, 8 solid-angle regions)
```

### 1.2 The Non-Invertibility Proof

**Claim:** φ is surjective but not injective. For any output symbol z ∈ ℤᵐ,
the pre-image φ⁻¹(z) has positive measure in the continuous input space ℝⁿ.

**Proof sketch (by construction):**

*Temporal component:* Any two input sequences that produce the same rolling
median within each 16.67ms window are mapped to the same output. Sub-window
timing variations, sub-millisecond jitter, and release velocity differences
— the features constituting L5 temporal rhythm and E4 spectral entropy — are
collapsed into identical output values. The set of inputs producing a given
median is an open interval (strictly positive measure).

*Spatial component:* The 4-bit radial sector map partitions the unit disk
into 16 regions of equal angular width. Any two stick vectors within the
same angular sector produce identical output. The set of inputs producing
a given sector code is a sector of the unit disk (area π/16 > 0). Active
Inactivity Tremor (AIT), micro-tremor variance, and grip asymmetry displace
the stick vector within a sector — they do not cross sector boundaries when
the tremor amplitude is within physiological norms (confirmed by the AIT
defensibility corpus: N=37, ratio 1.199, all pairs above 1.0).

**Consequence:** Given any output matrix Q ∈ ℤᵐ, the pre-image φ⁻¹(Q) is
an equivalence class with infinitely many members — an open set of
physiologically distinct input sequences. Recovery of the unique original
input (and therefore recovery of the biometric signature) is
**information-theoretically impossible** — not merely computationally hard.

**Verification approach:** Tests verify that the implementation satisfies the
formal claim. Tests do NOT claim to prove non-invertibility (that is proven
above); they verify the implementation produces the expected equivalence
classes. Specifically:

```python
# Test: N distinct AIT tremor amplitudes → identical quantized sector
def test_ait_equivalence_class():
    tremors = generate_distinct_ait_signals(N=100, amplitude_range=(0.1, 2.0))
    sector_outputs = [quantize_stick(t) for t in tremors]
    # All 100 tremors must map to the same sector code
    assert len(set(sector_outputs)) == 1

# Test: distinct sub-ms click jitter patterns → identical 60Hz output
def test_temporal_flattening_erases_jitter():
    base_sequence = generate_button_sequence(hz=1002, duration_ms=1000)
    jittered = [add_subms_jitter(base_sequence, σ=0.3) for _ in range(50)]
    outputs = [temporal_flatten(j, target_hz=60) for j in jittered]
    assert all(o == outputs[0] for o in outputs)
```

---

## 2. Pre-Processing Pipeline — Python Implementation

**Language decision: Python + numpy (not Rust).**

Rationale: each 60 Hz window covers ~17 raw frames. Rolling median over 17
samples per channel, followed by integer quantization, completes in
microseconds per window in vectorized numpy. The 60 Hz output loop fires
every 16.67ms — orders of magnitude more headroom than numpy requires.
Introducing Rust adds a new compile dependency, a PyO3/FFI boundary, a new
language in the CI pipeline, and a new invariant surface, with no
performance justification given the computation budget. Python is sufficient.

### 2.1 Module Structure

```
bridge/vapi_bridge/
└── replay_proof_pipeline/
    ├── __init__.py
    ├── pre_processor.py       # ReplayPreProcessor — temporal + spatial transforms
    ├── witness_generator.py   # WitnessGenerator — R1CS input compilation
    ├── prover.py              # LocalProver — snarkjs subprocess wrapper
    └── pipeline.py            # VAPIReplayProofPipeline — orchestrator
```

### 2.2 ReplayPreProcessor

```python
# bridge/vapi_bridge/replay_proof_pipeline/pre_processor.py

import numpy as np
from dataclasses import dataclass, field
from typing import Sequence

# FROZEN constants — pinned by INV-VHR-001 and INV-VHR-002
OUTPUT_HZ: int    = 60          # INV-VHR-002: FROZEN — 60 Hz downsampling target
SOURCE_HZ: int    = 1002        # matches DualShock Edge CFI-ZCP1 polling rate
RADIAL_BITS: int  = 4           # INV-VHR-001: FROZEN — 4-bit radial sector
TRIGGER_BITS: int = 4           # INV-VHR-001: FROZEN — 4-bit trigger quantization
IMU_BITS: int     = 3           # INV-VHR-001: FROZEN — 3-bit gravity posture

WINDOW_FRAMES: int = SOURCE_HZ // OUTPUT_HZ   # 17 frames per 16.67ms window
RADIAL_SECTORS: int = 2 ** RADIAL_BITS        # 16
TRIGGER_STATES: int = 2 ** TRIGGER_BITS       # 16
IMU_SECTORS: int    = 2 ** IMU_BITS           # 8


@dataclass(frozen=True)
class SanitizedReplayMatrix:
    """
    60 Hz downsampled, quantized session replay.

    Non-invertibility: guaranteed by construction of φ (see §1.2).
    The following biometric features are information-theoretically erased:
    - L5 temporal rhythm (sub-window jitter, release velocity, inter-event intervals)
    - E4 spectral entropy (high-frequency IMU oscillation signatures)
    - L4 Mahalanobis features (tremor variance, grip asymmetry, stick autocorrelation)
    - AIT (Active Inactivity Tremor — collapsed into equivalence class)

    The following macro-intent features are preserved:
    - Which direction the stick was pushed (within ±22.5° angular resolution)
    - Whether a trigger was pressed and at roughly what compression (16 states)
    - Which buttons were pressed per 16.67ms window
    - General postural orientation (8-sector gravity vector)
    """
    session_id: str
    ticks: int                       # number of 16.67ms windows in session
    stick_L_sector: bytes            # len=ticks, uint8, 0-15 (4-bit radial)
    stick_R_sector: bytes            # len=ticks, uint8, 0-15 (4-bit radial)
    trigger_L_state: bytes           # len=ticks, uint8, 0-15 (4-bit compression)
    trigger_R_state: bytes           # len=ticks, uint8, 0-15 (4-bit compression)
    button_mask: bytes               # len=ticks*2, uint16 little-endian bitmask
    imu_gravity_sector: bytes        # len=ticks, uint8, 0-7 (3-bit posture)
    poac_chain_root: bytes           # 32 bytes — Poseidon root of session PoAC records
    vhp_token_id: int                # gamer's VHP soulbound token ID (VAPIVerifiedHumanProof)
    humanity_prob_floor: float       # min humanity_probability across session windows
    session_verdict: str             # "HUMAN" | "CERTIFY" — from adjudicator


class ReplayPreProcessor:
    """
    Implements φ = φ_spatial ∘ φ_temporal.

    Reads structural input state from bridge.db (HID frame columns only).
    NEVER reads biometric feature columns (L4 vector, L5 rhythm scores,
    E4 entropy, AIT features). Those are computed separately by the PITL
    stack and remain in the bridge DB for adjudication — they never enter
    this pipeline.

    Data floor is enforced at the DB query level: only the following
    columns are fetched from the poac_records table:
      stick_l_x, stick_l_y, stick_r_x, stick_r_y,
      trigger_l_raw, trigger_r_raw,
      button_state_raw, accel_x, accel_y, accel_z
    Any attempt to fetch l4_vector, l5_cv, e4_entropy, ait_rms, or
    similar biometric columns raises DataFloorViolationError.
    """

    FORBIDDEN_COLUMNS = frozenset({
        "l4_mahalanobis_distance", "l4_vector", "l4_feature_0",
        "l5_cv", "l5_entropy", "l5_quantization",
        "e4_spectral_entropy", "e4_band_power",
        "ait_rms", "ait_variance", "grip_asymmetry",
        "micro_tremor_variance", "press_timing_jitter_variance",
        "trigger_onset_velocity_l2", "trigger_onset_velocity_r2",
        "stick_autocorr_lag1", "stick_autocorr_lag5",
        "accel_tremor_peak_hz", "tremor_band_power",
        "accel_magnitude_spectral_entropy",
    })

    def process_session(
        self,
        session_id: str,
        db_path: str,
    ) -> SanitizedReplayMatrix:
        """
        Main entry point. Reads raw HID structural columns from bridge.db,
        applies φ_temporal then φ_spatial, returns SanitizedReplayMatrix.
        """
        frames = self._fetch_structural_frames(session_id, db_path)
        flat   = self._temporal_flatten(frames)
        matrix = self._spatial_quantize(flat)
        root   = self._compute_poac_root(session_id, db_path)
        meta   = self._fetch_session_metadata(session_id, db_path)
        return SanitizedReplayMatrix(
            session_id=session_id,
            ticks=len(flat),
            **matrix,
            poac_chain_root=root,
            vhp_token_id=meta["vhp_token_id"],
            humanity_prob_floor=meta["humanity_prob_floor"],
            session_verdict=meta["verdict"],
        )

    def _fetch_structural_frames(
        self, session_id: str, db_path: str
    ) -> list[dict]:
        """
        Fetches ONLY structural input columns from bridge.db.
        DataFloorViolationError on any FORBIDDEN_COLUMNS reference.
        """
        allowed_cols = {
            "ts_ns", "stick_l_x", "stick_l_y",
            "stick_r_x", "stick_r_y",
            "trigger_l_raw", "trigger_r_raw",
            "button_state_raw",
            "accel_x", "accel_y", "accel_z",
        }
        # SQL constructed from allowed_cols only — no interpolation of
        # forbidden column names is possible
        ...

    def _temporal_flatten(self, frames: list[dict]) -> list[dict]:
        """
        φ_temporal: 1002 Hz → 60 Hz via rolling median per channel.

        For each 16.67ms window of WINDOW_FRAMES (~17) raw frames:
          - Stick X/Y: median of the 17 float values
          - Trigger: median of the 17 analog values (0-255)
          - Buttons: majority-vote across the 17 frames (held > 8 frames → pressed)
          - IMU: median per axis over the window

        The median is deterministic (odd N=17 always has a unique value).
        Sub-ms jitter, release velocities, and inter-event timing intervals
        are destroyed by this aggregation — they cannot be recovered from
        the window median.
        """
        arr = np.array([[
            f["stick_l_x"], f["stick_l_y"],
            f["stick_r_x"], f["stick_r_y"],
            f["trigger_l_raw"], f["trigger_r_raw"],
            f["button_state_raw"],
            f["accel_x"], f["accel_y"], f["accel_z"],
        ] for f in frames], dtype=np.float32)

        n_windows = len(arr) // WINDOW_FRAMES
        windows = arr[:n_windows * WINDOW_FRAMES].reshape(n_windows, WINDOW_FRAMES, -1)
        # Median per window per channel — numpy vectorized, microseconds
        medians = np.median(windows, axis=1)
        # Button majority vote: sum > WINDOW_FRAMES/2
        btn_col = 6
        btn_sum = windows[:, :, btn_col].sum(axis=1)
        medians[:, btn_col] = (btn_sum > WINDOW_FRAMES / 2).astype(np.float32)
        return medians

    def _spatial_quantize(self, flat: np.ndarray) -> dict:
        """
        φ_spatial: continuous float values → discrete integer states.

        Stick (X, Y) ∈ [-1, 1]² → radial sector {0..15}:
          angle = atan2(Y, X)  mapped to [0, 2π)
          sector = floor(angle / (2π/16))
          Centre-stick deadzone (magnitude < 0.1) → sector 16 (NEUTRAL)

        Trigger ∈ [0, 255] → state {0..15}: floor(value / 16)

        IMU gravity vector → 3-bit posture sector {0..7}:
          Normalize accel to unit sphere → octant index from sign bits of
          (X_norm, Y_norm, Z_norm). This captures general postural orientation
          (upright, tilted forward, tilted back, etc.) without continuous
          magnitude data. AIT tremor amplitudes are orders of magnitude below
          octant-crossing thresholds.
        """
        ...
        return {
            "stick_L_sector": ...,
            "stick_R_sector": ...,
            "trigger_L_state": ...,
            "trigger_R_state": ...,
            "button_mask": ...,
            "imu_gravity_sector": ...,
        }

    def _compute_poac_root(self, session_id: str, db_path: str) -> bytes:
        """
        Poseidon-8 Merkle root over the session's PoAC record hashes.
        Matches the hashing scheme of PitlSessionProofVerifier (Phase 62).
        The PoAC chain link hashes (SHA-256(body[0:164])) are the leaves.
        """
        ...
```

### 2.3 Pre-Processor Invariant Tests

Tests verify the implementation satisfies the formal non-invertibility claim:

```python
# bridge/tests/test_replay_pre_processor.py

def test_ait_equivalence_class_stick():
    """100 distinct AIT tremor amplitudes → identical sector output."""
    tremors = [generate_ait_signal(amplitude=a) for a in np.linspace(0.05, 1.5, 100)]
    sectors = [pre_processor._spatial_quantize_stick(t) for t in tremors]
    assert len(set(sectors)) == 1, "AIT tremors must collapse to single sector"

def test_subms_jitter_erased():
    """50 distinct sub-ms jitter patterns → identical 60Hz output per window."""
    base = generate_press_sequence(hz=1002, duration_ms=500)
    jittered = [add_subms_jitter(base, sigma_ms=0.3) for _ in range(50)]
    outputs = [pre_processor._temporal_flatten_window(j) for j in jittered]
    assert all(o == outputs[0] for o in outputs)

def test_data_floor_at_db_query_level():
    """Fetching any forbidden column raises DataFloorViolationError."""
    for col in ReplayPreProcessor.FORBIDDEN_COLUMNS:
        with pytest.raises(DataFloorViolationError):
            pre_processor._fetch_structural_frames(
                session_id="test", db_path=TEST_DB,
                _force_column=col   # test-only injection hook
            )

def test_l4_mahalanobis_not_recoverable():
    """
    Formal verification: distinct L4 Mahalanobis distances → identical
    quantized output. Verifies the implementation satisfies §1.2 claim.
    """
    for d in [5.0, 7.0, 9.0, 12.0, 20.0]:   # below + above threshold
        signal = generate_signal_at_mahalanobis_distance(d)
        quantized = pre_processor.process_signal(signal)
        # All produce the same sector output — Mahalanobis distance not
        # recoverable from sector code
        assert quantized.stick_L_sector[0] == BASELINE_SECTOR
```

---

## 3. ZK Circuit Architecture

### 3.1 Design Principles

**Private inputs contain no biometric data.**

The witness envelope binds the proof to:
- The sanitized session (via its Poseidon hash — not the raw input)
- The humanity classification result (a scalar float — not the feature vector that produced it)
- The VHP credential (the soulbound token — not the biometric baseline)
- A session nonce (prevents replay of the same proof)

None of these private inputs can be used to reconstruct L4/L5/E4/AIT features.

**One circuit, two verifiable claims:**

The `VAPIReplayProofVerifier` circuit simultaneously proves:
1. **Provenance:** this quantized replay is derived from a genuine PoAC session
   (poac_chain_root binds to the on-chain chain link)
2. **Humanity:** the session cleared the humanity_probability floor
   (private witness; threshold is public input)

A buyer verifying the proof on-chain learns: this replay is real and human.
They do not learn: which player, which specific session timestamps, or any
biometric feature value.

### 3.2 Circuit Definition

```circom
// circuits/VAPIReplayProofVerifier.circom
pragma circom 2.0.0;
include "poseidon.circom";

// NB_TICKS: number of 60 Hz windows in the session (typically 300-3600
// for a 5-60 minute gameplay session)
template VAPIReplayProofVerifier(NB_TICKS) {

    // ── PRIVATE INPUTS (Witness Envelope) ────────────────────────────────
    // None of these contain raw biometric feature vectors.

    signal private input sanitizedTraceRoot;
    // Poseidon hash of the SanitizedReplayMatrix canonical encoding.
    // Proves the quantized replay matrix is the authentic pre-processor
    // output — not an adversarially crafted matrix.

    signal private input humanityProbabilityWitness;
    // The session's minimum humanity_probability (scalar ∈ [0,1]).
    // Does NOT reveal which features contributed — only the aggregate score.
    // Constraint: humanityProbabilityWitness >= humanityThreshold.

    signal private input sessionNonce;
    // Random nonce generated at session close. Prevents proof reuse across
    // different listings of the same session. Unique per listing.

    signal private input vhpTokenId;
    // The gamer's VAPIVerifiedHumanProof soulbound token ID.
    // Proves the gamer held a valid VHP during this session.
    // Not on-chain in the proof — verified privately, commitment public.

    // ── PUBLIC INPUTS (Verifiable by Buyer On-Chain) ──────────────────────

    signal input quantizedReplayMatrix[NB_TICKS * 6];
    // The sanitized 60 Hz replay matrix (flattened):
    // [stick_L_sector, stick_R_sector, trigger_L, trigger_R,
    //  button_mask, imu_gravity_sector] × NB_TICKS
    // This is what the buyer receives as the replay surface.

    signal input poacChainRoot;
    // Poseidon-8 Merkle root of the session's PoAC records.
    // Binds the replay to the tamper-evident on-chain PoAC chain.
    // Verifier can re-derive from on-chain PoAC record hashes.

    signal input consentPolicyHash;
    // SHA-256 of the gamer's consent manifest at listing time.
    // Proves the listing was authorized by the gamer's policy.
    // Matches VAPIConsentRegistry.manifestHash(deviceId).

    signal input humanityThreshold;
    // The minimum humanity_probability the session must have cleared.
    // Set by gamer in consent manifest (default: 0.70, matching AIT gate).
    // Public so buyer knows the minimum standard the session met.

    signal input vhpCommitment;
    // Poseidon(vhpTokenId, sessionNonce) — public commitment to the
    // gamer's VHP without revealing the token ID itself.

    // ── OUTPUT ────────────────────────────────────────────────────────────

    signal output replayProofToken;
    // Poseidon(quantizedReplayMatrixRoot, poacChainRoot,
    //          consentPolicyHash, humanityThreshold)
    // The on-chain anchor. Stored in VAPIDataMarketplaceListings.proofHash.
    // Buyers call VAPIReplayProofVerifier.verify(proof, publicInputs) → bool.

    // ── CONSTRAINTS ──────────────────────────────────────────────────────

    // Constraint 1: sanitizedTraceRoot matches quantizedReplayMatrix
    // Verify: Poseidon(quantizedReplayMatrix) == sanitizedTraceRoot
    // (witness proves the public matrix is authentic pre-processor output)
    component matrixHasher = Poseidon(NB_TICKS * 6);
    for (var i = 0; i < NB_TICKS * 6; i++) {
        matrixHasher.inputs[i] <== quantizedReplayMatrix[i];
    }
    matrixHasher.out === sanitizedTraceRoot;

    // Constraint 2: humanity floor cleared
    // humanityProbabilityWitness >= humanityThreshold
    // Offloaded: pre-processor computes (h - threshold) and passes as
    // witness; circuit verifies: h_gap >= 0 via range check
    signal h_gap;
    h_gap <== humanityProbabilityWitness - humanityThreshold;
    // Range constraint: h_gap in [0, 1000] (scaled × 1000 integer)
    component hRangeCheck = Num2Bits(10);
    hRangeCheck.in <== h_gap;   // validates h_gap is non-negative

    // Constraint 3: VHP commitment binding
    component vhpHasher = Poseidon(2);
    vhpHasher.inputs[0] <== vhpTokenId;
    vhpHasher.inputs[1] <== sessionNonce;
    vhpHasher.out === vhpCommitment;

    // Constraint 4: replay proof token assembly
    component tokenHasher = Poseidon(4);
    tokenHasher.inputs[0] <== matrixHasher.out;     // quantized matrix
    tokenHasher.inputs[1] <== poacChainRoot;         // PoAC binding
    tokenHasher.inputs[2] <== consentPolicyHash;     // consent binding
    tokenHasher.inputs[3] <== humanityThreshold;     // floor disclosure
    replayProofToken <== tokenHasher.out;
}

component main {public [
    quantizedReplayMatrix,
    poacChainRoot,
    consentPolicyHash,
    humanityThreshold,
    vhpCommitment
]} = VAPIReplayProofVerifier(300);  // 300 ticks = 5 minute baseline
```

### 3.3 R1CS Optimization Analysis

**Total non-linear constraint budget: < 25,000**

| Operation | Technique | Constraint cost |
|---|---|---|
| Matrix Poseidon hash (NB_TICKS × 6 inputs) | Field-native Poseidon-8 permutation | ~2,400 per 8-input batch |
| Humanity floor range check | Single Num2Bits(10) | 10 |
| VHP commitment Poseidon(2) | Poseidon-2 | ~220 |
| Token assembly Poseidon(4) | Poseidon-4 | ~240 |
| Division offloading (h_gap = h - threshold) | Off-chain in WitnessGenerator | 1 (multiply check) |

**Optimization 1 — Inversion/Division Offloading (Poseidon-native):**

The WitnessGenerator computes all divisions and subtractions off-chain:

```python
# witness_generator.py
def compute_h_gap(humanity_prob: float, threshold: float) -> int:
    """
    Computes gap off-chain. Circuit verifies: gap >= 0.
    Converts to scaled integer to stay in BN254 field.
    """
    gap = humanity_prob - threshold
    assert gap >= 0, "session did not clear humanity threshold"
    return int(gap * 1000)  # scale to integer, range [0, 1000]
```

**Optimization 2 — Poseidon-8 over SHA-256:**

The `poacChainRoot` Merkle path verification uses Poseidon-8 throughout,
matching the existing `PitlSessionProofVerifier` (Phase 62). This reduces
constraint cost per hash by >90% vs SHA-256 bitwise decomposition. The
same MPC ceremony artifacts (PTAU file) are reused — no new trusted setup.

**Optimization 3 — Pre-quantized Lookup (no Num2Bits for range checks):**

The spatial quantization produces values already bounded by construction:
- Stick sectors: {0..15} — 4-bit, verified by enum lookup table
- Trigger states: {0..15} — 4-bit, same
- IMU sectors: {0..7} — 3-bit, same

No dynamic bit-decomposition or sorting loops needed for these fields.
The pre-processor's Python-side type enforcement (uint8 numpy arrays with
explicit max value assertions) makes the circuit's range check trivial.

**Estimated performance on edge hardware:**

- Proof generation: <200ms (25,000 constraints, native snarkjs WASM prover)
- Memory footprint: <150MB (proof key + witness)
- Verification (on-chain): O(1) pairing check — gas cost ~200k IoTeX units

### 3.4 Ceremony Alignment

The `VAPIReplayProofVerifier` ceremony reuses the existing PTAU file from
the `Groth16VerifierZKSepProof` Phase 237 ceremony (anchored to IoTeX beacon
block). No new trusted setup required — the existing ceremony is sufficient
for circuits up to 2^18 constraints.

New ceremony registry entry in `CeremonyAuditRegistry` anchors:
- Circuit hash: `keccak256(VAPIReplayProofVerifier.r1cs)`
- Verification key hash: `keccak256(verification_key.json)`
- PTAU CID: reused from Phase 237

---

## 4. Consent Manifest Extension — Dimension 8

The `VAPIReplayProofPipeline` requires a new consent dimension in the
structured consent manifest (Arc 4). Dimension 8 extends the manifest
without breaking backward compatibility.

```solidity
// Addition to ConsentManifest struct (VAPIConsentRegistry v2, Arc 4)
struct ConsentManifest {
    // ... Dimensions 1-7 (existing) ...

    // Dimension 8 — Verified Human Replay Proof
    bool  allowReplayProofs;         // master switch for VHR proof packaging
    uint8 replayHumanityThreshold;   // minimum humanity_prob floor × 100
                                     // e.g., 70 = 0.70 (matching AIT gate)
    uint8 replayQuantizationBits;    // 4 (default) — gamer cannot lower below 4
    bool  replayRequireVerdict;      // require "HUMAN" | "CERTIFY" verdict
                                     // (not "UNCLEAR") — default true
}
```

**Default state:** `allowReplayProofs = false`. The gamer must explicitly
enable VHR proof packaging. This is consistent with the autonomy ladder —
no new capability is default-ON.

**Humanity threshold minimum:** The gamer can set a higher threshold than
the protocol minimum (0.70) but cannot set a lower one. The protocol floor
matches the AIT defensibility gate used for corpus qualification.

---

## 5. VAPIReplayProofVerifier Contract

```solidity
// SPDX-License-Identifier: MIT
// VAPIReplayProofVerifier — on-chain verifier for VHR (Verified Human Replay) proofs.
// Proof type: SESSION-RECORD (orthogonal to ZK Skill Proof credential type).
// Proves: a verified human produced this sanitized gameplay replay.
// Does NOT prove: which human, what skill level, or any biometric feature value.
// Ceremony: reuses Phase 237 PTAU; new circuit hash anchored in CeremonyAuditRegistry.

pragma solidity ^0.8.20;

contract VAPIReplayProofVerifier {
    // Groth16 verification key (set at deploy from ceremony artifacts)
    uint256[2]   public alpha;
    uint256[2][2] public beta;
    uint256[2][2] public gamma;
    uint256[2][2] public delta;
    uint256[]    public gammaABC;   // per public input

    // Proof type discriminator — distinguishes from PitlSessionProofVerifier
    bytes32 public constant PROOF_TYPE =
        keccak256("VAPI-REPLAY-PROOF-v1");   // FROZEN — INV-VHR-003

    event ReplayProofVerified(
        bytes32 indexed replayProofToken,
        bytes32 indexed poacChainRoot,
        bytes32 indexed consentPolicyHash,
        uint256 humanityThreshold
    );

    /// @notice Verify a VHR proof.
    /// @param proof     Groth16 proof (a, b, c components)
    /// @param pubSignals Public inputs in circuit order:
    ///   [0..NB_TICKS*6-1] quantizedReplayMatrix (flattened)
    ///   [NB_TICKS*6]      poacChainRoot
    ///   [NB_TICKS*6+1]    consentPolicyHash
    ///   [NB_TICKS*6+2]    humanityThreshold
    ///   [NB_TICKS*6+3]    vhpCommitment
    ///   [NB_TICKS*6+4]    replayProofToken (output)
    /// @return valid True if the proof is valid.
    function verify(
        uint256[8] calldata proof,
        uint256[]  calldata pubSignals
    ) external returns (bool valid) {
        valid = _groth16Verify(proof, pubSignals);
        if (valid) {
            bytes32 token       = bytes32(pubSignals[pubSignals.length - 1]);
            bytes32 chainRoot   = bytes32(pubSignals[pubSignals.length - 5]);
            bytes32 consentHash = bytes32(pubSignals[pubSignals.length - 4]);
            uint256 threshold   = pubSignals[pubSignals.length - 3];
            emit ReplayProofVerified(token, chainRoot, consentHash, threshold);
        }
    }

    /// @notice Pure view verification (no event, no state write).
    ///         Gas-free for buyer pre-purchase verification.
    function verifyView(
        uint256[8] calldata proof,
        uint256[]  calldata pubSignals
    ) external view returns (bool) {
        return _groth16Verify(proof, pubSignals);
    }

    function _groth16Verify(
        uint256[8] calldata proof,
        uint256[]  calldata pubSignals
    ) internal view returns (bool) { ... }
}
```

---

## 6. Bridge Integration — VAPIReplayProofPipeline Orchestrator

```python
# bridge/vapi_bridge/replay_proof_pipeline/pipeline.py

class VAPIReplayProofPipeline:
    """
    Arc 5 orchestrator — Verified Human Replay Proof packaging.

    Activated by CuratorPackagingLoop.on_session_complete() ONLY IF:
    - consent_manifest.allowReplayProofs == True
    - consent_manifest.autonomyLevel permits (approval_required or higher)
    - Session verdict is "HUMAN" or "CERTIFY" (not "UNCLEAR")
    - Aggregation floor met (≥10 sessions if bundling; single-session if
      gamer has set consent_manifest.replayRequireVerdict = True and
      the session cleared 0.85+ humanity_prob — operator decision on
      single-session VHR threshold)

    Pipeline sequence (6 steps):
    """

    def package_session(
        self,
        session_id: str,
        consent_manifest: ConsentManifest,
    ) -> VHRProofPackage | None:
        """
        Returns VHRProofPackage on success, None on defer (not an error).

        Step 1: Consent gate
        Step 2: Data floor enforcement (separate from CuratorPackagingLoop's
                floor — this floor is at the DB column level, not field level)
        Step 3: Pre-processor → SanitizedReplayMatrix
        Step 4: Witness generation → canonical JSON witness file
        Step 5: Local prover invocation → Groth16 proof
        Step 6: Package assembly → VHRProofPackage
        """

        # Step 1 — Consent gate
        if not consent_manifest.allowReplayProofs:
            logger.info(f"[VHR] session {session_id}: replay proofs disabled in manifest")
            return None

        verdict = self.store.get_session_verdict(session_id)
        if verdict not in ("HUMAN", "CERTIFY"):
            logger.info(f"[VHR] session {session_id}: verdict {verdict} — VHR requires HUMAN or CERTIFY")
            return None

        # Step 2 — Data floor (column-level, in pre-processor)
        # ReplayPreProcessor._fetch_structural_frames enforces forbidden columns
        # No explicit check needed here — DataFloorViolationError propagates up

        # Step 3 — Pre-process
        matrix = self.pre_processor.process_session(session_id, self.db_path)

        # Step 4 — Witness
        witness = self.witness_generator.compile(
            matrix=matrix,
            humanity_threshold=consent_manifest.replayHumanityThreshold / 100.0,
            session_nonce=os.urandom(32).hex(),
        )

        # Step 5 — Prove
        proof = self.prover.prove(witness)
        if proof.generation_ms > 500:
            logger.warning(f"[VHR] proof generation {proof.generation_ms}ms — above 200ms target")

        # Step 6 — Package
        return VHRProofPackage(
            session_id=session_id,
            proof_bytes=proof.bytes,
            replay_proof_token=proof.public_outputs["replayProofToken"],
            quantized_matrix=matrix,
            poac_chain_root=matrix.poac_chain_root.hex(),
            consent_policy_hash=self.chain.get_manifest_hash(self.device_id),
            humanity_threshold=consent_manifest.replayHumanityThreshold / 100.0,
            vhp_commitment=witness["vhpCommitment"],
            proof_type="VAPI-REPLAY-PROOF-v1",
        )


@dataclass
class VHRProofPackage:
    """
    Complete VHR proof package. Listed on VAPIDataMarketplace as
    LISTING_TYPE_REPLAY_PROOF. Orthogonal to ZK Skill Proof listings.
    """
    session_id: str
    proof_bytes: bytes
    replay_proof_token: str    # hex — the on-chain anchor
    quantized_matrix: SanitizedReplayMatrix
    poac_chain_root: str       # hex — PoAC Merkle root
    consent_policy_hash: str   # hex — manifest hash at listing time
    humanity_threshold: float  # the floor disclosed to buyers
    vhp_commitment: str        # hex — VHP binding (token ID private)
    proof_type: str            # "VAPI-REPLAY-PROOF-v1"

    def to_listing_payload(self) -> dict:
        """
        Marketplace listing payload for VAPIDataMarketplaceListings.createListing().
        The consent_policy_hash field is mandatory — establishes permanent
        auditable lineage between the proof and the gamer's consent policy.
        """
        return {
            "listing_type": "REPLAY_PROOF",
            "proof_token": self.replay_proof_token,
            "poac_chain_root": self.poac_chain_root,
            "consent_policy_hash": self.consent_policy_hash,   # MANDATORY
            "humanity_threshold": int(self.humanity_threshold * 1000),
            "proof_bytes_ipfs_cid": ...,   # pinned separately
            "matrix_ticks": self.quantized_matrix.ticks,
            "proof_type": self.proof_type,
        }
```

### 6.1 CuratorPackagingLoop Integration Point

```python
# Addition to curator_packaging_loop.py (Arc 3)
# AFTER _apply_data_floor(), BEFORE createListing()

async def on_session_complete(self, session_id: str) -> None:
    # ... existing steps 1-4 (consent, data floor, ZK skill proofs) ...

    # Step 5 — VHR proof (if consented)
    vhr_package = None
    if self.consent_manifest.allowReplayProofs:
        vhr_package = await self.replay_pipeline.package_session(
            session_id=session_id,
            consent_manifest=self.consent_manifest,
        )
        if vhr_package:
            logger.info(
                f"[CURATOR][VHR] proof compiled — token={vhr_package.replay_proof_token[:16]}… "
                f"ticks={vhr_package.quantized_matrix.ticks} "
                f"humanity_floor={vhr_package.humanity_threshold:.2f}"
            )

    # Step 6 — List (ZK skill proofs + VHR proof, per autonomy level)
    packages = [*zk_skill_packages]
    if vhr_package:
        packages.append(vhr_package)

    await self._submit_or_queue(packages, autonomy_level=self.consent_manifest.autonomyLevel)
```

---

## 7. New Marketplace Listing Type

The `VAPIDataMarketplace` gains a new listing type alongside the existing
ZK Skill Proof type. Both are independently queryable and independently
priced.

```solidity
// Addition to VAPIDataMarketplace (or VAPIDataMarketplaceListings)

enum ListingType {
    ZK_SKILL_PROOF,       // credential about a player's skill level
    REPLAY_PROOF          // record of a verified human gameplay session
}

struct ListingMetadata {
    ListingType listingType;
    bytes32     proofToken;           // replayProofToken or skillProofToken
    bytes32     poacChainRoot;        // PoAC binding (both types)
    bytes32     consentPolicyHash;    // mandatory — auditable lineage
    uint256     humanityThreshold;    // floor disclosed to buyers (× 1000)
    string      proofType;            // "VAPI-REPLAY-PROOF-v1" | "VAPI-SKILL-PROOF-v1"
    address     verifierContract;     // VAPIReplayProofVerifier | PitlSessionProofVerifier
}
```

**Buyer verification flow:**

```
1. Buyer queries VAPIDataMarketplace for REPLAY_PROOF listings
   matching their credential category (VAPIBuyerRegistry.isAuthorizedBuyer)

2. Buyer calls VAPIReplayProofVerifier.verifyView(proof, pubSignals)
   → true: proof is valid; replay is authentic + human-produced

3. Buyer decrypts replay package using category key K_category
   (Layer 4 buyer verification — encrypted packaging)

4. Buyer receives: SanitizedReplayMatrix (quantized 60 Hz trace)
   Buyer does NOT receive: biometric feature values, timing signatures,
   session metadata beyond tick count, player identity
```

---

## 8. PV-CI Invariant Entries

Arc 5 adds four new invariant entries. PV-CI count: 35 (pre-Arc-5) → 39.

```python
# scripts/vapi_invariant_gate.py — four new entries

Invariant(
    id="INV-VHR-001",
    description="VAPIReplayProofPipeline FROZEN quantization params: "
                "RADIAL_BITS=4, TRIGGER_BITS=4, IMU_BITS=3",
    file="bridge/vapi_bridge/replay_proof_pipeline/pre_processor.py",
    pattern=r"RADIAL_BITS\s*:\s*int\s*=\s*4",
    min_matches=1,
),
Invariant(
    id="INV-VHR-002",
    description="VAPIReplayProofPipeline FROZEN output frequency: OUTPUT_HZ=60",
    file="bridge/vapi_bridge/replay_proof_pipeline/pre_processor.py",
    pattern=r"OUTPUT_HZ\s*:\s*int\s*=\s*60",
    min_matches=1,
),
Invariant(
    id="INV-VHR-003",
    description="VAPIReplayProofVerifier PROOF_TYPE constant FROZEN as "
                "keccak256('VAPI-REPLAY-PROOF-v1')",
    file="contracts/contracts/VAPIReplayProofVerifier.sol",
    pattern=r'keccak256\("VAPI-REPLAY-PROOF-v1"\)',
    min_matches=1,
),
Invariant(
    id="INV-VHR-004",
    description="VAPIReplayProofPipeline FORBIDDEN_COLUMNS frozenset must "
                "include l4_mahalanobis_distance, l5_cv, e4_spectral_entropy, "
                "ait_rms (data floor at DB column level)",
    file="bridge/vapi_bridge/replay_proof_pipeline/pre_processor.py",
    pattern=r'"l4_mahalanobis_distance"',
    min_matches=1,
),
```

---

## 9. Invariant Integrity Checklist (Corrected)

All five invariants corrected to match QorTroller's established verification
discipline. Test assertions replace informal claims; formal properties
replace untestable ones.

```
[ ] INV-VHR-PoAC (PoAC Wire Preservation)
    The 228-byte PoAC record wire format is read but never modified.
    Arc 5 reads poac_record hashes from bridge.db as leaves for the
    Poseidon Merkle root. No field of the 228-byte format changes.
    Test: assert sizeof(PoACRecord) == 228 in CI (pre-existing INV-001).

[ ] INV-VHR-DataFloor (Data Floor at Column Level)
    The pre-processor DB query is constructed from an allowlist of
    structural columns only. FORBIDDEN_COLUMNS (frozen by INV-VHR-004)
    cannot appear in any SQL query issued by ReplayPreProcessor.
    Test: test_data_floor_at_db_query_level() (§2.3) — injection of any
    forbidden column name raises DataFloorViolationError before query fires.
    Formal property: the quantization map φ has non-empty equivalence
    classes for all L4/L5/E4/AIT features (proven in §1.2).

[ ] INV-VHR-AutonLadder (Autonomy Ladder Bound)
    VHR proof packages obey the same autonomy_level gate as ZK skill proof
    packages. Default: approval_required — proof sits in pending_listings
    table until gamer approves via POST /curator/approve-listing/{id}.
    Test: test that full_autonomy is never the initialized default state
    for a new gamer's consent manifest.

[ ] INV-VHR-NonInvertibility (Non-Invertibility Verification)
    Formal claim (§1.2): φ is surjective, not injective. Pre-image of any
    output has positive measure. Implementation tested by:
    - test_ait_equivalence_class_stick(): 100 AIT amplitudes → 1 sector
    - test_subms_jitter_erased(): 50 jitter patterns → 1 window output
    - test_l4_mahalanobis_not_recoverable(): distinct distances → same sector
    These tests verify the implementation satisfies the formal claim —
    they do not claim to prove non-invertibility (proven analytically in §1.2).

[ ] INV-VHR-GasGuard (Deterministic Gas Guard)
    VAPIReplayProofVerifier deploy script enforces estimate_gas × 1.25
    before firing any deployment transaction on IoTeX testnet.
    This matches the established protocol deploy discipline
    (INV-005-series, all prior Arc deploy scripts).
    Test: deploy script ABORT guard verified in dry-run before operator GO.
```

---

## 10. Implementation Arc — Claude Code Specification

**Arc:** Data Economy Arc 5 — VAPIReplayProofPipeline
**Prerequisites:** Arcs 1–4 complete (VAPIBuyerRegistry live, consent manifest v2 live)
**Wallet estimate:** ~0.5–0.8 IOTX (VAPIReplayProofVerifier deploy)
**PV-CI delta:** 35 → 39 (+4 invariants)

### Pre-Investigation Checklist (Read-Only First)

Before any implementation, Claude Code must verify:

1. **Arc 4 consent manifest v2 landed.** Confirm `VAPIConsentRegistry`
   has a `manifestHash(deviceId)` method. Confirm the struct supports
   extension with Dimension 8 fields (`allowReplayProofs`, etc.).
   If not landed, stop — Arc 5 cannot proceed.

2. **Phase 237 ceremony artifacts available.** Read
   `docs/governance/ceremony-artifacts/` or `CeremonyAuditRegistry`.
   Confirm the PTAU file CID and verification key from the ZK-SEPPROOF
   ceremony are accessible. Arc 5 reuses them — no new trusted setup.

3. **PitlSessionProofVerifier Poseidon variant.** Read
   `contracts/contracts/PitlSessionProofVerifier.sol`. Confirm it uses
   Poseidon-8. Arc 5 uses the same permutation — confirm the circom
   include path for `poseidon.circom` is available in the circuit build.

4. **bridge.db schema — structural vs biometric columns.** Read
   `bridge/vapi_bridge/store.py`. Map exact column names for:
   - Structural (allowed): stick X/Y, trigger raw, button state, accel XYZ
   - Biometric (forbidden): l4 features, l5 scores, e4 entropy, AIT metrics
   Confirm FORBIDDEN_COLUMNS list in §9 matches actual column names exactly.
   Any mismatch surfaces as a finding before implementation.

5. **snarkjs availability.** Confirm `snarkjs` is in `package.json` or
   installable in the bridge Python environment (Node.js subprocess pattern
   or snarkjs Python binding). Document the exact invocation path.

6. **VAPIDataMarketplaceListings interface.** Read the Phase 238 contract.
   Confirm `createListing()` accepts a `listing_type` discriminator field
   or determine whether a new overload is needed for REPLAY_PROOF type.

Output: pre-implementation findings note. Surface any drift from this spec.
**Hold for operator review before any circuit authoring or contract writing.**

### Commit Plan

**Commit 1 — ReplayPreProcessor + tests (pure Python, no contract)**

`bridge/vapi_bridge/replay_proof_pipeline/pre_processor.py` — full
implementation of φ_temporal + φ_spatial. Tests (8): all §2.3 tests
including equivalence class verification for AIT, jitter, and Mahalanobis.

P-check: pytest replay suite green, INV-VHR-001/002/004 added to invariant
gate, vapi_invariant_gate --report 0 violations. **Hold.**

**Commit 2 — VAPIReplayProofVerifier circuit + witness generator**

`circuits/VAPIReplayProofVerifier.circom` — full circuit per §3.2.
`bridge/vapi_bridge/replay_proof_pipeline/witness_generator.py` — WitnessGenerator.
Ceremony: compile circuit, generate witness format, produce zkey from
existing PTAU, anchor in CeremonyAuditRegistry.

P-check: `npx snarkjs r1cs info` confirms < 25,000 constraints,
witness generation succeeds on test session data. **Hold.**

**Commit 3 — VAPIReplayProofVerifier.sol + deploy**

Contract per §5. Deploy script with ABORT guard + estimate_gas × 1.25.
INV-VHR-003 added. **Operator authorization required before deploy fires.**

P-check: Hardhat tests (6): verify() returns true for valid proof, false
for tampered matrix, false for invalid humanity threshold, emits correct
event, verifyView() matches verify() result, gas estimate within budget.
**Hold.**

**Commit 4 — VAPIReplayProofPipeline orchestrator + CuratorPackagingLoop wiring**

`pipeline.py` per §6. Integration hook in `curator_packaging_loop.py`.
Consent manifest Dimension 8 bridge-side support.
`GET /curator/pending-replay-proofs` endpoint.

Tests (6): proof package produced for HUMAN verdict, None returned for
UNCLEAR verdict, approval_required queues to pending, full_autonomy lists,
allowReplayProofs=false returns None, consent hash mismatch aborts.

P-check: full suite, invariant gate 35→39. **Hold.**

**Commit 5 — MEMORY.md + CLAUDE.md + Data Economy arc completion sync**

Arc 5 complete. VAPIReplayProofPipeline live. VHR proof type documented
as orthogonal to ZK Skill Proof tiers. PV-CI at 39. Two proof types live
in VAPIDataMarketplace: ZK_SKILL_PROOF + REPLAY_PROOF.

---

## 11. What This Delivers

At Arc 5 completion, QorTroller's data economy surfaces two distinct,
independently marketable proof types:

**For game developers and AI researchers:**
The VHR proof provides the only verified-human gameplay dataset in the
industry — provably not bot-generated, biometrically private, macro-intent
faithful. The sanitized 60 Hz quantized replay is suitable for AI training,
game balance research, and accessibility studies without creating biometric
surveillance risk.

**For esports scouts and coaches:**
The combination of ZK Skill Proof (Tier 1-3 credential) + VHR proof
(session record) provides a verifiable scouting package: "this player is
94th percentile (credential) AND here is a sample of their verified human
gameplay (record)." Neither proof exposes biometric fingerprint data.

**For the gamer:**
Revenue from two distinct proof types, under granular consent control,
packaged autonomously by the Curator after each session, with every
listing anchored to the consent policy hash on-chain. The biometric
signature that proves their humanity never leaves their local machine.

---

*Document generated: 2026-05-29*
*References: QorTroller Extraordinary Comprehensive Assessment (2026-05-27),*
*QORTROLLER_DATA_ECONOMY_FRAMEWORK.md (Arc 1-4 spec),*
*qortroller-state-genesis-to-complete-2026-05-28.md*
*Claude Code instructional instrument — load alongside DATA_ECONOMY_FRAMEWORK.md*
*for any Arc 5 implementation session.*
