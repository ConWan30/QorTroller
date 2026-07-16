"""UC-3 buyer-category ZK PROVER acceptance (the missing half, A2A round-1).

The prover generates a real Groth16 proof from a Curator-credential and LOCAL-verifies it against
the committed verification key (grok round-1 primary acceptance). Pinned here:
  - golden fixture -> prover succeeds, proof verifies, and the public signals BYTE-MATCH the deployed
    verifier's own Hardhat golden test (T-BCV-1) -> the prover produces on-chain-verifiable proofs;
  - fail-CLOSED rails: category outside FROZEN [1,4] (exit 4), expired credential (exit 5),
    claimedCategory != categoryId (exit 6).

Skips if node/snarkjs is unavailable (same posture as the repo's other JS-toolchain gates).
No chain write, no ceremony, no FROZEN edit.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROVER = REPO / "contracts" / "circuits" / "prove_buyer_category.js"
CIRCUITS = REPO / "contracts" / "circuits"

# the deployed verifier's golden public signals (contracts/test/VAPIBuyerCategoryVerifier.test.js)
FIX_COMMIT = int("0x2d22e513a5efb4ea6308c21458da2e569fc3e4928699a479623e389cef484e8f", 16)
FIX_NULL = int("0x0fd56a897af5cb70f165c3f9a18b32e97c81dc5bc6c351dbef8fdfe43333922e", 16)

_NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(
    _NODE is None or not PROVER.exists() or not (CIRCUITS / "VAPIBuyerCategoryVerifier_final.zkey").exists(),
    reason="node/snarkjs or circuit artifacts unavailable",
)


def _run(cred_json: str | None):
    args = [_NODE, str(PROVER)]
    tmp = None
    if cred_json is not None:
        tmp = CIRCUITS / "_uc3_test_cred.json"
        tmp.write_text(cred_json, encoding="utf-8")
        args.append(str(tmp))
    try:
        p = subprocess.run(args, cwd=str(CIRCUITS), capture_output=True, text=True, timeout=180)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()
    return p


def test_golden_credential_proves_and_verifies():
    p = _run(None)  # golden fixture
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["ok"] is True
    assert out["verified_local"] is True          # snarkjs groth16 verify vs committed vkey
    assert out["valid_output"] is True            # pubSignals[0] == "1"
    assert out["public_layout_ok"] is True
    # BYTE-MATCH the deployed verifier's own golden fixture -> on-chain-verifiable
    assert int(out["credential_commitment"]) == FIX_COMMIT
    assert int(out["nullifier_hash"]) == FIX_NULL
    assert out["public_signals"][0] == "1" and out["public_signals"][1] == "3"


def test_category_out_of_range_fails_closed():
    p = _run('{"buyerDID":"123","categoryId":9,"issuedAt":1700000000,"expiresAt":1800000000,'
             '"currentTimestamp":1750000000,"credentialNonce":"55"}')
    assert p.returncode == 4
    assert "FROZEN enum" in p.stderr


def test_expired_credential_fails_closed():
    p = _run('{"buyerDID":"123","categoryId":2,"issuedAt":1600000000,"expiresAt":1700000000,'
             '"currentTimestamp":1750000000,"credentialNonce":"55"}')
    assert p.returncode == 5
    assert "expired" in p.stderr


def test_claimed_mismatch_fails_closed():
    p = _run('{"buyerDID":"123","categoryId":2,"claimedCategory":4,"issuedAt":1700000000,'
             '"expiresAt":1800000000,"currentTimestamp":1750000000,"credentialNonce":"55"}')
    assert p.returncode == 6


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
