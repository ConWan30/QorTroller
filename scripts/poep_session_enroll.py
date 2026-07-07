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
import glob
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


# D-CERT-9 detection≠prevention: the nonce makes accidental cross-subject pooling POST-HOC
# DETECTABLE, not prevented. Prevention (label->device binding) needs a per-unit identity that is
# not reachable at this call site today — DEVICE_ID_CANON_v1 is secure-element-rooted + Arc-2-gated;
# fresh.device_id here is only the model string. This guard closes the SILENT path; it does not bind
# identity. Label->device binding is increment one's completion when Arc 2 lands, NOT a rejected
# alternative (degrading to an unverified HID serial would be a precision-looking-but-unproven bind).
_COLLISION_GUARD_NOTE = (
    "D-CERT-9 collision guard: enrollment_nonce identifies THIS enrollment instance so accidental "
    "cross-subject pooling under one label is POST-HOC DETECTABLE (compare nonces / extended_existing "
    "across a label's records) — it is NOT prevented. No per-unit identity binds the subject here; "
    "DEVICE_ID_CANON_v1 label->device binding (the prevention form) is Arc-2-gated (secure-element-"
    "rooted). extended_existing=True means an operator deliberately extended a pre-existing label "
    "corpus via --extend-existing."
)


def label_corpus_status(corpus_dir: str, player: str) -> tuple[str, int]:
    """D-CERT-9 collision guard: classify whether `player`'s label already has a corpus.

    FAIL CLOSED — 'fresh' is returned ONLY when we can PROVE no session under this label exists
    (every corpus file read cleanly and none matched). Any unreadable/corrupt file that could hide a
    matching session -> 'ambiguous' (treated as existing): an unreadable corpus is indistinguishable
    from an existing one, and the guard's whole value is that the silent path does not exist. A
    confirmed readable match takes precedence over unreadable files (we KNOW it exists).

    Returns ('fresh', 0) | ('existing', n_matched) | ('ambiguous', n_unreadable).
    """
    matched = 0
    unreadable = 0
    for path in sorted(glob.glob(os.path.join(corpus_dir, "*.poep.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            unreadable += 1
            continue
        if isinstance(d, dict) and d.get("player") == player:
            matched += 1
    if matched > 0:
        return "existing", matched
    if unreadable > 0:
        return "ambiguous", unreadable
    return "fresh", 0


def collision_verdict(status: str, extend_existing: bool) -> tuple[bool, bool]:
    """D-CERT-9 decision matrix: (refuse, extended). Refuse iff the label is not fresh AND
    --extend-existing was not passed — the silent path is closed; deliberate extension is allowed
    but recorded. `extended` is True iff a not-fresh label is being deliberately extended."""
    not_fresh = status in ("existing", "ambiguous")
    return (not_fresh and not extend_existing), (extend_existing and not_fresh)


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
    ap.add_argument("--extend-existing", action="store_true",
                    help="deliberately extend an existing label's corpus (D-CERT-9 collision guard). "
                         "Required to enroll under a label that already has sessions; the choice is "
                         "recorded on the verdict + disclosure.")
    a = ap.parse_args()

    # D-CERT-6: single-source the developer N-gate from config (not a hardcoded literal). Explicit
    # CLI --min-n wins and is logged on divergence; the emitted governing_model then embeds the
    # config-sourced value by construction, so any future mismatch is instantly visible on the artifact.
    a.min_n, _min_n_note = resolve_min_n(a.min_n, Config().developer_self_cert_min_reflex_n)
    if _min_n_note:
        print(_min_n_note)

    # D-CERT-9 collision guard: the player LABEL is the sole scope boundary on the developer-self band
    # (Fact A: no per-unit identity is reachable here today). A second subject enrolling under an
    # existing label would SILENTLY pool into one band. Close the silent path: extending an existing
    # (or unreadable -> fail-closed) label corpus REQUIRES --extend-existing, and the choice is recorded.
    _enrollment_nonce = secrets.token_hex(16)
    _label_status, _label_detail = label_corpus_status(a.corpus_dir, a.player)
    _refuse, _extended = collision_verdict(_label_status, a.extend_existing)
    if _refuse:
        _why = (f"{_label_detail} prior session(s)" if _label_status == "existing"
                else f"{_label_detail} unreadable corpus file(s) — cannot prove the label is unused")
        print(f"REFUSED: label '{a.player}' is not fresh ({_label_status}: {_why}). Enrolling under an "
              f"existing label pools into ONE band with no per-unit identity to separate subjects "
              f"(DEVICE_ID_CANON_v1 label->device binding is Arc-2-gated). Re-run with --extend-existing "
              f"to DELIBERATELY extend this label (logged to the record), or use a distinct --player.")
        return 2
    if _extended:
        print(f"[extend-existing] deliberately extending label '{a.player}' "
              f"({_label_status}: {_label_detail}); recorded on the verdict + disclosure.")
    _collision_meta = {
        "enrollment_nonce": _enrollment_nonce,
        "extended_existing": _extended,
        "label_status_at_enroll": _label_status,          # fresh | existing | ambiguous
        "label_corpus_count_at_enroll": _label_detail,    # matched (existing) / unreadable (ambiguous) / 0 (fresh)
    }

    # 1. Build the DEV band from EXISTING sessions (scored-against band excludes the fresh session).
    model = single_subject_reflex_model(a.corpus_dir, a.player, a.min_n)
    if not model.get("calibration_complete"):
        verdict = {"status": "calibration_incomplete", "player": a.player,
                   "n_reactions": model.get("n_reactions", 0), "min_n": a.min_n,
                   "ts_ns": time.time_ns(), "channel": "liveness_only", **_collision_meta}
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
    v.update(_collision_meta)   # D-CERT-9: enrollment-instance nonce + extend-existing audit trail

    # 3.5 D-CERT-8: mint the self-describing evidence base from the governing band. The COMMITMENT
    # (+ non-sensitive fields) rides the outward verdict; the raw (mu, sigma, salt) goes ONLY to the
    # operator-held disclosure record so it can never reach the proof/API. The disclosure also keeps
    # the real enrollment timestamp as its own field (the commitment's ts_ns slot carries a salt).
    _verdict_fields, _disclosure = compute_evidence_base(model, a.player, a.min_n, enrollment_ts_ns=_enroll_ts)
    v.update(_verdict_fields)
    if _disclosure is not None:
        _disclosure.update(_collision_meta)                       # D-CERT-9 audit trail (operator-held)
        _disclosure["_collision_guard_note"] = _COLLISION_GUARD_NOTE   # detection != prevention, stated
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
