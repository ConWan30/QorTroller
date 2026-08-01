#!/usr/bin/env python3
"""One-shot VSS seat OPEN/CLOSED for live dogfood. Not a production loop.

Usage:
  python scripts/_vss_dogfood_once.py open
  python scripts/_vss_dogfood_once.py close
  python scripts/_vss_dogfood_once.py cycle   # OPEN then CLOSED
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)


# Keys that must never be filled from scripts/.env when the caller already
# set a gamer key (bot NIP-OA tag breaks human-key publish).
_SECRET_KEYS = frozenset(
    {"BUZZ_PRIVATE_KEY", "BUZZ_AUTH_TAG", "BUZZ_OWNER_PRIVATE_KEY"}
)


def _load_env(path: Path, *, skip_secrets: bool = False) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if skip_secrets and k in _SECRET_KEYS:
            continue
        if not os.environ.get(k):
            os.environ[k] = v


# If caller already set BUZZ_PRIVATE_KEY (gamer), do not pull bot secrets.
_gamer_key_preloaded = bool(os.environ.get("BUZZ_PRIVATE_KEY"))
_load_env(ROOT / "scripts" / ".env", skip_secrets=_gamer_key_preloaded)
_load_env(ROOT / "bridge" / ".env")
if not os.environ.get("BRIDGE_API_KEY") and os.environ.get("OPERATOR_API_KEY"):
    os.environ["BRIDGE_API_KEY"] = os.environ["OPERATOR_API_KEY"]
# Human gamer publish is standalone — bot NIP-OA tag must not apply.
if _gamer_key_preloaded:
    os.environ.pop("BUZZ_AUTH_TAG", None)
    os.environ.pop("BUZZ_OWNER_PRIVATE_KEY", None)

sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "buzz_vss_seat", ROOT / "scripts" / "buzz_vss_seat.py"
)
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

action = (sys.argv[1] if len(sys.argv) > 1 else "open").strip().lower()
if action not in ("open", "close", "cycle"):
    sys.exit("usage: _vss_dogfood_once.py [open|close|cycle]")


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

print(f"[*] action={action}", file=sys.stderr)
print(f"[*] channel_prefix={cfg.channel_id[:8]}…", file=sys.stderr)
print(f"[*] relay={cfg.relay_url}", file=sys.stderr)
print(f"[*] bridge={cfg.bridge_base_url}", file=sys.stderr)
print(f"[*] media={cfg.media_url}", file=sys.stderr)
print(f"[*] helper={cfg.helper_path}", file=sys.stderr)

elig = m._poll_eligibility(cfg)
print(f"[*] elig={json.dumps(elig)}", file=sys.stderr)

role = m.check_signer_is_not_bot(cfg)
print(f"[*] signer_role={role}", file=sys.stderr)
if role == "bot":
    sys.exit("signer is bot — refuse (VSS-7)")
if role is None:
    sys.exit("cannot verify signer role — refuse (fail-closed)")


def _publish(seat_state: str, eligible: bool, honesty: dict) -> dict:
    result = m._build_and_publish(
        cfg,
        seat_state,
        eligible=eligible,
        honesty=honesty or {},
        signer_role=role,
    )
    print(f"[*] publish {seat_state}={json.dumps(result)}", file=sys.stderr)
    if not result:
        sys.exit(f"{seat_state} publish failed")
    return result


out: dict = {"ok": True, "action": action, "events": []}

if action in ("open", "cycle"):
    if not elig or not elig.get("eligible"):
        sys.exit("not eligible — refuse OPEN")
    r = _publish(m.SEAT_OPEN, True, elig.get("honesty") or {})
    out["events"].append({"seat": "OPEN", "event_id": r.get("event_id")})

if action in ("close", "cycle"):
    if action == "cycle":
        time.sleep(2)  # brief gap so desktop shows OPEN before CLOSED
    honesty = (elig or {}).get("honesty") or {
        "poep_enabled": False,
        "l6b_enabled": False,
        "candidate_ok": False,
    }
    # CLOSED is allowed even when still eligible (operator dogfood / shutdown path)
    r = _publish(m.SEAT_CLOSED, False, honesty)
    out["events"].append({"seat": "CLOSED", "event_id": r.get("event_id")})

print(json.dumps(out))
sys.exit(0)
