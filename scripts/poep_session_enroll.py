"""PoEP session-start enrollment (developer-self cert, Stage 2).

Run this BEFORE starting the bridge for a developer-self-cert play session. It:
  1. builds your DEV single-subject reflex band from poep_l9/DEV_*.poep.json (the campaign output);
  2. runs a SHORT liveness enrollment (react to the buzzes, controller still; force_trials=0 -> the
     device-auth channel is deferred per the DEV_01/02 slope=0 finding -- LIVENESS-ONLY v0);
  3. scores the fresh session against the band (developer_self_liveness_verdict);
  4. writes the session verdict to ~/.vapi/poep_session_verdict.json, which the bridge reads at startup
     (when developer_self_cert_enabled + poep_liveness_enabled) -> meta["poep_present"] goes live for the
     session via poep_activation.poep_present_signal.

PoEP is enrollment-mode/SESSION-level: this verdict is established still at session start and stays live
through the match (gameplay confounds mid-game reflex measurement). Stop the bridge first (pydualsense
contention). LIVENESS-ONLY: cert_scope stays developer_self; population_certified never True.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time

# repo root on sys.path so `l9_presence` imports regardless of invocation cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.poep import PoEPConfig, PoEPRecorder, load_poep_session
from l9_presence.poep_calibration import (
    developer_self_liveness_verdict,
    single_subject_reflex_model,
)
# D-CERT-8: mint the reflex-band commitment via the shared BIOMETRIC-SNAPSHOT-v1 adapter
# (repo root is on sys.path above, so the bridge package resolves).
from bridge.vapi_bridge.reflex_band_commitment import reflex_band_commitment
# D-CERT-6: single-source the developer N-gate. config.developer_self_cert_min_reflex_n
# (env DEVELOPER_SELF_CERT_MIN_REFLEX_N) is THE source; enroll reads it so it cannot drift from
# the bridge's canonical value.
from bridge.vapi_bridge.config import Config

DEFAULT_VERDICT_PATH = os.path.expanduser("~/.vapi/poep_session_verdict.json")
# D-CERT-8: operator-held raw-band disclosure (mu, sigma, salt) — the audit basis for the commitment
# emitted in the verdict. NEVER emitted to proof/API/JSONL; lives in ~/.vapi like the CA material.
DEFAULT_DISCLOSURE_PATH = os.path.expanduser("~/.vapi/poep_band_disclosure.json")


def _write_verdict(path: str, verdict: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(verdict, fh, indent=2)


def _write_disclosure(path: str, record: dict) -> None:
    """Write the operator-held raw-band disclosure record. Contains raw (mu, sigma, salt) — the
    audit basis that recomputes the commitment. NEVER emitted outward (proof/API/JSONL)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)


def compute_evidence_base(
    model: dict, player: str, min_n: int, enrollment_ts_ns: int | None = None,
) -> tuple[dict, dict | None]:
    """D-CERT-8: derive the self-describing evidence base from the governing reflex band.

    Returns ``(verdict_fields, disclosure)`` where:
      * ``verdict_fields`` (goes into the outward verdict + onto the proof) carries the raw non-sensitive
        fields plus ``calibration_band_commitment`` — a COMMITMENT, never raw band values.
      * ``disclosure`` (operator-held only, or ``None`` on a degenerate band) carries the raw
        ``(latency_mean_ms, latency_std_ms, salt)`` that recompute the commitment on audit.

    The commitment reuses the FROZEN BIOMETRIC-SNAPSHOT-v1 family as an F=1/N=1 centroid+variance
    fingerprint of the reflex band (mu +/- 2.5 sigma), hidden by a per-enrollment 64-bit salt.
    """
    governing_model = f"developer_self:single_subject_reflex_v1:min_n={min_n}"
    calibration_n = int(model.get("n_reactions", 0))
    verdict_fields: dict = {
        "governing_model": governing_model,
        "calibration_n": calibration_n,
        "calibration_player_scope": player,
        "calibration_band_commitment": None,      # null-safe: stays None on a degenerate band
    }
    mu = model.get("latency_mean_ms")
    sd = model.get("latency_std_ms")
    if not (isinstance(mu, (int, float)) and isinstance(sd, (int, float)) and sd > 0):
        return verdict_fields, None               # degenerate/absent band -> abstain (commitment None)
    salt = secrets.randbits(64)
    commitment = reflex_band_commitment(mu, sd, salt)
    verdict_fields["calibration_band_commitment"] = commitment
    disclosure = {
        "governing_model": governing_model,
        "calibration_n": calibration_n,
        "calibration_player_scope": player,
        "latency_mean_ms": float(mu),
        "latency_std_ms": float(sd),
        "band_lo_ms": model.get("band_lo_ms"),
        "band_hi_ms": model.get("band_hi_ms"),
        # `salt` is the per-enrollment hiding secret that the commitment carries IN the family's
        # ts_ns uint64 slot (that slot is opaque bytes to the hash — it is NOT a timestamp here).
        # `enrollment_ts_ns` is the real wall-clock enrollment time, kept as its own field so nothing
        # is lost. Named honestly so a future auditor needs zero docstring archaeology.
        "salt": salt,
        "enrollment_ts_ns": enrollment_ts_ns,
        "calibration_band_commitment": commitment,
        "_commitment_scheme": (
            "BIOMETRIC-SNAPSHOT-v1 over (latency_mean_ms as F=1 centroid, 1/latency_std_ms**2 as "
            "1x1 cov_inv, salt in the ts_ns slot). Recompute: verify_reflex_band_commitment("
            "latency_mean_ms, latency_std_ms, salt, calibration_band_commitment)."
        ),
    }
    return verdict_fields, disclosure


