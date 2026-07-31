#!/usr/bin/env python3
"""PORT-CERT full-VERIFIED runner — the PARTIAL -> VERIFIED one-command close.

`match_certificate.py verify` on a bare rig honestly reports OVERALL: PARTIAL because the ZK
check (C5) needs a snarkjs command and the on-chain anchor check (C6) needs an RPC URL. This
runner closes that gap in one command: it DISCOVERS a local snarkjs (env SNARKJS ->
contracts/node_modules/.bin -> PATH -> npx fallback), defaults the IoTeX TESTNET RPC (read-only
eth_getTransactionReceipt; 0 IOTX; the injected lookup already sends the User-Agent header
babel-api requires), pre-checks that the cert's ZK refs exist on disk, then runs the SAME
documented verify command (single source of truth -- no verify logic is duplicated here).

Bar (stricter than the base verifier, mirroring the golden pack's exit semantics):
  exit 0  -> OVERALL: VERIFIED (all checks incl. C5 ZK + C6 on-chain anchor)
  exit 1  -> verify ran but did NOT reach VERIFIED (PARTIAL/FAILED -- named)
  exit 2  -> environment incomplete (no snarkjs / missing refs / RPC unreachable) -- NEVER a pass

Default artifact pair = the M17 demo certificate (the one-pager's demo cert). Override with
--cert/--posp for a pilot session's certificate.

Run:
    python scripts/portcert_full_verify.py
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CERT = "audits/match_certificate_m17.json"
DEFAULT_POSP = "audits/posp_record_match17_rp_fixb3_2026-07-08.json"
DEFAULT_RPC = "https://babel-api.testnet.iotex.io"     # TESTNET; read-only receipt lookup, 0 IOTX
# The tracked verifying key. A cert's `vkey_ref` may point at a build-local artifact that is not in
# the repo (zk_artifacts/ is regenerated, not published), which strands a stranger at exit 2. This
# published copy is the fallback: it cannot manufacture a pass, because groth16 verification fails
# against any key but the circuit's own.
PUBLISHED_VKEY = "contracts/circuits/VAPIReplayProofVerifier_verification_key.json"


def discover_snarkjs() -> str | None:
    """First usable snarkjs candidate. Order: env SNARKJS -> repo-local node_modules bin ->
    PATH -> npx fallback (only if npx exists). Existence-only here; the verify itself is
    fail-closed (C5 passes only on snarkjs printing 'OK!')."""
    cands = []
    if os.environ.get("SNARKJS"):
        cands.append(os.environ["SNARKJS"])
    for rel in ("contracts/node_modules/.bin/snarkjs.cmd",       # Windows npm shim
                "contracts/node_modules/.bin/snarkjs"):
        cands.append(os.path.join(_REPO, rel))
    cands.append("snarkjs")                                       # PATH
    for c in cands:
        if shutil.which(c) or os.path.exists(c):
            return c
    if shutil.which("npx"):
        return "npx-snarkjs-fallback"                             # match_certificate falls back to npx
    return None


def rpc_reachable(url: str) -> bool:
    """One eth_blockNumber probe (read-only). babel-api 403s without a User-Agent -- send one."""
    import urllib.request
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                          "User-Agent": "qortroller-portcert"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return bool(json.loads(r.read()).get("result"))
    except Exception:  # noqa: BLE001 -- unreachable RPC -> honest exit 2, never a pass
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="PORT-CERT full-VERIFIED (C5 ZK + C6 on-chain) runner")
    ap.add_argument("--cert", default=DEFAULT_CERT)
    ap.add_argument("--posp", default=DEFAULT_POSP)
    ap.add_argument("--chain-rpc", default=DEFAULT_RPC)
    ap.add_argument("--snarkjs", default=None, help="override discovery")
    ap.add_argument("--vkey", default=None,
                    help=f"verifying key for C5, overriding the cert's vkey_ref "
                         f"(default when that ref is absent: {PUBLISHED_VKEY})")
    a = ap.parse_args()

    print("=" * 74)
    print("  PORT-CERT FULL VERIFY -- PARTIAL -> VERIFIED (C5 ZK + C6 on-chain anchor)")
    print("=" * 74)

    # -- environment pre-checks (exit 2 class: incomplete env is NEVER a pass) ------------------
    cert_p = os.path.join(_REPO, a.cert) if not os.path.isabs(a.cert) else a.cert
    posp_p = os.path.join(_REPO, a.posp) if not os.path.isabs(a.posp) else a.posp
    for label, p in (("cert", cert_p), ("posp", posp_p)):
        if not os.path.isfile(p):
            print(f"  INCOMPLETE: {label} file absent: {p}  (exit 2)")
            return 2
    cert = json.load(open(cert_p, encoding="utf-8"))
    vhr = (cert.get("surfaces") or {}).get("vhr") or {}
    missing_refs = [r for r in ("public_ref", "proof_ref")
                    if not (vhr.get(r) and os.path.isfile(os.path.join(_REPO, vhr[r])))]
    if missing_refs:
        print(f"  INCOMPLETE: cert ZK refs absent on disk: {missing_refs} -- C5 cannot run  (exit 2)")
        return 2

    vkey = a.vkey
    if not vkey and not (vhr.get("vkey_ref") and os.path.isfile(os.path.join(_REPO, vhr["vkey_ref"]))):
        if not os.path.isfile(os.path.join(_REPO, PUBLISHED_VKEY)):
            print(f"  INCOMPLETE: cert vkey_ref {vhr.get('vkey_ref')!r} absent and no published "
                  f"fallback at {PUBLISHED_VKEY} -- C5 cannot run  (exit 2)")
            return 2
        vkey = PUBLISHED_VKEY
        print(f"  vkey      : {vkey} (published fallback; cert vkey_ref {vhr.get('vkey_ref')!r} "
              f"is not in this tree)")
    elif vkey:
        print(f"  vkey      : {vkey} (supplied, overriding the cert's vkey_ref)")
    anchor_tx = ((cert.get("surfaces") or {}).get("anchor") or {}).get("tx")
    if not anchor_tx:
        print("  INCOMPLETE: cert carries no anchor tx -- C6 cannot run  (exit 2)")
        return 2

    snarkjs = a.snarkjs or discover_snarkjs()
    if snarkjs is None:
        print("  INCOMPLETE: no snarkjs found (env SNARKJS / contracts/node_modules/.bin / PATH / npx)."
              "  Install: cd contracts && npm install  (exit 2)")
        return 2
    snark_arg = "snarkjs" if snarkjs == "npx-snarkjs-fallback" else snarkjs
    print(f"  snarkjs   : {snark_arg}")

    if not rpc_reachable(a.chain_rpc):
        print(f"  INCOMPLETE: RPC unreachable: {a.chain_rpc}  (exit 2)")
        return 2
    print(f"  chain-rpc : {a.chain_rpc} (reachable; read-only receipt lookup, 0 IOTX)")

    # -- the documented verify, tools injected (single source of truth) -------------------------
    cmd = [sys.executable, os.path.join(_REPO, "scripts", "match_certificate.py"), "verify",
           "--cert", cert_p, "--posp", posp_p, "--snarkjs", snark_arg, "--chain-rpc", a.chain_rpc]
    if vkey:
        cmd += ["--vkey", vkey]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=_REPO)
    out = (res.stdout or "") + (res.stderr or "")
    print(out.rstrip()[-2000:])                                   # verifier's own report is the record

    if "OVERALL: VERIFIED" in out:
        print("\n  PORT-CERT FULL VERIFY: VERIFIED  (C5 ZK checked + C6 anchor checked)  exit=0")
        return 0
    print("\n  PORT-CERT FULL VERIFY: NOT VERIFIED -- see failed/unchecked checks above  exit=1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
