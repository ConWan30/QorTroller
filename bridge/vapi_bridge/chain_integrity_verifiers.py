"""Full-strength, read-only chain-integrity verifiers (closes the F5 dry-assemble leg gaps).

The F5 provenance-quadrille dry-assemble surfaced that two of its four legs rested on weaker
guarantees than the others:
  • WEC    — the canonical get_watchdog_event_chain_status verifies only a LIMIT 100 window, and a
             naive full-history recompute over global ts_ns order BREAKS at the first point where
             concurrent bridge processes interleave (94 PIDs in the live log). That break is a
             recompute-methodology artifact, NOT tamper.
  • CORPUS — get_corpus_snapshot_status returns head + count but does NOT recompute the snapshot
             commitments, so the corpus leg was presence-only (not tamper-verified).

This module closes both with ORDER-INDEPENDENT, TAMPER-EVIDENT verification that REUSES the FROZEN
primitives (watchdog_chain.compute_wec / genesis_wec, corpus_snapshot.compute_corpus_commitment) —
it never reimplements the crypto.

  • verify_wec_links: walks each row's STORED prev_wec_hash pointer and recomputes its wec_hash via
    the FROZEN compute_wec. Each link is validated against its own recorded predecessor, so the
    verdict is independent of global ordering and immune to the concurrent-process interleave that
    misled the naive recompute. Also reports structural shape (orphans / forks / tips) so the
    multi-process concurrency is visible, not hidden.
  • verify_corpus_commitments: recomputes each snapshot_commitment via the FROZEN
    compute_corpus_commitment and confirms it matches — real tamper-evidence for the corpus log.

READ-ONLY / fixtures-first: callers pass already-fetched rows (list[dict]); this module does NOT
open the DB, read the chain, or mutate anything. No new FROZEN-v1 family, no new PV-CI invariant.
Reusable by the F5 assembler to feed full-strength ChainStatus legs.
"""
from __future__ import annotations

from dataclasses import dataclass

from .watchdog_chain import compute_wec, genesis_wec
from .corpus_snapshot import compute_corpus_commitment


def _is_hex32(s: object) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


@dataclass(frozen=True)
class WecIntegrityReport:
    n_rows: int
    links_valid: int           # rows whose stored wec_hash == compute_wec(stored prev, fields)
    n_invalid: int             # tamper: a stored wec_hash that does NOT match its recompute
    n_orphans: int             # non-genesis rows whose prev_wec_hash is no row's wec_hash
    n_forks: int               # distinct non-empty prev values shared by >1 row (concurrency)
    n_tips: int                # wec_hashes referenced by no row's prev (chain tips)
    head_hex: str | None       # latest tip by ts_ns (the chain head), or None if no rows
    tamper_free: bool          # all links recompute correctly (no stored hash was altered)
    structurally_sound: bool   # tamper_free AND no orphans (forks allowed: concurrency, not tamper)

    @property
    def intact(self) -> bool:
        """For quadrille consumption: tamper-free AND no orphaned links. Forks (concurrent
        multi-process writes) are reported but do NOT by themselves fail intactness — every link
        is still a valid hash of its recorded predecessor."""
        return self.structurally_sound


def verify_wec_links(rows: list[dict]) -> WecIntegrityReport:
    """Order-independent full-history WEC verification via stored prev_wec_hash pointers.

    Each row dict must carry: event_code, pid, grind_session_id, ts_ns, wec_hash, prev_wec_hash
    (prev_wec_hash == "" marks a genesis link). Reuses the FROZEN compute_wec / genesis_wec."""
    if not rows:
        return WecIntegrityReport(0, 0, 0, 0, 0, 0, None, True, True)

    wec_set = {str(r.get("wec_hash", "")) for r in rows}
    prev_counts: dict[str, int] = {}
    links_valid = n_invalid = n_orphans = 0

    for r in rows:
        code = int(r.get("event_code") or 0)
        pid = int(r.get("pid") or 0)
        sid = str(r.get("grind_session_id") or "")
        ts = int(r.get("ts_ns") or 0)
        stored = str(r.get("wec_hash") or "")
        prev_hex = str(r.get("prev_wec_hash") or "")

        if prev_hex == "":
            prev = genesis_wec(sid, ts)
        else:
            if prev_hex not in wec_set:
                n_orphans += 1
            prev_counts[prev_hex] = prev_counts.get(prev_hex, 0) + 1
            try:
                prev = bytes.fromhex(prev_hex)
            except ValueError:
                n_invalid += 1
                continue
        try:
            expected = compute_wec(prev, code, pid, sid, ts)
        except Exception:
            n_invalid += 1
            continue
        if expected.hex() == stored:
            links_valid += 1
        else:
            n_invalid += 1

    n_forks = sum(1 for _, c in prev_counts.items() if c > 1)
    referenced = set(prev_counts)
    tips = [r for r in rows if str(r.get("wec_hash", "")) not in referenced]
    n_tips = len(tips)
    head_hex = None
    if rows:
        head_hex = max(rows, key=lambda r: int(r.get("ts_ns") or 0)).get("wec_hash") or None

    tamper_free = (n_invalid == 0)
    structurally_sound = tamper_free and (n_orphans == 0)
    return WecIntegrityReport(len(rows), links_valid, n_invalid, n_orphans, n_forks, n_tips,
                              head_hex, tamper_free, structurally_sound)


@dataclass(frozen=True)
class CorpusIntegrityReport:
    n_rows: int
    commitments_valid: int     # rows whose stored snapshot_commitment == recompute
    n_invalid: int             # tamper: a stored commitment that does NOT match
    head_hex: str | None       # latest snapshot_commitment by ts_ns
    tamper_free: bool

    @property
    def intact(self) -> bool:
        return self.tamper_free


def _to_bytes32(v) -> bytes:
    """Accept a 32-byte value stored as 64-hex str or raw bytes."""
    if isinstance(v, bytes):
        if len(v) != 32:
            raise ValueError("bytes field not 32 bytes")
        return v
    if _is_hex32(v):
        return bytes.fromhex(v)
    raise ValueError("field not a 32-byte hex/bytes value")


def verify_corpus_commitments(rows: list[dict]) -> CorpusIntegrityReport:
    """Recompute each corpus snapshot_commitment via the FROZEN compute_corpus_commitment and
    confirm it matches the stored value. Each row dict must carry: wiki_hash, agent_root,
    separation_ratio, corpus_n, ts_ns, snapshot_commitment."""
    if not rows:
        return CorpusIntegrityReport(0, 0, 0, None, True)
    valid = n_invalid = 0
    for r in rows:
        try:
            exp = compute_corpus_commitment(
                _to_bytes32(r.get("wiki_hash")), _to_bytes32(r.get("agent_root")),
                float(r.get("separation_ratio") or 0.0), int(r.get("corpus_n") or 0),
                int(r.get("ts_ns") or 0),
            ).hex()
        except Exception:
            n_invalid += 1
            continue
        if exp == str(r.get("snapshot_commitment") or ""):
            valid += 1
        else:
            n_invalid += 1
    head = max(rows, key=lambda r: int(r.get("ts_ns") or 0)).get("snapshot_commitment") or None
    return CorpusIntegrityReport(len(rows), valid, n_invalid, head, n_invalid == 0)