def resolve_min_n(cli_min_n: int | None, config_min_n: int) -> tuple[int, str | None]:
    """D-CERT-6 single-source: config.developer_self_cert_min_reflex_n is THE source for the
    developer N-gate. An explicit CLI --min-n still wins (operator intent) but is flagged when it
    diverges, so a one-off override can never silently become an uncoordinated fourth literal.
    Returns (resolved_min_n, divergence_note_or_None)."""
    if cli_min_n is None:
        return config_min_n, None
    if cli_min_n != config_min_n:
        return cli_min_n, (f"[min-n] CLI --min-n={cli_min_n} OVERRIDES config "
                           f"developer_self_cert_min_reflex_n={config_min_n} (explicit intent honored).")
    return cli_min_n, None


def main() -> int:
    ap = argparse.ArgumentParser(description="PoEP session-start enrollment (developer-self cert)")
    ap.add_argument("--player", default="DEV", help="developer profile (single-subject band)")
    ap.add_argument("--challenges", type=int, default=10, help="reflex challenges this session")
    ap.add_argument("--corpus-dir", default="poep_l9")
    ap.add_argument("--min-n", type=int, default=None,
                    help="developer-scoped data gate (default: config.developer_self_cert_min_reflex_n; "
                         "an explicit value overrides config and is logged)")
    ap.add_argument("--min-in-band-fraction", type=float, default=0.5)
    ap.add_argument("--out", default=DEFAULT_VERDICT_PATH)
    ap.add_argument("--disclosure-out", default=DEFAULT_DISCLOSURE_PATH,
                    help="operator-held raw-band disclosure record (audit basis; never emitted outward)")
    a = ap.parse_args()

    # D-CERT-6: single-source the developer N-gate from config (not a hardcoded literal). Explicit
    # CLI --min-n wins and is logged on divergence; the emitted governing_model then embeds the
    # config-sourced value by construction, so any future mismatch is instantly visible on the artifact.
    a.min_n, _min_n_note = resolve_min_n(a.min_n, Config().developer_self_cert_min_reflex_n)
    if _min_n_note:
        print(_min_n_note)

    # 1. Build the DEV band from EXISTING sessions (scored-against band excludes the fresh session).
    model = single_subject_reflex_model(a.corpus_dir, a.player, a.min_n)
    if not model.get("calibration_complete"):
        verdict = {"status": "calibration_incomplete", "player": a.player,
                   "n_reactions": model.get("n_reactions", 0), "min_n": a.min_n,
                   "ts_ns": time.time_ns(), "channel": "liveness_only"}
        _write_verdict(a.out, verdict)
        print(f"DEV band NOT calibrated (N={verdict['n_reactions']} < {a.min_n}). "
              f"Run the campaign (l9_presence.poep enroll --player {a.player}) first. "
              f"Wrote abstain verdict -> {a.out}")
        return 1

    print(f"DEV band ready: mean={model.get('latency_mean_ms')}ms "
          f"band=[{model.get('band_lo_ms')}, {model.get('band_hi_ms')}]ms. "
          f"Hold the controller STILL and react to each buzz.\n")

    # 2. Short liveness enrollment (force_trials=0 -> liveness-only).
    cfg = PoEPConfig(player=a.player, challenges=a.challenges, force_trials=0, out_dir=a.corpus_dir)
    summary = PoEPRecorder(cfg).enroll()

    # 3. Score the fresh session against the (pre-existing) band.
    fresh = load_poep_session(summary["path"])
    reactions = [c.get("features", {}) for c in fresh.challenge_records]
    v = developer_self_liveness_verdict(reactions, model, min_in_band_fraction=a.min_in_band_fraction)
    _enroll_ts = time.time_ns()
    v.update({"player": a.player, "device_id": fresh.device_id, "ts_ns": _enroll_ts,
              "session_path": summary["path"], "cert_scope": "developer_self"})

    # 3.5 D-CERT-8: mint the self-describing evidence base from the governing band. The COMMITMENT
    # (+ non-sensitive fields) rides the outward verdict; the raw (mu, sigma, salt) goes ONLY to the
    # operator-held disclosure record so it can never reach the proof/API. The disclosure also keeps
    # the real enrollment timestamp as its own field (the commitment's ts_ns slot carries a salt).
    _verdict_fields, _disclosure = compute_evidence_base(model, a.player, a.min_n, enrollment_ts_ns=_enroll_ts)
    v.update(_verdict_fields)
    if _disclosure is not None:
        _write_disclosure(a.disclosure_out, _disclosure)

    # 4. Write the session verdict for the bridge to read at startup.
    _write_verdict(a.out, v)
    print(f"\nsession verdict: {v.get('verdict', v.get('status'))} "
          f"(in_band_fraction={v.get('in_band_fraction')}, n_reacted={v.get('n_reacted')}) "
          f"-> {a.out}")
    print(f"evidence base: model={_verdict_fields['governing_model']} n={_verdict_fields['calibration_n']} "
          f"band_commitment={'set' if _verdict_fields['calibration_band_commitment'] else 'NONE'} "
          f"(raw band held -> {a.disclosure_out})")
    print("Start the bridge with DEVELOPER_SELF_CERT_ENABLED=true + POEP_LIVENESS_ENABLED=true to go live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
