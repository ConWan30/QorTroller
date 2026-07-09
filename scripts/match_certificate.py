#!/usr/bin/env python3
"""PORT-CERT runner — build / verify a portable Match Certificate (qortroller-match-certificate-v0).

  build  — assemble a certificate from a session's real artifacts (PoSP record + VHR proof + anchor
           [+ KAS/deferred/consent]); computes the PoSP file SHA-256 (the anchored digest).
  verify — off-rig verification. Offline checks (schema / session-join / PoSP / anchor-digest) always
           run. The ZK proof (C5) is checked only if a snarkjs command is available/supplied; the
           on-chain anchor (C6) only if --chain-rpc is given. Missing either -> honest PARTIAL, never a
           false VERIFIED. The pure verifier lives in l9_presence/port_cert.py; this script only injects
           the snarkjs subprocess + the RPC (the network/subprocess blast radius).

Offline, no rig, no chain WRITE (an optional --chain-rpc anchor read is a view call, 0 IOTX).
See docs/port-cert-design-2026-07-09.md.

Examples:
  python scripts/match_certificate.py build \
    --posp audits/posp_record_match17_rp_fixb3_2026-07-08.json \
    --anchor audits/posp_anchor_match17_rp_fixb3_2026-07-08_anchor.json \
    --vhr-public audits/vhr_proof2_m17/public_m17_real.json \
    --vhr-proof audits/vhr_proof2_m17/proof_m17_real.json \
    --vkey bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/VAPIReplayProofVerifier_verification_key.json \
    --out audits/match_certificate_m17.json

  python scripts/match_certificate.py verify --cert audits/match_certificate_m17.json \
    --posp audits/posp_record_match17_rp_fixb3_2026-07-08.json [--snarkjs snarkjs] [--chain-rpc URL]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")   # report notes carry no Unicode, but be safe on cp1252
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.port_cert import build_match_certificate, verify_match_certificate


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_file(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def cmd_build(a) -> int:
    posp = _load(a.posp)
    posp["file_sha256"] = _sha256_file(a.posp)      # the exact published-record digest
    posp["record_path"] = a.posp

    vhr = None
    if a.vhr_public and a.vhr_proof:
        public = _load(a.vhr_public)                # list of field-element strings (ZK-safe)
        vhr = {"replay_proof_token": (public[0] if public else None),
               "public_inputs": public,
               "sanitized_trace_root": (public[1] if len(public) > 1 else None),
               "poac_chain_root": (public[2] if len(public) > 2 else None),
               "proof_ref": a.vhr_proof, "public_ref": a.vhr_public, "vkey_ref": a.vkey}

    anchor = None
    if a.anchor:
        an = _load(a.anchor)
        anchor = {"registry": an.get("contract"), "tx": an.get("tx"), "block": an.get("block"),
                  "digest": an.get("file_sha256"), "method": an.get("method")}

    kas = _load(a.kas) if a.kas else None
    deferred = _load(a.deferred) if a.deferred else None
    consent = ({"manifest_hash": a.consent_hash} if a.consent_hash else None)

    cert = build_match_certificate(posp=posp, kas=kas, deferred=deferred, vhr=vhr,
                                   anchor=anchor, consent=consent)
    out = a.out or f"audits/match_certificate_{cert.get('session_id', 'x')[:12]}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(cert, fh, indent=2, sort_keys=True)
    print(json.dumps({"built": out, "session_id": cert["session_id"],
                      "surfaces": {k: (v is not None) for k, v in cert["surfaces"].items()}}, indent=2))
    return 0


def _make_groth16_verify(snarkjs_cmd):
    """Inject a snarkjs-shelling groth16 verifier: `snarkjs groth16 verify <vkey> <public> <proof>`.
    Returns None if no usable snarkjs (-> C5 UNCHECKED, honest). True only on 'OK!' output."""
    if not snarkjs_cmd:
        return None
    exe = shutil.which(snarkjs_cmd) or (snarkjs_cmd if os.path.exists(snarkjs_cmd) else None)
    base = ([exe] if exe else None)
    if base is None and shutil.which("npx"):
        base = ["npx", "snarkjs"]                   # last resort
    if base is None:
        return None

    def _verify(vhr) -> bool:
        vkey, public, proof = vhr.get("vkey_ref"), vhr.get("public_ref"), vhr.get("proof_ref")
        if not (vkey and public and proof):
            return False
        res = subprocess.run(base + ["groth16", "verify", vkey, public, proof],
                             capture_output=True, text=True, timeout=120)
        return "OK!" in (res.stdout + res.stderr)
    return _verify


def _make_chain_lookup(rpc_url, registry):
    """Inject an on-chain anchor lookup: eth_getTransactionReceipt(tx).status == 1 (read-only, 0 IOTX).
    Returns None if no rpc_url (-> C6 UNCHECKED)."""
    if not rpc_url:
        return None
    import urllib.request

    def _lookup(tx) -> bool:
        txh = tx if tx.startswith("0x") else "0x" + tx
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt",
                           "params": [txh]}).encode()
        req = urllib.request.Request(rpc_url, data=body, headers={"Content-Type": "application/json",
                                                                  "User-Agent": "qortroller-portcert"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        rc = d.get("result")
        return bool(rc) and rc.get("status") in ("0x1", 1)
    return _lookup


def cmd_verify(a) -> int:
    cert = _load(a.cert)
    posp_bytes = None
    if a.posp:
        with open(a.posp, "rb") as fh:
            posp_bytes = fh.read()
    g16 = _make_groth16_verify(a.snarkjs)
    chain = _make_chain_lookup(a.chain_rpc, (cert.get("surfaces", {}).get("anchor") or {}).get("registry"))
    rep = verify_match_certificate(cert, posp_file_bytes=posp_bytes, groth16_verify=g16, chain_lookup=chain)
    print(json.dumps(rep.to_dict(), indent=2))
    print(f"\nOVERALL: {rep.overall}"
          f"  (ZK {'checked' if g16 else 'UNCHECKED — pass --snarkjs'}, "
          f"anchor-onchain {'checked' if chain else 'UNCHECKED — pass --chain-rpc'})")
    return 0 if rep.overall in ("VERIFIED", "PARTIAL") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="PORT-CERT — portable Match Certificate build/verify")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--posp", required=True)
    b.add_argument("--anchor", default=None)
    b.add_argument("--vhr-public", default=None)
    b.add_argument("--vhr-proof", default=None)
    b.add_argument("--vkey", default=None)
    b.add_argument("--kas", default=None)
    b.add_argument("--deferred", default=None)
    b.add_argument("--consent-hash", default=None)
    b.add_argument("--out", default=None)

    v = sub.add_parser("verify")
    v.add_argument("--cert", required=True)
    v.add_argument("--posp", default=None, help="published PoSP record file (for the anchor-digest match)")
    v.add_argument("--snarkjs", default=None, help="snarkjs command/path (enables the ZK check C5)")
    v.add_argument("--chain-rpc", default=None, help="IoTeX RPC URL (enables the on-chain anchor check C6)")

    a = ap.parse_args()
    return cmd_build(a) if a.cmd == "build" else cmd_verify(a)


if __name__ == "__main__":
    raise SystemExit(main())
