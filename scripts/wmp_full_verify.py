#!/usr/bin/env python3
"""WMP full-VERIFY runner — the 5/5 zero-stub consumer check (Phase-2 promote, INC-1).

Injects the four Phase-2 callables into `sdk.wmp_verify.verify_bundle` (the SDK stays pure;
this runner is the subprocess/network blast radius — the PORT-CERT pattern):

  groth16_verify — reconstructs snarkjs proof.json FROM the bundle's 256-byte ABI wire
                   (8×32B big-endian: a.x a.y b00 b01 b10 b11 c.x c.y — the exact inverse of
                   groth16_prover's encode) + public.json FROM the bundle's own public inputs
                   (FROZEN INV-VHR-005 order), then shells `snarkjs groth16 verify` against the
                   published verifying key. Zero-trust: nothing verified comes from outside
                   the bundle except the vkey.
  poseidon_root  — shells the FROZEN compute_inputs_replay_proof.js (--print-commitments)
                   over the bundle's own matrix hex.
  beacon_lookup  — read-only eth_call getBeacon(block) on the LIVE VAPITemporalBeaconRegistry.
  consent_lookup — read-only eth_call isWorldModelConsentGranted(gamer) on WMP-4.

Bar (golden-pack exit semantics): exit 0 ONLY when overall VERIFIED **and zero checks are
stubbed/deferred** (the strict 5/5). `--allow-deferred recency` (repeatable) permits an
explicitly-named honest deferral to count — reported as exactly that, never rounded up.
exit 1 = ran but not at bar; exit 2 = incomplete environment (never a silent pass).

  python scripts/wmp_full_verify.py --bundle <bundle.json | corpus.jsonl>
      [--vkey path] [--chain-rpc URL] [--beacon-registry 0x..] [--consent-registry 0x..]
      [--allow-synthetic] [--allow-deferred recency]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from sdk.wmp_verify import verify_bundle

DEFAULT_RPC = "https://babel-api.testnet.iotex.io"
DEFAULT_VKEY = os.path.join(_REPO, "bridge", "vapi_bridge", "replay_proof_pipeline",
                            "zk_artifacts", "VAPIReplayProofVerifier_verification_key.json")
_HELPER = os.path.join(_REPO, "bridge", "vapi_bridge", "replay_proof_pipeline",
                       "zk_artifacts", "compute_inputs_replay_proof.js")
# Default = the LIVE Arc 6 registry (deployed 2026-06-05, keeper active since 2026-06-25).
DEFAULT_BEACON_REGISTRY = "0x962440312a995b21d4E203bE6d93021CC22bA051"
# FROZEN INV-VHR-005 public-input order (output-first).
_PUBLIC_ORDER = ("replayProofToken", "sanitizedTraceRoot", "poacChainRoot",
                 "consentPolicyHash", "humanityThreshold", "vhpCommitment")
_CHANNELS = ("stick_L_sector", "stick_R_sector", "trigger_L_state",
             "trigger_R_state", "button_mask", "imu_gravity_sector")


def _discover_snarkjs():
    for c in ([os.environ["SNARKJS"]] if os.environ.get("SNARKJS") else []) + [
            os.path.join(_REPO, "contracts", "node_modules", ".bin", "snarkjs.cmd"),
            os.path.join(_REPO, "contracts", "node_modules", ".bin", "snarkjs"), "snarkjs"]:
        if shutil.which(c) or os.path.exists(c):
            return [c]
    return ["npx", "snarkjs"] if shutil.which("npx") else None


def _proof_bytes_to_snarkjs_json(proof_hex: str) -> dict:
    """Invert groth16_prover's 256-byte ABI encode back to snarkjs proof.json."""
    h = proof_hex[2:] if proof_hex.startswith("0x") else proof_hex
    raw = bytes.fromhex(h)
    if len(raw) != 256:
        raise ValueError(f"proof must be 256 bytes, got {len(raw)}")
    w = [str(int.from_bytes(raw[i * 32:(i + 1) * 32], "big")) for i in range(8)]
    return {"pi_a": [w[0], w[1], "1"],
            "pi_b": [[w[2], w[3]], [w[4], w[5]], ["1", "0"]],
            "pi_c": [w[6], w[7], "1"],
            "protocol": "groth16", "curve": "bn128"}


def make_groth16_verify(snark_cmd: list, vkey_path: str):
    def _verify(public_inputs: dict, proof_hex: str) -> bool:
        missing = [k for k in _PUBLIC_ORDER if str(public_inputs.get(k, "")).strip() == ""]
        if missing:
            raise ValueError(f"bundle public inputs missing {missing}")
        with tempfile.TemporaryDirectory() as td:
            pj, uj = os.path.join(td, "proof.json"), os.path.join(td, "public.json")
            json.dump(_proof_bytes_to_snarkjs_json(proof_hex), open(pj, "w"))
            json.dump([str(public_inputs[k]) for k in _PUBLIC_ORDER], open(uj, "w"))
            res = subprocess.run(snark_cmd + ["groth16", "verify", vkey_path, uj, pj],
                                 capture_output=True, text=True, timeout=180)
            return "OK!" in (res.stdout + res.stderr)
    return _verify


