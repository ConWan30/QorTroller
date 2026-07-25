"""RWM → QorTroller session continuum loader (CANDIDATE).

Loads L0 archive (+ optional NOV-2 bind / escrow / presence / ioID JSON) and builds a
`qortroller-session-continuum-v0` postcard via pure `l9_presence.session_continuum`.

Also: sealed live-sim PoEP summary mint (mechanism dogfood) and fail-open daemon emit helper.

Offline composition. No network, no FROZEN seal, no chain spend.
Daemon stop may call issue_continuum_after_l0 under fail-open discipline.
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
    SYNCHRONIZED_CONTINUUM,
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
    "SYNCHRONIZED_CONTINUUM",
    "ContinuumError",
    "load_rwm_surface",
    "normalize_poep_surface",
    "normalize_ioid_surface",
    "build_continuum_from_archive",
    "mint_sealed_sim_live_poep_summary",
    "issue_continuum_after_l0",
    "verify_continuum",
    "build_session_continuum",
]

# Live ioID Inc-D ceremony (public addresses; used when CONTINUUM_IOID_JSON unset)
DEFAULT_IOID_CEREMONY = {
    "token_id": 498,
    "did": "did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692",
    "tba": "0xFCee237789FA91a141781aFB574ADAbcA2660e7b",
    "registered_device_id": (
        "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
    ),
    "note": "ioID Inc-D live ceremony 2026-07-17; public addresses only",
}

SIM_LIVE_POEP_CEILING = (
    "MECHANISM dogfood only: presence_summary is produced by the sealed summarize_live_session "
    "path with a real_hardware=True fire simulator (same path as test_live_simulator_reaches_"
    "synchronized). It proves SYNCHRONIZED_CONTINUUM is reachable when a live-hardware fire "
    "summary co-joins the RWM session_id + device_id. It is NOT a claim that a particular "
    "optical RWM capture co-ran dual-connect PoEP under real play. poep_enabled stays False."
)


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


def normalize_poep_surface(obj: Optional[dict]) -> Optional[dict]:
    """Accept raw GP-session summary or identity-attach artifact; return poep_live_summary shape."""
    if not isinstance(obj, dict) or not obj:
        return None
    if isinstance(obj.get("presence_summary"), dict):
        ps = dict(obj["presence_summary"])
    elif str(obj.get("schema") or "").startswith("qortroller-poep-gameplay"):
        ps = dict(obj)
    elif "presence_session_candidate_ok" in obj or "device_id" in obj:
        ps = dict(obj)
    else:
        return None
    # optional seal from outer attach envelope
    if not ps.get("live_seal") and obj.get("live_seal"):
        ps["live_seal"] = obj["live_seal"]
    return ps


def normalize_ioid_surface(obj: Optional[dict]) -> Optional[dict]:
    """Accept ceremony JSON, attach.identity, or controller_presence.ioid."""
    if not isinstance(obj, dict) or not obj:
        return None
    if isinstance(obj.get("identity"), dict):
        idn = obj["identity"]
        link = idn.get("device_to_owner_link") or {}
        return {
            "token_id": idn.get("ioid_token_id", idn.get("token_id")),
            "did": idn.get("owner_did", idn.get("did")),
            "tba": idn.get("tba_address", idn.get("tba")),
            "registered_device_id": link.get("device_id")
            or idn.get("registered_device_id")
            or obj.get("device_id"),
        }
    cp = obj.get("controller_presence")
    if isinstance(cp, dict) and isinstance(cp.get("ioid"), dict):
        return dict(cp["ioid"])
    # ceremony / bare ioid shape
    if any(k in obj for k in ("token_id", "ioid_token_id", "did", "tba", "tba_address")):
        return {
            "token_id": obj.get("token_id", obj.get("ioid_token_id")),
            "did": obj.get("did", obj.get("owner_did")),
            "tba": obj.get("tba", obj.get("tba_address")),
            "registered_device_id": obj.get("registered_device_id")
            or obj.get("device_id"),
        }
    return None


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


def mint_sealed_sim_live_poep_summary(
    *,
    device_id: str,
    session_id: str,
    ioid_identity: Optional[dict] = None,
    player_label: str = "P1",
    t_start_ns: int = 1_000_000_000,
    process_nonce: str = "continuum_sim_live_v0",
    n_go: int = 2,
) -> dict[str, Any]:
    """Mint a presence_summary via sealed start_live → challenge_live → summarize_live_session.

    Fire path uses real_hardware=True simulator (same bar as gp-identity live simulator tests).
    Candidate bits are NEVER hand-assigned — only sealed summarize_live_session sets them.

    Returns a package with presence_summary + honesty ceiling metadata.
    """
    from l9_presence.poep_gameplay_live import FireResult, ImuWindow
    from l9_presence.poep_gameplay_session import ChallengeKind
    from l9_presence.poep_session_identity_run import run_session_identity_attach

    dev = (device_id or "").strip().lower().removeprefix("0x")
    sid = (session_id or "").strip().lower()
    if len(dev) != 64 or len(sid) != 64:
        raise ContinuumError("mint_sealed_sim_live_poep_summary needs 32-byte hex device + session_id")

    ioid = ioid_identity or {
        "owner_did": DEFAULT_IOID_CEREMONY["did"],
        "ioid_token_id": DEFAULT_IOID_CEREMONY["token_id"],
        "tba_address": DEFAULT_IOID_CEREMONY["tba"],
        "registration_tx": "0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f",
        "vmdr_pubkey_hash": "0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802",
        "controller_nft": "0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55",
        "controller_nft_token_id": 1,
    }

    def _sim_live_fire(amplitude: int, nonce: str) -> FireResult:
        return FireResult(
            fired=True,
            real_hardware=True,
            t_fire_ns=1_000 + int(amplitude),
            amplitude=amplitude,
        )

    def _imu(t_fire_ns: int) -> ImuWindow:
        return ImuWindow(
            t_response_ns=int(t_fire_ns) + 250_000_000,
            latency_ms=250.0,
            peak_lsb=3000.0,
            precursor_gap_ms=5.0,
        )

    plan = [(ChallengeKind.GO, f"continuum_nonce_{i}") for i in range(max(2, int(n_go)))]
    artifact = run_session_identity_attach(
        device_id=dev,
        player_label=player_label,
        t_start_ns=int(t_start_ns),
        process_nonce=process_nonce,
        challenge_plan=plan,
        fire_fn=_sim_live_fire,
        imu_capture_fn=_imu,
        activity_fetcher=lambda: {"gameplay_context": "ACTIVE_GAMEPLAY"},
        pcc_sampler=lambda: {
            "capture_state": "NOMINAL",
            "host_state": "EXCLUSIVE_USB",
        },
        ioid_identity=ioid,
        session_id=sid,
        include_custody_seal=True,
    )
    ps = artifact.get("presence_summary") or {}
    if not ps.get("presence_session_candidate_ok"):
        raise ContinuumError(
            "sealed sim-live path did not mint presence_session_candidate_ok "
            f"(got dry={ps.get('dry_plumbing_ok')} live={ps.get('effective_live')})"
        )
    return {
        "schema": "qortroller-poep-live-summary-package-v0",
        "candidate": True,
        "mechanism": "sealed_summarize_live_session+sim_real_hardware_fire",
        "claim_ceiling": SIM_LIVE_POEP_CEILING,
        "presence_summary": ps,
        "identity_attach": {
            "schema": artifact.get("schema"),
            "controller_presence_verdict": (artifact.get("controller_presence") or {}).get(
                "verdict"
            ),
            "identity": artifact.get("identity"),
        },
        "advances_poep_enabled": False,
        "advances_presence_session_candidate": False,
        "advisory": True,
    }


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
    auto_nov2_bind: bool = False,
) -> dict[str, Any]:
    """Build continuum postcard from an L0 archive + optional surface JSON paths/dicts."""
    rwm = load_rwm_surface(archive_dir, require_verified=require_l0_verified)

    display = session_display
    if not display and label is not None and stamp is not None:
        display = _infer_session_display(label, stamp)

    def _as_dict(src: dict | Path | str | None) -> Optional[dict]:
        if src is None:
            return None
        if isinstance(src, dict):
            return src
        return _load_json(src)

    ioid_d = normalize_ioid_surface(_as_dict(ioid))
    poep_d = normalize_poep_surface(_as_dict(poep_live))

    stack: dict[str, Any] = {}
    bind_d = _as_dict(nov2_bind)
    if bind_d is None and auto_nov2_bind:
        try:
            from vapi_bridge.rwm_session_bind import build_bind

            bind_d = build_bind(archive_dir, bind_kind="none")
        except Exception:  # noqa: BLE001 — optional stack cite
            bind_d = None
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


def _resolve_ioid_for_daemon(
    archive_dir: Path,
    device_id_hex: str,
    *,
    ioid_path: Path | str | None = None,
) -> Optional[dict]:
    """Load ioID surface: explicit path > CONTINUUM_IOID_JSON > archive/ioid.json > default if device matches."""
    import os

    candidates: list[Path] = []
    if ioid_path:
        candidates.append(Path(ioid_path))
    env_p = os.environ.get("CONTINUUM_IOID_JSON", "").strip()
    if env_p:
        candidates.append(Path(env_p))
    candidates.append(Path(archive_dir) / "ioid.json")
    candidates.append(_REPO / "audits" / "ioid_edge_live_ceremony.json")

    for p in candidates:
        if not p.is_file():
            # allow relative to repo
            alt = _REPO / p if not p.is_absolute() else None
            if alt is None or not alt.is_file():
                continue
            p = alt
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ioid = normalize_ioid_surface(raw if isinstance(raw, dict) else None)
        if not ioid:
            continue
        reg = (ioid.get("registered_device_id") or "").lower()
        if reg and reg != device_id_hex.lower():
            continue  # wrong Edge — skip, do not poison continuum
        return ioid

    # default ceremony only when device is the live Edge
    if device_id_hex.lower() == DEFAULT_IOID_CEREMONY["registered_device_id"]:
        return dict(DEFAULT_IOID_CEREMONY)
    return None


def _resolve_poep_for_daemon(
    archive_dir: Path,
    session_id: str,
    *,
    poep_path: Path | str | None = None,
) -> Optional[dict]:
    """Load PoEP surface: explicit > CONTINUUM_POEP_JSON > archive/poep_live_summary.json > audits match."""
    import os

    candidates: list[Path] = []
    if poep_path:
        candidates.append(Path(poep_path))
    env_p = os.environ.get("CONTINUUM_POEP_JSON", "").strip()
    if env_p:
        candidates.append(Path(env_p))
    candidates.append(Path(archive_dir) / "poep_live_summary.json")
    candidates.append(_REPO / "audits" / f"poep_live_summary_{session_id[:16]}.json")
    # broader dogfood name
    candidates.append(_REPO / "audits" / "poep_live_summary_LIVE10_sim.json")

    for p in candidates:
        path = p
        if not path.is_file():
            alt = _REPO / p if not p.is_absolute() else None
            if alt is None or not alt.is_file():
                continue
            path = alt
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        ps = normalize_poep_surface(raw)
        if not ps:
            continue
        # session join: if summary has session_id, must match (else skip — do not poison)
        ps_sid = (ps.get("session_id") or "").lower()
        if ps_sid and ps_sid != session_id.lower():
            continue
        return raw  # keep envelope; normalize later
    return None


def issue_continuum_after_l0(
    archive_dir: Path | str | None,
    *,
    label: str,
    stamp: int | str,
    ioid_path: Path | str | None = None,
    poep_path: Path | str | None = None,
    auto_nov2_bind: bool = True,
    write_audits: bool = True,
) -> Optional[dict[str, Any]]:
    """Fail-open continuum emit for daemon stop. Returns package or None if skipped/failed.

    Prerequisites: archive_dir with rwm_manifest_chain.json that re-verifies.
    Never raises to the caller (callers should still wrap) — returns None on skip/error.
    """
    if archive_dir is None:
        return None
    d = Path(archive_dir)
    if not (d / "rwm_manifest_chain.json").is_file():
        return None
    try:
        rwm = load_rwm_surface(d, require_verified=True)
    except ContinuumError:
        return None

    ioid = _resolve_ioid_for_daemon(d, rwm["device_id_hex"], ioid_path=ioid_path)
    poep = _resolve_poep_for_daemon(d, rwm["session_id"], poep_path=poep_path)

    try:
        cont = build_continuum_from_archive(
            d,
            label=label,
            stamp=stamp,
            ioid=ioid,
            poep_live=poep,
            auto_nov2_bind=auto_nov2_bind,
        )
    except ContinuumError:
        return None

    # sidecar next to L0
    try:
        side = d / "session_continuum.json"
        side.write_text(json.dumps(cont, indent=2), encoding="utf-8")
        cont["continuum_sidecar"] = str(side)
    except OSError:
        pass

    if write_audits:
        try:
            audits = _REPO / "audits"
            audits.mkdir(parents=True, exist_ok=True)
            out = audits / f"rwm_continuum_{label}_{stamp}.json"
            out.write_text(json.dumps(cont, indent=2), encoding="utf-8")
            cont["continuum_audit"] = str(out)
        except OSError:
            pass

    return cont
