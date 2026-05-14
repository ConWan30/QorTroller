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
DIST_WASM = W3B_DIR / "dist" / "poseidon_bn254.wasm"
DIST_LOADER = W3B_DIR / "dist" / "poseidon_bn254.js"

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
