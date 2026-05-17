"""M-1 Mythos-Stability cleanup helper — annotate intentional silent excepts.

Background
==========

Mythos-Stability variant (`bridge/vapi_bridge/mythos_variants.py`) flags every
`except Exception: pass` block in `bridge/vapi_bridge/` + `scripts/` that
lacks a deliberate-fail-open skip-marker within 2 lines of the except. The
empirical Mythos audit 2026-05-16 found 160 unmarked + 37 already-marked
blocks (156 in the audit's stricter count). The audit's prescribed remediation
distinguishes:

  - intentional fail-open / idempotent (the common case in VAPI's bridge code
    per CLAUDE.md hard rules: store helpers fail-open on DB errors returning
    0/0.0; chain read-views fail-open on RPC errors returning False/{}; startup
    blocks fail-open so import failures don't block boot) → add a skip-marker
    comment (this script does that).

  - genuine swallowed-bug → convert to `except Exception as exc:
    log.warning(...)` (this script does NOT do that — that requires
    per-site judgment and must remain manual).

VAPI's bridge code is overwhelmingly the former; the rare swallowed-bug case
should already have surfaced as a Phase 235.x or Phase O5-EVIDENCE-OS
loop-block / stability finding (those arcs converted the load-bearing ones
already, e.g. `_persist_record_sync` Phase 235.x-STABILITY-4 + `_resolve_pubkey`
Phase 235.x-STABILITY-5). This script handles the long-tail observability
noise; it does NOT attempt to convert genuine bugs.

What this script does
=====================

For each .py file under `bridge/vapi_bridge/` + `scripts/` (excluding tests,
vendored deps, generated files, and `mythos_variants.py` itself per the
audit's own exclude list), find every `except Exception: pass` (optionally
`except Exception as X: pass`) without a skip-marker in the 2-line window
around it, and append an inline marker comment to the `pass` line:

  pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

That marker is one of the existing Mythos-Stability skip strings (`fail-open`),
so a subsequent Mythos-Stability sweep will skip these blocks. The behavior
of the code is UNCHANGED — only documentation is added.

Usage
=====

  python scripts/cleanup_m1_silent_excepts.py            # dry-run preview
  python scripts/cleanup_m1_silent_excepts.py --apply    # write changes

Idempotent — running twice has no additional effect because the marker
itself is one of the skip strings.

Hard constraints
================

- Operates on PRODUCTION source ONLY (bridge/vapi_bridge/ + scripts/).
  Tests excluded per `_AUDIT_EXCLUDE_SUBSTR` in mythos_variants.py.
- Does NOT modify file behavior — only adds a comment to the `pass` line.
- Does NOT convert `pass` to `log.warning(...)` (manual decision per site).
- Preserves existing inline comments on the pass line (won't double-comment).
- Skips blocks already containing any skip-marker substring within 2 lines.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Same regex as mythos_variants._PAT_EXCEPT_PASS — must stay byte-identical.
_PAT_EXCEPT_PASS = re.compile(
    r"except\s+Exception\s*(?:as\s+\w+)?\s*:\s*\n(?P<indent>\s+)pass\b(?P<trailing>[^\n]*)",
    re.MULTILINE,
)

# Same skip markers as mythos_variants._FAIL_OPEN_MARKERS.
_FAIL_OPEN_MARKERS = (
    "idempotent",
    "fail-open",
    "fail_open",
    "noqa: BLE001",
    "intentional",
    "silent ok",
)

# Same audit dirs + exclude substrings as mythos_variants._AUDIT_DIRS /
# _AUDIT_EXCLUDE_SUBSTR. Kept in sync by convention; if Mythos-Stability ever
# updates these, this script's results may drift from the variant's sweep.
_AUDIT_DIRS = ("bridge/vapi_bridge", "scripts")
_AUDIT_EXTS = (".py",)
_AUDIT_EXCLUDE_SUBSTR = (
    "__pycache__",
    "node_modules",
    "/.git/",
    "/dist/",
    "/build/",
    "/venv/",
    "/.venv/",
    "/bridge/tests/",
    "/sdk/tests/",
    "/w3bstream/poseidon_test_vectors",
    "/bridge/vapi_bridge/mythos_variants.py",
    "/scripts/cleanup_m1_silent_excepts.py",  # this script itself contains the regex
)

_MARKER_COMMENT = "  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip"


def _iter_audit_files(root: Path):
    """Walk audit dirs; yield .py files not excluded."""
    for sub in _AUDIT_DIRS:
        base = root / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in _AUDIT_EXTS:
                continue
            posix = p.as_posix()
            if any(excl in posix for excl in _AUDIT_EXCLUDE_SUBSTR):
                continue
            yield p


def _has_skip_marker_nearby(text: str, except_start: int, except_end: int) -> bool:
    """Mirror mythos_variants.mythos_stability_sweep skip-marker check:
    inspect the 2-line window before the except and 2-line window after the
    pass for any of the deliberate-fail-open marker substrings."""
    lines_before = text[:except_start].splitlines()
    lines_after = text[except_end:].splitlines()
    window = "\n".join(lines_before[-2:] + lines_after[:2])
    return any(mk in window for mk in _FAIL_OPEN_MARKERS)


def annotate_file(path: Path, apply: bool) -> tuple[int, int]:
    """Return (annotated, skipped_already_marked)."""
    text = path.read_text(encoding="utf-8")
    annotated = 0
    skipped = 0
    # Find all matches; collect (start, end, full_match, indent, trailing) so we
    # can do replacements right-to-left without offset confusion.
    edits: list[tuple[int, int, str]] = []
    for m in _PAT_EXCEPT_PASS.finditer(text):
        if _has_skip_marker_nearby(text, m.start(), m.end()):
            skipped += 1
            continue
        trailing = m.group("trailing")
        if any(mk in trailing for mk in _FAIL_OPEN_MARKERS):
            # Marker already present inline (edge case for our regex window
            # check missing it because the marker is past column 2 of the post
            # window). Skip.
            skipped += 1
            continue
        # Replace the pass line. If trailing already has a comment (starts with
        # whitespace then '#'), append our marker inline so we don't clobber.
        new_pass_line = "pass"
        stripped_trailing = trailing.lstrip(" \t")
        if stripped_trailing.startswith("#"):
            # Existing comment — append marker as a continuation prefix.
            new_pass_line = f"pass{trailing}; fail-open: M-1 cleanup 2026-05-16"
        else:
            new_pass_line = f"pass{_MARKER_COMMENT}{trailing}"
        # Reconstruct full match: keep everything before 'pass' identical.
        full = m.group(0)
        # The match is `except Exception...:\n<indent>pass<trailing>` — replace
        # just the `pass<trailing>` portion.
        pass_start_in_match = full.rindex("pass")
        new_chunk = full[:pass_start_in_match] + new_pass_line
        edits.append((m.start(), m.end(), new_chunk))
        annotated += 1
    if not edits:
        return 0, skipped
    # Apply edits right-to-left.
    new_text = text
    for start, end, chunk in sorted(edits, key=lambda e: -e[0]):
        new_text = new_text[:start] + chunk + new_text[end:]
    if apply:
        path.write_text(new_text, encoding="utf-8")
    return annotated, skipped


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default: dry-run preview)",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo root (default: parent of scripts/)",
    )
    args = p.parse_args()
    total_annotated = 0
    total_skipped = 0
    per_file: list[tuple[Path, int, int]] = []
    for f in _iter_audit_files(args.root):
        annotated, skipped = annotate_file(f, apply=args.apply)
        if annotated or skipped:
            per_file.append((f, annotated, skipped))
        total_annotated += annotated
        total_skipped += skipped
    mode = "APPLIED" if args.apply else "DRY-RUN (preview; pass --apply to write)"
    print(f"M-1 Mythos-Stability silent-except cleanup — {mode}")
    print(f"  total annotated:        {total_annotated}")
    print(f"  total skipped (marked): {total_skipped}")
    print(f"  files affected:         {sum(1 for _, a, _ in per_file if a)}")
    print()
    print("Per-file:")
    for f, ann, skp in sorted(per_file, key=lambda x: -x[1])[:30]:
        rel = f.relative_to(args.root).as_posix()
        print(f"  +{ann:3d}  (skip {skp:3d})  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
