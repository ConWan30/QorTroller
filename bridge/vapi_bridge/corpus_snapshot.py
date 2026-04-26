"""Phase 236-CORPUS-SNAPSHOT — ZK-attested corpus snapshot. FROZEN FORMULA v1.

Sits below GIC (Phase 235-A) and WEC (Phase 236-WATCHDOG) in the chain stack.
GIC documents per-session cognitive integrity. WEC documents per-restart
operational integrity. CORPUS-SNAPSHOT documents per-snapshot CORPUS integrity:
the wiki state + agent fleet root + separation ratio + corpus size at a single
ts_ns, anchored as one tamper-evident commitment.

Why this matters for the grind:
  At GIC_100 deposit, you need to prove not just "100 sessions happened" (GIC)
  and "the bridge was up" (WEC) — you need to prove WHAT the corpus looked like
  while those sessions were generated. Wiki content, fleet topology, and
  separation ratio at snapshot time all bind into the commitment. A reviewer
  given the snapshot_commitment at any later date can verify the corpus was
  exactly that state — even if wiki/ has moved on, ait_session_log has grown,
  or the fleet has gained/lost an agent.

Snapshot triggers (caller-driven; this module is pure functions):
  - New AIT session inserted (separation ratio likely changed)
  - Separation ratio changed > 0.01 from the prior snapshot
  - Agent fleet Merkle root changed (any agent added/updated)
  - Manual via POST /operator/force-corpus-snapshot
  - Periodic baseline (e.g. once per grind day)

CORPUS-SNAPSHOT_v1 commitment formula:
    commitment = SHA-256(
        b"VAPI-CORPUS-SNAPSHOT-v1"  (23 bytes)  — domain separation
        || wiki_hash                (32 bytes)  — SHA-256 over sorted wiki tree
        || agent_root               (32 bytes)  — fleet Merkle root from
                                                  ProtocolCoherenceAgent latest anchor;
                                                  32 zero bytes if no anchor exists yet
        || ratio_milli_be           (8 bytes)   — uint64 BE: ratio * 1_000_000
                                                  (deterministic int encoding for floats)
        || corpus_n_be              (8 bytes)   — uint64 BE: total corpus session count
        || ts_ns_be                 (8 bytes)   — uint64 BE: snapshot time
    )                                = 111 bytes → SHA-256 → 32 bytes

Wiki hashing rule (FROZEN):
    1. Walk `wiki_dir` recursively for files matching `*.md` (default).
    2. Sort by POSIX-style relative path (forward slashes, lowercased — Windows agnostic).
    3. For each file: hash separator `b"--FILE:" + posix_path_bytes + b"\n"` then file bytes.
    4. SHA-256 the whole stream → 32-byte wiki_hash.

  Same wiki content + same files = identical hash regardless of OS, mtime, or
  directory enumeration order. Adding/removing/editing any file or moving a
  file to a new path changes the hash.

Any change to byte order, domain tag, or wiki-walk rule requires v2 + new tag.
v1 is permanently frozen.
"""
from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

_SNAPSHOT_TAG = b"VAPI-CORPUS-SNAPSHOT-v1"   # 23 bytes
_RATIO_SCALE = 1_000_000                      # 6 decimal places, deterministic int
_WIKI_FILE_SEP = b"--FILE:"


