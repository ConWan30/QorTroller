#!/usr/bin/env python3
"""
poseidon_vector_validator.py -- Phase O4-W3B-POSEIDON-AS Stream P.3 (AMBER path)

P.0 preflight resolved to AMBER (operator-confirmed 2026-05-14): no quick
BN254-compatible 2nd Poseidon reference was available in the agent runtime,
so the plan's GREEN-path differential-reference validator (2nd independent
Poseidon impl cross-checking every vector) cannot be shipped. circomlibjs
0.1.7 is the single reference.

2nd-reference candidates tried at P.0, and why each failed:
  (a) `pip install poseidon-hash`   -- native build failure (meson subprocess)
  (b) `pip install py-iden3-crypto` -- does not exist on PyPI
  (c) `cargo install` arkworks      -- cargo not available on the system
  extra probe: `poseidon-py` 0.2.0  -- installs cleanly BUT is STARKNET
      Poseidon (Stark prime field, hades_permutation, m=3/r=2 params) -- a
      genuinely different hash function, NOT BN254 circomlib Poseidon;
      uninstalled. (This was Risk #1 -- "incompatible Poseidon variants
      exist in the ecosystem" -- surfacing and being neutralized at the
      preflight boundary.)
  (d) Python impl from spec          -- the fallback; a significant spec
      port, not a <10-min preflight item.

Per the AMBER branch of wiki/phases/phase_o4_w3b_poseidon_as.md:
  - Stream V.3 (cross-reference triangulation: AS == ref1 AND AS == ref2)
    is DEFERRED -- there is no 2nd reference to triangulate against.
  - The compensating differential discipline is: V.1 boundary-input
    coverage + V.2 per-round intermediate-state verification, both against
    the single circomlibjs reference.
  - The single-reference caveat is documented in the PV.1 invariant bodies,
    the W.3 audit script, and the relevant commit bodies.

WHAT THIS VALIDATOR DOES (single-reference, self-contained -- no node_modules,
no circomlibjs dependency; works from the committed vector file alone):

  1. TAMPER CHECK   -- SHA-256 of poseidon_test_vectors.json matches the
                       committed poseidon_test_vectors.sha256.
  2. STRUCTURE      -- metadata present; exactly the 3 in-scope arities
                       {t2,t3,t9}; expected vector-set counts; per-round
                       vectors have R_F+R_P round_states each of width t.
  3. CONSISTENCY    -- for every per-round vector, the final round_state's
                       element[0] equals the declared `output` (the naive
                       permutation's own internal consistency).
  4. CANONICAL      -- the published circomlib BN254 canonical test vectors
                       for Poseidon(1)/Poseidon(2)/Poseidon(8) are present
                       in the corpus with their known-correct outputs.

WHAT THIS VALIDATOR DOES NOT DO (the AMBER limitation, stated honestly):
  - It does NOT perform independent 2nd-reference differential
    triangulation. The vector corpus was generated + self-checked
    (naive-vs-opt, 3225 self-checks) by poseidon_vector_generator.js
    against circomlibjs 0.1.7 ONLY. If circomlibjs 0.1.7's parameter set
    were itself wrong, neither the generator's self-check nor this
    validator would catch it -- the canonical-vector check (step 4) is the
    single guard against that, and it is single-reference.

FUTURE UPGRADE PATH: if a BN254-compatible 2nd Poseidon reference becomes
available in the ecosystem (a maintained PyPI package, an arkworks binding,
or a vetted in-protocol Python spec port), this stub should be upgraded to
the GREEN-path validator: load the vector file, recompute every vector with
the 2nd reference, and assert byte-identical agreement -- restoring the
V.3 cross-reference triangulation the AMBER path deferred.

Usage:  python poseidon_vector_validator.py
Exit codes: 0 = PASS  |  1 = tamper/structural/consistency failure  |  2 = file missing
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VECTOR_FILE = HERE / "poseidon_test_vectors.json"
SHA_FILE = HERE / "poseidon_test_vectors.sha256"

# circomlib BN254 Poseidon round counts (R_F constant 8; R_P per arity).
_R_F = 8
_R_P = {"t2": 56, "t3": 57, "t9": 63}
_T = {"t2": 2, "t3": 3, "t9": 9}
_N_IN = {"t2": 1, "t3": 2, "t9": 8}

# Published canonical circomlib BN254 test vectors -- the single-reference
# guard that circomlibjs 0.1.7's parameter set IS the standard circomlib
# Poseidon. These are widely-published, known-correct values.
_CANONICAL = {
    "t2": (["1"], "18586133768512220936620570745912940619677854269274689475585506675881198879027"),
    "t3": (["1", "2"], "7853200120776062878684798364095072458815029376092732009249414926327459813530"),
    "t9": (
        ["1", "2", "3", "4", "5", "6", "7", "8"],
        "18604317144381847857886385684060986177838410221561136253933256952257712543953",
    ),
}

_EXPECTED_RANDOM = 1000
_EXPECTED_PER_ROUND = 50


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    print("")
    print("=== P.3 VALIDATOR: FAIL ===")
    sys.exit(1)


def main() -> None:
    print("=== Phase O4-W3B-POSEIDON-AS Stream P.3 -- AMBER vector validator ===")
    print("  path: AMBER (single-reference; V.3 differential triangulation DEFERRED)")
    print("")

    if not VECTOR_FILE.exists():
        print(f"  [ERROR] vector file not found: {VECTOR_FILE}")
        sys.exit(2)
    if not SHA_FILE.exists():
        print(f"  [ERROR] sha256 file not found: {SHA_FILE}")
        sys.exit(2)

    raw = VECTOR_FILE.read_bytes()

    # 1. TAMPER CHECK
    actual_sha = hashlib.sha256(raw).hexdigest()
    claimed_sha = SHA_FILE.read_text(encoding="utf-8").strip()
    if actual_sha != claimed_sha:
        _fail(
            f"tamper check: poseidon_test_vectors.json SHA-256 {actual_sha} "
            f"!= committed poseidon_test_vectors.sha256 {claimed_sha}"
        )
    print(f"  [OK]   tamper check -- SHA-256 matches committed .sha256 ({actual_sha[:16]}...)")

    try:
        doc = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        _fail(f"structure: vector file is not valid JSON -- {exc}")

    # 2. STRUCTURE
    meta = doc.get("metadata")
    vectors = doc.get("vectors")
    if not isinstance(meta, dict) or not isinstance(vectors, dict):
        _fail("structure: missing 'metadata' or 'vectors' top-level objects")
    if meta.get("schema") != "vapi-poseidon-test-vectors-v1":
        _fail(f"structure: unexpected schema '{meta.get('schema')}'")
    if set(vectors.keys()) != {"t2", "t3", "t9"}:
        _fail(f"structure: arities {sorted(vectors.keys())} != expected ['t2','t3','t9']")
    print("  [OK]   structure -- schema + 3 in-scope arities {t2,t3,t9} present")

    total_random = total_boundary = total_per_round = 0
    for key in ("t2", "t3", "t9"):
        t = _T[key]
        total_rounds = _R_F + _R_P[key]
        arity = vectors[key]
        for band in ("random", "boundary", "per_round"):
            if not isinstance(arity.get(band), list):
                _fail(f"structure: {key}.{band} is not a list")
        if len(arity["random"]) != _EXPECTED_RANDOM:
            _fail(f"structure: {key}.random has {len(arity['random'])}, expected {_EXPECTED_RANDOM}")
        if len(arity["per_round"]) != _EXPECTED_PER_ROUND:
            _fail(
                f"structure: {key}.per_round has {len(arity['per_round'])}, "
                f"expected {_EXPECTED_PER_ROUND}"
            )
        # every vector: inputs length == nIn; output is a decimal string
        for band in ("random", "boundary", "per_round"):
            for n, vec in enumerate(arity[band]):
                if len(vec.get("inputs", [])) != _N_IN[key]:
                    _fail(f"structure: {key}.{band}[{n}] inputs length != {_N_IN[key]}")
                if not str(vec.get("output", "")).isdigit():
                    _fail(f"structure: {key}.{band}[{n}] output is not a decimal string")
        # per-round vectors: round_states shape
        for n, vec in enumerate(arity["per_round"]):
            rs = vec.get("round_states")
            if not isinstance(rs, list) or len(rs) != total_rounds:
                _fail(
                    f"structure: {key}.per_round[{n}] round_states has "
                    f"{len(rs) if isinstance(rs, list) else 'n/a'}, expected {total_rounds}"
                )
            for r, st in enumerate(rs):
                if not isinstance(st, list) or len(st) != t:
                    _fail(
                        f"structure: {key}.per_round[{n}].round_states[{r}] width "
                        f"{len(st) if isinstance(st, list) else 'n/a'} != t={t}"
                    )
        total_random += len(arity["random"])
        total_boundary += len(arity["boundary"])
        total_per_round += len(arity["per_round"])
    print(
        f"  [OK]   structure -- {total_random} random + {total_boundary} boundary + "
        f"{total_per_round} per-round vectors; round_states shapes correct"
    )

    # 3. CONSISTENCY -- per-round final state[0] == declared output
    consistency_checked = 0
    for key in ("t2", "t3", "t9"):
        for n, vec in enumerate(vectors[key]["per_round"]):
            final_state0 = vec["round_states"][-1][0]
            if final_state0 != vec["output"]:
                _fail(
                    f"consistency: {key}.per_round[{n}] final round_state[0] "
                    f"{final_state0} != output {vec['output']}"
                )
            consistency_checked += 1
    print(
        f"  [OK]   consistency -- {consistency_checked} per-round vectors: "
        f"final round_state[0] == declared output"
    )

    # 4. CANONICAL -- published circomlib BN254 vectors present + correct
    for key, (inputs, expected) in _CANONICAL.items():
        found = False
        for band in ("random", "boundary", "per_round"):
            for vec in vectors[key][band]:
                if vec["inputs"] == inputs:
                    found = True
                    if vec["output"] != expected:
                        _fail(
                            f"canonical: {key} Poseidon({inputs}) output {vec['output']} "
                            f"!= published canonical {expected}"
                        )
        if not found:
            _fail(f"canonical: {key} canonical vector inputs {inputs} not present in corpus")
    print(
        "  [OK]   canonical -- published circomlib BN254 vectors for "
        "Poseidon(1)/Poseidon(2)/Poseidon(8) present + correct"
    )

    print("")
    print("  AMBER LIMITATION (stated honestly): no independent 2nd-reference")
    print("  differential triangulation was performed -- the corpus was generated +")
    print("  self-checked against circomlibjs 0.1.7 ONLY. V.3 cross-reference is")
    print("  DEFERRED pending ecosystem availability of a BN254-compatible 2nd")
    print("  Poseidon reference. The canonical-vector check above is the single guard")
    print("  that circomlibjs's parameter set IS standard circomlib BN254 Poseidon.")
    print("")
    print(f"  circomlibjs reference version (from metadata): {meta.get('circomlibjs_version')}")
    print(f"  generator self-checks recorded (from metadata): {meta.get('self_checks_passed')}")
    print("")
    print("=== P.3 VALIDATOR: PASS (single-reference; AMBER) ===")
    sys.exit(0)


if __name__ == "__main__":
    main()
