"""F2 — Recency-Bound Living Presence verifier (packaging-only, no new crypto).

Fuses three ALREADY-SHIPPED QorTroller primitives into one session attestation:

  • PoCP  (l9_presence.coupling.CouplingFeatures) — input→output causal coupling:
          a live human's stick motion causally drives camera motion; a time-SHUFFLED
          input (negative control) must lose that coupling. Coupling present + negative
          control collapsing = causally LIVE (anti-relay).
  • PoSR  (replay_proof_pipeline.posr.PoSRSessionBeacon) — IoTeX temporal beacon binding:
          open/close beacons on cadence-aligned blocks, close strictly AFTER open =
          recency BOUND, cannot backdate or replay (anti-replay).
  • GIC   (grind_chain) — Grind Integrity Chain link: cognitive-session continuity.

The fusion closes the relay+replay seam that either primitive alone leaves open — the exact
cloud-gaming-bot stealth pattern the BT-calibration anchor names as the real adversary. See the
VSD synthesis notes s-feature-fusion-enhancements (F2) + s-fusion-near-term-leverage.

WHAT THIS MODULE IS / IS NOT (honesty rails, held across the module):
  • Packaging/verification ONLY. It READS already-computed leg verdicts (the CouplingFeatures
    dict, the beacon block numbers + commitment hexes, the GIC link hex). It does NOT compute
    coupling (no numpy), does NOT read the chain, does NOT sign or anchor anything.
  • No new FROZEN-v1 family. SCHEMA_VERSION is a packaging string, not a commitment domain tag.
  • No new PV-CI invariant. Mirrors the WMP-lane discipline (bundle_assembler.py).
  • Anti-overclaim by construction. PoCP is validated but NOT standalone-tournament-grade per
    the L9 arc, so EVERY attestation carries a mandatory claim_scope declaring it session-bound
    and NOT tournament-grade, and the VPM label never claims zk_verified / on_chain_anchor.
    This is the same anti-overclaim discipline the VSD loop applies to itself (VSD-emits-VPM).

Pure stdlib. Reversible. No chain write, no FROZEN edit.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

SCHEMA_VERSION = "vapi-recency-bound-presence-v1"   # packaging string (NOT a FROZEN domain tag)

# Mirror of the FROZEN VPM artifact visual-state vocabulary (scripts/vsd_ui_compiler.py:322;
# hyphen convention of vapi-vpm-artifact-v1). Reproduced as plain strings to stay import-light,
# same precedent as vsd_vpm_label.py. A drift guard test asserts subset of the FROZEN enum.
VPM_VISUAL_STATES = ("live", "dry-run", "emulated", "frozen-disabled", "revoked", "unverified")

# PoCP thresholds mirror l9_presence.coupling defaults (COUPLING_THRESHOLD / LAG band). Kept as
# module constants so the verifier is self-contained; if the l9 defaults move, T-RBP-VOCAB-style
# review surfaces it (these are verification floors, not the authoritative oracle config).
COUPLING_THRESHOLD = 0.20          # coupling_score floor (l9 L9_COUPLING_THRESHOLD)
NEG_CONTROL_MARGIN = 0.10          # coupling_score must beat the shuffled negative control by this
LAG_MIN_MS = 0.0
LAG_MAX_MS = 500.0                 # human voluntary-reaction band (l9 L9_LAG_MAX_MS)
ANCHOR_CADENCE_BLOCKS = 64         # mirrors posr.ANCHOR_CADENCE_BLOCKS / INV-TBR-002

# The mandatory ceiling. Load-bearing: F2 STRENGTHENS an existing presence capability; it does
# not manufacture a standalone tournament-grade one. This string is always present on a pass.
CLAIM_SCOPE = ("session-bound living presence; strengthens existing capability; "
               "NOT standalone-tournament-grade (PoCP not tournament-grade per L9 arc)")


class PresenceVerdict(str, Enum):
    """The fusion's own verdict (distinct from the VPM visual_state honesty literal)."""
    RECENCY_BOUND_PRESENT      = "recency_bound_present"        # all three legs verified
    PRESENT_NOT_RECENCY_BOUND  = "present_not_recency_bound"    # causally live but recency unbound
    DECOUPLED_REVIEW           = "decoupled_review"             # PoCP failed: input≁output
    INSUFFICIENT               = "insufficient"                 # missing/unusable leg evidence


@dataclass(frozen=True)
class PoCPLeg:
    """Already-computed PoCP evidence (read from CouplingFeatures + negative_control())."""
    coupling_score: float
    lag_ms: float
    decoupled_energy: float
    coupled: bool
    negative_control: Optional[float] = None   # None => causal evidence incomplete (strict)
    synthetic: bool = False


