"""WMP Verifiable Derived-Claim (VDC-1) — the gamer's certified data yields a
DETERMINISTIC, BOUND, independently-verifiable derived claim.

The value ladder this opens (honest about which rung v0 is on):

  Today            to trust "trigger engagement was 9%%" a buyer must obtain the
                   raw matrix AND trust the seller computed it honestly.
  VDC v0 (here)    the derived property is a PURE function of the certified
                   bundle, BOUND to that bundle's hash, and RE-DERIVED by the
                   verifier (recompute + byte-compare — the seller cannot lie
                   about it, and it cannot be swapped onto a different session).
                   A party WITH the bundle confirms the claim independently; a
                   party WITHOUT it sees a claim cryptographically bound to a
                   certified-human session.
  VDC + ZK (next)  prove the derivation WITHOUT disclosing the matrix
                   (zero-knowledge) — the "withhold + prove" rung. Ceremony-
                   gated; named per-claim; NOT claimed by v0.

REFERENCE-AND-BIND (the skill_strata / PoSP pattern): the claim cites the parent
bundle by hash; verification is re-derivation, not trust. The derivation reads
ONLY the post-φ action channels and REUSES the AH-1-hardened data-floor rail
(`sdk.wmp_verify`) — a claim derived from a bundle carrying a forbidden biometric
column is refused at both build and verify.

Purest "Core Controllers of their Data": the gamer publishes a verifiable claim
ABOUT their play without the consumer having to trust QorTroller.

Pure stdlib + sdk.wmp_verify; all I/O lives in scripts/build_wmp_derived_claim.py.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter

# Reuse the AH-1-hardened rails directly (deliberate — one frozen data-floor,
# one canonical bundle hash; no duplication, and VDC inherits the A15 fix).
from sdk.wmp_verify import (
    _bundle_hash,
    _forbidden_hits,
    _FROZEN_FORBIDDEN_COLUMNS,
)

SCHEMA = "vapi-wmp-derived-claim-v1"
PARENT_SCHEMA = "vapi-wmp-provenance-bundle-v1"

# Honesty ceiling — shipped verbatim in every claim and re-checked at verify.
CEILING = {
    "derived_not_raw": (
        "a VDC is a DERIVED property of one certified bundle; the claim record "
        "does not itself contain the raw post-φ matrix"),
    "n_equals_1": (
        "each claim is a property of a SINGLE session — never a population "
        "percentile, ELO, or cross-player rank (the population gate stands)"),
    "deterministic_bound_not_zk": (
        "v0 makes the derivation deterministic + bound to the parent bundle hash "
        "+ re-derived by the verifier; it does NOT prove the derivation in "
        "zero-knowledge — withholding-the-matrix is the named ZK upgrade "
        "(ceremony-gated), not a v0 claim"),
    "action_only": (
        "derivations read ONLY post-φ action channels; forbidden biometric "
        "columns are refused (reuses the AH-1 data-floor rail)"),
    "no_buyer_implied": (
        "demonstration of the claim surface; no marketplace transaction implied; "
        "TGE frozen"),
}


# ── matrix access (post-φ action channels only) ─────────────────────────

def _channel_values(bundle: dict, channel: str) -> list:
    """Decode one channel's per-tick integer values from its hex, inferring
    bytes-per-tick from the declared tick count. Refuses forbidden channels."""
    if channel in _FROZEN_FORBIDDEN_COLUMNS:
        raise ValueError(f"refusing to read forbidden channel {channel!r}")
    ticks = int(bundle.get("action_trace_ticks", 0) or 0)
    hexstr = str((bundle.get("action_trace_matrix_hex") or {}).get(channel, ""))
    if ticks <= 0 or not hexstr:
        raise ValueError(f"channel {channel!r}: empty matrix or non-positive ticks")
    raw = bytes.fromhex(hexstr)
    if len(raw) % ticks != 0:
        raise ValueError(f"channel {channel!r}: {len(raw)} bytes not divisible by {ticks} ticks")
    bpt = len(raw) // ticks
    return [int.from_bytes(raw[i * bpt:(i + 1) * bpt], "big") for i in range(ticks)]


# ── derivations (pure functions over the post-φ matrix) ─────────────────
# Each returns a JSON-serializable `value` dict that MUST include a
# `channels_read` list (verify asserts it excludes every forbidden column) and
# a `definition` string (the derivation shipped in-band, self-documenting).

def derive_trigger_engagement_fraction(bundle: dict) -> dict:
    """Fraction of ticks with a trigger pressed (trigger_L_state>0 OR
    trigger_R_state>0). This is the Phase 235-GAD ACTIVE_GAMEPLAY signal made
    into a verifiable derived claim (grounded in an existing protocol signal,
    not an invented metric). Honest at N=1 — a property of THIS session.
    """
    ticks = int(bundle.get("action_trace_ticks", 0) or 0)
    lt = _channel_values(bundle, "trigger_L_state")
    rt = _channel_values(bundle, "trigger_R_state")
    active = sum(1 for i in range(ticks) if lt[i] > 0 or rt[i] > 0)
    return {
        "ticks": ticks,
        "active_ticks": active,
        "fraction": round(active / ticks, 6) if ticks else 0.0,
        "channels_read": ["trigger_L_state", "trigger_R_state"],
        "definition": ("fraction of ticks where trigger_L_state>0 OR "
                       "trigger_R_state>0 (Phase 235-GAD ACTIVE_GAMEPLAY signal)"),
    }


# The player-action channels (imu_gravity_sector is EXCLUDED — always-on postural
# gravity, not a discrete action; its "entropy" would measure orientation, not input).
_ACTION_CHANNELS = ("stick_L_sector", "stick_R_sector", "trigger_L_state",
                    "trigger_R_state", "button_mask")

# Stick NEUTRAL sentinel = the centered/deadzone sector. FROZEN by the φ encoding
# (pre_processor NEUTRAL_SECTOR = RADIAL_SECTORS = 2**RADIAL_BITS; RADIAL_BITS=4 is
# pinned by INV-VHR-001). Sectors 0..15 are ACTIVE directions; 16 = centered — so
# "engaged" is `sector != 16`, NOT `sector != 0` (value 0 is a real direction).
_NEUTRAL_SECTOR = 16


def _shannon_millibits(values: list) -> tuple:
    """(entropy_millibits, symbols, normalized_milli) — all INTEGERS for
    deterministic re-derivation (log2 is float-ULP-sensitive across platforms;
    millibits = round(bits × 1000) is stable). normalized = H / log2(symbols)."""
    n = len(values)
    if n == 0:
        return 0, 0, 0
    counts = Counter(values)
    symbols = len(counts)
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * math.log2(p)
    h_max = math.log2(symbols) if symbols > 1 else 0.0
    norm = (h / h_max) if h_max > 0 else 0.0
    return round(h * 1000), symbols, round(norm * 1000)


def derive_action_entropy(bundle: dict) -> dict:
    """Per-channel Shannon entropy of the player-action distribution — the
    variety / unpredictability of the inputs in THIS session. Honest at N=1
    (a property of one session's distribution, not a cross-player comparison).
    Reported in integer millibits (bits × 1000) for deterministic re-derivation.
    """
    ticks = int(bundle.get("action_trace_ticks", 0) or 0)
    per = {}
    for ch in _ACTION_CHANNELS:
        mb, sym, nm = _shannon_millibits(_channel_values(bundle, ch))
        per[ch] = {"entropy_millibits": mb, "symbols": sym, "normalized_milli": nm}
    return {
        "ticks": ticks,
        "per_channel": per,
        "channels_read": list(_ACTION_CHANNELS),
        "definition": ("per-channel Shannon entropy in millibits (bits×1000, integer for "
                       "deterministic re-derivation) + normalized_milli [0..1000] over the "
                       "post-φ action channels; imu excluded (postural). Measures input variety"),
    }


def derive_input_tempo(bundle: dict) -> dict:
    """Per-channel input cadence — how often each action channel's state CHANGES.
    Transition count + rate per 1000 ticks (all integers). Rate-AGNOSTIC: the
    bundle carries no verified wall-clock, so the canonical value is tick-relative
    (the post-φ matrix is nominally 60 Hz per the φ spec, but that rate is NOT
    asserted here). Honest at N=1 — the tempo of THIS session.
    """
    ticks = int(bundle.get("action_trace_ticks", 0) or 0)
    per = {}
    total = 0
    for ch in _ACTION_CHANNELS:
        vals = _channel_values(bundle, ch)
        trans = sum(1 for i in range(1, len(vals)) if vals[i] != vals[i - 1])
        total += trans
        rate = round(trans * 1000 / (ticks - 1)) if ticks > 1 else 0
        per[ch] = {"transitions": trans, "per_1000_ticks": rate}
    return {
        "ticks": ticks,
        "total_transitions": total,
        "per_channel": per,
        "channels_read": list(_ACTION_CHANNELS),
        "definition": ("per-channel input-state transition count + rate per 1000 ticks "
                       "(cadence); imu excluded (postural). Integer + rate-agnostic — no "
                       "wall-clock asserted (post-φ matrix is nominally 60 Hz per the φ spec)"),
    }


def derive_stick_engagement_fraction(bundle: dict) -> dict:
    """Fraction of ticks with either stick DISPLACED from the deadzone — steering
    / aim engagement. A stick is engaged when its sector != NEUTRAL_SECTOR (16);
    sectors 0..15 are active directions (value 0 is a real direction, NOT idle).
    Honest at N=1 — a property of THIS session.
    """
    ticks = int(bundle.get("action_trace_ticks", 0) or 0)
    ls = _channel_values(bundle, "stick_L_sector")
    rs = _channel_values(bundle, "stick_R_sector")
    engaged = sum(1 for i in range(ticks)
                  if ls[i] != _NEUTRAL_SECTOR or rs[i] != _NEUTRAL_SECTOR)
    return {
        "ticks": ticks,
        "engaged_ticks": engaged,
        "fraction": round(engaged / ticks, 6) if ticks else 0.0,
        "neutral_sector": _NEUTRAL_SECTOR,
        "channels_read": ["stick_L_sector", "stick_R_sector"],
        "definition": ("fraction of ticks with either stick displaced from the "
                       "NEUTRAL_SECTOR=16 deadzone sentinel (sectors 0..15 = active "
                       "direction, 16 = centered) — per pre_processor φ_spatial, "
                       "RADIAL_BITS=4 frozen by INV-VHR-001"),
    }


def derive_button_press_count(bundle: dict) -> dict:
    """Button interaction volume — total press EVENTS (per-bit 0→1 rising edges
    summed across the 16-bit button_mask, so overlapping/simultaneous presses each
    count) + distinct button bits used + active ticks. Honest at N=1. All integers
    → deterministic.
    """
    ticks = int(bundle.get("action_trace_ticks", 0) or 0)
    masks = _channel_values(bundle, "button_mask")
    presses = 0
    prev = 0
    ever = 0
    active = 0
    for m in masks:
        rising = m & ~prev              # bits newly set this tick (0->1)
        presses += bin(rising).count("1")
        ever |= m
        if m != 0:
            active += 1
        prev = m
    return {
        "ticks": ticks,
        "press_events": presses,
        "distinct_buttons": bin(ever).count("1"),
        "active_ticks": active,
        "channels_read": ["button_mask"],
        "definition": ("total button-press events (per-bit 0→1 rising edges summed across "
                       "the 16-bit button_mask) + distinct button bits used + active ticks; "
                       "interaction volume. Integer, deterministic"),
    }


# Frozen derivation registry — one id per cycle. Ids are versioned; changing a
# derivation's math means a new id (never silent).
DERIVATIONS = {
    "TRIGGER_ENGAGEMENT_FRACTION_v1": derive_trigger_engagement_fraction,
    "ACTION_ENTROPY_v1": derive_action_entropy,
    "INPUT_TEMPO_v1": derive_input_tempo,
    "STICK_ENGAGEMENT_FRACTION_v1": derive_stick_engagement_fraction,
    "BUTTON_PRESS_COUNT_v1": derive_button_press_count,
}


def _claim_hash(claim: dict) -> str:
    """SHA-256 over the canonical claim minus claim_hash itself (record integrity)."""
    c = {k: v for k, v in claim.items() if k != "claim_hash"}
    return hashlib.sha256(
        json.dumps(c, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_claim(bundle: dict, derivation_id: str, *, generated_at: str = "") -> dict:
    """Build a VDC from a certified WMP bundle. Refuses a wrong-schema parent or
    a parent carrying forbidden columns (fail-closed at produce time)."""
    if derivation_id not in DERIVATIONS:
        raise KeyError(f"unknown derivation {derivation_id!r}; known: {sorted(DERIVATIONS)}")
    if bundle.get("schema") != PARENT_SCHEMA:
        raise ValueError(f"parent bundle wrong schema: {bundle.get('schema')!r}")
    hits = _forbidden_hits(bundle)
    if hits:
        raise ValueError(f"parent bundle carries forbidden biometric columns: {hits}")
    value = DERIVATIONS[derivation_id](bundle)
    claim = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "derivation_id": derivation_id,
        "parent_schema": PARENT_SCHEMA,
        "parent_bundle_hash": _bundle_hash(bundle),
        "action_trace_ticks": int(bundle.get("action_trace_ticks", 0) or 0),
        "value": value,
        "ceiling": dict(CEILING),
    }
    claim["claim_hash"] = _claim_hash(claim)
    return claim


def verify_claim(claim: dict, bundle: dict) -> dict:
    """Fail-closed re-derivation verifier. The crux is `value_rederive`: recompute
    the derivation over the bundle and byte-compare — the stored value is never
    trusted. Tamper the matrix or the value → mismatch; swap the parent → binding
    fail; taint the bundle → data-floor fail."""
    checks: list = []

    def _chk(name: str, ok: bool, note: str = "") -> bool:
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", claim.get("schema") == SCHEMA, f"schema={claim.get('schema')!r}")
    ok &= _chk("parent_schema", bundle.get("schema") == PARENT_SCHEMA,
               f"parent schema={bundle.get('schema')!r}")
    ok &= _chk("claim_hash", claim.get("claim_hash") == _claim_hash(claim),
               "claim record integrity (recomputed)")
    ok &= _chk("parent_binding", claim.get("parent_bundle_hash") == _bundle_hash(bundle),
               "claim must bind to THIS exact bundle (swap/tamper rail)")
    hits = _forbidden_hits(bundle)
    ok &= _chk("data_floor", not hits,
               f"parent carries forbidden columns: {hits}" if hits else "clean")
    ok &= _chk("ceiling_verbatim", claim.get("ceiling") == CEILING,
               "honesty ceiling must ship verbatim")

    did = claim.get("derivation_id")
    if not _chk("derivation_known", did in DERIVATIONS, f"derivation={did!r}"):
        return {"ok": False, "checks": checks, "claim_hash": claim.get("claim_hash")}

    read = list((claim.get("value") or {}).get("channels_read") or [])
    ok &= _chk("channels_allowed",
               all(c not in _FROZEN_FORBIDDEN_COLUMNS for c in read),
               f"channels_read={read}")
    try:
        rederived = DERIVATIONS[did](bundle)
    except Exception as exc:  # noqa: BLE001 — a failing derivation is a FAIL, never a silent pass
        ok &= _chk("value_rederive", False, f"re-derivation raised: {exc}")
        return {"ok": False, "checks": checks, "claim_hash": claim.get("claim_hash")}
    ok &= _chk("value_rederive", rederived == claim.get("value"),
               "derived value must re-derive from the bundle matrix (byte-compare)")

    return {"ok": bool(ok), "checks": checks, "claim_hash": claim.get("claim_hash")}
