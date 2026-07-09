"""EVENT-BIND increment 3 — PoSR recency compose (replay resistance).

EVENT-BIND (event_bind.py) alone closes cross-source SPLICE via a shared record_hash. It does NOT
close full-session REPLAY: a faithful replay reproduces self-consistent OLD record_hash anchors, so
the crypto join still passes. This layer composes the crypto binding with the Arc 6 PoSR temporal
beacon (the on-chain-anchored IoTeX block hash the PoSP A3-b `temporal_beacon` field already carries):
a REPLAY_RESISTANT authorship claim requires BOTH `binding_is_cryptographic` (splice-proof) AND a
FRESH beacon (the session was witnessed against a recent block).

HONEST LIMITS (docs/event-bind-design-2026-07-09.md §2):
  - CLOSES the naive/stale replay: an OLD or ABSENT beacon fails recency -> not REPLAY_RESISTANT.
  - Does NOT close a compromised HOST that re-captures old records under a FRESH beacon — that is the
    witness-independence long arc (verifier_independence stays False).
  - CANNOT bind the beacon PER-RECORD: the 228-byte PoAC body is FROZEN, so the block hash cannot be
    folded into record_hash. The beacon binds at the SESSION level (the PoSP A3-b reference / PoSR
    sidecar), so recency is a session-scoped bar, not a per-kill one.

The reference block (the "now" the beacon is judged against) is INJECTED — this module does NO RPC.
PURE stdlib. Composes event_bind.EventBindReport with a PoSP temporal_beacon dict.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .event_bind import EventBindReport

# PoSR anchor cadence (blocks). Provenance: VAPI-TEMPORAL-BEACON-v1, ANCHOR_CADENCE=64
# (Arc 6). Restated here so this module carries no bridge import (event_bind's discipline).
ANCHOR_CADENCE_BLOCKS = 64
# Default freshness bar: 4 cadences. IoTeX testnet empirical ~2.616 s/block (Arc 6 D6-1) ->
# 256 blocks ~= 11 min, matching the ~11.2 min BLOCKHASH window. Overridable per caller.
DEFAULT_MAX_STALENESS_BLOCKS = 4 * ANCHOR_CADENCE_BLOCKS      # 256

RECENCY_SCHEMA = "qortroller-event-bind-recency-v0"


class RecencyVerdict(str, Enum):
    FRESH = "FRESH"                 # beacon within the staleness bar of the reference block
    STALE = "STALE"                # beacon too old — the naive/stale replay signature
    NO_BEACON = "NO_BEACON"        # session carries no temporal_beacon (recency unprovable)
    UNVERIFIABLE = "UNVERIFIABLE"  # malformed beacon / future block (anti-forgery)


class ReplayResistance(str, Enum):
    REPLAY_RESISTANT = "REPLAY_RESISTANT"   # splice-proof AND fresh
    SPLICE_PROOF_ONLY = "SPLICE_PROOF_ONLY"  # crypto-bound but stale/no beacon -> replay NOT resisted
    TEMPORAL_ONLY = "TEMPORAL_ONLY"          # not even splice-proof (temporal join)
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class RecencyResult:
    verdict: RecencyVerdict
    beacon_block: Optional[int]
    reference_block: Optional[int]
    staleness_blocks: Optional[int]
    max_staleness_blocks: int
    note: str


def recency_verdict(temporal_beacon: Optional[dict], reference_block: Optional[int], *,
                    max_staleness_blocks: int = DEFAULT_MAX_STALENESS_BLOCKS) -> RecencyResult:
    """Judge a session's PoSP `temporal_beacon` against an injected reference (current/latest anchored)
    block. FRESH iff 0 <= reference_block - beacon_block <= max_staleness_blocks. A beacon claiming a
    block NEWER than the reference is UNVERIFIABLE (a session cannot be witnessed against the future)."""
    def _r(v, bb, sb, note):
        return RecencyResult(v, bb, reference_block if isinstance(reference_block, int) else None,
                             sb, max_staleness_blocks, note)

    if not temporal_beacon:
        return _r(RecencyVerdict.NO_BEACON, None, None, "no temporal_beacon on the session (PoSP A3-b absent)")
    bb = temporal_beacon.get("block_number")
    if not isinstance(bb, int) or bb < 0:
        return _r(RecencyVerdict.UNVERIFIABLE, None, None, f"beacon block_number not a non-negative int: {bb!r}")
    if not isinstance(reference_block, int) or reference_block < 0:
        return _r(RecencyVerdict.UNVERIFIABLE, bb, None, "no valid reference block injected")
    staleness = reference_block - bb
    if staleness < 0:
        return _r(RecencyVerdict.UNVERIFIABLE, bb, staleness,
                  "beacon block is NEWER than the reference block (cannot witness against the future)")
    if staleness <= max_staleness_blocks:
        return _r(RecencyVerdict.FRESH, bb, staleness,
                  f"beacon {staleness} blocks behind reference (<= {max_staleness_blocks})")
    return _r(RecencyVerdict.STALE, bb, staleness,
              f"beacon {staleness} blocks behind reference (> {max_staleness_blocks}) — stale-replay signature")


@dataclass(frozen=True)
class ReplayResistanceResult:
    verdict: ReplayResistance
    binding_is_cryptographic: bool
    recency: RecencyResult

    def to_dict(self) -> dict:
        return {"schema": RECENCY_SCHEMA, "verdict": self.verdict.value,
                "binding_is_cryptographic": self.binding_is_cryptographic,
                "recency_verdict": self.recency.verdict.value,
                "beacon_block": self.recency.beacon_block,
                "reference_block": self.recency.reference_block,
                "staleness_blocks": self.recency.staleness_blocks,
                "max_staleness_blocks": self.recency.max_staleness_blocks,
                "note": self.recency.note}


def replay_resistance(bind_report: EventBindReport, temporal_beacon: Optional[dict],
                      reference_block: Optional[int], *,
                      max_staleness_blocks: int = DEFAULT_MAX_STALENESS_BLOCKS) -> ReplayResistanceResult:
    """Compose EVENT-BIND crypto binding with PoSR recency. REPLAY_RESISTANT iff every authored kill is
    crypto-bound (splice-proof) AND the session beacon is FRESH. Crypto-but-stale/absent-beacon ->
    SPLICE_PROOF_ONLY (the honest downgrade: splice is closed, replay is NOT). Not crypto -> TEMPORAL_ONLY."""
    rec = recency_verdict(temporal_beacon, reference_block, max_staleness_blocks=max_staleness_blocks)
    crypto = bool(bind_report.binding_is_cryptographic)
    if rec.verdict == RecencyVerdict.UNVERIFIABLE:
        v = ReplayResistance.UNVERIFIABLE
    elif not crypto:
        v = ReplayResistance.TEMPORAL_ONLY
    elif rec.verdict == RecencyVerdict.FRESH:
        v = ReplayResistance.REPLAY_RESISTANT
    else:                                            # crypto but STALE / NO_BEACON
        v = ReplayResistance.SPLICE_PROOF_ONLY
    return ReplayResistanceResult(verdict=v, binding_is_cryptographic=crypto, recency=rec)
