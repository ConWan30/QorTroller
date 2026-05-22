"""QorTroller PoEP P2 — calibration: population reflex-band model + per-device physics
signature + the N>=50 L6B readiness gate.

Liveness is POPULATION-level (no per-person identity corpus needed): a live human's
reaction falls inside the empirical population reflex band; a bot/replay/anticipation does
not. The per-device adaptive-trigger force-response signature is the device-auth channel
(a real Edge produces it; an emulator/translator cannot).

L6B HARD RULE enforced here: NO liveness verdict until N>=50 calibration reactions exist.
`liveness_score` returns `calibration_incomplete` until then, and `poep_enabled` stays
False — calibration only. This module just BUILDS and READS the model; activation is P4.

STATUS: design-only. No FROZEN-v1/PoAC/chain/contract. Consumes poep_l9/*.poep.json.
"""
from __future__ import annotations

import glob
import os
from collections import Counter

import numpy as np

from .poep import load_poep_session

_MIN_N = 50              # L6B neuromuscular-reflex calibration hard rule
_FORCE_KEYS = ("peak_r2", "force_response_auc", "grip_micro_adjustment")


def load_enrollment_sessions(corpus_dir: str = "poep_l9"):
    return [load_poep_session(p) for p in sorted(glob.glob(os.path.join(corpus_dir, "*.poep.json")))]


def _in_band_reactions(sessions):
    """(player, device_id, features) for every genuine in-band reaction across sessions."""
    out = []
    for s in sessions:
        for c in s.challenge_records:
            f = c.get("features", {})
            if f.get("reacted") and f.get("in_band") and f.get("reaction_latency_ms") is not None:
                out.append((s.player, s.device_id, f))
    return out


def population_reflex_model(sessions, min_n: int = _MIN_N) -> dict:
    """Empirical population reflex-band (mean ± 2.5σ of in-band latencies) + per-device
    force-response signature. calibration_complete iff >= min_n in-band reactions."""
    rx = _in_band_reactions(sessions)
    model = {"n_reactions": len(rx), "min_n": min_n,
             "calibration_complete": len(rx) >= min_n,
             "per_player": dict(Counter(p for p, _, _ in rx))}
    lats = np.array([f["reaction_latency_ms"] for _, _, f in rx], float)
    if lats.size >= 2:
        mu, sd = float(lats.mean()), float(lats.std())
        model["latency_mean_ms"] = round(mu, 1)
        model["latency_std_ms"] = round(sd, 1)
        model["band_lo_ms"] = round(mu - 2.5 * sd, 1)
        model["band_hi_ms"] = round(mu + 2.5 * sd, 1)
    devs: dict = {}
    for _, dev, f in rx:
        d = devs.setdefault(dev, {k: [] for k in _FORCE_KEYS})
        for k in _FORCE_KEYS:
            d[k].append(float(f.get(k, 0.0)))
    model["device_signatures"] = {
        dev: {k: {"mean": round(float(np.mean(v)), 3), "std": round(float(np.std(v)), 3)}
              for k, v in sig.items()} for dev, sig in devs.items()}
    return model


def poep_readiness(corpus_dir: str = "poep_l9", min_n: int = _MIN_N) -> dict:
    """L6B readiness gate: are there >= min_n in-band reactions to lift the calibration
    hold? Reports per-player counts + exactly how many more are needed."""
    m = population_reflex_model(load_enrollment_sessions(corpus_dir), min_n)
    need = max(0, min_n - m["n_reactions"])
    return {
        "corpus_dir": corpus_dir,
        "total_in_band_reactions": m["n_reactions"],
        "min_n": min_n,
        "per_player": m["per_player"],
        "devices": list(m["device_signatures"].keys()),
        "calibration_complete": m["calibration_complete"],
        "reactions_needed": need,
        "recommendation": ("calibration complete — liveness model usable (activation still "
                           "operator-gated, P4)" if m["calibration_complete"]
                           else f"need {need} more in-band reactions (L6B N>={min_n} hard rule)"),
    }


def liveness_score(features: dict, model: dict, device_id: str = None) -> dict:
    """Score one reaction against the calibrated model. Honors the L6B gate: returns
    calibration_incomplete until the model has N>=min_n reactions. Population latency band
    = liveness; device signature presence = device-auth (force-match is a P3 refinement)."""
    if not model.get("calibration_complete"):
        return {"status": "calibration_incomplete",
                "n_reactions": model.get("n_reactions", 0), "min_n": model.get("min_n", _MIN_N)}
    lat = features.get("reaction_latency_ms")
    if lat is None or "band_lo_ms" not in model:
        return {"liveness_pass": False, "reason": "no_reaction_or_no_band"}
    latency_ok = model["band_lo_ms"] <= lat <= model["band_hi_ms"]
    device_ok = bool(device_id is None or device_id in model.get("device_signatures", {}))
    return {"liveness_pass": bool(latency_ok and device_ok),
            "latency_ok": latency_ok, "device_registered": device_ok,
            "latency_ms": lat, "band": [model["band_lo_ms"], model["band_hi_ms"]]}


def device_auth_score(features: dict, model: dict, device_id: str) -> dict:
    """Device-auth via the adaptive-trigger force-response signature. A real Edge produces
    a non-trivial force-response (peak_r2 / force-AUC / grip) consistent with the registered
    signature; an emulator/translator (Cronus/XIM) can't render the adaptive-trigger physics,
    so its flat/zero response falls far outside the registered mean -> fails. P3 strengthens
    P2's 'registered' check into a physics-consistency check."""
    sig = model.get("device_signatures", {}).get(device_id)
    if not sig:
        return {"device_auth_pass": False, "reason": "device_not_registered", "score": 0.0}
    checks, ok = {}, 0
    for k in _FORCE_KEYS:
        s = sig[k]
        v = float(features.get(k, 0.0))
        within = abs(v - s["mean"]) <= (3.0 * s["std"] + 1e-6)   # zero/flat emulator -> far below mean -> fails
        checks[k] = bool(within)
        ok += int(within)
    score = ok / len(_FORCE_KEYS)
    return {"device_auth_pass": bool(score >= 0.5), "score": round(score, 3), "checks": checks}


def poep_verify(features: dict, model: dict, device_id: str = None) -> dict:
    """Full PoEP verdict = liveness (population reflex band) AND device-auth (force-response
    physics). Honors the L6B gate (calibration_incomplete until N>=50). PRESENT only if both
    pass; the nonce (capture-time) is the third, anti-replay layer."""
    live = liveness_score(features, model, device_id)
    if live.get("status") == "calibration_incomplete":
        return live
    dev = device_auth_score(features, model, device_id) if device_id else {"device_auth_pass": True, "score": 1.0}
    present = bool(live.get("liveness_pass") and dev.get("device_auth_pass"))
    return {
        "verdict": "PRESENT" if present else "REJECT",
        "liveness_pass": bool(live.get("liveness_pass")),
        "device_auth_pass": bool(dev.get("device_auth_pass")),
        "device_auth_score": dev.get("score"),
        "latency_ms": features.get("reaction_latency_ms"),
        "band": live.get("band"),
    }


def _cli() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="L9 PoEP P2 — calibration readiness + model")
    ap.add_argument("--corpus-dir", default="poep_l9")
    ap.add_argument("--min-n", type=int, default=_MIN_N)
    ap.add_argument("--model", action="store_true", help="print the full population model")
    a = ap.parse_args()
    if a.model:
        out = population_reflex_model(load_enrollment_sessions(a.corpus_dir), a.min_n)
    else:
        out = poep_readiness(a.corpus_dir, a.min_n)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
