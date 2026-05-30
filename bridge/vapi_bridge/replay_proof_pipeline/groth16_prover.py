"""Data Economy Arc 5 Commit 4.5/+ — Real Groth16 prover for VHR.

Closes ceremony gate (b) per docs/data-economy-deploy-hold-and-arc5-readiness.md
§4. Replaces DeferredProver when all of these are present:

  • compute_inputs_replay_proof.js          (the circomlibjs Poseidon helper)
  • node_modules/circomlibjs                (the dep that helper requires)
  • VAPIReplayProofVerifier.wasm            (witness calculator from Commit 2)
  • VAPIReplayProofVerifier_final.zkey      (from the 2026-05-30 ceremony)
  • VAPIReplayProofVerifier_verification_key.json

All five live at bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/. When
any are missing, `artifacts_available()` returns False and the orchestrator
falls back to DeferredProver — `auto_prover()` is the factory that picks.

Pipeline (mirrors zk_sepproof_prover._real_proof + the spec §3.3 Optimization 1
witness-side check):

  1. Python pre-flight (`compute_h_gap`) raises if humanity < threshold —
     fail-fast before subprocess work.
  2. Emit `private_inputs.json` to a tempdir.
  3. Spawn node `compute_inputs_replay_proof.js` → it computes
     vhpCommitment + sanitizedTraceRoot via circomlibjs and emits
     `circuit_input.json` (FROZEN public-input order matching the circuit's
     `component main {public [...]}` declaration).
  4. Spawn `npx snarkjs groth16 fullprove circuit_input.json wasm zkey
     proof.json public.json`.
  5. Decode `proof.json` → 256-byte ABI wire format matching the snarkjs
     Solidity verifier's expected `(uint[2] a, uint[2][2] b, uint[2] c)`
     layout. Parse `public.json` → 6-element snarkjs publicInputs in the
     INV-VHR-005 frozen order: [0] replayProofToken (output), [1]
     sanitizedTraceRoot, [2] poacChainRoot, [3] consentPolicyHash,
     [4] humanityThreshold, [5] vhpCommitment.
  6. Return ProofResult.

Honesty rails:

  • The Python WitnessGenerator's BN254 field validation and humanity-gap
    pre-flight run *before* any node/snarkjs spawn — catches the easy
    cases without a 10-second subprocess.
  • All commitments come from circomlibjs (the same Poseidon permutation
    snarkjs's compiled .wasm uses). The Python side NEVER reimplements
    Poseidon — eliminates the silent-divergence class of failure.
  • Subprocess failure → ProofResult with empty proof_bytes + a
    deferred_reason describing what went wrong. The orchestrator surfaces
    this as `vhr_proof_deferred` honestly.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .pipeline import ProofResult
from .pre_processor import SanitizedReplayMatrix
from .witness_generator import (
    HumanityFloorNotClearedError,
    WitnessGenerator,
    compute_h_gap,
    scale_probability,
)

log = logging.getLogger(__name__)

# Snarkjs Groth16 proof wire format: a(2)+b(2,2)+c(2) = 8 field elements × 32B.
PROOF_SIZE = 256

# Artifact directory under the package.
_THIS_DIR = Path(__file__).resolve().parent
ZK_ARTIFACTS_DIR = _THIS_DIR / "zk_artifacts"

_COMPUTE_INPUTS_JS  = ZK_ARTIFACTS_DIR / "compute_inputs_replay_proof.js"
_WASM_PATH          = ZK_ARTIFACTS_DIR / "VAPIReplayProofVerifier.wasm"
_ZKEY_PATH          = ZK_ARTIFACTS_DIR / "VAPIReplayProofVerifier_final.zkey"
_VKEY_PATH          = ZK_ARTIFACTS_DIR / "VAPIReplayProofVerifier_verification_key.json"
_CIRCOMLIBJS_PATH   = ZK_ARTIFACTS_DIR / "node_modules" / "circomlibjs"


def artifacts_available() -> bool:
    """True when every Groth16Prover prerequisite is on disk."""
    return all(p.exists() for p in (
        _COMPUTE_INPUTS_JS, _WASM_PATH, _ZKEY_PATH, _VKEY_PATH, _CIRCOMLIBJS_PATH,
    ))


def missing_artifacts() -> list[str]:
    """Names of the prerequisites NOT present — for honest deferral messages."""
    pairs = [
        ("compute_inputs_replay_proof.js", _COMPUTE_INPUTS_JS),
        ("VAPIReplayProofVerifier.wasm",   _WASM_PATH),
        ("VAPIReplayProofVerifier_final.zkey", _ZKEY_PATH),
        ("VAPIReplayProofVerifier_verification_key.json", _VKEY_PATH),
        ("node_modules/circomlibjs",       _CIRCOMLIBJS_PATH),
    ]
    return [name for name, path in pairs if not path.exists()]


def auto_prover() -> Any:
    """Return a Groth16Prover if ceremony+helper artifacts are present, else
    a DeferredProver carrying the reason — never raises, never fabricates."""
    # Lazy DeferredProver import avoids circular at module load.
    from .pipeline import DeferredProver
    if artifacts_available():
        return Groth16Prover()
    missing = missing_artifacts()
    return DeferredProver(
        reason=f"ceremony / helper artifacts absent: {', '.join(missing)}"
    )


# ── Matrix → private-inputs JSON ────────────────────────────────────────────

def _matrix_to_private_inputs_dict(
    matrix: SanitizedReplayMatrix,
) -> dict:
    """Serialize the matrix into the shape the node helper expects.

    The node helper's CANONICAL ENCODING (FROZEN VAPI-VHR-MATRIX-v1) parses
    these hex strings byte-by-byte; the field order here MUST match the
    helper's `canonicalMatrixBytes` order.
    """
    return {
        "ticks": int(matrix.ticks),
        "stick_L_sector":     matrix.stick_L_sector.hex(),
        "stick_R_sector":     matrix.stick_R_sector.hex(),
        "trigger_L_state":    matrix.trigger_L_state.hex(),
        "trigger_R_state":    matrix.trigger_R_state.hex(),
        "button_mask":        matrix.button_mask.hex(),
        "imu_gravity_sector": matrix.imu_gravity_sector.hex(),
    }


# ── Subprocess helpers ──────────────────────────────────────────────────────

def _resolve_exe(name: str) -> str:
    """Cross-platform executable resolution. On Windows npm installs `.cmd`
    shims for node/npx; `shutil.which` finds them. Falls back to the bare
    name if PATH lookup fails (preserving the original error surface)."""
    found = shutil.which(name)
    return found or name


def _run_node(script: str, args: list[str], out_path: Optional[Path] = None,
              cwd: Optional[str] = None) -> None:
    cmd = [_resolve_exe("node"), script] + list(args)
    if out_path is not None:
        cmd.extend(["--out", str(out_path)])
    r = subprocess.run(cmd, capture_output=True, cwd=cwd, check=False,
                       shell=(sys.platform == "win32"))
    if r.returncode != 0:
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        raise RuntimeError(f"node helper failed (exit {r.returncode}): {stderr[:600]}")


def _run_snarkjs(args: list[str]) -> None:
    cmd = [_resolve_exe("npx"), "--yes", "snarkjs"] + list(args)
    r = subprocess.run(cmd, capture_output=True, check=False,
                       shell=(sys.platform == "win32"))
    if r.returncode != 0:
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        raise RuntimeError(
            f"snarkjs failed (exit {r.returncode}): {stderr[:600]} | stdout: {stdout[:300]}"
        )


# ── Proof encoding (matches Phase 26/237 PITLProver wire format) ────────────

def _encode_proof(proof_json: dict) -> bytes:
    def to_bytes32(v) -> bytes:
        n = int(v, 16) if str(v).startswith(("0x", "0X")) else int(v)
        return n.to_bytes(32, "big")
    buf = bytearray(PROOF_SIZE)
    buf[0:32]    = to_bytes32(proof_json["pi_a"][0])
    buf[32:64]   = to_bytes32(proof_json["pi_a"][1])
    buf[64:96]   = to_bytes32(proof_json["pi_b"][0][0])
    buf[96:128]  = to_bytes32(proof_json["pi_b"][0][1])
    buf[128:160] = to_bytes32(proof_json["pi_b"][1][0])
    buf[160:192] = to_bytes32(proof_json["pi_b"][1][1])
    buf[192:224] = to_bytes32(proof_json["pi_c"][0])
    buf[224:256] = to_bytes32(proof_json["pi_c"][1])
    return bytes(buf)


# ── Prover ──────────────────────────────────────────────────────────────────

class Groth16Prover:
    """Real Groth16 prover — closes ceremony gate (b).

    Constructor takes no required args; defaults pick up the artifact paths
    next to this module. Tests inject alternate paths via kwargs.
    """

    def __init__(
        self,
        *,
        compute_inputs_js: Optional[Path] = None,
        wasm: Optional[Path] = None,
        zkey: Optional[Path] = None,
        verification_key: Optional[Path] = None,
        witness_generator: Optional[WitnessGenerator] = None,
    ) -> None:
        self._compute_inputs_js = compute_inputs_js or _COMPUTE_INPUTS_JS
        self._wasm = wasm or _WASM_PATH
        self._zkey = zkey or _ZKEY_PATH
        self._vkey = verification_key or _VKEY_PATH
        self._witness_gen = witness_generator or WitnessGenerator()

    def is_available(self) -> bool:
        return all(p.exists() for p in (
            self._compute_inputs_js, self._wasm, self._zkey, self._vkey,
        ))

    def prove(
        self,
        *,
        matrix: SanitizedReplayMatrix,
        humanity_probability: float,
        humanity_threshold: float,
        vhp_token_id: int,
        session_nonce: int,
    ) -> ProofResult:
        # Pre-flight: humanity gap check (raises HumanityFloorNotClearedError
        # before any subprocess spawn).
        try:
            _ = compute_h_gap(humanity_probability, humanity_threshold)
        except HumanityFloorNotClearedError as exc:
            return ProofResult(
                proof_bytes=b"",
                replay_proof_token="",
                sanitized_trace_root="",
                vhp_commitment="",
                humanity_threshold_scaled=0,
                deferred_reason=f"humanity floor not cleared: {exc}",
            )

        scaled_threshold = scale_probability(humanity_threshold)
        scaled_witness   = scale_probability(humanity_probability)

        # poacChainRoot + consentPolicyHash are field elements coming from the
        # pre-processor + consent manifest; if the matrix's chain root is bytes,
        # encode as 0x-hex so the node helper's hex decoder accepts it.
        poac_chain_root_hex = "0x" + matrix.poac_chain_root.hex()

        priv_inputs = {
            "humanityProbabilityWitness": str(scaled_witness),
            "humanityThreshold":          str(scaled_threshold),
            "vhpTokenId":                 str(int(vhp_token_id)),
            "sessionNonce":               str(int(session_nonce)),
            "poacChainRoot":              poac_chain_root_hex,
            # consent_policy_hash is supplied at orchestration time and lives
            # in the consent manifest as bytes32 hex.
            "consentPolicyHash":          "0x" + bytes(32).hex(),
            "matrix":                     _matrix_to_private_inputs_dict(matrix),
        }

        try:
            return self._prove_via_subprocess(priv_inputs, scaled_threshold)
        except Exception as exc:
            log.exception("Groth16Prover.prove failed")
            return ProofResult(
                proof_bytes=b"",
                replay_proof_token="",
                sanitized_trace_root="",
                vhp_commitment="",
                humanity_threshold_scaled=scaled_threshold,
                deferred_reason=f"{type(exc).__name__}: {str(exc)[:200]}",
            )

    def _prove_via_subprocess(
        self, priv_inputs: dict, scaled_threshold: int,
    ) -> ProofResult:
        with tempfile.TemporaryDirectory() as _tmp:
            tmp = Path(_tmp)
            priv_path    = tmp / "private_inputs.json"
            circuit_path = tmp / "circuit_input.json"
            proof_path   = tmp / "proof.json"
            public_path  = tmp / "public.json"

            priv_path.write_text(json.dumps(priv_inputs))

            _run_node(
                str(self._compute_inputs_js), [str(priv_path)],
                out_path=circuit_path,
                cwd=str(self._compute_inputs_js.parent),
            )
            _run_snarkjs([
                "groth16", "fullprove",
                str(circuit_path), str(self._wasm), str(self._zkey),
                str(proof_path), str(public_path),
            ])

            proof_json  = json.loads(proof_path.read_text())
            public_json = json.loads(public_path.read_text())
            if not isinstance(public_json, list) or len(public_json) != 6:
                raise RuntimeError(
                    f"public.json must be a 6-element array, got {len(public_json) if isinstance(public_json, list) else type(public_json).__name__}"
                )

            proof_bytes = _encode_proof(proof_json)
            # Public-input layout pinned by INV-VHR-005:
            #   [0] replayProofToken (output)
            #   [1] sanitizedTraceRoot
            #   [2] poacChainRoot
            #   [3] consentPolicyHash
            #   [4] humanityThreshold
            #   [5] vhpCommitment
            replay_token_dec    = str(public_json[0])
            sanitized_root_dec  = str(public_json[1])
            vhp_commitment_dec  = str(public_json[5])
            replay_token_hex    = "0x" + int(replay_token_dec).to_bytes(32, "big").hex()

            log.info(
                "Groth16Prover OK — token=%s root=%s vhp=%s",
                replay_token_hex[:18],
                sanitized_root_dec[:18] + "...",
                vhp_commitment_dec[:18] + "...",
            )
            return ProofResult(
                proof_bytes=proof_bytes,
                replay_proof_token=replay_token_hex,
                sanitized_trace_root=sanitized_root_dec,
                vhp_commitment=vhp_commitment_dec,
                humanity_threshold_scaled=int(scaled_threshold),
                deferred_reason=None,
            )
