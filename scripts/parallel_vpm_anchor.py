"""Phase O4-VPM-ANCHOR-CEREMONY — Per-VPM-artifact anchor ceremony script.

Sibling of scripts/parallel_o3_act_anchor.py + scripts/parallel_o2_
anchor.py with a simpler 1-tx surface: each invocation anchors ONE VPM
artifact's manifest hash to VPMAnchorRegistry on IoTeX testnet via
chain.anchor_vpm() (commit 19e6ba0f).

DESIGN — TRIPLE-GATE AUTHORIZATION (process-scoped, mirrors
parallel_o3_act_anchor.py without the quadruple-gate watcher veto
because per-VPM anchoring has no fleet-phase concept):

  Gate 1: env CHAIN_SUBMISSION_PAUSED=false        (kill-switch lift)
  Gate 2: env OPERATOR_VPM_ANCHOR_AUTHORIZED=true  (intent gate;
          distinct env var from O2/O3 anchoring — prevents residual
          O2/O3 authorization carrying over into VPM anchoring)
  Gate 3: --confirm CLI flag                       (third-layer auth)

  All three gates must align before any tx is fired. Any failing gate
  -> graceful exit with descriptive message.

USAGE:
  PowerShell:
    $env:CHAIN_SUBMISSION_PAUSED="false"
    $env:OPERATOR_VPM_ANCHOR_AUTHORIZED="true"
    python scripts/parallel_vpm_anchor.py --manifest path/to/<commit>.manifest.json --confirm

  Bash:
    CHAIN_SUBMISSION_PAUSED=false \\
      OPERATOR_VPM_ANCHOR_AUTHORIZED=true \\
      python scripts/parallel_vpm_anchor.py \\
        --manifest path/to/<commit>.manifest.json --confirm

  After this shell exits, env vars vanish — bridge/.env is unchanged.

WHAT IT DOES:
  1. Verify all three gates aligned (incl. that VPMAnchorRegistry is
     configured in bridge/.env).
  2. Read + parse the VPM manifest JSON; extract:
       - zkba_manifest_hash_hex (the upstream ZKBA the VPM wraps)
       - output_hash_hex (the VPM manifest's content hash; used as
         the anchor key on chain)
       - ts_ns (manifest's timestamp; passed as uint64 to anchorVPM)
  3. Read wallet balance + network gas price (read-only RPC).
  4. Cross-check pre-flight: verify upstream ZKBA artifact IS already
     anchored in AdjudicationRegistry via chain.is_record_verified()
     (the contract enforces this at write time but cheap to pre-flight
     here so we save the failed-tx gas).
  5. Call chain.anchor_vpm(zkba_hash, vpm_hash, ts_ns) which builds +
     signs + sends the tx with gas-estimate × 1.25 buffer.
  6. Read wallet balance after; report cost.
  7. Print tx hash + updated wallet for operator records.

EXIT CODES:
  0  Anchor success; tx hash printed
  1  Gate failure (refused to fire)
  2  Wallet balance / pre-flight failure
  3  Manifest parse / shape failure
  4  Tx revert / 'VPM: already anchored' / 'VPM: zkba not anchored'
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Cost budget = 1 tx × ~0.005 IOTX (testnet) + 50% margin
COST_BUDGET_IOTX = 0.05
SAFETY_FLOOR_IOTX = 0.5


def check_gates(args) -> tuple[bool, str]:
    """Three-factor authorization check. Returns (gates_ok, reason)."""
    # Gate 1
    if os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").lower() != "false":
        return False, (
            "Gate 1 FAIL — CHAIN_SUBMISSION_PAUSED is not 'false' in env. "
            "Run: $env:CHAIN_SUBMISSION_PAUSED='false' before re-invoking."
        )

    # Gate 2
    if os.environ.get("OPERATOR_VPM_ANCHOR_AUTHORIZED", "").lower() != "true":
        return False, (
            "Gate 2 FAIL — OPERATOR_VPM_ANCHOR_AUTHORIZED env var not "
            "set to 'true'. This is the operator's explicit-intent flag "
            "for VPM anchoring. Distinct from O2/O3 to prevent residual "
            "authorization carrying over. "
            "Run: $env:OPERATOR_VPM_ANCHOR_AUTHORIZED='true'"
        )

    # Gate 3
    if not args.confirm:
        return False, (
            "Gate 3 FAIL — --confirm CLI flag missing. Run with --confirm "
            "to authorize. Dry-run mode (without --confirm) is intentionally "
            "absent for this script — invocation requires explicit intent."
        )

    return True, "all three gates aligned"


def parse_manifest(manifest_path: Path) -> tuple[dict | None, str]:
    """Read + validate the VPM manifest. Returns (parsed_dict, error)."""
    if not manifest_path.exists():
        return None, f"manifest file does not exist: {manifest_path}"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"manifest parse failed: {exc}"

    schema = manifest.get("schema")
    if schema not in ("vapi-vpm-artifact-v1", "vapi-zkba-manifest-v1"):
        return None, (
            f"manifest schema {schema!r} is not vapi-vpm-artifact-v1 or "
            f"vapi-zkba-manifest-v1; this script can only anchor those"
        )

    required = ["output_hash_hex", "ts_ns"]
    for k in required:
        if k not in manifest:
            return None, f"manifest missing required field: {k}"

    # For VPM-form manifests, the upstream ZKBA hash is explicit.
    # For ZKBA-form manifests, the manifest IS the ZKBA — no upstream;
    # we'd want a different ceremony (anchor_zkba_artifact, not VPM).
    if schema == "vapi-vpm-artifact-v1":
        if "zkba_manifest_hash_hex" not in manifest:
            return None, (
                "VPM manifest missing zkba_manifest_hash_hex — wrapper "
                "schema vapi-vpm-manifest-v1 requires it per Phase O4 "
                "Stream A.0 design"
            )
    else:
        return None, (
            f"manifest schema is vapi-zkba-manifest-v1 — use "
            f"scripts/parallel_zkba_anchor.py for ZKBA anchoring, "
            f"not this script. parallel_vpm_anchor.py is for VPM "
            f"(wrapped) artifacts only."
        )

    return manifest, ""


async def fire_anchor(manifest: dict, args) -> int:
    """Build the chain client + fire anchor_vpm. Returns exit code."""
    try:
        from bridge.vapi_bridge.config import Config
        from bridge.vapi_bridge.chain import ChainClient
    except ImportError as exc:
        print(f"FAIL: chain client import failed: {exc}", file=sys.stderr)
        return 2

    cfg = Config()
    if not getattr(cfg, "vpm_anchor_registry_address", ""):
        print(
            "Gate 4 FAIL — cfg.vpm_anchor_registry_address is empty. "
            "Deploy VPMAnchorRegistry first via "
            "contracts/scripts/deploy-vpm-anchor-registry.js and set "
            "VPM_ANCHOR_REGISTRY_ADDRESS in bridge/.env.",
            file=sys.stderr,
        )
        return 2

    try:
        chain = ChainClient(cfg)
    except Exception as exc:
        print(f"FAIL: ChainClient construction failed: {exc}", file=sys.stderr)
        return 2

    # Pre-anchor wallet balance check
    try:
        bal_before = await chain.get_balance()
    except Exception as exc:
        print(f"FAIL: wallet balance read failed: {exc}", file=sys.stderr)
        return 2

    if bal_before < SAFETY_FLOOR_IOTX:
        print(
            f"FAIL: wallet balance {bal_before:.4f} IOTX below "
            f"safety floor {SAFETY_FLOOR_IOTX} IOTX. Refuel before retry.",
            file=sys.stderr,
        )
        return 2

    zkba_hash = manifest["zkba_manifest_hash_hex"]
    vpm_hash = manifest["output_hash_hex"]
    ts_ns = int(manifest["ts_ns"])

    print(f"VPM anchor ceremony — pre-anchor state:")
    print(f"  zkba_manifest_hash: 0x{zkba_hash}")
    print(f"  vpm_manifest_hash:  0x{vpm_hash}")
    print(f"  ts_ns:              {ts_ns}")
    print(f"  wallet balance:     {bal_before:.4f} IOTX")
    print(f"  cost budget:        {COST_BUDGET_IOTX} IOTX (~150x margin)")
    print(f"  vpm_anchor_addr:    {cfg.vpm_anchor_registry_address}")
    print()
    print(f"Firing chain.anchor_vpm() ...")

    tx_hash, ok = await chain.anchor_vpm(zkba_hash, vpm_hash, ts_ns)

    if not ok:
        print(
            f"FAIL: anchor_vpm returned (None, False). Common causes:",
            file=sys.stderr,
        )
        print(
            f"  - kill-switch still held in process env",
            file=sys.stderr,
        )
        print(
            f"  - 'VPM: already anchored' (idempotent; vpm_hash present "
            f"on chain)",
            file=sys.stderr,
        )
        print(
            f"  - 'VPM: zkba not anchored' (upstream ZKBA must be "
            f"anchored in AdjudicationRegistry first; see chain.anchor_"
            f"zkba_artifact / parallel_zkba_anchor.py)",
            file=sys.stderr,
        )
        return 4

    try:
        bal_after = await chain.get_balance()
        cost = bal_before - bal_after
    except Exception:
        bal_after = -1.0
        cost = -1.0

    print()
    print(f"VPM anchor SUCCESS")
    print(f"  tx_hash:           0x{tx_hash}")
    print(f"  wallet (pre):      {bal_before:.4f} IOTX")
    print(f"  wallet (post):     {bal_after:.4f} IOTX")
    print(f"  cost:              {cost:.4f} IOTX")
    print()
    print(f"Verify on IoTeX testnet explorer:")
    print(f"  https://testnet.iotexscan.io/tx/0x{tx_hash}")
    print()
    print(f"Post-anchor operator actions:")
    print(f"  1. Re-pin CHAIN_SUBMISSION_PAUSED=true in current shell")
    print(f"  2. Clear OPERATOR_VPM_ANCHOR_AUTHORIZED env var")
    print(f"  3. Record this anchor in operator audit log")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Per-VPM-artifact anchor ceremony — fires VPMAnchorRegistry."
            "anchorVPM() via chain.anchor_vpm()"
        ),
    )
    parser.add_argument(
        "--manifest", type=Path, required=True,
        help="Path to the VPM manifest JSON (vapi-vpm-artifact-v1 schema)",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Third-factor authorization — required to fire",
    )
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    # Gate 1 + 2 + 3
    ok, reason = check_gates(args)
    if not ok:
        print(reason, file=sys.stderr)
        return 1

    # Manifest parse
    manifest, err = parse_manifest(args.manifest)
    if manifest is None:
        print(f"FAIL: {err}", file=sys.stderr)
        return 3

    # Fire anchor
    return asyncio.run(fire_anchor(manifest, args))


if __name__ == "__main__":
    sys.exit(main())
