"""RWM NOV-2 — cross-primitive session bind (CANDIDATE, not FROZEN-v1).

Offline tip-equality bind of L0 chain tip to optional PoAC segment / GIC tips.
Pure module: no stop-path, no network, no PoAC wire mutation.

See docs/a2a/retina-witness-mark-ladder/nov-2-implementation-plan.md.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from vapi_bridge.rwm_dispute_escrow import (
    EscrowError,
    load_l0_chain,
    verify_l0_archive,
)

SCHEMA = "qortroller-rwm-session-bind-v0"
BIND_KINDS = frozenset({"none", "poac_segment", "gic_tip", "dual"})
ALGORITHM = "sha256-hex-eq-v0"


class BindError(ValueError):
    """Fail-closed bind build error."""


def _norm_hex32(value: str, *, label: str) -> str:
    s = (value or "").strip().lower().removeprefix("0x")
    if not s:
        return ""
    try:
        raw = bytes.fromhex(s)
    except ValueError as e:
        raise BindError(f"{label}: not valid hex") from e
    if len(raw) != 32:
        raise BindError(f"{label}: must decode to 32 bytes, got {len(raw)}")
    return raw.hex()


def load_tip_hex(source: str | Path | None) -> tuple[str, str]:
    """Load a 32-byte tip from inline hex or a file path.

    Returns (tip_hex, source_label) where source_label is 'inline' or path str.
    Empty source → ("", "").
    """
    if source is None:
        return "", ""
    s = str(source).strip()
    if not s:
        return "", ""
    p = Path(s)
    if p.is_file():
        text = p.read_text(encoding="utf-8").strip()
        # allow JSON with tip/hash field or raw hex
        if text.startswith("{"):
            import json

            obj = json.loads(text)
            for k in ("tip_hex", "gic_tip_hex", "poac_tip_hex", "chain_tip_hex", "hash", "commitment"):
                if k in obj and obj[k]:
                    return _norm_hex32(str(obj[k]), label=k), str(p)
            raise BindError(f"JSON tip file {p} has no known tip field")
        # first non-empty line
        line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        return _norm_hex32(line, label=str(p)), str(p)
    # treat as inline hex
    return _norm_hex32(s, label="inline tip"), "inline"


def verify_bind(
    bind: dict[str, Any],
    *,
    archive_dir: Path | str | None = None,
    l0: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-check bind package structure + tip equality. Soft: returns ok/checks."""
    checks: list[dict[str, Any]] = []

    def _chk(name: str, ok: bool, note: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "note": note})

    try:
        if bind.get("schema") != SCHEMA:
            _chk("schema", False, f"expected {SCHEMA}")
            return {"ok": False, "checks": checks, "bind_ok": False}

        kind = bind.get("bind_kind") or "none"
        _chk("bind_kind", kind in BIND_KINDS, str(kind))

        poac = (bind.get("poac_tip_hex") or "").lower()
        gic = (bind.get("gic_tip_hex") or "").lower()
        tip = (bind.get("l0_chain_tip_hex") or "").lower()

        if archive_dir is not None:
            d = Path(archive_dir)
            rec = l0 if l0 is not None else load_l0_chain(d)
            l0_ok = verify_l0_archive(d, rec)
            _chk("l0_chain_disk", l0_ok)
            if l0_ok:
                expect_tip = rec["chain_hex"][-1].lower()
                _chk("l0_tip_match", tip == expect_tip, "package tip equals archive tip")
                _chk("session_id", bind.get("session_id") == rec["session_id"])
        else:
            _chk("archive_optional", True, "no archive_dir")

        need_poac = kind in ("poac_segment", "dual")
        need_gic = kind in ("gic_tip", "dual")

        poac_present = len(poac) == 64
        gic_present = len(gic) == 64

        # Presence required only when bind_ok claims success; soft-false is valid.
        if need_poac:
            _chk(
                "poac_present_if_ok",
                (not bind.get("bind_ok")) or poac_present,
                "32-byte hex required when bind_ok=true",
            )
        else:
            _chk("poac_optional", True)

        if need_gic:
            _chk(
                "gic_present_if_ok",
                (not bind.get("bind_ok")) or gic_present,
                "32-byte hex required when bind_ok=true",
            )
        else:
            _chk("gic_optional", True)

        declared = bool(bind.get("bind_ok"))
        if kind == "none":
            expected_ok = True
        elif kind == "poac_segment":
            expected_ok = poac_present
        elif kind == "gic_tip":
            expected_ok = gic_present
        elif kind == "dual":
            expected_ok = poac_present and gic_present
        else:
            expected_ok = False

        _chk("bind_ok_field", declared == expected_ok, f"declared={declared} expected={expected_ok}")
        _chk("algorithm", bind.get("bind_proof", {}).get("algorithm") == ALGORITHM)

    except Exception as e:  # noqa: BLE001
        _chk("exception", False, repr(e)[:200])
        return {"ok": False, "checks": checks, "bind_ok": False}

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks, "bind_ok": bool(bind.get("bind_ok"))}


