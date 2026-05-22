"""QorTroller PoEP P1 — enrollment-mode capture + features + born-PQ commitment.

The de-risk passed for the ENROLLMENT form (BUZZ detect 1.0 / ~309 ms, SHAM 0.0 — genuine
buzz-driven reflex; in-game is confounded by gameplay, proven). P1 builds the real capture:
a nonce-scheduled sub-perceptual challenge sequence, a post-stimulus reflex-window capture,
the discriminative features (reaction latency, force-response curve, grip micro-adjustment),
a stored session, and a born-PQ commitment (SHA-256 — PQ-safe per Mythos crypto audit).

ENROLLMENT mode only — the gamer is NOT mid-match (gameplay confounds; proven SHAM=1.0
in-game). L6B reflex hard rule: P1 is capture + calibration corpus only; **no liveness
verdict until N≥50** (poep_enabled=False). The hybrid ECDSA + ML-DSA-65 credential signing
is deferred to P3/governed (POEP_SCOPE.md) — IoTeX's PQ precompile/registry not shipped yet.

STATUS: design-only candidate. No FROZEN-v1 primitive, no PoAC, no chain, no contract.
QORTROLLER-POEP-v0 is a v0 CANDIDATE tag (not registered, not anchored).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .poep_derisk import _fire, _stop, _test_write, in_human_band

_DOMAIN = b"QORTROLLER-POEP-v0"
_trapz = getattr(np, "trapezoid", getattr(np, "trapz"))  # np.trapz deprecated -> trapezoid
_STICK_DELTA = 40
_TRIG_PRESS = 64
_FEATURE_KEYS = ("reaction_latency_ms", "peak_stick_deflection", "peak_r2",
                 "grip_micro_adjustment", "force_response_auc")


def nonce_schedule(n: int, min_gap: float = 1.0, max_gap: float = 3.0, seed=None):
    """n (nonce, delay_s) challenges. seed=None → cryptographic nonces (secrets) for
    production unforgeability; a seed gives deterministic nonces for tests only."""
    import random
    import secrets
    rng = random.Random(seed) if seed is not None else None
    out = []
    for _ in range(n):
        nonce = (f"{rng.getrandbits(128):032x}" if rng is not None else secrets.token_hex(16))
        gap = (rng.uniform(min_gap, max_gap) if rng is not None
               else secrets.SystemRandom().uniform(min_gap, max_gap))
        out.append((nonce, gap))
    return out


def extract_reflex_features(window: list, stim_t_ms: float, baseline: dict) -> dict:
    """Discriminative features from one post-stimulus reflex window. window = list of
    {t_ms, RX, RY, R2, L2, accel_mag}. Beyond raw latency: peak motor response, the R2
    force-response trajectory (device-auth/biomechanical channel), and the involuntary
    grip micro-adjustment (IMU)."""
    if not window:
        return {k: 0.0 for k in _FEATURE_KEYS} | {"reacted": False, "in_band": False,
                                                  "reaction_latency_ms": None}
    onset = None
    peak_stick, peak_r2 = 0.0, 0.0
    for s in window:
        dstick = max(abs(s["RX"] - baseline["RX"]), abs(s["RY"] - baseline["RY"]))
        peak_stick = max(peak_stick, dstick)
        peak_r2 = max(peak_r2, s["R2"])
        if onset is None and (dstick > _STICK_DELTA or s["R2"] > _TRIG_PRESS):
            onset = s["t_ms"]
    lat = (onset - stim_t_ms) if onset is not None else None
    accels = [s.get("accel_mag", 0.0) for s in window]
    grip = float(np.std(accels)) if len(accels) > 1 else 0.0
    auc = (float(_trapz([s["R2"] for s in window], [s["t_ms"] for s in window]))
           if len(window) > 1 else 0.0)
    return {
        "reaction_latency_ms": lat,
        "reacted": onset is not None,
        "in_band": in_human_band(lat) if lat is not None else False,
        "peak_stick_deflection": float(peak_stick),
        "peak_r2": float(peak_r2),
        "grip_micro_adjustment": grip,
        "force_response_auc": auc,
    }


def compute_poep_commitment(*, player: str, device_id: str, challenge_records: list,
                            ts_ns: int) -> str:
    """Born-PQ PoEP commitment: SHA-256 over device + per-challenge (nonce + quantized
    features). Hash-based → quantum-safe (Grover only). v0 candidate; not anchored."""
    h = hashlib.sha256()
    h.update(_DOMAIN)
    h.update(hashlib.sha256(player.encode()).digest())
    h.update(hashlib.sha256(device_id.encode()).digest())
    for c in challenge_records:
        h.update(bytes.fromhex(c["nonce"]))
        feats = c.get("features", {})
        for k in _FEATURE_KEYS:
            v = feats.get(k) or 0.0
            h.update(int(round(float(v) * 1000)).to_bytes(8, "big", signed=True))
    h.update(int(ts_ns).to_bytes(8, "big", signed=False))
    return h.hexdigest()


@dataclass
class PoEPSession:
    player: str
    device_id: str
    challenge_records: list   # [{nonce, stim_t_ms, features}]
    commitment: str
    ts_ns: int
    poep_enabled: bool = False   # L6B hard rule: no liveness verdict until N>=50


def save_poep_session(path: str, s: PoEPSession) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"player": s.player, "device_id": s.device_id,
                   "challenge_records": s.challenge_records, "commitment": s.commitment,
                   "ts_ns": s.ts_ns, "poep_enabled": s.poep_enabled}, fh, indent=2)
    return path


def load_poep_session(path: str) -> PoEPSession:
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return PoEPSession(d["player"], d["device_id"], d["challenge_records"],
                       d["commitment"], int(d["ts_ns"]), bool(d.get("poep_enabled", False)))


def _snapshot(ds) -> dict:
    s = ds.state
    acc = getattr(s, "accelerometer", None)
    if acc is not None:
        ax, ay, az = getattr(acc, "X", 0), getattr(acc, "Y", 0), getattr(acc, "Z", 0)
        accel_mag = float((ax * ax + ay * ay + az * az) ** 0.5)
    else:
        accel_mag = 0.0
    return {"RX": getattr(s, "RX", 128), "RY": getattr(s, "RY", 128),
            "R2": getattr(s, "R2_value", getattr(s, "R2", 0)),   # analog 0-255 (R2 is digital bool)
            "L2": getattr(s, "L2_value", getattr(s, "L2", 0)), "accel_mag": accel_mag}


@dataclass
class PoEPConfig:
    player: str = "P1"
    device_id: str = "Sony_DualShock_Edge_CFI-ZCP1"
    challenges: int = 20
    window_ms: float = 600.0
    out_dir: str = "poep_l9"


class PoEPRecorder:
    """Enrollment-mode capture: nonce-scheduled challenges, each followed by a reflex-
    window capture + feature extraction. Hardware (pydualsense). NOT activated (L6B N≥50)."""

    def __init__(self, cfg: Optional[PoEPConfig] = None) -> None:
        self.cfg = cfg or PoEPConfig()
        os.makedirs(self.cfg.out_dir, exist_ok=True)

    def enroll(self) -> dict:
        from pydualsense import pydualsense
        ds = pydualsense(); ds.init()
        _test_write(ds)
        records = []
        try:
            for nonce, gap in nonce_schedule(self.cfg.challenges):
                time.sleep(gap)
                base = _snapshot(ds)
                _fire(ds)
                t0 = time.time()
                window = []
                while (time.time() - t0) * 1000.0 < self.cfg.window_ms:
                    s = _snapshot(ds); s["t_ms"] = (time.time() - t0) * 1000.0
                    window.append(s)
                    time.sleep(0.001)
                _stop(ds)
                feats = extract_reflex_features(window, 0.0, base)
                records.append({"nonce": nonce, "stim_t_ms": 0.0, "features": feats})
                lat = feats["reaction_latency_ms"]
                print(f"  challenge {len(records)}/{self.cfg.challenges}: "
                      f"{f'{lat:.0f} ms' if lat is not None else 'no reaction'}"
                      f"{' (in band)' if feats['in_band'] else ''}")
                time.sleep(0.3)
        finally:
            _stop(ds)
            try:
                ds.close()
            except Exception:
                pass
        ts_ns = time.time_ns()
        commitment = compute_poep_commitment(player=self.cfg.player, device_id=self.cfg.device_id,
                                             challenge_records=records, ts_ns=ts_ns)
        sess = PoEPSession(self.cfg.player, self.cfg.device_id, records, commitment, ts_ns)
        n = len([f for f in os.listdir(self.cfg.out_dir) if f.startswith(self.cfg.player)]) + 1
        out = os.path.join(self.cfg.out_dir, f"{self.cfg.player}_{n:02d}.poep.json")
        save_poep_session(out, sess)
        in_band = sum(1 for r in records if r["features"]["in_band"])
        return {"path": out, "player": self.cfg.player, "challenges": len(records),
                "in_band": in_band, "commitment": commitment[:16] + "…", "poep_enabled": False}


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="L9 PoEP P1 — enrollment capture (NOT mid-game)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("enroll", help="record one enrollment PoEP session (controller still, react to buzzes)")
    pe.add_argument("--player", required=True)
    pe.add_argument("--challenges", type=int, default=20)
    pe.add_argument("--out-dir", default="poep_l9")
    a = ap.parse_args()
    if a.cmd == "enroll":
        cfg = PoEPConfig(player=a.player, challenges=a.challenges, out_dir=a.out_dir)
        print("PoEP enrollment — hold the controller STILL (not in a game); react to each buzz.\n")
        print(json.dumps(PoEPRecorder(cfg).enroll(), indent=2, default=str))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
