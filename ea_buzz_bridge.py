"""SCRUBBED — was a scratch Buzz bridge with a hardcoded nsec.

The private key that lived here is compromised by having been written to a
file. It must be rotated and never reused. See
docs/design/buzz-qortroller-gamer-mvp-v0.md §0 (Phase 0 hygiene) and §10.

The real Phase 1 bot lives at scripts/qortroller_buzz_bot.py and reads
BUZZ_PRIVATE_KEY / BUZZ_OWNER_PRIVATE_KEY from the environment.
"""
import sys

print("ea_buzz_bridge.py is scrubbed. Use scripts/qortroller_buzz_bot.py.", file=sys.stderr)
sys.exit(1)
