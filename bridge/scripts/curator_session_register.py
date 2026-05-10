"""Phase 238 Step I-FINAL — Curator on-chain registration session runner.

Operator-driven runner that mirrors the Sentry/Guardian Block-B-prime
pattern from Phase O0 (commit 06099677 / 44c26ce0) but extends it with
the Curator-unique post-mint workflow:

   step_6_mint_device_nft("curator")        # Phase O0 wrapper, reused
   step_7_register_full_flow("curator")     # Phase O0 wrapper, reused
   step_8_register_agent("curator")         # Phase O0 wrapper, reused
   STEP 9 (CURATOR-UNIQUE): substitute_curator_agent_id_in_bundles()
   STEP 10 (CURATOR-UNIQUE): re_derive_bundle_merkle_roots()
   STEP 11: operator triggers POST /operator/anchor-cedar-bundle (manual)
   STEP 12: operator updates bridge/.env CURATOR_REVIEW_ENABLED=true
   STEP 13: operator restarts bridge

Usage (steps 6-10 — operator session, requires wallet ≥0.5 IOTX):

    python -m bridge.scripts.curator_session_register --execute

Or per-step:

    python -m bridge.scripts.curator_session_register --step 6
    python -m bridge.scripts.curator_session_register --step 7
    python -m bridge.scripts.curator_session_register --step 8
    python -m bridge.scripts.curator_session_register --step 9
    python -m bridge.scripts.curator_session_register --step 10

Pre-flight: run `python scripts/curator_preflight_runbook.py` first.

Costs (testnet):
   step 6 (mint VAPIOperatorAgentNFT)            ~0.02 IOTX
   step 7 (ioIDRegistry.register full flow)      ~0.04 IOTX (incl. fees)
   step 8 (AgentRegistry.registerAgent)          ~0.02 IOTX
   step 9 (substitute agentId in bundles)        0
   step 10 (re-derive Merkle locally)            0

Total session 6-10: ~0.08 IOTX.  Step H deploy (~0.10 IOTX) is run
separately via contracts/scripts/deploy-phase238-step-h.js BEFORE this
session.

This wrapper does NOT execute the on-chain Cedar bundle anchor (steps
11-13) — those happen via existing POST /operator/anchor-cedar-bundle
endpoint after the operator has bridge running with the substituted
agentId in the bundle JSON.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Bundle paths
REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = REPO_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
O1_BUNDLE = BUNDLE_DIR / "curator_o1_shadow_v1.json"
O2_BUNDLE = BUNDLE_DIR / "curator_o2_suggest_v1.json"

# Placeholder agentId that gets substituted at step 9
PLACEHOLDER_AGENT_ID = "0xc0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0"

CURATOR_AGENT_NAME = "curator"


# ── STEPS 6-8: Reuse Phase O0 wrapper ──────────────────────────────────────

async def step_6_mint_curator_device_nft() -> dict:
    """Mint VAPIOperatorAgentNFT for Curator (tokenId 3).

    Delegates to bridge.scripts.operator_session_register_agents.step_6_mint_device_nft
    with agent="curator".  AGENT_TO_DEVICE_TOKEN_ID["curator"] = 3 was added
    in this commit's agent_registration.py extension.
    """
    from bridge.scripts.operator_session_register_agents import step_6_mint_device_nft
    return await step_6_mint_device_nft(CURATOR_AGENT_NAME)


async def step_7_register_curator_full_flow(use_mock_kms: bool = False) -> dict:
    """ioIDRegistry.register full 13-step flow for Curator.

    Pins DID document to IPFS, computes content hash, queries nonce,
    builds EIP-712 permit, signs via KMS (curator alias), parses DER,
    submits register tx, reads back ioID tokenId from NewDevice event,
    queries TBA address.

    Args:
        use_mock_kms: TESTNET ONLY.  When True, injects MockKMSClient with
            deterministic per-agent keys (seed-based) instead of real AWS
            KMS.  Acceptable for testnet activation but the private key
            lives in-process, not HSM-backed.  MAINNET activation MUST
            provision real AWS KMS for Curator before this flag is unset.
    """
    from bridge.scripts.operator_session_register_agents import step_7_register_full_flow
    kms_client = None
    if use_mock_kms:
        from bridge.vapi_bridge.mock_kms_client import MockKMSClient
        kms_client = MockKMSClient()
        print("  [WARN] TESTNET-ONLY: MockKMSClient injected for Curator step_7.")
        print("    Curator's private key lives in-process; HSM-backed real")
        print("    AWS KMS provisioning required before mainnet activation.")
    return await step_7_register_full_flow(
        CURATOR_AGENT_NAME, kms_client=kms_client,
    )


async def step_8_register_curator_agent_with_mock(use_mock_kms: bool = False) -> dict:
    """Internal helper — step_8 with optional mock KMS injection.

    Mirror step_7 mock injection so the SAME deterministic keypair is used
    for both register flow AND AgentRegistry.registerAgent — otherwise the
    derived device address would differ between steps and AgentRegistry
    would record a different publicKey than ioID DID resolves to.
    """
    from bridge.scripts.operator_session_register_agents import step_8_register_agent
    kms_client = None
    if use_mock_kms:
        from bridge.vapi_bridge.mock_kms_client import MockKMSClient
        kms_client = MockKMSClient()
    return await step_8_register_agent(
        CURATOR_AGENT_NAME, kms_client=kms_client,
    )


async def step_8_register_curator_agent() -> dict:
    """AgentRegistry.registerAgent for Curator — produces Q9-encoded agentId."""
    from bridge.scripts.operator_session_register_agents import step_8_register_agent
    return await step_8_register_agent(CURATOR_AGENT_NAME)


# ── STEP 9 (CURATOR-UNIQUE): Substitute agentId in Cedar bundles ────────────

def substitute_curator_agent_id_in_bundles(real_agent_id: str) -> dict:
    """Replace placeholder agentId across all 41 policies in O1 + O2 bundles.

    The bundle authoring at Phase 238 Step I shipped the placeholder
    0xc0c0...c0c0 because the real Q9-encoded agentId only exists after
    step_8 AgentRegistry.registerAgent emits the AgentRegistered event.

    This function performs a literal string replacement of the placeholder
    with the real agentId across:
      - "agent_id" header field (1× per bundle)
      - principal.agentId in each policy (20 + 21 = 41 occurrences total)

    Args:
        real_agent_id: 64-char hex (with 0x prefix) — Q9-encoded agentId
                       returned from step_8_register_agent.

    Returns:
        dict with substitution counts + new bundle paths.
        Raises ValueError if real_agent_id is malformed.
    """
    if not real_agent_id.startswith("0x"):
        raise ValueError("real_agent_id must start with 0x")
    if len(real_agent_id) != 66:  # "0x" + 64 hex chars
        raise ValueError(f"real_agent_id must be 66 chars (got {len(real_agent_id)})")
    try:
        bytes.fromhex(real_agent_id[2:])
    except ValueError as exc:
        raise ValueError(f"real_agent_id is not valid hex: {exc}")

    if real_agent_id == PLACEHOLDER_AGENT_ID:
        raise ValueError(
            "Refusing to substitute placeholder with itself.  "
            "Pass the REAL agentId returned by step_8."
        )

    results = {}
    for label, path in (("o1_shadow", O1_BUNDLE), ("o2_suggest", O2_BUNDLE)):
        if not path.exists():
            results[label] = {"error": f"bundle missing: {path}"}
            continue
        original = path.read_text(encoding="utf-8")
        substituted = original.replace(PLACEHOLDER_AGENT_ID, real_agent_id)
        n_replacements = original.count(PLACEHOLDER_AGENT_ID)
        path.write_text(substituted, encoding="utf-8")
        results[label] = {
            "path": str(path),
            "replacements": n_replacements,
            "agent_id_after": real_agent_id,
        }

    return results


# ── STEP 10 (CURATOR-UNIQUE): Re-derive Merkle roots ────────────────────────

def re_derive_bundle_merkle_roots() -> dict:
    """Run scripts/cedar_bundle_validate.py validate against both bundles
    after agentId substitution to confirm new Merkle roots.

    The Merkle root MUST change after substitution because the agentId
    is hashed into every policy leaf.  Operator must compare the new
    roots against the audit-trail entries in operator_agent_activation_log
    after on-chain anchor completes.
    """
    import subprocess

    results = {}
    for label, path in (("o1_shadow", O1_BUNDLE), ("o2_suggest", O2_BUNDLE)):
        if not path.exists():
            results[label] = {"error": f"bundle missing: {path}"}
            continue
        try:
            cmd = [sys.executable, "scripts/cedar_bundle_validate.py", "validate", str(path)]
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=str(REPO_ROOT),
            )
            if r.returncode != 0:
                results[label] = {"error": f"validate exit={r.returncode}: {r.stdout[:200]}"}
                continue
            m = re.search(r"Merkle root:\s+(0x[0-9a-f]+)", r.stdout)
            results[label] = {
                "path":         str(path),
                "merkle_root":  m.group(1) if m else "unknown",
                "validate_ok": True,
            }
        except Exception as exc:
            results[label] = {"error": str(exc)}
    return results


# ── Entry point ─────────────────────────────────────────────────────────────

async def run_step(step: int, use_mock_kms: bool = False) -> dict:
    if step == 6:
        return await step_6_mint_curator_device_nft()
    if step == 7:
        return await step_7_register_curator_full_flow(use_mock_kms=use_mock_kms)
    if step == 8:
        return await step_8_register_curator_agent_with_mock(use_mock_kms=use_mock_kms)
    if step == 9:
        # Step 9 needs the real agentId from step 8 session state.
        # Phase O0 wrapper saves under agent_registry_data[agent].agent_id
        # (NOT agent_ids[agent] — that was an earlier draft path).
        from bridge.scripts.operator_session_register_agents import _load_session_state
        state = _load_session_state()
        agent_registry_data = state.get("agent_registry_data", {})
        curator_record = agent_registry_data.get(CURATOR_AGENT_NAME, {})
        real_id = curator_record.get("agent_id")
        if not real_id:
            raise RuntimeError(
                "step_8 has not completed; "
                "agent_registry_data[curator].agent_id missing from "
                "session state. Run step 8 first."
            )
        return {"step": 9, "substitutions": substitute_curator_agent_id_in_bundles(real_id)}
    if step == 10:
        return {"step": 10, "merkle_roots": re_derive_bundle_merkle_roots()}
    raise ValueError(f"Unknown step: {step}")


async def run_all_steps() -> dict:
    """Run steps 6-10 in sequence.  Operator authorizes each on-chain tx."""
    print("=" * 72)
    print("Phase 238 Step I-FINAL — Curator on-chain registration session")
    print("=" * 72)
    results = {}
    for step in (6, 7, 8, 9, 10):
        print(f"\n[step {step}] running...")
        try:
            r = await run_step(step)
            results[f"step_{step}"] = r
            print(f"[step {step}] OK")
            if step == 6 and "device_token_id" in r:
                print(f"   device_token_id: {r['device_token_id']}")
            if step == 8 and "agent_id" in r:
                print(f"   curator agentId: {r['agent_id']}")
            if step in (9, 10):
                print(f"   {json.dumps(r, indent=2)[:400]}")
        except Exception as exc:
            print(f"[step {step}] FAILED: {exc}")
            results[f"step_{step}"] = {"error": str(exc)}
            raise
    return results


def _main_cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", type=int, choices=[6, 7, 8, 9, 10],
                        help="Run a single step (6-10)")
    parser.add_argument("--execute", action="store_true",
                        help="Run all steps 6-10 in sequence")
    parser.add_argument("--use-mock-kms", action="store_true",
                        help="TESTNET ONLY: inject MockKMSClient instead of real "
                             "AWS KMS.  Curator's private key lives in-process; "
                             "HSM-backed real KMS required before mainnet.")
    args = parser.parse_args()
    if not args.step and not args.execute:
        parser.print_help()
        return 1

    if args.step:
        result = asyncio.run(run_step(args.step, use_mock_kms=args.use_mock_kms))
        print(json.dumps(result, indent=2, default=str))
    else:
        result = asyncio.run(run_all_steps())
        print()
        print("=" * 72)
        print("SESSION COMPLETE.  Next operator actions:")
        print("  11. POST /operator/anchor-cedar-bundle bundle_path=...curator_o1_shadow_v1.json")
        print("       (operational FIRST per INV-OPERATOR-AGENT-001;")
        print("        the endpoint then anchors governance second)")
        print("  12. Add CURATOR_REVIEW_ENABLED=true to bridge/.env")
        print("  13. Restart bridge — CuratorReviewLoop task auto-spawns")
        print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(_main_cli())
