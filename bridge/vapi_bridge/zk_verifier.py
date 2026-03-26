"""
Phase 67 — ZKVerifier: local Groth16 proof pre-verification before on-chain submission.

Wraps snarkjs.groth16.verify() via a Node.js subprocess.
Rejects invalid proofs before they consume gas on PITLSessionRegistryV2.
Returns False on any error — never raises, never blocks the bridge.

Integration point:
  chain.py → submit_pitl_proof() calls ZKVerifier.verify_proof() before
  send_raw_transaction. Invalid proofs are rejected with ValueError before
  any gas is spent.

Initialisation:
  verifier = ZKVerifier("bridge/zk_artifacts/PitlSession_verification_key.json")
  valid = await verifier.verify_proof(proof_dict, public_inputs_list)
"""

import asyncio
import json
import logging
import os
import sys
import tempfile

log = logging.getLogger(__name__)

_NODE_TIMEOUT_S = 30


class ZKVerifier:
    """
    Local Groth16 proof verifier using snarkjs via Node.js subprocess (Phase 67).

    Attributes:
        _vkey_path: Absolute path to verification_key.json.
        _node_cwd:  Working directory for Node.js (must contain node_modules/snarkjs).
    """

    def __init__(self, vkey_path: str) -> None:
        self._vkey_path = os.path.abspath(vkey_path)
        # node_modules/snarkjs lives alongside the vkey in zk_artifacts/
        self._node_cwd = os.path.dirname(self._vkey_path)

    async def verify_proof(self, proof: dict, public_inputs: list) -> bool:
        """
        Verify a Groth16 proof locally using snarkjs.

        Args:
            proof:         Groth16 proof dict (pi_a, pi_b, pi_c, protocol, curve).
            public_inputs: List of public signal strings (big-endian decimal).

        Returns:
            True if the proof is valid under the embedded verification key.
            False on invalid proof, Node.js error, or timeout — never raises.
        """
        # Write proof and public inputs to temp files — subprocess reads them
        proof_path = inputs_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w", dir=self._node_cwd
            ) as pf:
                json.dump(proof, pf)
                proof_path = pf.name
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w", dir=self._node_cwd
            ) as pi:
                json.dump(public_inputs, pi)
                inputs_path = pi.name

            # Resolve forward-slash paths for Node.js (handles Windows backslashes)
            vkey_js   = self._vkey_path.replace("\\", "/")
            proof_js  = proof_path.replace("\\", "/")
            inputs_js = inputs_path.replace("\\", "/")

            js_src = (
                "const snarkjs = require('snarkjs');\n"
                f"const vkey   = require('{vkey_js}');\n"
                f"const proof  = require('{proof_js}');\n"
                f"const pub    = require('{inputs_js}');\n"
                "snarkjs.groth16.verify(vkey, pub, proof)\n"
                "  .then(ok => { process.stdout.write(ok ? '1' : '0'); process.exit(0); })\n"
                "  .catch(err => { process.stderr.write(String(err)); process.exit(1); });\n"
            )

            proc = await asyncio.create_subprocess_exec(
                "node", "--input-type=commonjs", "-e", js_src,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._node_cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=_NODE_TIMEOUT_S
                )
            except asyncio.TimeoutError:
                proc.kill()
                log.warning("ZKVerifier: Node.js timed out after %ds", _NODE_TIMEOUT_S)
                return False

            if proc.returncode != 0:
                log.warning(
                    "ZKVerifier: node exited %d: %s",
                    proc.returncode, stderr.decode()[:200],
                )
                return False

            result = stdout.decode().strip()
            if result == "1":
                return True
            log.debug("ZKVerifier: proof invalid (snarkjs returned 0)")
            return False

        except Exception as exc:
            log.warning("ZKVerifier: verify_proof error: %s", exc)
            return False
        finally:
            for p in (proof_path, inputs_path):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    def vkey_path(self) -> str:
        """Return the absolute path to the verification key file."""
        return self._vkey_path
