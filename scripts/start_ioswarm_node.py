"""
Phase 132 — IoSwarm Live Node launcher

Usage:
    python scripts/start_ioswarm_node.py [--host HOST] [--port PORT]
        [--staker-address ADDR] [--secret SECRET] [--hmac]

Environment variables (take precedence over args when set):
    IOSWARM_STAKER_ADDRESS — operator staking wallet address
    IOSWARM_NODE_SECRET    — HMAC-SHA256 shared secret
    IOSWARM_HMAC_ENABLED   — "true" to enable HMAC auth
    IOSWARM_NODE_ID        — optional custom node ID (default: auto-generated)
    IOSWARM_STAKE_AMOUNT   — staked VAPI amount (default: 10000)

Example:
    python scripts/start_ioswarm_node.py \\
        --host 0.0.0.0 --port 8090 \\
        --staker-address 0xYourAddress \\
        --secret mysecret --hmac
"""

import argparse
import os
import sys

# ── path setup ──────────────────────────────────────────────────────────────
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "bridge"))

# ── argument parsing ─────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Start a VAPI IoSwarm live node server",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument("--host", default="0.0.0.0", help="Bind host")
parser.add_argument("--port", type=int, default=8090, help="Bind port")
parser.add_argument("--staker-address", default="", help="Operator staking wallet address")
parser.add_argument("--secret", default="", help="HMAC-SHA256 shared secret")
parser.add_argument("--hmac", action="store_true", help="Enable HMAC response signing")

args = parser.parse_args()

# ── apply args → env (env takes precedence if already set) ──────────────────
if args.staker_address and not os.environ.get("IOSWARM_STAKER_ADDRESS"):
    os.environ["IOSWARM_STAKER_ADDRESS"] = args.staker_address
if args.secret and not os.environ.get("IOSWARM_NODE_SECRET"):
    os.environ["IOSWARM_NODE_SECRET"] = args.secret
if args.hmac and not os.environ.get("IOSWARM_HMAC_ENABLED"):
    os.environ["IOSWARM_HMAC_ENABLED"] = "true"

staker = os.environ.get("IOSWARM_STAKER_ADDRESS", "(not set)")
hmac_on = os.environ.get("IOSWARM_HMAC_ENABLED", "false").lower() == "true"

# ── startup banner ───────────────────────────────────────────────────────────
print(f"""
╔══════════════════════════════════════════════════════╗
║  VAPI IoSwarm Node  v3.0.0-phase132                  ║
╠══════════════════════════════════════════════════════╣
║  Staker : {staker[:44]:<44} ║
║  Host   : {args.host}:{args.port:<40} ║
║  HMAC   : {"enabled" if hmac_on else "disabled":<47} ║
║  Caps   : renewal, classj, triage, vhp_mint          ║
╚══════════════════════════════════════════════════════╝
""")

# ── launch uvicorn ───────────────────────────────────────────────────────────
try:
    import uvicorn
except ImportError:
    print("[ERROR] uvicorn not installed. Run: pip install uvicorn[standard]")
    sys.exit(1)

uvicorn.run(
    "vapi_bridge.ioswarm_live_node_server:app",
    host=args.host,
    port=args.port,
    reload=False,
    log_level="info",
)
