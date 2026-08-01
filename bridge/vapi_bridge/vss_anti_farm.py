"""VSS-S2 — Anti-farm guards for stream seats.

Scope later-spine S2 (after VSS-7): one logical OPEN per key per channel
at a time; no empty OPEN (media_url required — enforced in schema).

Local state is operational only (JSON file). Not a cryptographic ban book.
Never touches FROZEN wire or chain.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


def default_state_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / "audits" / "vss_seat_local_state.json"


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {"seats": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "seats" not in data:
            return {"seats": {}}
        if not isinstance(data["seats"], dict):
            data["seats"] = {}
        return data
    except (OSError, json.JSONDecodeError):
        return {"seats": {}}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seat_key(channel_id: str, signer_pubkey: str) -> str:
    return f"{channel_id.strip().lower()}|{signer_pubkey.strip().lower()}"


def is_empty_open(media_url: Optional[str], seat_state: str = "OPEN") -> bool:
    """Empty OPEN = OPEN without a media pointer (anti-farm S2)."""
    if seat_state != "OPEN":
        return False
    return not (media_url and str(media_url).strip())


def can_open_seat(
    *,
    channel_id: str,
    signer_pubkey: str,
    media_url: Optional[str],
    state: dict,
) -> tuple[bool, str]:
    """Return (allowed, reason). Fail-closed on empty OPEN or double OPEN.

    Double OPEN: local state shows this channel+signer already OPEN without
    an intervening CLOSED. First OPEN is allowed.
    """
    if is_empty_open(media_url, "OPEN"):
        return False, "empty OPEN refused (S2: media_url required)"

    if not channel_id or not signer_pubkey:
        return False, "channel_id and signer_pubkey required for anti-farm"

    key = _seat_key(channel_id, signer_pubkey)
    seats = state.get("seats") or {}
    cur = seats.get(key) or {}
    if cur.get("state") == "OPEN":
        return False, "already OPEN for this key+channel (S2: one seat at a time)"
    return True, "ok"


def record_transition(
    state: dict,
    *,
    channel_id: str,
    signer_pubkey: str,
    seat_state: str,
    media_url: Optional[str] = None,
    event_id: Optional[str] = None,
) -> dict:
    """Update local seat state after a successful publish."""
    key = _seat_key(channel_id, signer_pubkey)
    seats = state.setdefault("seats", {})
    seats[key] = {
        "state": seat_state,
        "media_url": media_url or "",
        "event_id": event_id or "",
        "ts": int(time.time()),
        "channel_id": channel_id,
        "signer_pubkey": signer_pubkey,
    }
    return state
