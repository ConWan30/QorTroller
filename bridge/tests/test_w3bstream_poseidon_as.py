"""Phase O4-W3B-POSEIDON-AS Stream V.1 -- AS Poseidon(BN254) vector verification.

This is the V.1 verification gate. It is the INDEPENDENT check that the
AssemblyScript Poseidon(BN254) implementation (Streams I.1a/I.1b, committed by
the I.1 agent) produces output byte-identical to the circomlibjs 0.1.7
reference for every test vector in the committed corpus.

The I.1 agent's own smoke test cross-checked 135 vectors (20 random + 25
boundary per arity). V.1 is broader and independent: it compiles the AS
module fresh from source, then verifies 100 random + all boundary vectors
per arity {t2, t3, t9} = 375 vectors, plus the 3 published circomlib BN254
canonical vectors, plus per-arity determinism.

Verification path is AMBER (P.0-confirmed): circomlibjs 0.1.7 is the single
reference. V.3 cross-reference triangulation is deferred; V.1 boundary
coverage + V.2 per-round differential are the compensating discipline.

Toolchain: requires `node` + `npx` on PATH. If the toolchain is genuinely
absent the tests SKIP (CI environments without Node). If the toolchain is
present but any vector mismatches, the tests FAIL loudly -- a mismatch is a
hard atomic-stop signal per the plan's Stream V.1 discipline.

Tests: T-W3B-POSEIDON-AS-1 .. T-W3B-POSEIDON-AS-10.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
W3B_DIR = PROJECT_ROOT / "scripts" / "w3bstream"
RUNTIME_JS = W3B_DIR / "poseidon_runtime.js"
VECTOR_FILE = W3B_DIR / "poseidon_test_vectors.json"
SOURCE_TS = W3B_DIR / "poseidon_bn254.ts"
SOURCE_DEBUG_TS = W3B_DIR / "poseidon_bn254_debug.ts"
DIST_WASM = W3B_DIR / "dist" / "poseidon_bn254.wasm"
DIST_LOADER = W3B_DIR / "dist" / "poseidon_bn254.js"
DIST_DEBUG_WASM = W3B_DIR / "dist" / "poseidon_bn254_debug.wasm"
DIST_DEBUG_LOADER = W3B_DIR / "dist" / "poseidon_bn254_debug.js"

_NODE = shutil.which("node")
_NPX = shutil.which("npx") or shutil.which("npx.cmd")

_TOOLCHAIN_REASON = "node + npx toolchain required for AS Poseidon WASM verification"


def _toolchain_available() -> bool:
    return bool(_NODE) and bool(_NPX) and SOURCE_TS.exists() and VECTOR_FILE.exists()


@pytest.fixture(scope="module")
def v1_result():
    """Compile the AS Poseidon module fresh, then run poseidon_runtime.js
    once over the vector corpus and return the parsed JSON result.

    Module-scoped: one compile + one Node invocation serves all 10 tests.
    """
    if not _toolchain_available():
        pytest.skip(_TOOLCHAIN_REASON)

    # Compile fresh from source -- V.1 must verify the CURRENT source, never
    # a stale dist artifact. asc 0.28.17 does not substitute {name}; the
    # outFile/textFile are explicit (matches package.json asbuild:* pattern).
    compile_cmd = [
        _NPX,
        "asc",
        "poseidon_bn254.ts",
        "--config",
        "asconfig.json",
        "--target",
        "release",
        "--outFile",
        "dist/poseidon_bn254.wasm",
        "--textFile",
        "dist/poseidon_bn254.wat",
    ]
    compile_proc = subprocess.run(
        compile_cmd,
        cwd=str(W3B_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if compile_proc.returncode != 0:
        pytest.fail(
            "asc compile of poseidon_bn254.ts failed (exit "
            f"{compile_proc.returncode}):\n{compile_proc.stdout}\n{compile_proc.stderr}"
        )
    if not DIST_WASM.exists() or not DIST_LOADER.exists():
        pytest.fail(
            "asc compile reported success but dist artifacts missing: "
            f"{DIST_WASM.exists()=} {DIST_LOADER.exists()=}"
        )

    # Run the V.1 verification band. stdout carries the JSON result; stderr
    # may carry a harmless MODULE_TYPELESS_PACKAGE_JSON warning -- parse
    # stdout ONLY.
    run_proc = subprocess.run(
        [_NODE, str(RUNTIME_JS), str(VECTOR_FILE), "--random-count", "100"],
        cwd=str(W3B_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if run_proc.returncode != 0:
        pytest.fail(
            "poseidon_runtime.js exited non-zero (it should always exit 0): "
            f"{run_proc.returncode}\n{run_proc.stdout}\n{run_proc.stderr}"
        )
    try:
        result = json.loads(run_proc.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"poseidon_runtime.js stdout is not parseable JSON ({exc}):\n"
            f"STDOUT:\n{run_proc.stdout}\nSTDERR:\n{run_proc.stderr}"
        )
    if "error" in result:
        pytest.fail(f"poseidon_runtime.js reported error: {result['error']}")
    return result


# ---- T-W3B-POSEIDON-AS-1: compile produces WASM + loader artifacts -----

def test_t_w3b_poseidon_as_1_compile_artifacts(v1_result):
    """The AS Poseidon module compiles cleanly and produces both the WASM
    binary and the asc-generated ESM loader the runtime depends on."""
    assert DIST_WASM.exists() and DIST_WASM.stat().st_size > 0
    assert DIST_LOADER.exists() and DIST_LOADER.stat().st_size > 0
    # the runtime helper itself must be present and committed
    assert RUNTIME_JS.exists()


# ---- T-W3B-POSEIDON-AS-2: runtime loads + instantiates WASM ------------

def test_t_w3b_poseidon_as_2_runtime_instantiates(v1_result):
    """poseidon_runtime.js loaded the asc ESM loader, compiled the WASM
    module, instantiated it, and produced a structured result with all 3
    in-scope arities. (Absence of an 'error' key is asserted in the
    fixture; this confirms the result shape.)"""
    assert set(v1_result["arities"].keys()) == {"t2", "t3", "t9"}
    assert v1_result["random_count"] == 100


# ---- T-W3B-POSEIDON-AS-3/4/5: random-input vectors byte-exact ----------

def _assert_band(v1_result, arity, band, min_tested):
    bandresult = v1_result["arities"][arity][band]
    assert bandresult["tested"] >= min_tested, (
        f"{arity}.{band}: only {bandresult['tested']} vectors tested, "
        f"expected >= {min_tested}"
    )
    assert bandresult["failed"] == 0, (
        f"{arity}.{band}: {bandresult['failed']} of {bandresult['tested']} "
        f"vectors MISMATCH the circomlibjs reference -- first mismatches: "
        f"{bandresult['mismatches']}"
    )
    assert bandresult["passed"] == bandresult["tested"]


def test_t_w3b_poseidon_as_3_t2_random(v1_result):
    """poseidon_t2 (circomlib Poseidon(1)): 100 random-input vectors
    byte-identical to circomlibjs reference."""
    _assert_band(v1_result, "t2", "random", 100)


def test_t_w3b_poseidon_as_4_t3_random(v1_result):
    """poseidon_t3 (circomlib Poseidon(2)): 100 random-input vectors
    byte-identical to circomlibjs reference."""
    _assert_band(v1_result, "t3", "random", 100)


def test_t_w3b_poseidon_as_5_t9_random(v1_result):
    """poseidon_t9 (circomlib Poseidon(8)): 100 random-input vectors
    byte-identical to circomlibjs reference."""
    _assert_band(v1_result, "t9", "random", 100)


# ---- T-W3B-POSEIDON-AS-6/7/8: boundary-input vectors byte-exact --------

def test_t_w3b_poseidon_as_6_t2_boundary(v1_result):
    """poseidon_t2: all boundary-input vectors (zero, p-1, all-ones,
    sequential ramp, hand-picked) byte-identical to reference."""
    _assert_band(v1_result, "t2", "boundary", 20)


def test_t_w3b_poseidon_as_7_t3_boundary(v1_result):
    """poseidon_t3: all boundary-input vectors byte-identical to reference."""
    _assert_band(v1_result, "t3", "boundary", 20)


def test_t_w3b_poseidon_as_8_t9_boundary(v1_result):
    """poseidon_t9: all boundary-input vectors byte-identical to reference."""
    _assert_band(v1_result, "t9", "boundary", 20)


# ---- T-W3B-POSEIDON-AS-9: published circomlib BN254 canonical vectors --

def test_t_w3b_poseidon_as_9_canonical_vectors(v1_result):
    """The AS implementation reproduces the widely-published circomlib
    BN254 canonical test vectors for Poseidon(1)/Poseidon(2)/Poseidon(8).
    This is the single-reference guard (AMBER path) that circomlibjs's
    parameter set IS the standard circomlib BN254 Poseidon."""
    expected = {
        "t2": "18586133768512220936620570745912940619677854269274689475585506675881198879027",
        "t3": "7853200120776062878684798364095072458815029376092732009249414926327459813530",
        "t9": "18604317144381847857886385684060986177838410221561136253933256952257712543953",
    }
    for arity, exp_output in expected.items():
        canon = v1_result["canonical"][arity]
        assert canon["ok"], (
            f"{arity} canonical vector MISMATCH: inputs={canon['inputs']} "
            f"expected={canon['expected']} got={canon['got']}"
        )
        assert canon["got"] == exp_output, (
            f"{arity} canonical output {canon['got']} != published "
            f"circomlib BN254 canonical {exp_output}"
        )


# ---- T-W3B-POSEIDON-AS-10: per-arity determinism -----------------------

def test_t_w3b_poseidon_as_10_determinism(v1_result):
    """The AS Poseidon implementation is deterministic: the same input
    invoked twice produces byte-identical output for every arity. A
    non-deterministic result would indicate uninitialised memory or a
    stub-runtime allocator hazard."""
    for arity in ("t2", "t3", "t9"):
        assert v1_result["determinism"][arity] is True, (
            f"{arity}: poseidon is NOT deterministic across two invocations "
            f"of the same canonical input -- memory hazard suspected"
        )


# ===========================================================================
# Stream V.2 -- per-round differential
#
# A final-output match (V.1) can mask a bug whose error happens to cancel by
# the last round. V.2 verifies EVERY intermediate round state of the AS
# permutation against the circomlibjs per-round states stored in the vector
# file. poseidon_bn254_debug.ts is the per-round-emitting mirror; it imports
# the EXACT same field arithmetic + C/M constants the production module uses,
# so a V.2 pass is a per-round witness for the production permutation too.
#
# Tests: T-W3B-POSEIDON-AS-11 .. T-W3B-POSEIDON-AS-16.
# ===========================================================================


@pytest.fixture(scope="module")
def v2_result():
    """Compile the per-round debug variant fresh, then run poseidon_runtime.js
    in --mode per-round once over the 50 per_round vectors per arity and
    return the parsed JSON result.

    The debug variant imports its field arithmetic + C/M constants from
    poseidon_bn254.ts at compile time (asc resolves the dependency), so the
    debug WASM is self-contained -- only poseidon_bn254_debug.ts needs an
    explicit compile here.
    """
    if not _toolchain_available() or not SOURCE_DEBUG_TS.exists():
        pytest.skip(_TOOLCHAIN_REASON)

    compile_cmd = [
        _NPX,
        "asc",
        "poseidon_bn254_debug.ts",
        "--config",
        "asconfig.json",
        "--target",
        "release",
        "--outFile",
        "dist/poseidon_bn254_debug.wasm",
        "--textFile",
        "dist/poseidon_bn254_debug.wat",
    ]
    compile_proc = subprocess.run(
        compile_cmd,
        cwd=str(W3B_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if compile_proc.returncode != 0:
        pytest.fail(
            "asc compile of poseidon_bn254_debug.ts failed (exit "
            f"{compile_proc.returncode}):\n{compile_proc.stdout}\n{compile_proc.stderr}"
        )
    if not DIST_DEBUG_WASM.exists() or not DIST_DEBUG_LOADER.exists():
        pytest.fail(
            "asc compile reported success but debug dist artifacts missing: "
            f"{DIST_DEBUG_WASM.exists()=} {DIST_DEBUG_LOADER.exists()=}"
        )

    run_proc = subprocess.run(
        [_NODE, str(RUNTIME_JS), str(VECTOR_FILE), "--mode", "per-round"],
        cwd=str(W3B_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if run_proc.returncode != 0:
        pytest.fail(
            "poseidon_runtime.js --mode per-round exited non-zero: "
            f"{run_proc.returncode}\n{run_proc.stdout}\n{run_proc.stderr}"
        )
    try:
        result = json.loads(run_proc.stdout.strip().splitlines()[-1])
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"poseidon_runtime.js --mode per-round stdout not parseable JSON ({exc}):\n"
            f"STDOUT:\n{run_proc.stdout}\nSTDERR:\n{run_proc.stderr}"
        )
    if "error" in result:
        pytest.fail(f"poseidon_runtime.js --mode per-round reported error: {result['error']}")
    return result


# ---- T-W3B-POSEIDON-AS-11: debug build compiles + per-round runtime ----

def test_t_w3b_poseidon_as_11_debug_build(v2_result):
    """poseidon_bn254_debug.ts compiles to a self-contained WASM and the
    per-round runtime instantiates it and produces a structured result for
    all 3 in-scope arities."""
    assert DIST_DEBUG_WASM.exists() and DIST_DEBUG_WASM.stat().st_size > 0
    assert DIST_DEBUG_LOADER.exists() and DIST_DEBUG_LOADER.stat().st_size > 0
    assert v2_result["mode"] == "per-round"
    assert set(v2_result["arities"].keys()) == {"t2", "t3", "t9"}


# ---- T-W3B-POSEIDON-AS-12/13/14: per-round intermediate state byte-exact -

def _assert_per_round(v2_result, arity, expect_total_rounds, expect_width):
    a = v2_result["arities"][arity]
    assert a["total_rounds"] == expect_total_rounds, (
        f"{arity}: total_rounds {a['total_rounds']} != {expect_total_rounds}"
    )
    assert a["state_width"] == expect_width, (
        f"{arity}: state_width {a['state_width']} != {expect_width}"
    )
    assert a["vectors_tested"] == 50, (
        f"{arity}: vectors_tested {a['vectors_tested']} != 50 per_round vectors"
    )
    expected_checks = 50 * expect_total_rounds * expect_width
    assert a["round_states_checked"] == expected_checks, (
        f"{arity}: round_states_checked {a['round_states_checked']} != "
        f"{expected_checks} (50 vectors x {expect_total_rounds} rounds x "
        f"{expect_width} width)"
    )
    assert a["round_states_failed"] == 0, (
        f"{arity}: {a['round_states_failed']} of {a['round_states_checked']} "
        f"intermediate round-state elements MISMATCH the circomlibjs "
        f"reference -- first mismatches: {a['mismatches']}"
    )
    assert a["round_states_passed"] == a["round_states_checked"]


def test_t_w3b_poseidon_as_12_t2_per_round(v2_result):
    """poseidon_t2: all 6400 intermediate round-state elements (50 vectors x
    64 rounds x width 2) byte-identical to the circomlibjs per-round states."""
    _assert_per_round(v2_result, "t2", 64, 2)


def test_t_w3b_poseidon_as_13_t3_per_round(v2_result):
    """poseidon_t3: all 9750 intermediate round-state elements (50 vectors x
    65 rounds x width 3) byte-identical to the circomlibjs per-round states."""
    _assert_per_round(v2_result, "t3", 65, 3)


def test_t_w3b_poseidon_as_14_t9_per_round(v2_result):
    """poseidon_t9: all 31950 intermediate round-state elements (50 vectors x
    71 rounds x width 9) byte-identical to the circomlibjs per-round states.
    This is the broadest single check -- it witnesses the MDS mix, the
    round-constant indexing, and the full-vs-partial S-box lane selection at
    every one of the 71 rounds."""
    _assert_per_round(v2_result, "t9", 71, 9)


# ---- T-W3B-POSEIDON-AS-15: circomlib BN254 round structure -------------

def test_t_w3b_poseidon_as_15_round_structure(v2_result):
    """The AS permutation runs the canonical circomlib BN254 round structure:
    R_F=8 full rounds + R_P partial rounds, with R_P = 56/57/63 for
    t=2/3/9. A wrong round count would silently change the hash."""
    expected = {"t2": (64, 2), "t3": (65, 3), "t9": (71, 9)}
    for arity, (total_rounds, width) in expected.items():
        a = v2_result["arities"][arity]
        assert (a["total_rounds"], a["state_width"]) == (total_rounds, width), (
            f"{arity}: round structure ({a['total_rounds']}, {a['state_width']}) "
            f"!= circomlib BN254 ({total_rounds}, {width})"
        )


# ---- T-W3B-POSEIDON-AS-16: per-round path agrees with final-output path -

def test_t_w3b_poseidon_as_16_final_state_closes_loop(v2_result):
    """The final round's state[0] from the per-round path equals the declared
    vector output for all 50 per_round vectors per arity. This closes the
    loop between the V.2 per-round path and the V.1 final-output path: the
    debug permutation and the production permutation agree at the boundary."""
    for arity in ("t2", "t3", "t9"):
        a = v2_result["arities"][arity]
        assert a["final_output_matches"] == a["vectors_tested"] == 50, (
            f"{arity}: final_output_matches {a['final_output_matches']} != "
            f"vectors_tested {a['vectors_tested']} (expected 50) -- the "
            f"per-round path's final state[0] diverges from the declared output"
        )
