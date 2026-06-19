#!/usr/bin/env python3
"""Record D-DAEMON-1 chain junction (operator ceremony only).

Upgrades daemon identity from provisional SHA-256(ed25519_pubkey) to
canonical on-chain agentId WITHOUT rewriting the provisional chain genesis.

Usage (operator only, after D-DAEMON-1 resolves YES):
  python scripts/record_daemon_chain_junction.py \\
    --canonical-agent-id-hex <64 hex chars> \\
    --provisional-last-commitment-hex <64 hex chars> \\
    [--io-id-did <did>] [--tba-address <0x...>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from _daemon_tools_schema import write_chain_junction_config  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Record D-DAEMON-1 chain junction")
    p.add_argument("--canonical-agent-id-hex", required=True, help="32-byte agentId as 64 hex chars")
    p.add_argument("--provisional-last-commitment-hex", required=True)
    p.add_argument("--io-id-did", default="")
    p.add_argument("--tba-address", default="")
    args = p.parse_args()
    if len(args.canonical_agent_id_hex) != 64:
        print("Error: canonical_agent_id_hex must be 64 hex characters (32 bytes)", file=sys.stderr)
        return 1
    if len(args.provisional_last_commitment_hex) != 64:
        print("Error: provisional_last_commitment_hex must be 64 hex characters", file=sys.stderr)
        return 1
    path = write_chain_junction_config(
        canonical_agent_id_hex=args.canonical_agent_id_hex.lower(),
        provisional_last_commitment_hex=args.provisional_last_commitment_hex.lower(),
        io_id_did=args.io_id_did,
        tba_address=args.tba_address,
    )
    print(f"Chain junction recorded at {path}")
    print("Provisional chain genesis is NOT modified (F-AGC-2).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