@dataclass(frozen=True)
class PoSRLeg:
    """Already-read PoSR session beacon endpoints (block numbers + 32B commitment hexes)."""
    open_block_number: int
    close_block_number: int
    open_commitment_hex: str
    close_commitment_hex: str


@dataclass(frozen=True)
class GICLeg:
    """Already-read GIC link (32B hex) + the grind session it belongs to."""
    gic_link_hex: str
    grind_session_id: str


@dataclass(frozen=True)
class LegResult:
    ok: bool
    reason: str


def _is_hex32(s: object) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def verify_pocp_leg(leg: PoCPLeg) -> LegResult:
    """Causally-live check. The negative-control collapse is the anti-relay core: a relayed /
    replayed stream may show apparent coupling, but shuffled input must lose it."""
    if leg.synthetic:
        return LegResult(False, "PoCP leg is synthetic (real capture required)")
    if not leg.coupled:
        return LegResult(False, "PoCP not coupled (input does not drive output)")
    if leg.coupling_score < COUPLING_THRESHOLD:
        return LegResult(False, f"coupling_score {leg.coupling_score:.3f} < {COUPLING_THRESHOLD}")
    if not (LAG_MIN_MS <= leg.lag_ms <= LAG_MAX_MS):
        return LegResult(False, f"lag_ms {leg.lag_ms} outside human band [{LAG_MIN_MS},{LAG_MAX_MS}]")
    if leg.negative_control is None:
        return LegResult(False, "negative control absent (causal evidence incomplete)")
    if leg.coupling_score - leg.negative_control < NEG_CONTROL_MARGIN:
        return LegResult(False, (f"negative control did not collapse: coupling {leg.coupling_score:.3f} "
                                 f"- nc {leg.negative_control:.3f} < {NEG_CONTROL_MARGIN}"))
    return LegResult(True, "causally live (coupled + negative control collapsed)")


def verify_posr_leg(leg: PoSRLeg) -> LegResult:
    """Recency-bound check. Forward ordering (close > open) = no backdating; cadence alignment
    ties the open beacon to the registry's anchored cadence (anti-replay)."""
    if not _is_hex32(leg.open_commitment_hex):
        return LegResult(False, "open_commitment not 32B hex")
    if not _is_hex32(leg.close_commitment_hex):
        return LegResult(False, "close_commitment not 32B hex")
    if leg.open_commitment_hex.lower() == leg.close_commitment_hex.lower():
        return LegResult(False, "open and close commitments identical (no temporal span)")
    if type(leg.open_block_number) is not int or type(leg.close_block_number) is not int:
        return LegResult(False, "block numbers must be int")
    if leg.close_block_number <= leg.open_block_number:
        return LegResult(False, (f"close block {leg.close_block_number} not after open "
                                 f"{leg.open_block_number} (backdate/replay guard)"))
    if leg.open_block_number % ANCHOR_CADENCE_BLOCKS != 0:
        return LegResult(False, (f"open block {leg.open_block_number} not cadence-aligned "
                                 f"(% {ANCHOR_CADENCE_BLOCKS} != 0)"))
    return LegResult(True, "recency bound (forward beacon span on cadence-aligned open)")


def verify_gic_leg(leg: GICLeg) -> LegResult:
    """Cognitive-continuity check: the session carries a well-formed GIC link."""
    if not _is_hex32(leg.gic_link_hex):
        return LegResult(False, "gic_link not 32B hex")
    if not isinstance(leg.grind_session_id, str) or not leg.grind_session_id.strip():
        return LegResult(False, "grind_session_id empty")
    return LegResult(True, "cognitive continuity present (GIC link well-formed)")


def _derive_visual_state(verdict: PresenceVerdict, any_synthetic: bool) -> str:
    """Anti-overclaim resolver mirroring the VPM grammar: a synthetic input never renders live;
    only a fully recency-bound, real-capture fusion earns `live`; everything else is `unverified`."""
    if any_synthetic:
        return "emulated"
    if verdict == PresenceVerdict.RECENCY_BOUND_PRESENT:
        return "live"
    return "unverified"


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class RecencyBoundPresenceAttestation:
    schema: str
    verdict: str
    visual_state: str
    pocp: dict
    posr: dict
    gic: dict
    claim_scope: str
    vpm_label: dict
    ts_ns: int
    attestation_hash: str


