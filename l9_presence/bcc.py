"""QorTroller BCC — sealed dormant developer-reference corpus (see BCC_SCOPE.md).

Passive provenance-chained accumulator harvested from casual gameplay (GIC pattern).
ISOLATION is load-bearing: BCC is read-only w.r.t. every proven system. It writes ONLY to
its own bcc_l9/ lane + its own chain; it NEVER touches separation_ratio / EER / L4 thresholds
/ PoEP calibration / the lattice / the multi-player corpora, and it computes no separation.
The harvester accepts ALREADY-COMPUTED feature payloads (the caller uses the read-only
extractors) and merely digests + chains + appends them — so BCC structurally cannot mutate a
proven number. It only ACCUMULATES; promotion into proven corpora is out of scope.

Default-OFF (BCCConfig.enabled=False) -> fully dormant, zero behavior. STATUS: build v0;
QORTROLLER-BCC-GENESIS-v0 is a CANDIDATE chain tag (not a registered PATTERN-017 family).
No FROZEN-v1 / PoAC / chain / contract surface touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

BCC_GENESIS_TAG = b"QORTROLLER-BCC-GENESIS-v0"
_LANE_A = 0x01   # passive L9 render-loop features (active gameplay)
_LANE_B = 0x02   # opportunistic PoEP micro-sample (GAD menu windows)
_Q_NOMINAL = 0x01
_Q_DEGRADED = 0x10


def canonical_digest(payload: dict) -> str:
    """Deterministic SHA-256 of a payload (sort_keys -> order-independent)."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def genesis_bcc() -> str:
    return hashlib.sha256(BCC_GENESIS_TAG).hexdigest()


def compute_bcc_hash(prev_hex: str, feature_digest_hex: str, quality_code: int,
                     sub_lane: int, ts_ns: int) -> str:
    """BCC FROZEN formula v0 (candidate): 74-byte preimage, mirrors the GIC discipline.
    SHA-256(prev(32) || feature_digest(32) || quality(1) || sub_lane(1) || ts_ns_be(8))."""
    h = hashlib.sha256()
    h.update(bytes.fromhex(prev_hex))
    h.update(bytes.fromhex(feature_digest_hex))
    h.update(int(quality_code).to_bytes(1, "big"))
    h.update(int(sub_lane).to_bytes(1, "big"))
    h.update(int(ts_ns).to_bytes(8, "big"))
    return h.hexdigest()


class BCCStore:
    """Append-only JSONL chain in its own sealed lane. The ONLY thing BCC writes to."""

    def __init__(self, out_dir: str = "bcc_l9") -> None:
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.path = os.path.join(out_dir, "bcc_chain.jsonl")

    def load(self) -> list:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def append(self, payload: dict, quality_code: int, sub_lane: int,
               ts_ns: Optional[int] = None) -> dict:
        recs = self.load()
        last = recs[-1] if recs else None
        prev = last["bcc_hash"] if last else genesis_bcc()
        ts_ns = ts_ns if ts_ns is not None else time.time_ns()
        if last and ts_ns <= last["ts_ns"]:           # monotonicity guard (INV-GIC-002 analog)
            ts_ns = last["ts_ns"] + 1
        fdig = canonical_digest(payload)
        bcc_hash = compute_bcc_hash(prev, fdig, quality_code, sub_lane, ts_ns)
        rec = {"seq": (last["seq"] + 1 if last else 0), "prev_hash": prev, "bcc_hash": bcc_hash,
               "feature_digest": fdig, "quality_code": quality_code, "sub_lane": sub_lane,
               "ts_ns": ts_ns, "payload": payload}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return rec

    def verify(self) -> bool:
        prev = genesis_bcc()
        for r in self.load():
            if r["prev_hash"] != prev:
                return False
            if canonical_digest(r["payload"]) != r["feature_digest"]:   # payload tamper -> digest mismatch
                return False
            if compute_bcc_hash(prev, r["feature_digest"], r["quality_code"],
                                r["sub_lane"], r["ts_ns"]) != r["bcc_hash"]:
                return False
            prev = r["bcc_hash"]
        return True

    def status(self) -> dict:
        recs = self.load()
        return {"chain_length": len(recs), "chain_intact": self.verify(),
                "head": recs[-1]["bcc_hash"] if recs else None,
                "sub_lane_a": sum(1 for r in recs if r["sub_lane"] == _LANE_A),
                "sub_lane_b": sum(1 for r in recs if r["sub_lane"] == _LANE_B)}


@dataclass
class BCCConfig:
    enabled: bool = False          # dormant by default — flip on to accumulate
    sublane_b_enabled: bool = False  # PoEP micro-samples: a second, independent opt-in
    out_dir: str = "bcc_l9"


class BCCHarvester:
    """Witness extension: digests + chains ALREADY-COMPUTED feature payloads into the sealed
    lane. No-op while dormant; PCC/GAD-gated (fail-closed on non-NOMINAL). Touches nothing
    outside out_dir — structurally cannot mutate a proven number."""

    def __init__(self, cfg: Optional[BCCConfig] = None) -> None:
        self.cfg = cfg or BCCConfig()
        self.store = BCCStore(self.cfg.out_dir)

    def record_l9(self, feature_vec, nominal: bool = True) -> Optional[dict]:
        if not self.cfg.enabled or not nominal:
            return None
        payload = {"type": "l9", "features": [float(x) for x in feature_vec]}
        return self.store.append(payload, _Q_NOMINAL, _LANE_A)

    def record_poep(self, sample: dict, nominal: bool = True) -> Optional[dict]:
        if not (self.cfg.enabled and self.cfg.sublane_b_enabled) or not nominal:
            return None
        return self.store.append({"type": "poep", "sample": dict(sample)}, _Q_NOMINAL, _LANE_B)

    def status(self) -> dict:
        return {"enabled": self.cfg.enabled, "sublane_b_enabled": self.cfg.sublane_b_enabled,
                **self.store.status()}


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="BCC — sealed dormant developer-reference corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show BCC chain status (read-only)")
    st = sub.add_parser("selftest", help="end-to-end chain demo in a temp lane (no real lane touched)")
    st.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    if a.cmd == "status":
        print(json.dumps(BCCHarvester(BCCConfig()).status(), indent=2))
        return 0
    if a.cmd == "selftest":
        import tempfile
        d = a.out_dir or tempfile.mkdtemp(prefix="bcc_selftest_")
        h = BCCHarvester(BCCConfig(enabled=True, sublane_b_enabled=True, out_dir=d))
        h.record_l9([0.31, 1.2, 0.6])
        h.record_l9([0.29, 1.1, 0.7])
        h.record_poep({"delta": 0.61, "adaptive_response_detected": True})
        print(json.dumps({"lane": d, **h.status()}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
