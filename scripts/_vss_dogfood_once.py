#!/usr/bin/env python3
"""One-shot VSS seat OPEN for live dogfood. Not for production loops."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

# Load scripts/.env then bridge/.env OPERATOR into BRIDGE_API_KEY if needed
def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        # Prefer existing process env only if already set and non-empty
        if not os.environ.get(k):
            os.environ[k] = v


_load_env(ROOT / "scripts" / ".env")
_load_env(ROOT / "bridge" / ".env")
if not os.environ.get("BRIDGE_API_KEY") and os.environ.get("OPERATOR_API_KEY"):
    os.environ["BRIDGE_API_KEY"] = os.environ["OPERATOR_API_KEY"]

sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

# Import seat helper as module via path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "buzz_vss_seat", ROOT / "scripts" / "buzz_vss_seat.py"
)
# Register in sys.modules before exec so @dataclass works
m = importlib.util.module_from_spec(spec)
sys.modules["buzz_vss_seat"] = m
assert spec.loader is not None
spec.loader.exec_module(m)

MEDIA = os.environ.get(
    "VSS_MEDIA_URL", "https://example.com/qortroller-vss-dogfood"
)
channel = os.environ.get("VSS_STREAMS_CHANNEL", "")
if not channel:
    sys.exit("VSS_STREAMS_CHANNEL missing")
if not os.environ.get("BUZZ_PRIVATE_KEY"):
    sys.exit("BUZZ_PRIVATE_KEY missing")

class A:
    pass

a = A()
a.channel = channel
a.media_url = MEDIA
a.session_id = None
a.ioid_token = None
a.poll_interval = 15.0
a.dry_run = False
cfg = m._load_config(a)

print(f"[*] channel_prefix={cfg.channel_id[:8]}…", file=sys.stderr)
print(f"[*] relay={cfg.relay_url}", file=sys.stderr)
print(f"[*] bridge={cfg.bridge_base_url}", file=sys.stderr)
print(f"[*] media={cfg.media_url}", file=sys.stderr)
print(f"[*] helper={cfg.helper_path}", file=sys.stderr)

elig = m._poll_eligibility(cfg)
print(f"[*] elig={json.dumps(elig)}", file=sys.stderr)
if not elig or not elig.get("eligible"):
    sys.exit("not eligible — refuse OPEN")

role = m.check_signer_is_not_bot(cfg)
print(f"[*] signer_role={role}", file=sys.stderr)
if role == "bot":
    sys.exit("signer is bot — refuse OPEN (VSS-7)")
if role is None:
    sys.exit("cannot verify signer role — refuse OPEN (fail-closed)")

result = m._build_and_publish(
    cfg,
    m.SEAT_OPEN,
    eligible=True,
    honesty=elig.get("honesty") or {},
    signer_role=role,
)
print(f"[*] publish={json.dumps(result)}", file=sys.stderr)
if not result:
    sys.exit("OPEN publish failed")
print(json.dumps({"ok": True, "event_id": result.get("event_id"), "result": result}))
sys.exit(0)
