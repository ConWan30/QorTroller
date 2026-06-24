"""F5 — Provenance Quadrille assembler (read-only, packaging-only, no new crypto).

Fuses the FOUR provenance chains QorTroller already ships into one read-only attestation that a
grind run is consistent across BOTH the product AND the process that built it:

  • GIC   (grind_chain,          VAPI-GIC-GENESIS-v1)  — COGNITIVE:   per-session adjudication
  • WEC   (watchdog_chain,       VAPI-WEC-GENESIS-v1)  — OPERATIONAL: per-restart bridge continuity
  • CORPUS(corpus_snapshot, VAPI-CORPUS-SNAPSHOT-v1)  — CORPUS:      wiki + agent-root integrity
  • SIC   (synthesis_integrity_chain, VAPI-SIC-GENESIS-v1) — METHODOLOGY: per-cycle synthesis

The novelty is COVERAGE: no other protocol chains both its product (GIC/WEC/CORPUS) and the
methodology that builds it (SIC) under one verification. See the VSD synthesis note
s-f5-provenance-quadrille (+ the F2 sibling s-f2-recency-bound-presence-built for the shared shape).

WHAT THIS MODULE IS / IS NOT (honesty rails, held across the module):
  • Read-only / packaging ONLY. It READS four already-computed chain-STATUS dicts (each
    {head_hex, intact, n_links}); it does NOT read the chain, recompute any chain, sign, or
    anchor. Callers pass the status (e.g. from get_grind_chain_status / get_watchdog_event_chain_
    status / corpus snapshot status / the VSD ledger). Mirrors WMP-lane + recency_bound_presence.
  • NO new FROZEN-v1 family. The unified root is a plain SHA-256 packaging digest over the four
    heads — deliberately NO `b"VAPI-...-v1"` byte-literal domain tag, so it does not register as a
    commitment family or trip the crypto-drift detectors. SCHEMA is a lowercase packaging string.
  • NO new PV-CI invariant (179 unchanged).
  • Anti-overclaim by construction. The unified root is the digest that WOULD be anchored; the VPM
    label declares on_chain_anchor=false until the operator-fired IoTeX anchor lands (as GIC_100
    was). visual_state is `live` ONLY when all four chains are intact; any broken/absent chain ->
    `unverified`. verify_attestation re-checks visual_state == derived, rejecting a hand-edited
    `live` over a broken quadrille. Same discipline as F2 + VSD-emits-VPM.

Pure stdlib. Reversible. No chain write, no FROZEN edit.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

SCHEMA_VERSION = "vapi-provenance-quadrille-v1"   # packaging string (NOT a FROZEN domain tag)

# Mirror of the FROZEN VPM artifact visual-state vocabulary (scripts/vsd_ui_compiler.py:322).
VPM_VISUAL_STATES = ("live", "dry-run", "emulated", "frozen-disabled", "revoked", "unverified")

# The four chains, in canonical order (fixes the unified-root byte order). The labels match the
# shipped genesis tags; this tuple is the canonical iteration order, not a new commitment.
CHAIN_ORDER = ("gic", "wec", "corpus", "sic")
CHAIN_DIMENSION = {
    "gic": "cognitive", "wec": "operational", "corpus": "corpus", "sic": "methodology",
}


class QuadrilleVerdict(str, Enum):
    QUADRILLE_INTACT = "quadrille_intact"   # all four chains present, intact, well-formed heads
    QUADRILLE_BROKEN = "quadrille_broken"   # at least one chain present but intact=False
    INSUFFICIENT     = "insufficient"       # at least one chain missing / malformed head


@dataclass(frozen=True)
class ChainStatus:
    """One chain's already-computed status (read from its *_chain_status surface)."""
    head_hex: Optional[str]
    intact: bool
    n_links: int


@dataclass(frozen=True)
class LegResult:
    ok: bool
    reason: str


def _is_hex32(s: object) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def verify_chain_leg(name: str, st: ChainStatus) -> LegResult:
    """A chain leg passes iff it is intact, has >=1 link, and carries a well-formed 32B head.
    A genesis-only / empty chain (head None or n_links 0) is INSUFFICIENT, not a pass."""
    if st.head_hex is None or st.n_links < 1:
        return LegResult(False, f"{name}: no established head (n_links={st.n_links})")
    if not _is_hex32(st.head_hex):
        return LegResult(False, f"{name}: head not 32B hex")
    if not st.intact:
        return LegResult(False, f"{name}: chain not intact (break detected)")
    return LegResult(True, f"{name}: intact ({st.n_links} links)")


def _derive_visual_state(verdict: QuadrilleVerdict) -> str:
    """Anti-overclaim resolver: only an all-intact quadrille earns `live`; else `unverified`."""
    return "live" if verdict == QuadrilleVerdict.QUADRILLE_INTACT else "unverified"


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_unified_root(heads_in_order: list[str]) -> str:
    """SHA-256 over the four heads in CHAIN_ORDER — the digest that WOULD be anchored on IoTeX.
    Plain packaging digest: NO domain tag, NOT a FROZEN commitment family (operator anchors it)."""
    return hashlib.sha256(_canonical(heads_in_order)).hexdigest()


@dataclass(frozen=True)
class QuadrilleAttestation:
    schema: str
    verdict: str
    visual_state: str
    grind_session_id: str
    chains: dict                 # name -> {ok, reason, head_hex, intact, n_links, dimension}
    unified_root: Optional[str]  # set only when QUADRILLE_INTACT; else None
    vpm_label: dict
    ts_ns: int
    attestation_hash: str