def build_bind(
    archive_dir: Path | str,
    *,
    bind_kind: str = "none",
    poac_source: str | Path | None = None,
    gic_source: str | Path | None = None,
    require_bind: bool = False,
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build a CANDIDATE session-bind package against a verified L0 archive."""
    kind = (bind_kind or "none").strip().lower()
    if kind not in BIND_KINDS:
        raise BindError(f"bind_kind must be one of {sorted(BIND_KINDS)}")

    d = Path(archive_dir)
    l0 = load_l0_chain(d)
    if not verify_l0_archive(d, l0):
        raise BindError("L0 chain does not re-verify — refuse to attach bind")

    tip_hex = l0["chain_hex"][-1].lower()
    session_id = l0["session_id"]

    poac_hex, poac_src = load_tip_hex(poac_source)
    gic_hex, gic_src = load_tip_hex(gic_source)

    need_poac = kind in ("poac_segment", "dual")
    need_gic = kind in ("gic_tip", "dual")

    if need_poac and not poac_hex:
        if require_bind:
            raise BindError("poac tip required for bind_kind but missing/unloadable")
    if need_gic and not gic_hex:
        if require_bind:
            raise BindError("gic tip required for bind_kind but missing/unloadable")

    bind_ok = True
    if kind == "none":
        bind_ok = True
    elif kind == "poac_segment":
        bind_ok = bool(poac_hex)
    elif kind == "gic_tip":
        bind_ok = bool(gic_hex)
    elif kind == "dual":
        bind_ok = bool(poac_hex) and bool(gic_hex)

    if require_bind and not bind_ok:
        raise BindError("require_bind=True but bind_ok would be false")

    ts = int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    return {
        "schema": SCHEMA,
        "candidate": True,
        "session_id": session_id,
        "l0_chain_tip_hex": tip_hex,
        "bind_kind": kind,
        "poac_tip_hex": poac_hex,
        "gic_tip_hex": gic_hex,
        "bind_proof": {
            "poac_source": poac_src,
            "gic_source": gic_src,
            "algorithm": ALGORITHM,
        },
        "bind_ok": bind_ok,
        "created_ts_ns": ts,
    }


def attach_bind(escrow: dict[str, Any], bind: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of escrow with session_bind attached (additive)."""
    if escrow.get("session_id") and bind.get("session_id"):
        if escrow["session_id"] != bind["session_id"]:
            raise BindError("escrow session_id != bind session_id")
    if escrow.get("l0_chain_tip_hex") and bind.get("l0_chain_tip_hex"):
        if escrow["l0_chain_tip_hex"].lower() != bind["l0_chain_tip_hex"].lower():
            raise BindError("escrow l0_chain_tip_hex != bind l0_chain_tip_hex")
    out = dict(escrow)
    out["session_bind"] = dict(bind)
    return out
