"""QorTroller L9 — Gameplay Witness Agent (Phase 1, autonomous background capture).

The capture-time role in the operator fleet (alongside Sentry/Guardian/Curator). While
a gamer plays Remote Play, the Witness autonomously runs the session lifecycle:
  detect play -> capture -> analyze (L9 coupling + render-loop biometric) -> store ->
  emit a PoCP commitment + a gamer-facing HTML verification card.

Hand-offs to the signing fleet and ZKBA are STUBBED to dry-run and default-OFF — they
log what they WOULD do. Live anchoring/signing/ZKBA are deferred behind explicit
operator opt-in (and gate-2 biometric separability) per the project's deferred-
activation discipline. This file touches no FROZEN-v1 primitive, no PoAC, no chain.

CLI:
  python -m l9_presence.witness_agent process <session.npz> --player P1
  python -m l9_presence.witness_agent run --player P1 [--once]
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

import numpy as np

from . import pocp
from .biometric_features import _SEP_FEATURES, extract_feature_vector
from .session_recorder import (
    SessionData, analyze_session_data, load_session, make_stick_parser, record_session,
)
from .verification_card import render_card

# governed seams: (config flag attr, what it WOULD do once enabled)
_HANDOFFS = {
    "sentry": "anchor the PoCP commitment on AdjudicationRegistry (pda-attestation-anchor)",
    "guardian": "HSM-sign an audit entry attesting the L9 method/result (audit-drafting)",
    "curator": "grade/govern the session as a marketable verified-presence data asset",
    "zkba": "compile a ZKBA proof from the PoCP inputs via the governed ceremony",
}


@dataclass
class WitnessConfig:
    player: str = "P1"
    label: str = "human"
    duration_s: float = 60.0
    region: Optional[Tuple[int, int, int, int]] = (640, 360, 1280, 720)
    rx: int = 3
    ry: int = 4
    fire_offset: int = 6
    backend: str = "mss"
    out_dir: str = "sessions_l9"
    poll_idle_s: float = 10.0
    coupling_floor: float = 0.2
    # governed seams — ALL default OFF (dry-run). Flip only after gate-2 + governance.
    sentry_anchor_enabled: bool = False
    guardian_sign_enabled: bool = False
    curator_govern_enabled: bool = False
    zkba_enabled: bool = False
    # BCC sealed-lane harvest — default OFF (dormant). Sub-lane A only accumulates PRESENT
    # (causally-verified) reliable sessions; writes only to bcc_out_dir; touches no proven number.
    bcc_enabled: bool = False
    bcc_sublane_b_enabled: bool = False
    bcc_out_dir: str = "bcc_l9"


def _verdict(analysis: dict) -> str:
    if analysis.get("status") == "insufficient_aim_activity":
        return "INSUFFICIENT_AIM"
    if analysis.get("coupled"):
        return "PRESENT"
    # had activity but coupling below threshold — could be decoupled or just a quiet window
    nc = analysis.get("negative_control") or 0.0
    cs = analysis.get("coupling_score") or 0.0
    return "DECOUPLED" if cs <= nc + 0.02 else "REVIEW_LOW_COUPLING"


def _should_harvest_l9(verdict: str, reliable: bool) -> bool:
    """The synergistic BCC quality gate: accumulate a capture into the sealed lane ONLY when
    the Witness already certified it PRESENT (input causally drove the render, coupling beat
    the time-shuffle negative control) AND the biometric vector is reliable. So the corpus is
    'provably causally-present captures', self-cleaned by the validated L9 result — not a raw
    session dump. AFK / replay / decoupled / video-only sessions never enter."""
    return verdict == "PRESENT" and bool(reliable)


def _maybe_harvest_bcc(cfg: "WitnessConfig", manifest: dict, bvec: Optional[dict]) -> dict:
    """Hand a PRESENT+reliable session's _SEP_FEATURES to the sealed BCC lane. Isolated
    (writes only bcc_out_dir), guarded (never breaks the Witness), dormant unless bcc_enabled."""
    if not cfg.bcc_enabled:
        return {"harvested": False, "reason": "bcc_disabled"}
    reliable = bool(bvec and bvec.get("reliable"))
    if not _should_harvest_l9(manifest["verdict"], reliable):
        return {"harvested": False, "reason": f"gate:verdict={manifest['verdict']},reliable={reliable}"}
    try:
        from .bcc import BCCConfig, BCCHarvester
        h = BCCHarvester(BCCConfig(enabled=True, sublane_b_enabled=cfg.bcc_sublane_b_enabled,
                                   out_dir=cfg.bcc_out_dir))
        fvec = [bvec[k] for k in _SEP_FEATURES]
        rec = h.record_l9(fvec, nominal=True, extra={
            "session_id": manifest["session_id"], "verdict": manifest["verdict"],
            "pocp_commitment": manifest["pocp_commitment"]})
        return {"harvested": True, "sub_lane": "A", "bcc_seq": rec["seq"],
                "bcc_hash": rec["bcc_hash"][:16] + "…"}
    except Exception as exc:                       # never let harvesting break the witness
        return {"harvested": False, "reason": f"error:{exc}"}


def _handoff(name: str, enabled: bool, payload: dict) -> dict:
    """Stubbed operator-fleet / ZKBA hand-off. Dry-run unless explicitly enabled."""
    return {
        "target": name,
        "enabled": bool(enabled),
        "action": "live_pending_governance" if enabled else "dry_run",
        "would": _HANDOFFS[name],
        "payload_keys": sorted(payload.keys()),
    }


def process_session(path: str, cfg: Optional[WitnessConfig] = None) -> dict:
    """Analyze one recorded session -> PoCP commitment + HTML card + manifest.
    The hardware-free core; safe to unit-test on any .npz. Writes the card and a
    .manifest.json next to the session and returns the manifest dict."""
    cfg = cfg or WitnessConfig()
    s = load_session(path)
    analysis = analyze_session_data(s)
    bvec = extract_feature_vector(s, cfg.coupling_floor)
    ts_ns = time.time_ns()
    ts_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session_id = os.path.basename(path)
    player = s.player or cfg.player

    coupling = float(analysis.get("coupling_score") or 0.0)
    lag_ms = float(analysis.get("lag_ms") or 0.0)
    nc = float(analysis.get("negative_control") or 0.0)
    decoupled = float(analysis.get("decoupled_energy") or 0.0)
    n_samples = int(np.asarray(s.in_ts).size)
    verdict = _verdict(analysis)

    commitment = pocp.compute_pocp_commitment(
        player=player, session_id=session_id, coupling=coupling, lag_ms=lag_ms,
        negative_control=nc, decoupled_energy=decoupled, n_samples=n_samples, ts_ns=ts_ns)

    html = render_card(
        player=player, session_id=session_id, label=s.label, verdict=verdict,
        coupling=coupling, lag_ms=lag_ms, negative_control=nc,
        neg_margin=coupling - nc, decoupled_energy=decoupled, n_samples=n_samples,
        commitment=commitment, ts_iso=ts_iso)
    base = path[:-4] if path.endswith(".npz") else path
    card_path = base + ".verification.html"
    with open(card_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    handoff_payload = {"commitment": commitment, "player": player, "verdict": verdict}
    manifest = {
        "session_id": session_id,
        "player": player,
        "label": s.label,
        "verdict": verdict,
        "ts_ns": ts_ns,
        "ts_iso": ts_iso,
        "coupling_score": coupling,
        "lag_ms": lag_ms,
        "negative_control": nc,
        "decoupled_energy": decoupled,
        "biometric_reliable": bool(bvec["reliable"]) if bvec else False,
        "biometric_vector": bvec,
        "pocp_commitment": commitment,
        "verification_card": card_path,
        "handoffs": {
            "sentry": _handoff("sentry", cfg.sentry_anchor_enabled, handoff_payload),
            "guardian": _handoff("guardian", cfg.guardian_sign_enabled, handoff_payload),
            "curator": _handoff("curator", cfg.curator_govern_enabled, handoff_payload),
            "zkba": _handoff("zkba", cfg.zkba_enabled, handoff_payload),
        },
    }
    manifest["bcc"] = _maybe_harvest_bcc(cfg, manifest, bvec)
    with open(base + ".manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    return manifest


class WitnessAgent:
    """Autonomous capture-time agent. run() loops: when it detects play (non-black
    Remote Play capture + readable HID), it records a session and processes it."""

    def __init__(self, cfg: Optional[WitnessConfig] = None) -> None:
        self.cfg = cfg or WitnessConfig()
        os.makedirs(self.cfg.out_dir, exist_ok=True)

    def is_playing(self) -> bool:
        """True iff Remote Play captures a non-black frame AND HID reads."""
        try:
            from .screen_capture import ScreenCapturer, is_black_frame
            cap = ScreenCapturer(region=self.cfg.region, backend=self.cfg.backend)
            frame = None
            for _ in range(10):
                frame = cap.grab()
                if frame is not None:
                    break
                time.sleep(0.02)
            cap.close()
            if frame is None or is_black_frame(frame):
                return False
        except Exception:
            return False
        try:
            import hid
            d = hid.device(); d.open(0x054C, 0x0DF2); d.set_nonblocking(True)
            got = b""
            for _ in range(50):
                r = d.read(64)
                if r:
                    got = bytes(r); break
                time.sleep(0.005)
            d.close()
            return bool(got)
        except Exception:
            return False

    def _next_path(self) -> str:
        import glob
        n = len(glob.glob(os.path.join(self.cfg.out_dir, f"{self.cfg.player}_*.npz"))) + 1
        return os.path.join(self.cfg.out_dir, f"{self.cfg.player}_{n:02d}.npz")

    def run_once(self) -> dict:
        """Capture one live session and process it (hardware required)."""
        out = self._next_path()
        record_session(out, duration_s=self.cfg.duration_s, label=self.cfg.label,
                       region=self.cfg.region, stick_parser=make_stick_parser(self.cfg.rx, self.cfg.ry),
                       backend=self.cfg.backend, fire_offset=self.cfg.fire_offset, player=self.cfg.player)
        return process_session(out, self.cfg)

    def run(self, max_sessions: int = 0) -> None:
        """Background loop: record+process whenever play is detected. max_sessions=0
        runs until interrupted."""
        made = 0
        print(f"[witness] watching for {self.cfg.player} play "
              f"(seams: sentry/guardian/curator/zkba all dry-run)")
        while True:
            if self.is_playing():
                m = self.run_once()
                made += 1
                print(f"[witness] {m['session_id']}: {m['verdict']} "
                      f"coupling={m['coupling_score']:.3f} -> {m['verification_card']}")
                if max_sessions and made >= max_sessions:
                    return
            else:
                time.sleep(self.cfg.poll_idle_s)


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="L9 Gameplay Witness Agent (Phase 1)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("process", help="process one recorded session -> card + commitment")
    pp.add_argument("path")
    pp.add_argument("--player", default="P1")

    pr = sub.add_parser("run", help="autonomous capture loop (hardware)")
    pr.add_argument("--player", default="P1")
    pr.add_argument("--duration", type=float, default=60.0)
    pr.add_argument("--region", nargs=4, type=int, metavar=("L", "T", "R", "B"),
                    default=[640, 360, 1280, 720])
    pr.add_argument("--once", action="store_true", help="capture a single session and exit")

    a = ap.parse_args()
    if a.cmd == "process":
        m = process_session(a.path, WitnessConfig(player=a.player))
        print(json.dumps({k: v for k, v in m.items() if k != "biometric_vector"},
                         indent=2, default=str))
        return 0
    if a.cmd == "run":
        cfg = WitnessConfig(player=a.player, duration_s=a.duration, region=tuple(a.region))
        agent = WitnessAgent(cfg)
        if a.once:
            print(json.dumps({k: v for k, v in agent.run_once().items()
                              if k != "biometric_vector"}, indent=2, default=str))
        else:
            agent.run()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