def compute_wiki_snapshot_hash(
    wiki_dir: str | os.PathLike,
    pattern: str = "*.md",
) -> bytes:
    """Hash the entire wiki tree to a 32-byte content-addressed digest.

    Walks `wiki_dir` recursively, sorts by POSIX relative path, hashes content
    with explicit per-file separator including the path itself. Path is part
    of the digest so renames change the hash.

    Args:
        wiki_dir: Path to wiki/ root (absolute or relative). Missing dir → 32 zero bytes.
        pattern: Glob pattern for files to include (default `*.md`).

    Returns:
        32-byte SHA-256 digest of the canonical concatenation. Empty/missing
        directory returns 32 zero bytes (not an error — useful for genesis snapshots).
    """
    root = Path(wiki_dir)
    if not root.exists() or not root.is_dir():
        return b"\x00" * 32

    # Collect (relative_posix_path, absolute_path) sorted deterministically
    files: list[tuple[str, Path]] = []
    for p in root.rglob(pattern):
        if p.is_file():
            try:
                rel = p.relative_to(root)
            except ValueError:
                continue
            posix = rel.as_posix().lower()  # normalise for cross-OS reproducibility
            files.append((posix, p))
    files.sort(key=lambda t: t[0])

    h = hashlib.sha256()
    for posix_path, abs_path in files:
        h.update(_WIKI_FILE_SEP)
        h.update(posix_path.encode("utf-8"))
        h.update(b"\n")
        try:
            with open(abs_path, "rb") as f:
                # Stream in chunks so very large wikis don't blow memory
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError:
            # Unreadable file → still record the path attempt with empty content marker
            h.update(b"--UNREADABLE--")
    return h.digest()


def encode_ratio_milli(ratio: float) -> int:
    """Convert a float ratio to a uint64-safe integer (ratio * 1e6, rounded)."""
    if ratio is None:
        ratio = 0.0
    n = int(round(float(ratio) * _RATIO_SCALE))
    if n < 0:
        raise ValueError(f"ratio_milli must be >= 0, got {n}")
    if n > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"ratio_milli overflow uint64: {n}")
    return n


def compute_corpus_commitment(
    wiki_hash: bytes,
    agent_root: bytes,
    separation_ratio: float,
    corpus_n: int,
    ts_ns: int,
) -> bytes:
    """Compute the corpus snapshot commitment v1 — FROZEN formula.

    Args:
        wiki_hash:        32-byte digest from compute_wiki_snapshot_hash().
        agent_root:       32-byte fleet Merkle root (or 32 zero bytes if no anchor).
        separation_ratio: Float (e.g. 1.199 for AIT). Encoded as uint64 milliratio.
        corpus_n:         Total corpus session count (uint64).
        ts_ns:            Unix timestamp in nanoseconds (uint64).

    Returns:
        32-byte SHA-256 digest.
    """
    if len(wiki_hash) != 32:
        raise ValueError(f"wiki_hash must be 32 bytes, got {len(wiki_hash)}")
    if len(agent_root) != 32:
        raise ValueError(f"agent_root must be 32 bytes, got {len(agent_root)}")
    if not (0 <= int(corpus_n) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"corpus_n out of uint64 range: {corpus_n}")
    if not (0 <= int(ts_ns) <= 0xFFFFFFFFFFFFFFFF):
        raise ValueError(f"ts_ns out of uint64 range: {ts_ns}")

    ratio_milli = encode_ratio_milli(separation_ratio)
    return hashlib.sha256(
        _SNAPSHOT_TAG
        + wiki_hash
        + agent_root
        + struct.pack(">Q", ratio_milli)
        + struct.pack(">Q", int(corpus_n))
        + struct.pack(">Q", int(ts_ns))
    ).digest()


def agent_root_from_hex(merkle_root_hex: str | None) -> bytes:
    """Parse a 64-char hex Merkle root into 32 bytes; missing/invalid → 32 zero bytes.

    The Phase 221 ProtocolCoherenceRegistry stores 32-byte Merkle roots as hex.
    No anchor yet (early grind, fresh DB) → genesis 32 zero bytes — this is a
    valid snapshot input, just not bound to any specific fleet topology.
    """
    if not merkle_root_hex:
        return b"\x00" * 32
    try:
        b = bytes.fromhex(merkle_root_hex)
    except (ValueError, TypeError):
        return b"\x00" * 32
    if len(b) == 32:
        return b
    if len(b) > 32:
        return b[:32]
    return b + b"\x00" * (32 - len(b))
