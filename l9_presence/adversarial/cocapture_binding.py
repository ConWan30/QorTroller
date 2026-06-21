"""Presence <-> retina co-capture BINDING correlator (the section-6 gap closure).

The honest problem this closes
------------------------------
A retina event (`retina_event_log`) carries `record_hash_hex`, which anchors it to a
real PoAC gameplay record (`records.record_hash`). A presence proof (`l6b_probe_log`)
carries only a TIMESTAMP -- it has no record_hash. So a HUMAN presence proof and the
gameplay record it co-occurred with cannot (yet) be tied together CRYPTOGRAPHICALLY;
they can only be paired by time proximity.

This module pairs them by a +/-window TEMPORAL join (default = the engine's 2.0 s
fusion window) and reports how much of the presence corpus can even be bound at all.
It is explicit, everywhere, that a temporal pair is a PROTOTYPE correlation, NOT a
cryptographic proof. The production closure is `BindingMode.RECORD_HASH_PRODUCTION`:
the challenger stamps the live PoAC `record_hash` into `l6b_probe_log` at probe time,
so a presence proof and a gameplay record share one verifiable anchor independent of
clock skew. When a probe carries a record_hash that an in-window retina row also
carries, this correlator reports that pair as cryptographically bound.

Pure + standalone: no bridge import, no DB access (the runner does that and injects
rows). The only intra-repo dependency is `DEFAULT_WINDOW_NS` from the engine, so the
join window is the SAME 2.0 s `check_binding` already enforces -- one source of truth.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..presence_retina_consistency import DEFAULT_WINDOW_NS


class BindingMode(str, Enum):
    """How a presence proof is tied to a gameplay/retina record."""
    TEMPORAL_PROTOTYPE = "TEMPORAL_PROTOTYPE"          # paired by +/-window timestamp proximity ONLY
    RECORD_HASH_PRODUCTION = "RECORD_HASH_PRODUCTION"  # paired by a SHARED cryptographic record_hash
    UNBOUND = "UNBOUND"                                # no retina record within the window


@dataclass(frozen=True)
class ProbeRow:
    """A presence proof from l6b_probe_log (only the join-relevant fields)."""
    device_id: str
    ts_ns: int
    classification: str                 # HUMAN / NO_RESPONSE / TOO_FAST
    latency_ms: Optional[float] = None
    record_hash: Optional[str] = None   # populated ONLY once production stamping lands


@dataclass(frozen=True)
class RetinaRow:
    """A retina event from retina_event_log (only the join-relevant fields)."""
    device_id: str
    ts_ns: int
    record_hash: Optional[str]          # retina_event_log.record_hash_hex (the PoAC anchor)
    anomaly_count: int = 0


@dataclass(frozen=True)
class BoundPair:
    probe: ProbeRow
    retina: Optional[RetinaRow]
    offset_ns: Optional[int]            # signed: retina.ts_ns - probe.ts_ns
    mode: BindingMode
    cryptographically_bound: bool

    @property
    def bound(self) -> bool:
        return self.retina is not None

    @property
    def anchor_record_hash(self) -> Optional[str]:
        """The PoAC anchor this presence proof can claim, if any.

        Production: the probe's own record_hash, confirmed by an in-corpus retina row
        carrying the same hash. Prototype: the nearest in-window retina row's hash --
        a CANDIDATE anchor, valid only under the temporal-proximity assumption.
        """
        if self.retina is None:
            return None
        if self.cryptographically_bound and self.probe.record_hash:
            return self.probe.record_hash
        return self.retina.record_hash


@dataclass(frozen=True)
class BindingReport:
    pairs: list[BoundPair]
    window_ns: int

    # ---- coverage (computed) ----
    @property
    def n_probes(self) -> int:
        return len(self.pairs)

    @property
    def n_bound(self) -> int:
        return sum(1 for p in self.pairs if p.bound)

    @property
    def n_crypto(self) -> int:
        return sum(1 for p in self.pairs if p.cryptographically_bound)

    def _subset(self, classification: str) -> list[BoundPair]:
        return [p for p in self.pairs if p.probe.classification == classification]

    @property
    def n_human(self) -> int:
        return len(self._subset("HUMAN"))

    @property
    def n_human_bound(self) -> int:
        return sum(1 for p in self._subset("HUMAN") if p.bound)

    def coverage(self) -> float:
        return self.n_bound / self.n_probes if self.n_probes else 0.0

    def human_coverage(self) -> float:
        return self.n_human_bound / self.n_human if self.n_human else 0.0

    def crypto_coverage(self) -> float:
        return self.n_crypto / self.n_probes if self.n_probes else 0.0

    def offset_stats_ms(self) -> dict:
        """min/median/max ABSOLUTE temporal offset over the bound pairs, in ms."""
        offs = sorted(abs(p.offset_ns) for p in self.pairs if p.offset_ns is not None)
        if not offs:
            return {"n": 0, "min_ms": None, "median_ms": None, "max_ms": None}
        mid = offs[len(offs) // 2]
        return {
            "n": len(offs),
            "min_ms": round(offs[0] / 1e6, 1),
            "median_ms": round(mid / 1e6, 1),
            "max_ms": round(offs[-1] / 1e6, 1),
        }

    def to_dict(self) -> dict:
        return {
            "schema": "vapi-presence-retina-binding-v1",
            "window_ms": self.window_ns / 1e6,
            "n_probes": self.n_probes,
            "n_bound": self.n_bound,
            "n_crypto_bound": self.n_crypto,
            "coverage": round(self.coverage(), 4),
            "human_coverage": round(self.human_coverage(), 4),
            "crypto_coverage": round(self.crypto_coverage(), 4),
            "n_human": self.n_human,
            "n_human_bound": self.n_human_bound,
            "offset_stats_ms": self.offset_stats_ms(),
            "binding_is_cryptographic": self.n_crypto == self.n_probes and self.n_probes > 0,
        }

    def to_markdown(self) -> str:
        d = self.to_dict()
        crypto_done = d["binding_is_cryptographic"]
        banner = (
            "**CRYPTOGRAPHIC BINDING (production).** Every presence proof carries a "
            "PoAC `record_hash` confirmed by a retina row -- this is a verifiable bind."
            if crypto_done else
            "**TEMPORAL CORRELATION (prototype) -- NOT a cryptographic proof.** Pairs are "
            "joined by +/-window timestamp proximity only. A temporal pair shows a presence "
            "proof and a gameplay/retina record CO-OCCURRED; it does NOT prove they belong "
            "to the same record. Production closure = stamp the live `record_hash` into "
            "`l6b_probe_log` at probe time (see module docstring)."
        )
        off = d["offset_stats_ms"]
        lines = [
            "# Presence <-> Retina Binding Report",
            "",
            banner,
            "",
            f"- Join window: +/-{d['window_ms']:.0f} ms (engine `DEFAULT_WINDOW_NS`)",
            f"- Probes: {d['n_probes']}",
            f"- Temporally bound: {d['n_bound']} ({d['coverage'] * 100:.1f}%)",
            f"- Cryptographically bound: {d['n_crypto_bound']} ({d['crypto_coverage'] * 100:.1f}%)",
            f"- HUMAN probes: {d['n_human']}; HUMAN bound: {d['n_human_bound']} "
            f"({d['human_coverage'] * 100:.1f}%)",
            f"- Bound-pair offset |Δt|: min={off['min_ms']}ms median={off['median_ms']}ms "
            f"max={off['max_ms']}ms (n={off['n']})",
            "",
            "| probe ts_ns | class | lat ms | mode | crypto | Δt ms | anchor record_hash |",
            "|---|---|---|---|---|---|---|",
        ]
        for p in self.pairs:
            anchor = p.anchor_record_hash
            anchor_s = html.escape(anchor[:16] + "..") if anchor else "(none)"
            dt = round(p.offset_ns / 1e6, 1) if p.offset_ns is not None else ""
            lat = "" if p.probe.latency_ms is None else f"{p.probe.latency_ms:.0f}"
            lines.append(
                f"| {p.probe.ts_ns} | {html.escape(p.probe.classification)} | {lat} "
                f"| {p.mode.value} | {'yes' if p.cryptographically_bound else 'no'} "
                f"| {dt} | {anchor_s} |"
            )
        return "\n".join(lines)


def _nearest_in_window(probe: ProbeRow, retina: list[RetinaRow],
                       window_ns: int) -> Optional[RetinaRow]:
    """Same-device retina row with the smallest |Δt| within window_ns, or None."""
    best: Optional[RetinaRow] = None
    best_abs = window_ns + 1
    for r in retina:
        if r.device_id != probe.device_id:
            continue
        d = abs(r.ts_ns - probe.ts_ns)
        if d <= window_ns and d < best_abs:
            best, best_abs = r, d
    return best


def _crypto_match(probe: ProbeRow, retina: list[RetinaRow]) -> Optional[RetinaRow]:
    """Same-device retina row sharing the probe's record_hash, regardless of time.

    This is the PRODUCTION bind: a shared cryptographic anchor needs no temporal
    assumption. Returns the closest-in-time such row if several share the hash.
    """
    if not probe.record_hash:
        return None
    cands = [r for r in retina
             if r.device_id == probe.device_id and r.record_hash == probe.record_hash]
    if not cands:
        return None
    return min(cands, key=lambda r: abs(r.ts_ns - probe.ts_ns))


def correlate(probes: list[ProbeRow], retina: list[RetinaRow], *,
              window_ns: int = DEFAULT_WINDOW_NS) -> BindingReport:
    """Bind each presence probe to a retina/PoAC record.

    Per probe, production binding (shared record_hash) is preferred over temporal:
      1. If the probe carries a record_hash and an in-corpus retina row shares it ->
         RECORD_HASH_PRODUCTION, cryptographically_bound=True (time-independent).
      2. Else, the nearest same-device retina row within +/-window_ns ->
         TEMPORAL_PROTOTYPE, cryptographically_bound=False.
      3. Else -> UNBOUND.

    Fail-open: malformed/empty inputs yield an empty/UNBOUND report, never an error.
    """
    pairs: list[BoundPair] = []
    for probe in probes:
        crypto = _crypto_match(probe, retina)
        if crypto is not None:
            pairs.append(BoundPair(
                probe=probe, retina=crypto,
                offset_ns=crypto.ts_ns - probe.ts_ns,
                mode=BindingMode.RECORD_HASH_PRODUCTION,
                cryptographically_bound=True))
            continue
        near = _nearest_in_window(probe, retina, window_ns)
        if near is not None:
            pairs.append(BoundPair(
                probe=probe, retina=near,
                offset_ns=near.ts_ns - probe.ts_ns,
                mode=BindingMode.TEMPORAL_PROTOTYPE,
                cryptographically_bound=False))
            continue
        pairs.append(BoundPair(
            probe=probe, retina=None, offset_ns=None,
            mode=BindingMode.UNBOUND, cryptographically_bound=False))
    return BindingReport(pairs=pairs, window_ns=window_ns)