def assemble_quadrille(chains: dict, *, grind_session_id: str, ts_ns: int) -> QuadrilleAttestation:
    """Fuse the four chain statuses into one provenance-quadrille attestation + a VPM honesty label.
    `chains` maps each of {gic,wec,corpus,sic} -> ChainStatus. Read-only; anchors nothing."""
    legs: dict = {}
    all_ok = True
    any_broken = False
    for name in CHAIN_ORDER:
        st = chains.get(name)
        if not isinstance(st, ChainStatus):
            legs[name] = {"ok": False, "reason": f"{name}: status missing", "head_hex": None,
                          "intact": False, "n_links": 0, "dimension": CHAIN_DIMENSION[name]}
            all_ok = False
            continue
        r = verify_chain_leg(name, st)
        legs[name] = {"ok": r.ok, "reason": r.reason, "head_hex": st.head_hex,
                      "intact": st.intact, "n_links": st.n_links, "dimension": CHAIN_DIMENSION[name]}
        if not r.ok:
            all_ok = False
            if st.head_hex is not None and st.n_links >= 1 and not st.intact:
                any_broken = True

    if all_ok:
        verdict = QuadrilleVerdict.QUADRILLE_INTACT
    elif any_broken:
        verdict = QuadrilleVerdict.QUADRILLE_BROKEN
    else:
        verdict = QuadrilleVerdict.INSUFFICIENT

    visual_state = _derive_visual_state(verdict)
    unified_root = (compute_unified_root([legs[n]["head_hex"] for n in CHAIN_ORDER])
                    if verdict == QuadrilleVerdict.QUADRILLE_INTACT else None)

    label_body = {
        "schema": "vsd-vpm-label-v1",            # reuse the shipped VPM honesty-label grammar
        "vpm_id": "QR-PROVENANCE-QUADRILLE-v1",
        "audience": "auditors / partner due-diligence",
        "visual_state": visual_state,
        "capture_mode": "live",
        "proof_weight": 3,                       # CHAIN_ONLY: cross-checks existing chain heads
        "anchor_status": "none",
        "revocation_status": "active",
        "integrity_label": {
            "proof_type": "PROVENANCE-QUADRILLE",
            "capture_mode": "live",
            "raw_biometrics_exposed": False,
            "consent_active": True,
            "zk_verified": False,                # honest: head cross-check, not a ZK proof
            "on_chain_anchor": False,            # honest: unified root not anchored until operator GO
            "proof_weight": 3,
            "revocation_status": "active",
            "limitations": [
                "covers product (GIC/WEC/CORPUS) + methodology (SIC) provenance intactness only",
                "unified_root is the digest that WOULD be anchored; on-chain anchor is operator-fired",
            ],
        },
        "ts_ns": int(ts_ns),
    }
    label_body["label_hash"] = hashlib.sha256(_canonical(label_body)).hexdigest()

    body = {
        "schema": SCHEMA_VERSION, "verdict": verdict.value, "visual_state": visual_state,
        "grind_session_id": str(grind_session_id), "chains": legs, "unified_root": unified_root,
        "vpm_label": label_body, "ts_ns": int(ts_ns),
    }
    att_hash = hashlib.sha256(_canonical(body)).hexdigest()
    return QuadrilleAttestation(
        schema=SCHEMA_VERSION, verdict=verdict.value, visual_state=visual_state,
        grind_session_id=str(grind_session_id), chains=legs, unified_root=unified_root,
        vpm_label=label_body, ts_ns=int(ts_ns), attestation_hash=att_hash)


def verify_attestation(att: dict) -> tuple[bool, str]:
    """Re-verify a serialized quadrille attestation, pure stdlib. Checks (1) canonical hash binds
    the body, (2) visual_state ∈ frozen VPM set, (3) anti-overclaim visual_state == derived(verdict),
    (4) unified_root present iff intact (and recomputes it), (5) label never claims zk/anchor."""
    if not isinstance(att, dict) or att.get("schema") != SCHEMA_VERSION:
        return False, f"schema not {SCHEMA_VERSION}"
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    if hashlib.sha256(_canonical(body)).hexdigest() != att.get("attestation_hash"):
        return False, "attestation_hash mismatch (body tampered)"
    if att.get("visual_state") not in VPM_VISUAL_STATES:
        return False, f"visual_state {att.get('visual_state')!r} not in frozen VPM set"
    try:
        verdict = QuadrilleVerdict(att.get("verdict"))
    except ValueError:
        return False, f"unknown verdict {att.get('verdict')!r}"
    if att.get("visual_state") != _derive_visual_state(verdict):
        return False, f"overclaim: visual_state {att.get('visual_state')!r} != derived"
    chains = att.get("chains", {})
    if verdict == QuadrilleVerdict.QUADRILLE_INTACT:
        heads = [chains.get(n, {}).get("head_hex") for n in CHAIN_ORDER]
        if any(h is None for h in heads):
            return False, "intact verdict but a chain head is missing"
        if att.get("unified_root") != compute_unified_root(heads):
            return False, "unified_root does not match the four heads"
    elif att.get("unified_root") is not None:
        return False, "non-intact verdict must not carry a unified_root"
    il = att.get("vpm_label", {}).get("integrity_label", {})
    if il.get("zk_verified") is not False or il.get("on_chain_anchor") is not False:
        return False, "label must not claim zk_verified or on_chain_anchor"
    return True, f"provenance-quadrille attestation verified (verdict={verdict.value})"
