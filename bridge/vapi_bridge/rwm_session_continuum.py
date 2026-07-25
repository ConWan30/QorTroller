"""RWM → QorTroller session continuum loader (CANDIDATE).

Loads L0 archive (+ optional NOV-2 bind / escrow / presence / ioID JSON) and builds a
`qortroller-session-continuum-v0` postcard via pure `l9_presence.session_continuum`.

Offline only. No stop-path hook, no network, no FROZEN seal, no chain spend.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from vapi_bridge.rwm_dispute_escrow import (
    EscrowError,
    load_l0_chain,
    verify_l0_archive,
)

# l9_presence is repo-root package
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from l9_presence.session_continuum import (  # noqa: E402
    SCHEMA,
    SessionContinuumRecord,
    build_session_continuum,
    verify_continuum,
)
from l9_presence.session_identity import (  # noqa: E402
    derive_session_id,
    session_display as u1_session_display,
)

__all__ = [
    "SCHEMA",
    "ContinuumError",
    "load_rwm_surface",
    "build_continuum_from_archive",
    "verify_continuum",
    "build_session_continuum",
]


class ContinuumError(ValueError):
    """Fail-closed continuum build error."""


def _load_json(path: Path | str | None) -> Optional[dict[str, Any]]:
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        raise ContinuumError(f"JSON not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ContinuumError(f"expected object JSON in {p}")
    return obj


def load_rwm_surface(
    archive_dir: Path | str,
    *,
    require_verified: bool = True,
) -> dict[str, Any]:
    """Load L0 manifest + disk re-verify into an `rwm` surface dict for the pure composer."""
    d = Path(archive_dir)
    try:
        l0 = load_l0_chain(d)
    except EscrowError as e:
        raise ContinuumError(str(e)) from e
    verified = verify_l0_archive(d, l0)
    if require_verified and not verified:
        raise ContinuumError("L0 chain does not re-verify from disk — refuse continuum")
    tip = (l0.get("chain_hex") or [None])[-1]
    return {
        "session_id": l0["session_id"],
        "device_id_hex": l0["device_id_hex"],
        "l0_chain_tip_hex": str(tip).lower() if tip else "",
        "l0_verified": bool(verified),
        "n_frames": len(l0.get("frames") or []),
        "schema": l0.get("schema"),
        "genesis_ts_ns": l0.get("genesis_ts_ns"),
    }


def _infer_session_display(label: str | None, stamp: int | str | None) -> Optional[str]:
    if label is None or stamp is None or str(stamp).strip() == "":
        return None
    return u1_session_display(label, stamp)


def build_continuum_from_archive(
    archive_dir: Path | str,
    *,
    label: str | None = None,
    stamp: int | str | None = None,
    session_display: str | None = None,
    ioid: dict | Path | str | None = None,
    poep_live: dict | Path | str | None = None,
    nov2_bind: dict | Path | str | None = None,
    escrow: dict | Path | str | None = None,
    posp: dict | Path | str | None = None,
    kas: dict | Path | str | None = None,
    require_l0_verified: bool = True,
    created_ts_ns: int | None = None,
) -> dict[str, Any]:
    """Build continuum postcard from an L0 archive + optional surface JSON paths/dicts."""
    rwm = load_rwm_surface(archive_dir, require_verified=require_l0_verified)

    # session_display: explicit > label_stamp > None
    display = session_display
    if not display and label is not None and stamp is not None:
        display = _infer_session_display(label, stamp)
        # Soft check: if display derives a different session_id than L0, still pass display
        # so pure module can fail-closed on U1 mismatch rather than silent skip.
        if display:
            derived = derive_session_id(label, stamp)
            if derived != rwm["session_id"]:
                # still attach — composer will flag MISMATCH
                pass

    def _as_dict(src: dict | Path | str | None) -> Optional[dict]:
        if src is None:
            return None
        if isinstance(src, dict):
            return src
        return _load_json(src)

    ioid_d = _as_dict(ioid)
    poep_d = _as_dict(poep_live)

    stack: dict[str, Any] = {}
    bind_d = _as_dict(nov2_bind)
    if bind_d:
        stack["nov2_bind"] = {
            "session_id": bind_d.get("session_id"),
            "bind_ok": bind_d.get("bind_ok"),
            "l0_chain_tip_hex": bind_d.get("l0_chain_tip_hex"),
            "bind_kind": bind_d.get("bind_kind"),
            "ok": bind_d.get("bind_ok", True),
        }
        if bind_d.get("poac_tip_hex"):
            stack["poac_tip_hex"] = bind_d["poac_tip_hex"]
        if bind_d.get("gic_tip_hex"):
            stack["gic_tip_hex"] = bind_d["gic_tip_hex"]

    escrow_d = _as_dict(escrow)
    if escrow_d:
        stack["escrow"] = {
            "session_id": escrow_d.get("session_id"),
            "ok": True,
            "commitment_root": escrow_d.get("commitment_root")
            or escrow_d.get("root_hex"),
        }

    posp_d = _as_dict(posp)
    if posp_d:
        stack["posp"] = {
            "session_id": posp_d.get("session_id"),
            "verdict": posp_d.get("verdict"),
            "ok": True,
        }

    kas_d = _as_dict(kas)
    if kas_d:
        stack["kas"] = {
            "session_id": kas_d.get("session_id"),
            "verdict": kas_d.get("verdict"),
            "ok": True,
        }

    rec: SessionContinuumRecord = build_session_continuum(
        device_id=rwm["device_id_hex"],
        session_id=rwm["session_id"],
        session_display=display,
        rwm=rwm,
        ioid=ioid_d,
        poep_live_summary=poep_d,
        stack=stack or None,
    )
    out = rec.to_dict()
    out["candidate"] = True
    out["created_ts_ns"] = (
        int(created_ts_ns) if created_ts_ns is not None else time.time_ns()
    )
    out["archive_dir"] = str(archive_dir)
    return out
