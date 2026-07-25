"""RWM panel content diversity helpers (CANDIDATE ops tooling).

Used by post-session check and live session watcher to detect FROZEN_RING
sessions (all original panel_*.png share one content hash) without trusting
chain length alone.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def panel_content_stats(
    paths: Iterable[Path],
    *,
    sample_limit: int | None = None,
) -> dict:
    """Return unique content counts over original panel files.

    sample_limit: if set, only hash the most recent N paths by mtime (for
    mid-session cheap probes). Full pass uses sample_limit=None.
    """
    files = [Path(p) for p in paths if Path(p).is_file()]
    if sample_limit is not None and sample_limit > 0 and len(files) > sample_limit:
        files = sorted(files, key=lambda p: p.stat().st_mtime)[-sample_limit:]
    else:
        files = sorted(files, key=lambda p: p.name)

    hashes = [sha256_file(p) for p in files]
    n = len(hashes)
    unique = len(set(hashes)) if hashes else 0
    ratio = (unique / n) if n else 0.0
    frozen = n > 0 and unique <= 1
    return {
        "n": n,
        "unique": unique,
        "ratio": ratio,
        "frozen": frozen,
        "label": "FROZEN_RING" if frozen else ("LOW" if ratio < 0.10 else "OK"),
    }


def panel_stats_for_dir(dir_path: Path | str, pattern: str = "panel_*.png", **kw) -> dict:
    d = Path(dir_path)
    if not d.is_dir():
        return {"n": 0, "unique": 0, "ratio": 0.0, "frozen": False, "label": "EMPTY"}
    return panel_content_stats(d.glob(pattern), **kw)
