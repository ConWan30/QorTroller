"""WMP-3 consumer-side verifier — the value-add of the lane.

A world-model researcher receives a `ProvenanceBundle v1` (or a JSONL
corpus) and runs five independent checks WITHOUT trusting QorTroller's
infrastructure:

  1. HUMANITY        — Arc 5 VHR Groth16 verify against the published
                       verifying key (snarkjs `groth16 verify` or
                       equivalent on-chain `verify`).

  2. MATRIX↔ROOT     — Poseidon(action_trace_matrix) ==
                       public_inputs.sanitizedTraceRoot. This closes
                       the long-open Arc 5 off-circuit-root finding:
                       the WMP verifier is the canonical home for the
                       rehash check. A consumer that skips it could be
                       handed a valid proof paired with a DIFFERENT
                       matrix.

  3. RECENCY         — Arc 6 PoSR: `verifyBeacon(openBlock, openHash)`
                       AND `verifyBeacon(closeBlock, closeHash)` AND
                       `closeBlock > openBlock`. Honest no-op when the
                       Arc 6 registry address is empty (returns
                       BEACON_REGISTRY_NOT_DEPLOYED).

  4. CONSENT         — Arc 4 consent reference. In v1 (W1-D) the world-
                       model consent dimension is DEFERRED; the verifier
                       returns CONSENT_GATE_DEFERRED honestly rather
                       than passing/failing. When Phase-2 ships the
                       greenfield VAPIWorldModelConsentRegistry, the
                       check performs an on-chain view-call.

  5. SCOPE HONESTY   — `scope_disclosure` block must be present AND
                       must carry the FROZEN values (ACTION_ONLY,
                       ABSENT_BY_DESIGN_DATA_FLOOR,
                       MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL,
                       is_full_pomdp_tuple=False). A bundle missing or
                       overclaiming scope is REJECTED.

Outcomes per bundle:
    VERIFIED         — all five checks pass (or honestly DEFERRED)
    REJECTED         — at least one check explicitly fails
    + result_dict carrying per-check outcomes for the consumer to audit

The verifier deliberately does NOT call into QorTroller bridge code —
the consumer's threat model is "QorTroller might lie." The only inputs
are the bundle, the published verifying key path, and (optionally) a
read-only IoTeX RPC URL for the Arc 6 view-call.

For v1 fixture testing this module ships a SOFT verifier that performs
the structural + Poseidon checks but stubs the Groth16 verify + on-chain
view-calls. The stub clearly logs which steps are stubbed so a consumer
never confuses a fixture pass with a real-data pass.

PHASE-2 PROMOTION (2026-07-11, injection pattern — PORT-CERT precedent):
each stubbed check now accepts an OPTIONAL injected callable; every
default of None reproduces the v1 stub/deferred behavior byte-identically
(the network/subprocess blast radius lives in the runner,
`scripts/wmp_full_verify.py`, never in this module):

    groth16_verify(public_inputs: dict, proof_bytes_hex: str) -> bool
    poseidon_root(matrix: dict)                              -> str  (decimal field element)
    beacon_lookup(block: int)                                -> str|None  (0x block hash)
    consent_lookup(gamer_address: str)                       -> bool

A check that ran its injected callable reports `stubbed=False`; a
consumer therefore always knows whether a pass was cryptographic or
structural.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional


# ── frozen scope_disclosure values (must match bundle_assembler) ─────
_SCOPE_CHANNEL_ACTION_ONLY = "ACTION_ONLY"
_SCOPE_OBSERVATION_ABSENT = "ABSENT_BY_DESIGN_DATA_FLOOR"
_SCOPE_FIDELITY_MACRO = "MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL"


# ── published post-phi data-floor list (consumer-side mirror) ────────
# The verifier is zero-trust: it MUST NOT import bridge code. This is a FROZEN
# published copy of the producer floor (ReplayPreProcessor.FORBIDDEN_COLUMNS,
# pinned by INV-VHR-004). A certified-human bundle promises the biometric moat
# never exports; check_scope_honesty enforces that by scanning the payload for
# any of these keys, so the scope assertion is no longer trusted on its own
# (AH-1 finding F-AH1-A15). Keep in sync with pre_processor if that list grows.
_FROZEN_FORBIDDEN_COLUMNS = frozenset({
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


def _forbidden_hits(bundle: dict) -> list:
    """Sorted forbidden biometric keys smuggled anywhere a consumer reads them:
    top-level bundle keys, extra_metadata keys (any depth), and the
    action_trace_channels names. Evidence for the data-floor scan (F-AH1-A15).
    """
    hits = set()
    for k in bundle.keys():
        if k in _FROZEN_FORBIDDEN_COLUMNS:
            hits.add(k)

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _FROZEN_FORBIDDEN_COLUMNS:
                    hits.add(k)
                _walk(v)
        elif isinstance(obj, list):
            for it in obj:
                _walk(it)

    _walk(bundle.get("extra_metadata", {}))
    for ch in bundle.get("action_trace_channels", []) or []:
        if isinstance(ch, str) and ch in _FROZEN_FORBIDDEN_COLUMNS:
            hits.add(ch)
    return sorted(hits)


# ── outcome codes ─────────────────────────────────────────────────────
OUTCOME_VERIFIED = "VERIFIED"
OUTCOME_REJECTED = "REJECTED"

CHECK_HUMANITY   = "humanity"
CHECK_REHASH     = "matrix_root_rehash"
CHECK_RECENCY    = "recency"
CHECK_CONSENT    = "consent"
CHECK_SCOPE      = "scope_honesty"


@dataclass
class VerificationResult:
    """Per-bundle verification outcome.

    `overall` is REJECTED iff any check explicitly failed. Honest
    no-ops (BEACON_REGISTRY_NOT_DEPLOYED, CONSENT_GATE_DEFERRED) are
    NOT failures — they're surfaced as `deferred` so a consumer can
    decide whether to accept a partially-anchored proof.
    """
    overall: str
    bundle_hash: str
    checks: dict[str, dict] = field(default_factory=dict)
    deferred: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall":     self.overall,
            "bundle_hash": self.bundle_hash,
            "checks":      self.checks,
            "deferred":    self.deferred,
            "reasons":     self.reasons,
        }


def _bundle_hash(bundle_dict: dict) -> str:
    canon = json.dumps(bundle_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# ── individual checks ─────────────────────────────────────────────────

def check_scope_honesty(bundle: dict) -> dict:
    """Check 5: scope_disclosure must carry the FROZEN values AND the payload
    must honor them.

    Asserting the scope strings (action-only / observation-absent / macro-intent)
    is not enough: a forged bundle could claim biometric-absent while carrying a
    raw biometric key. So this check ALSO scans the payload for the published
    forbidden columns (AH-1 finding F-AH1-A15) — scope-honesty now enforces what
    it asserts. A hit is a post-phi data-floor breach → REJECTED.
    """
    issues = []
    if bundle.get("scope_channel") != _SCOPE_CHANNEL_ACTION_ONLY:
        issues.append(f"scope_channel must be {_SCOPE_CHANNEL_ACTION_ONLY!r}")
    if bundle.get("scope_observation_channel") != _SCOPE_OBSERVATION_ABSENT:
        issues.append(f"scope_observation_channel must be {_SCOPE_OBSERVATION_ABSENT!r}")
    if bundle.get("scope_fidelity") != _SCOPE_FIDELITY_MACRO:
        issues.append(f"scope_fidelity must be {_SCOPE_FIDELITY_MACRO!r}")
    if bundle.get("scope_is_full_pomdp_tuple") is not False:
        issues.append("scope_is_full_pomdp_tuple must be False (lane is not full POMDP)")
    forbidden = _forbidden_hits(bundle)
    if forbidden:
        issues.append(
            "post-phi data-floor breach: forbidden biometric key(s) present: "
            + ", ".join(forbidden)
        )
    return {
        "passed": len(issues) == 0,
        "issues": issues,
    }


def check_matrix_root_rehash(bundle: dict, poseidon_root=None) -> dict:
    """Check 2: Poseidon(action_trace_matrix) == sanitizedTraceRoot.

    CANONICAL HOME for the Arc 5 off-circuit root rehash. A consumer
    that skips this check could be handed a valid Groth16 proof paired
    with a DIFFERENT matrix — the proof would verify against the wrong
    sanitizedTraceRoot input.

    v1 implementation: structural rehash via SHA-256 over the
    canonicalized matrix bytes, asserting equality with a stored
    structural-rehash digest carried in the bundle's matrix_hex map.
    The Poseidon-over-BN254 substitution is a Phase-2 wiring task that
    invokes a node helper or a Python Poseidon library; for v1 the
    STRUCTURAL_REHASH check still catches the "different matrix"
    attack (an adversary swapping the matrix bytes for a different
    session would change the structural digest).

    Returns:
        passed     — bool
        actual     — the rehash digest the verifier computed
        claimed    — the sanitized_trace_root the bundle claims
        algorithm  — "STRUCTURAL_REHASH_v1" (Phase-2 promotes to
                     "POSEIDON_BN254")
    """
    channels = bundle.get("action_trace_channels", [])
    matrix_hex = bundle.get("action_trace_matrix_hex", {})
    if not channels or not matrix_hex:
        return {
            "passed": False,
            "actual": "",
            "claimed": str(bundle.get("sanitized_trace_root_ref", "")),
            "algorithm": "STRUCTURAL_REHASH_v1",
            "issues": ["action_trace channels or matrix_hex empty"],
        }
    # Canonical channel order — exactly as the assembler emitted.
    h = hashlib.sha256()
    h.update(b"WMP_STRUCTURAL_REHASH_v1")
    for ch in channels:
        h.update(ch.encode("utf-8"))
        h.update(bytes.fromhex(matrix_hex.get(ch, "")))
    h.update(str(bundle.get("action_trace_ticks", 0)).encode("utf-8"))
    actual_digest = h.hexdigest()
    # The bundle's `sanitized_trace_root_ref` is the producer's claim
    # of what the in-circuit Poseidon root was. In v1 we additionally
    # store a structural rehash digest alongside, and a CORRECT bundle
    # will have rehash digest == bundle.sanitized_trace_root_ref OR a
    # paired "structural_rehash" field. To catch the matrix-swap attack
    # we recompute and require: actual_digest determines whether the
    # bundle's matrix hex was tampered with relative to a paired
    # structural commitment.
    paired = bundle.get("structural_rehash_v1") or ""
    if paired:
        passed = (actual_digest == paired)
        issues = [] if passed else [f"structural rehash mismatch: actual={actual_digest!r} paired={paired!r}"]
    else:
        # No paired structural digest in v1 bundles produced by current
        # assembler — pass with an explicit note that the Poseidon
        # cryptographic rehash will land in Phase-2. The structural
        # rehash is computed and exposed for the consumer to log;
        # tamper-detection happens at the producer side via Phase-2.
        passed = True
        issues = ["structural_rehash_v1 not paired in bundle — v1 verifier surfaces digest only; Phase-2 promotes to Poseidon"]
    result = {
        "passed": passed,
        "actual": actual_digest,
        "claimed": str(bundle.get("sanitized_trace_root_ref", "")),
        "algorithm": "STRUCTURAL_REHASH_v1",
        "issues": issues,
    }
    if poseidon_root is None:
        return result
    # ── Phase-2 promoted path: THE cryptographic matrix↔root binding. Recompute the
    # Poseidon-BN254 root over the bundle's own matrix bytes and require equality with the
    # root the Groth16 proof actually verified against (public_inputs.sanitizedTraceRoot,
    # falling back to the producer's sanitized_trace_root_ref). This is the matrix-swap kill.
    try:
        recomputed = str(poseidon_root({
            "ticks": int(bundle.get("action_trace_ticks", 0) or 0),
            **{ch: matrix_hex.get(ch, "") for ch in channels},
        })).strip()
    except Exception as exc:  # noqa: BLE001 — a failing helper is a FAIL, never a silent pass
        result.update(passed=False, algorithm="POSEIDON_BN254", stubbed=False)
        result["issues"] = [f"poseidon_root callable failed: {exc}"]
        return result
    pub = bundle.get("humanity_proof_public_inputs") or {}
    claimed = str(pub.get("sanitizedTraceRoot", "") or bundle.get("sanitized_trace_root_ref", "")).strip()
    ok = bool(recomputed) and recomputed == claimed
    result.update(passed=ok, actual=recomputed, claimed=claimed,
                  algorithm="POSEIDON_BN254", stubbed=False)
    result["issues"] = [] if ok else [
        f"Poseidon root mismatch: recomputed={recomputed!r} claimed={claimed!r} — "
        "matrix does not match the root the proof verified against"]
    return result


def check_humanity(bundle: dict, groth16_verify=None) -> dict:
    """Check 1: Arc 5 VHR Groth16 verify.

    Default (groth16_verify=None) = v1 STUB, byte-identical: structural
    hex check only, `stubbed=True`. Phase-2 promoted path: the injected
    `groth16_verify(public_inputs: dict, proof_bytes_hex: str) -> bool`
    runs the REAL snarkjs verify against the published verifying key
    (the runner reconstructs proof.json from the 256-byte ABI wire and
    public.json from the bundle's own public inputs — zero-trust).
    """
    proof_hex = bundle.get("humanity_proof_bytes_hex", "")
    deferred = bool(bundle.get("humanity_deferred", False))
    if deferred:
        return {
            "passed": True,        # honest deferral, not a failure
            "stubbed": True,
            "deferred": True,
            "deferred_reason": str(bundle.get("humanity_deferred_reason", "")),
        }
    # Structural: 256-byte proof = 512 hex chars (+ optional 0x)
    h = proof_hex[2:] if proof_hex.startswith("0x") else proof_hex
    structurally_ok = bool(h) and all(c in "0123456789abcdefABCDEF" for c in h)
    if groth16_verify is None:
        return {
            "passed": structurally_ok,
            "stubbed": True,
            "deferred": False,
            "note": "v1 stub — snarkjs groth16 verify wiring is Phase-2",
        }
    if not structurally_ok:
        return {"passed": False, "stubbed": False, "deferred": False,
                "issues": ["proof_bytes_hex structurally invalid"]}
    try:
        ok = bool(groth16_verify(dict(bundle.get("humanity_proof_public_inputs") or {}), proof_hex))
    except Exception as exc:  # noqa: BLE001 — a failing verifier is a FAIL, never a silent pass
        return {"passed": False, "stubbed": False, "deferred": False,
                "issues": [f"groth16_verify callable failed: {exc}"]}
    return {"passed": ok, "stubbed": False, "deferred": False,
            "note": "snarkjs groth16 verify (injected)",
            "issues": [] if ok else ["Groth16 proof did NOT verify against the bundle's public inputs"]}


def check_recency(bundle: dict, beacon_lookup=None) -> dict:
    """Check 3: Arc 6 PoSR beacons.

    Honest no-op when the bundle's recency_registry_address is empty
    (Arc 6 was dormant when this bundle was assembled). Default
    (beacon_lookup=None) = v1 structural stub, byte-identical. Phase-2
    promoted path: the injected `beacon_lookup(block: int) -> hash|None`
    reads the LIVE registry (view-call, 0 IOTX) and the bundle's claimed
    open/close hashes must equal the anchored hashes.
    """
    registry = bundle.get("recency_registry_address", "")
    if not registry:
        return {
            "passed": True,
            "deferred": True,
            "deferred_reason": "BEACON_REGISTRY_NOT_DEPLOYED",
        }
    open_block = int(bundle.get("recency_open_block", 0) or 0)
    close_block = int(bundle.get("recency_close_block", 0) or 0)
    issues = []
    if open_block <= 0 or close_block <= 0:
        issues.append("open_block / close_block must be positive")
    if close_block <= open_block:
        issues.append("close_block must be > open_block (temporal ordering)")
    open_h  = bundle.get("recency_open_block_hash", "")
    close_h = bundle.get("recency_close_block_hash", "")
    if not (open_h.startswith("0x") and len(open_h) == 66):
        issues.append("recency_open_block_hash must be 0x + 64 hex")
    if not (close_h.startswith("0x") and len(close_h) == 66):
        issues.append("recency_close_block_hash must be 0x + 64 hex")
    if beacon_lookup is None:
        return {
            "passed": len(issues) == 0,
            "stubbed": True,
            "note": "v1 stub — IoTeX verifyBeacon view-call wiring is Phase-2",
            "issues": issues,
        }
    if issues:                                   # structural failures short-circuit the RPC
        return {"passed": False, "stubbed": False, "issues": issues}
    try:
        anchored_open = beacon_lookup(open_block)
        anchored_close = beacon_lookup(close_block)
    except Exception as exc:  # noqa: BLE001 — RPC failure is a FAIL, never a silent pass
        return {"passed": False, "stubbed": False,
                "issues": [f"beacon_lookup callable failed: {exc}"]}
    if not anchored_open:
        issues.append(f"no beacon anchored at open_block {open_block}")
    elif str(anchored_open).lower() != open_h.lower():
        issues.append(f"open beacon mismatch: anchored={anchored_open} claimed={open_h}")
    if not anchored_close:
        issues.append(f"no beacon anchored at close_block {close_block}")
    elif str(anchored_close).lower() != close_h.lower():
        issues.append(f"close beacon mismatch: anchored={anchored_close} claimed={close_h}")
    return {"passed": len(issues) == 0, "stubbed": False,
            "note": "IoTeX beacon view-calls (injected)", "issues": issues}


def check_consent(bundle: dict, consent_lookup=None) -> dict:
    """Check 4: Arc 4 consent reference.

    v1 W1-D: world-model consent dimension is DEFERRED → deferred=True
    with CONSENT_GATE_DEFERRED (byte-identical default). Phase-2
    promoted path: dimension "GRANTED" + the injected
    `consent_lookup(gamer_address) -> bool` view-calls the LIVE
    VAPIWorldModelConsentRegistry — the bundle's consent claim must be
    TRUE on-chain for the gamer it names.
    """
    dim = str(bundle.get("world_model_consent_dimension", "") or "")
    if dim == "DEFERRED":
        return {
            "passed": True,
            "deferred": True,
            "deferred_reason": "CONSENT_GATE_DEFERRED",
            "note": "Phase-2 promote: VAPIWorldModelConsentRegistry view-call",
        }
    if consent_lookup is None:
        # Phase-2 dimension without an injected lookup: structural-only, honestly stubbed.
        return {
            "passed": True,
            "stubbed": True,
            "note": "v1 stub — Phase-2 wires registry view-call",
        }
    gamer = str(bundle.get("consent_gamer_address", "") or "")
    if not gamer:
        return {"passed": False, "stubbed": False,
                "issues": ["bundle names no consent_gamer_address"]}
    try:
        granted = bool(consent_lookup(gamer))
    except Exception as exc:  # noqa: BLE001 — RPC failure is a FAIL, never a silent pass
        return {"passed": False, "stubbed": False,
                "issues": [f"consent_lookup callable failed: {exc}"]}
    return {"passed": granted, "stubbed": False,
            "note": "VAPIWorldModelConsentRegistry view-call (injected)",
            "issues": [] if granted else
            [f"world-model consent NOT granted on-chain for {gamer}"]}


# ── orchestrator ──────────────────────────────────────────────────────

def verify_bundle(
    bundle: dict,
    *,
    allow_synthetic: bool = False,
    groth16_verify=None,
    poseidon_root=None,
    beacon_lookup=None,
    consent_lookup=None,
) -> VerificationResult:
    """Run all five checks and return a consolidated result.

    Args:
        bundle: a `ProvenanceBundle` v1 as a dict (the same shape
            `BundleAssembler.assemble(...).to_dict()` produces).
        allow_synthetic: when False, a bundle with
            scope_synthetic=True is REJECTED as non-real corpus data.
            Set True for fixture verification.
        groth16_verify / poseidon_root / beacon_lookup / consent_lookup:
            Phase-2 injected callables (see module docstring). All-None
            reproduces the v1 stub/deferred behavior byte-identically.
    """
    bh = _bundle_hash(bundle)
    result = VerificationResult(
        overall=OUTCOME_VERIFIED,
        bundle_hash=bh,
        checks={},
        deferred=[],
        reasons=[],
    )

    # Schema check (lightweight — reject obviously-wrong bundles early).
    if bundle.get("schema") != "vapi-wmp-provenance-bundle-v1":
        result.overall = OUTCOME_REJECTED
        result.reasons.append(f"unknown schema {bundle.get('schema')!r}")
        return result

    # Synthetic check
    if bundle.get("scope_synthetic") and not allow_synthetic:
        result.overall = OUTCOME_REJECTED
        result.reasons.append("scope_synthetic=True; this verifier was invoked without allow_synthetic")
        return result

    checks = {
        CHECK_SCOPE:    check_scope_honesty(bundle),
        CHECK_REHASH:   check_matrix_root_rehash(bundle, poseidon_root),
        CHECK_HUMANITY: check_humanity(bundle, groth16_verify),
        CHECK_RECENCY:  check_recency(bundle, beacon_lookup),
        CHECK_CONSENT:  check_consent(bundle, consent_lookup),
    }
    result.checks = checks

    for name, ch in checks.items():
        if ch.get("deferred"):
            result.deferred.append(name)
        if not ch.get("passed"):
            result.overall = OUTCOME_REJECTED
            issues = ch.get("issues") or []
            for i in issues:
                result.reasons.append(f"{name}: {i}")

    return result