def verify_recency_bound_presence(pocp: PoCPLeg, posr: PoSRLeg, gic: GICLeg,
                                  *, ts_ns: int) -> RecencyBoundPresenceAttestation:
    """Fuse the three legs into one recency-bound presence attestation + a VPM honesty label.
    Read-only: computes a verdict over already-computed evidence; writes/anchors nothing."""
    rp, rs, rg = verify_pocp_leg(pocp), verify_posr_leg(posr), verify_gic_leg(gic)
    any_synthetic = pocp.synthetic

    if rp.ok and rs.ok and rg.ok:
        verdict = PresenceVerdict.RECENCY_BOUND_PRESENT
    elif rp.ok and rg.ok and not rs.ok:
        verdict = PresenceVerdict.PRESENT_NOT_RECENCY_BOUND
    elif not rp.ok and (pocp.coupled is False or pocp.coupling_score < COUPLING_THRESHOLD):
        verdict = PresenceVerdict.DECOUPLED_REVIEW
    else:
        verdict = PresenceVerdict.INSUFFICIENT

    visual_state = _derive_visual_state(verdict, any_synthetic)
    pocp_d = {"ok": rp.ok, "reason": rp.reason, "coupling_score": pocp.coupling_score,
              "lag_ms": pocp.lag_ms, "negative_control": pocp.negative_control,
              "synthetic": pocp.synthetic}
    posr_d = {"ok": rs.ok, "reason": rs.reason, "open_block": posr.open_block_number,
              "close_block": posr.close_block_number}
    gic_d = {"ok": rg.ok, "reason": rg.reason, "grind_session_id": gic.grind_session_id}

    label_body = {
        "schema": "vsd-vpm-label-v1",            # reuse the shipped VPM honesty-label grammar
        "vpm_id": "QR-RECENCY-PRESENCE-v1",
        "audience": "tournament organizers / verifiers",
        "visual_state": visual_state,
        "capture_mode": "emulated" if any_synthetic else "live",
        "proof_weight": 3,                       # CHAIN_ONLY: read verdicts, not fresh ZK biometric
        "anchor_status": "none",
        "revocation_status": "active",
        "integrity_label": {
            "proof_type": "RECENCY-BOUND-PRESENCE",
            "capture_mode": "emulated" if any_synthetic else "live",
            "raw_biometrics_exposed": False,
            "consent_active": True,
            "zk_verified": False,                # honest: fusion of verdicts, not a ZK proof
            "on_chain_anchor": False,            # honest: beacon referenced, not anchored here
            "proof_weight": 3,
            "revocation_status": "active",
            "limitations": [CLAIM_SCOPE, "beacon referenced, not anchored by this verifier"],
        },
        "ts_ns": int(ts_ns),
    }
    label_body["label_hash"] = hashlib.sha256(_canonical(label_body)).hexdigest()

    body = {
        "schema": SCHEMA_VERSION, "verdict": verdict.value, "visual_state": visual_state,
        "pocp": pocp_d, "posr": posr_d, "gic": gic_d, "claim_scope": CLAIM_SCOPE,
        "vpm_label": label_body, "ts_ns": int(ts_ns),
    }
    att_hash = hashlib.sha256(_canonical(body)).hexdigest()
    return RecencyBoundPresenceAttestation(
        schema=SCHEMA_VERSION, verdict=verdict.value, visual_state=visual_state,
        pocp=pocp_d, posr=posr_d, gic=gic_d, claim_scope=CLAIM_SCOPE,
        vpm_label=label_body, ts_ns=int(ts_ns), attestation_hash=att_hash)


def verify_attestation(att: dict) -> tuple[bool, str]:
    """Re-verify a serialized attestation, pure stdlib. Checks (1) canonical hash binds the body,
    (2) visual_state ∈ frozen VPM set, (3) anti-overclaim — visual_state matches verdict+synthetic,
    (4) the VPM label never claims zk/anchor, (5) claim_scope present."""
    if not isinstance(att, dict) or att.get("schema") != SCHEMA_VERSION:
        return False, f"schema not {SCHEMA_VERSION}"
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    if hashlib.sha256(_canonical(body)).hexdigest() != att.get("attestation_hash"):
        return False, "attestation_hash mismatch (body tampered)"
    if att.get("visual_state") not in VPM_VISUAL_STATES:
        return False, f"visual_state {att.get('visual_state')!r} not in frozen VPM set"
    try:
        verdict = PresenceVerdict(att.get("verdict"))
    except ValueError:
        return False, f"unknown verdict {att.get('verdict')!r}"
    any_synthetic = bool(att.get("pocp", {}).get("synthetic"))
    expected = _derive_visual_state(verdict, any_synthetic)
    if att.get("visual_state") != expected:
        return False, f"overclaim: visual_state {att.get('visual_state')!r} != derived {expected!r}"
    il = att.get("vpm_label", {}).get("integrity_label", {})
    if il.get("zk_verified") is not False or il.get("on_chain_anchor") is not False:
        return False, "label must not claim zk_verified or on_chain_anchor"
    if not att.get("claim_scope"):
        return False, "claim_scope (anti-overclaim ceiling) missing"
    return True, f"recency-bound presence attestation verified (verdict={verdict.value})"