def make_poseidon_root():
    def _root(matrix: dict) -> str:
        priv = {"humanityProbabilityWitness": "0", "humanityThreshold": "0",
                "vhpTokenId": "0", "sessionNonce": "0", "poacChainRoot": "0",
                "consentPolicyHash": "0",
                "matrix": {"ticks": int(matrix.get("ticks", 0)),
                           **{c: matrix.get(c, "") for c in _CHANNELS}}}
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "priv.json")
            json.dump(priv, open(p, "w"))
            res = subprocess.run(["node", _HELPER, p, "--print-commitments"],
                                 capture_output=True, text=True, timeout=300, cwd=_REPO)
            out = (res.stdout or "") + (res.stderr or "")
            if res.returncode != 0:
                raise RuntimeError(f"poseidon helper exit {res.returncode}: {out[-300:]}")
            # The helper prints a JSON commitments object; older paths printed key=value lines.
            # Extract the DECIMAL field element robustly for both shapes.
            import re
            m = (re.search(r'"sanitizedTraceRoot"\s*:\s*"?(\d+)', out)
                 or re.search(r'sanitizedTraceRoot\s*=\s*"?(\d+)', out))
            if not m:
                raise RuntimeError(f"could not parse sanitizedTraceRoot from helper output: {out[-300:]}")
            return m.group(1)
    return _root


def _eth_call(rpc: str, to: str, data: str) -> str:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(rpc, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "qortroller-wmp-verify"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    if "error" in d:
        raise RuntimeError(d["error"])
    return d.get("result") or "0x"


def make_beacon_lookup(rpc: str, registry: str):
    # anchoredHash(uint256) public-mapping auto-getter — selector keccak-computed 2026-07-11
    # and LIVE-PROBED: block 45026880 -> 0xa8592690250fee... (byte-matches the M17 PoSP beacon).
    sel = "0x160f1991"

    def _lookup(block: int):
        data = sel + hex(int(block))[2:].rjust(64, "0")
        out = _eth_call(rpc, registry, data)
        h = out[2:] if out.startswith("0x") else out
        if len(h) < 64 or int(h[:64], 16) == 0:
            return None
        return "0x" + h[:64]
    return _lookup


def make_consent_lookup(rpc: str, registry: str):
    sel = "0xf92ce72a"  # isWorldModelConsentGranted(address) — keccak-computed 2026-07-11

    def _lookup(gamer: str) -> bool:
        g = gamer[2:] if gamer.startswith("0x") else gamer
        out = _eth_call(rpc, registry, sel + g.rjust(64, "0"))
        return out != "0x" and int(out, 16) == 1
    return _lookup


def main() -> int:
    ap = argparse.ArgumentParser(description="WMP 5/5 zero-stub bundle verify")
    ap.add_argument("--bundle", required=True, help="bundle .json or corpus .jsonl")
    ap.add_argument("--vkey", default=DEFAULT_VKEY)
    ap.add_argument("--chain-rpc", default=DEFAULT_RPC)
    ap.add_argument("--beacon-registry", default=DEFAULT_BEACON_REGISTRY)
    ap.add_argument("--consent-registry",
                    default=os.environ.get("WORLD_MODEL_CONSENT_REGISTRY_ADDRESS", ""))
    ap.add_argument("--allow-synthetic", action="store_true")
    ap.add_argument("--allow-deferred", action="append", default=[],
                    help="explicitly permit a named honest deferral (e.g. recency)")
    a = ap.parse_args()

    print("=" * 74)
    print("  WMP FULL VERIFY — 5/5 zero-stub consumer check")
    print("=" * 74)
    snark = _discover_snarkjs()
    if snark is None:
        print("  INCOMPLETE: no snarkjs (env SNARKJS / contracts/node_modules / PATH / npx)  (exit 2)")
        return 2
    if not os.path.isfile(a.vkey):
        print(f"  INCOMPLETE: vkey absent: {a.vkey}  (exit 2)")
        return 2
    path = a.bundle if os.path.isabs(a.bundle) else os.path.join(_REPO, a.bundle)
    if not os.path.isfile(path):
        print(f"  INCOMPLETE: bundle absent: {path}  (exit 2)")
        return 2
    raw = open(path, encoding="utf-8").read().strip()
    bundles = ([json.loads(ln) for ln in raw.splitlines() if ln.strip()]
               if path.endswith(".jsonl") else [json.loads(raw)])
    print(f"  snarkjs   : {' '.join(snark)}")
    print(f"  rpc       : {a.chain_rpc}")
    print(f"  bundles   : {len(bundles)}")

    g16 = make_groth16_verify(snark, a.vkey)
    pos = make_poseidon_root()
    bea = make_beacon_lookup(a.chain_rpc, a.beacon_registry)
    con = make_consent_lookup(a.chain_rpc, a.consent_registry) if a.consent_registry else None
    if con is None:
        print("  note      : no consent registry configured — consent check runs un-injected "
              "(deferred/stub reads honestly)")

    worst = 0
    for i, b in enumerate(bundles):
        res = verify_bundle(b, allow_synthetic=a.allow_synthetic, groth16_verify=g16,
                            poseidon_root=pos, beacon_lookup=bea, consent_lookup=con)
        stubbed = [n for n, c in res.checks.items() if c.get("stubbed")]
        bad_deferred = [n for n in res.deferred if n not in a.allow_deferred]
        at_bar = (res.overall == "VERIFIED" and not stubbed and not bad_deferred)
        print(f"  [{'PASS' if at_bar else 'FAIL':4}] bundle#{i} overall={res.overall} "
              f"stubbed={stubbed or '-'} deferred={res.deferred or '-'} "
              f"(allowed={a.allow_deferred or '-'})")
        for r in res.reasons[:4]:
            print(f"         reason: {r}")
        if not at_bar:
            worst = max(worst, 1)
    if worst == 0:
        print("\n  WMP FULL VERIFY: VERIFIED — 5/5, zero stubs"
              + (f" (explicitly-allowed deferrals: {a.allow_deferred})" if a.allow_deferred else "")
              + "  exit=0")
    else:
        print("\n  WMP FULL VERIFY: NOT AT BAR — see reasons above  exit=1")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
