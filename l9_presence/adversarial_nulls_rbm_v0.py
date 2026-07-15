"""Adversarial null generator for RBM-v0 presence-readiness (A2A-POEP-P3P4, grok round-14).

Pure stdlib. Produces presence-FAKING (latency_ms, peak_lsb) samples across attack classes a
bot/replay/macro would use to land in RBM-v0's accept band [80,300]ms x peak>=1000 LSB. The point:
a presence proof must DEFEAT these; if RBM-v0's 2-feature boolean fires on them, it is a band check,
not a presence detector, and poep_enabled MUST NOT flip.
"""
from __future__ import annotations

import hashlib
import math
import random
from typing import Optional

MASTER_SEED = 0x504F45503134  # "P0EP14"
ATTACKS = ("A-CONST", "A-REPLAY", "A-RAND", "A-JITTER", "A-HYBRID")


def _gauss(rng: random.Random, mu: float, sd: float) -> float:
    return mu + sd * math.sqrt(-2.0 * math.log(rng.random())) * math.cos(2.0 * math.pi * rng.random())


def _row(attack_id, lat, peak, seed, i, **meta):
    return {"attack_id": attack_id, "latency_ms": float(lat), "peak_lsb": float(peak),
            "seed": seed, "trial_index": i, "meta": meta}


def gen_const(rng, n=200):
    """A-CONST: fixed-delay macro -> deterministic in-band (latency, peak)."""
    out = []
    for i in range(n):
        if i < 100:
            lat, pk = 150.0, 2000.0                                  # pure fixed macro
        else:
            lat = [100, 150, 200, 250][i % 4]; pk = [1000, 1500, 2500, 5000][(i // 4) % 4]  # grid
        out.append(_row("A-CONST", lat, pk, MASTER_SEED, i, mode="fixed" if i < 100 else "grid"))
    return out


def gen_replay(rng, replay_library, n=200):
    """A-REPLAY: replay real accepted reflex pairs (the hardest class -- they ARE human values)."""
    out = []
    lib = replay_library or [(169.0, 1500.0)]
    for i in range(n):
        l, p = lib[rng.randrange(len(lib))]
        if i >= 100:                                                # replay + tiny epsilon
            l += rng.uniform(-2, 2); p += rng.uniform(-20, 20)
        out.append(_row("A-REPLAY", l, p, MASTER_SEED, i, sub="pure" if i < 100 else "eps"))
    return out


def gen_rand(rng, n=300):
    """A-RAND: uniform in-band -- 'unlimited amp bot' gaming the published band."""
    out = []
    for i in range(n):
        lat = rng.uniform(80, 300)
        pk = rng.uniform(1000, 1200) if i >= 200 else rng.uniform(1000, 8000)  # tail: barely-above-thr
        out.append(_row("A-RAND", lat, pk, MASTER_SEED, i))
    return out


def gen_jitter(rng, n=300):
    """A-JITTER: Gaussian bot mimicking the human latency/peak distribution."""
    out = []
    for i in range(n):
        mu_l, sd_l = (220.0, 25.0) if i >= 240 else (160.0, 35.0)   # 20% bimodal-fatigue mode
        for _ in range(50):
            lat = _gauss(rng, mu_l, sd_l); pk = _gauss(rng, 2200.0, 400.0)
            if 80 <= lat <= 300 and pk >= 1000:
                break
        else:
            pk = max(pk, 1000.0); lat = min(max(lat, 80), 300)
        out.append(_row("A-JITTER", lat, pk, MASTER_SEED, i))
    return out


def gen_hybrid(rng, replay_library, n=200):
    """A-HYBRID: mix jitter/replay latency x fixed/rand peak (joint-structure abuse)."""
    out, lib = [], replay_library or [(169.0, 1500.0)]
    for i in range(n):
        lat = _gauss(rng, 160.0, 35.0) if rng.random() < 0.5 else lib[rng.randrange(len(lib))][0]
        pk = 3000.0 if rng.random() < 0.5 else rng.uniform(1000, 8000)
        lat = min(max(lat, 80), 300)
        out.append(_row("A-HYBRID", lat, pk, MASTER_SEED, i))
    return out


def generate_all(replay_library: Optional[list] = None, master_seed: int = MASTER_SEED) -> list[dict]:
    rng = random.Random(master_seed)
    return (gen_const(rng) + gen_replay(rng, replay_library) + gen_rand(rng)
            + gen_jitter(rng) + gen_hybrid(rng, replay_library))


def score_against_rbm_v0(rows: list[dict], evaluate_fn, params) -> dict:
    """Per-attack adversarial FAR = fraction that RBM-v0 fires operating_point_fire=True on."""
    by: dict[str, list[bool]] = {}
    for r in rows:
        fired = evaluate_fn(r["latency_ms"], r["peak_lsb"], params)["operating_point_fire"]
        by.setdefault(r["attack_id"], []).append(bool(fired))
    return {aid: {"n": len(v), "n_accept": sum(v), "far": sum(v) / len(v)} for aid, v in by.items()}
