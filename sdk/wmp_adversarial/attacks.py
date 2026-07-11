"""Pure outside-in forgery constructors + honest injected-callable mocks.

Every constructor takes (or loads) a bundle dict and returns a NEW dict — the
base is never mutated in place. No bridge import (AH-1 threat model).

The injected mocks here are HONEST models of the crypto/chain oracles, not
fakes that paper over them:

  * `poseidon_mock_for(base)` returns base's REAL sanitizedTraceRoot only for
    base's exact matrix bytes; any mutation → a different field element. This
    models Poseidon's collision-resistance — the ACTUAL BN254 Poseidon is
    exercised by `scripts/wmp_full_verify.py`, and A1's full-path kill is
    already banked in `audits/wmp-phase2-first-real-bundle-2026-07-11.md` (L25,
    "one flipped matrix byte -> REJECTED").

  * `honest_kwargs(base)`'s `groth16_verify` mock enforces the SAME public-input
    completeness the real runner does (`wmp_full_verify.py` L81-83) per AH-1 §9
    A16 — so a pure test can never "pass" a self-consistent fake-root/ref pair.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_UC1 = _REPO / "wmp_corpus_real" / "wmp_corpus.jsonl"

# Canonical channel order — must match sdk.wmp_verify / wmp_full_verify.
CHANNELS = (
    "stick_L_sector",
    "stick_R_sector",
    "trigger_L_state",
    "trigger_R_state",
    "button_mask",
    "imu_gravity_sector",
)

# FROZEN INV-VHR-005 public-input order (mirrors wmp_full_verify._PUBLIC_ORDER).
_REQUIRED_PUBLIC = (
    "replayProofToken",
    "sanitizedTraceRoot",
    "poacChainRoot",
    "consentPolicyHash",
    "humanityThreshold",
    "vhpCommitment",
)


def load_uc1_bundle(path: str | os.PathLike | None = None) -> dict:
    """Load the first line of the published real UC-1 corpus as the attack base.

    File read only — never the assembler. Raises (does NOT skip) if absent: the
    corpus is committed, and a missing base would silently hollow out the loop.
    """
    p = Path(path) if path is not None else _UC1
    if not p.is_file():
        raise FileNotFoundError(
            f"UC-1 corpus not found at {p} — AH-1 attacks the committed real "
            "bundle; expected wmp_corpus_real/wmp_corpus.jsonl on the branch."
        )
    first = p.read_text(encoding="utf-8").splitlines()[0]
    return json.loads(first)


def _matrix_sig(ticks, matrix_hex: dict) -> tuple:
    """Content signature of a matrix over the canonical channel order."""
    return (
        int(ticks or 0),
        tuple(str(matrix_hex.get(ch, "")) for ch in CHANNELS),
    )


def poseidon_mock_for(base: dict):
    """Honest Poseidon model keyed to `base`'s matrix.

    Returns base's real sanitizedTraceRoot iff the matrix handed in matches
    base's matrix bytes; any mutation -> a different value (collision-resistance
    model). Signature matches what `check_matrix_root_rehash` passes:
    `{"ticks": int, **{ch: hex}}`.
    """
    base_sig = _matrix_sig(
        base.get("action_trace_ticks", 0),
        base.get("action_trace_matrix_hex", {}) or {},
    )
    claimed = str((base.get("humanity_proof_public_inputs") or {}).get("sanitizedTraceRoot", ""))

    def _root(matrix: dict) -> str:
        sig = (
            int(matrix.get("ticks", 0) or 0),
            tuple(str(matrix.get(ch, "")) for ch in CHANNELS),
        )
        if sig == base_sig:
            return claimed
        # Any different matrix -> a provably different root.
        if claimed.isdigit():
            return str(int(claimed) + 1)
        return (claimed + "0") or "1"

    return _root


def honest_kwargs(base: dict) -> dict:
    """Injected callables under which the UNFORGED base VERIFIES.

    So any REJECTED outcome on a forged clone is attributable to the forgery,
    not the harness. The groth16 mock mirrors the real runner's public-input
    completeness guard (AH-1 §9 A16).
    """
    gamer = str(base.get("consent_gamer_address", "") or "")

    def _g16(public_inputs: dict, proof_hex: str) -> bool:
        missing = [k for k in _REQUIRED_PUBLIC if str(public_inputs.get(k, "")).strip() == ""]
        if missing:
            # Mirror wmp_full_verify.make_groth16_verify L81-83: incomplete
            # public inputs are a hard error, never a silent True.
            raise ValueError(f"bundle public inputs missing {missing}")
        return True

    return dict(
        allow_synthetic=False,
        poseidon_root=poseidon_mock_for(base),
        groth16_verify=_g16,
        beacon_lookup=None,                       # UC-1 recency is honest-deferred (empty registry)
        consent_lookup=lambda g: g == gamer,      # on-chain oracle: true only for the real gamer
    )


# ── attack constructors (one per vector) ────────────────────────────────

def matrix_swap(base: dict, channel: str = "stick_L_sector") -> dict:
    """A1 — matrix-swap.

    Clone the base; flip one nibble of one matrix channel; leave the Groth16
    proof bytes and public inputs untouched. Goal: attach a real human's proof
    to DIFFERENT action data. Expected: REJECTED at `matrix_root_rehash` (the
    Poseidon recompute no longer matches the root the proof verified against).
    """
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    forged = copy.deepcopy(base)
    mh = forged.get("action_trace_matrix_hex") or {}
    hexstr = str(mh.get(channel, ""))
    if not hexstr:
        raise ValueError(f"channel {channel!r} carries no matrix hex to mutate")
    flipped = format(int(hexstr[0], 16) ^ 0x1, "x")   # deterministic single-nibble flip
    mh[channel] = flipped + hexstr[1:]
    forged["action_trace_matrix_hex"] = mh
    return forged


# A non-consenter address (valid 0x+40hex format, deterministically NOT the real gamer).
NON_CONSENTER = "0x" + "de" * 20


def gamer_address_swap(base: dict, new_address: str = NON_CONSENTER) -> dict:
    """A3 — gamer-address swap.

    Clone the base; repoint `consent_gamer_address` to a DIFFERENT EOA that has
    not granted world-model consent; leave the proof + matrix untouched. Goal:
    steal a real human's proof credibility under another (non-consenting)
    identity. Expected: REJECTED at `consent` — the injected on-chain oracle
    (`isWorldModelConsentGranted`) returns false for the swapped gamer.

    Note (design §9.1 / A3 gap-watch): CAUGHT requires the consent oracle to be
    injected. With `consent_lookup=None`, a `GRANTED` bundle passes consent as
    an HONEST stub (`stubbed=True`) — the full-verify zero-stub bar
    (`wmp_full_verify.py` L205) excludes it, so a runner without
    `--consent-registry` is misconfiguration, never a silent pass.
    """
    forged = copy.deepcopy(base)
    forged["consent_gamer_address"] = new_address
    return forged


# A stand-in raw biometric payload (the value doesn't matter — the KEY is the breach).
_BIOMETRIC_PAYLOAD = [3.14, 15.9, 26.5]


def forbidden_key_smuggle(
    base: dict,
    key: str = "l4_mahalanobis_distance",
    where: str = "top",
) -> dict:
    """A15 — observation/biometric smuggle (post-phi data floor).

    Clone the base; inject a forbidden biometric key (one of the published
    FORBIDDEN_COLUMNS) into the bundle. `where`:
      "top"            — a top-level bundle key
      "extra_metadata" — nested where the strata band rides
      "channel"        — a forbidden name appended to action_trace_channels

    Goal: export raw biometric data under a certified-human wrapper. Expected
    (post-fix): REJECTED at `scope_honesty` — the payload no longer honors the
    scope block's "observation-absent / macro-intent-not-biomechanical" claim.
    """
    forged = copy.deepcopy(base)
    if where == "top":
        forged[key] = _BIOMETRIC_PAYLOAD
    elif where == "extra_metadata":
        meta = dict(forged.get("extra_metadata") or {})
        meta[key] = _BIOMETRIC_PAYLOAD
        forged["extra_metadata"] = meta
    elif where == "channel":
        chans = list(forged.get("action_trace_channels") or [])
        chans.append(key)
        forged["action_trace_channels"] = chans
    else:
        raise ValueError(f"unknown placement {where!r} (top | extra_metadata | channel)")
    return forged
