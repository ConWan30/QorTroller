"""WMP Adversarial Hardening Loop (AH-1) — consumer-verifier attack harness.

Constructs forgery bundles FROM OUTSIDE (a file read / clone of the public UC-1
artifact, or synthetic JSON) and asserts `sdk.wmp_verify.verify_bundle` catches
them. The whole point of the WMP lane is zero-trust verification — a stranger
confirms real-human + on-chain consent + matrix<->root without trusting
QorTroller. AH-1 attacks that claim ourselves, publicly, before others do.

HARD RULE (threat model = "QorTroller might lie"): this package imports ONLY
`sdk.wmp_verify` + stdlib. It never imports `bridge.vapi_bridge.wmp` — the
attacker does not get to call our assembler. Loading the UC-1 golden is a file
read, not an assembler call.

Design:  docs/wmp-adversarial-hardening-ah1-design-2026-07-11.md  (+ §9 auditor addendum)
Matrix:  docs/wmp-adversarial-matrix-2026-07-11.md  (public living doc)
"""
from .attacks import (
    load_uc1_bundle,
    matrix_swap,
    gamer_address_swap,
    forbidden_key_smuggle,
    poseidon_mock_for,
    honest_kwargs,
    CHANNELS,
    NON_CONSENTER,
)
from .matrix import (
    run_all,
    run_one,
    AttackResult,
    MatrixResult,
    VECTORS,
    CAUGHT,
    GAP_FOUND,
    GAP_FIXED,
    OUT_OF_SCOPE,
)

__all__ = [
    "load_uc1_bundle",
    "matrix_swap",
    "gamer_address_swap",
    "forbidden_key_smuggle",
    "poseidon_mock_for",
    "honest_kwargs",
    "CHANNELS",
    "NON_CONSENTER",
    "run_all",
    "run_one",
    "AttackResult",
    "MatrixResult",
    "VECTORS",
    "CAUGHT",
    "GAP_FOUND",
    "GAP_FIXED",
    "OUT_OF_SCOPE",
]
