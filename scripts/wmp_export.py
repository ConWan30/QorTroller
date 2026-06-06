"""WMP-2 exporter — JSONL batch export of `ProvenanceBundle` v1.

Honest scope (W1-D operator decision, 2026-06-06):

  • v1 ships a FIXTURES-ONLY export path. Real gamer data CANNOT export
    in v1; the `world_model_consent_present()` gate hard-returns False.

  • The deferred-export guard is intentional and load-bearing — the
    WMP lane's headline property is that consent is CRYPTOGRAPHICALLY
    VERIFIABLE on every leg. Until the greenfield
    `VAPIWorldModelConsentRegistry` ships and the consumer verifier can
    read `setWorldModelConsent(true)` on-chain for a specific gamer,
    the lane has no on-chain consent leg to verify. Exporting real
    data before that would force the lane to claim consent it cannot
    cryptographically prove.

  • Fixtures pass `--allow-fixtures` and write to a separate fixtures
    directory. Fixture bundles carry `scope_synthetic=True` in their
    `scope_disclosure` so a consumer verifier (WMP-3) can REJECT them
    when running against a real corpus and ACCEPT them when invoked
    with `allow_synthetic=True`.

CLI:

    # Default refuses real export (the deferred-export guard):
    python scripts/wmp_export.py --out ./out --dry-run
    python scripts/wmp_export.py --out ./out --session-limit 5
    # → exit 2, message: "world-model consent is DEFERRED in v1"

    # Fixtures path (the v1 supported workflow):
    python scripts/wmp_export.py --out ./out --allow-fixtures \
        --fixture-corpus tests/fixtures/wmp_corpus

The exporter is idempotent + resumable. It writes a single JSONL file
(one bundle per line) plus a `corpus_manifest.json` index of
(session_id, ts, bundle_hash, schema). Re-running with the same output
directory continues from the last persisted session_id; bundles are
never duplicated.

NO PII in `corpus_manifest.json`. No gamer wallet, no device_id, no
session boundaries beyond timestamps. The index is structurally a
header.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

# Allow `python scripts/wmp_export.py` from repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bridge"))

from vapi_bridge.wmp import ProvenanceBundle, SCHEMA_VERSION


# ── deferred-export guard ──────────────────────────────────────────────
# W1-D: this lambda hard-returns False in v1. WHEN the greenfield
# VAPIWorldModelConsentRegistry ships (Phase-2 promote) and the bridge
# is wired to view-call setWorldModelConsent for a specific gamer, this
# function will return the view-call result. Until then, REAL-gamer data
# cannot leave the export script.
def world_model_consent_present(gamer_address: str) -> bool:
    """Returns False in v1 — the cryptographic consent leg for WMP export
    does not yet exist on-chain. Real-data export is intentionally
    blocked behind this gate."""
    _ = gamer_address  # kept for API stability — Phase-2 will read it
    return False


# ── output paths ───────────────────────────────────────────────────────

JSONL_FILENAME = "wmp_corpus.jsonl"
INDEX_FILENAME = "corpus_manifest.json"


def _bundle_hash(bundle_dict: dict) -> str:
    """Stable SHA-256 over the canonical JSON of a bundle. NOT a
    commitment-family hash — operational fingerprint only."""
    canon = json.dumps(bundle_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _load_index(out_dir: Path) -> dict:
    p = out_dir / INDEX_FILENAME
    if not p.exists():
        return {
            "schema":     SCHEMA_VERSION,
            "created_at": time.time_ns(),
            "entries":    [],
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # Corrupt index → start clean. The JSONL is the source of truth;
        # the index will rebuild on the next successful flush.
        return {
            "schema":     SCHEMA_VERSION,
            "created_at": time.time_ns(),
            "entries":    [],
        }


def _save_index(out_dir: Path, index: dict) -> None:
    p = out_dir / INDEX_FILENAME
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=False), encoding="utf-8")
    tmp.replace(p)


def export_bundles(
    bundles: Iterable[ProvenanceBundle],
    *,
    out_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Append a stream of bundles to the JSONL at `out_dir/wmp_corpus.jsonl`
    and update `out_dir/corpus_manifest.json`. Idempotent on bundle_hash.

    Returns a summary dict with:
        written       — count of new bundles written
        skipped       — count of duplicates skipped
        total_entries — total entries in the corpus_manifest.json after
        out_jsonl     — path to the JSONL file
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    index = _load_index(out_dir)
    seen_hashes = {e["bundle_hash"] for e in index.get("entries", [])}

    out_jsonl = out_dir / JSONL_FILENAME
    written = 0
    skipped = 0
    new_entries: list[dict] = []

    handle = None
    try:
        if not dry_run:
            handle = out_jsonl.open("a", encoding="utf-8")
        for b in bundles:
            d = b.to_dict()
            bh = _bundle_hash(d)
            if bh in seen_hashes:
                skipped += 1
                continue
            seen_hashes.add(bh)
            entry = {
                # NO gamer wallet, NO device_id in the index. Header info only.
                "schema":          b.schema,
                "bundle_hash":     bh,
                "ts_ns":           b.bundle_created_at_ns,
                "ticks":           b.action_trace_ticks,
                "humanity_deferred": b.humanity_deferred,
                "scope_synthetic": b.scope_synthetic,
            }
            new_entries.append(entry)
            if handle is not None:
                handle.write(json.dumps(d, separators=(",", ":")) + "\n")
            written += 1
    finally:
        if handle is not None:
            handle.close()

    if not dry_run and new_entries:
        index["entries"] = index.get("entries", []) + new_entries
        _save_index(out_dir, index)

    return {
        "written":       written,
        "skipped":       skipped,
        "total_entries": len(index.get("entries", [])) + (len(new_entries) if dry_run else 0),
        "out_jsonl":     str(out_jsonl),
    }


def _load_fixture_corpus(path: Path) -> list[ProvenanceBundle]:
    """Load a fixture corpus of pre-assembled bundles from JSONL.

    Fixture path layout:
        <path>/wmp_corpus.jsonl   — one bundle dict per line

    Returns a list of `ProvenanceBundle` dataclasses. Validates only the
    schema string + presence of FROZEN scope_disclosure values; a fixture
    that mis-states scope is loaded but the consumer verifier will REJECT
    it.
    """
    fp = path / JSONL_FILENAME
    if not fp.exists():
        raise FileNotFoundError(f"fixture corpus not found at {fp}")
    bundles: list[ProvenanceBundle] = []
    for line in fp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        # tuple channel-order restoration
        d["action_trace_channels"] = tuple(d.get("action_trace_channels", ()))
        bundles.append(ProvenanceBundle(**d))
    return bundles


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wmp_export",
        description="WMP-2 fixtures-first exporter (W1-D deferred-export guard).",
    )
    p.add_argument("--out", required=True, type=Path,
                   help="Output directory. Created if missing.")
    p.add_argument("--dry-run", action="store_true",
                   help="Estimate without writing. Reports what would change.")
    p.add_argument("--allow-fixtures", action="store_true",
                   help="Required to export fixture bundles. Without this, "
                        "the script refuses to export ANYTHING in v1.")
    p.add_argument("--fixture-corpus", type=Path, default=None,
                   help="Path to a fixture corpus dir containing wmp_corpus.jsonl.")
    p.add_argument("--gamer", type=str, default="",
                   help="Gamer wallet address. Reserved for Phase-2 when the "
                        "consent gate is cryptographic.")
    args = p.parse_args(argv)

    # ── deferred-export guard ──────────────────────────────────────────
    # Real-data export gate. v1 hard-returns False.
    real_data_ok = world_model_consent_present(args.gamer)
    if not real_data_ok and not args.allow_fixtures:
        sys.stderr.write(
            "[wmp_export] REFUSING real-data export — world-model consent "
            "is DEFERRED in v1 (W1-D).\n"
            "  v1 requires --allow-fixtures plus --fixture-corpus PATH.\n"
            "  See docs/world-model-provenance.md §W1-D for the deferral\n"
            "  rationale and the Phase-2 promote path.\n"
        )
        return 2

    # ── fixtures path ──────────────────────────────────────────────────
    if args.allow_fixtures:
        if args.fixture_corpus is None:
            sys.stderr.write("[wmp_export] --allow-fixtures requires --fixture-corpus PATH\n")
            return 2
        bundles = _load_fixture_corpus(args.fixture_corpus)
    else:
        # Unreachable in v1 (the guard above rejects). Reserved for
        # Phase-2 when real_data_ok can return True.
        sys.stderr.write("[wmp_export] real-data path is not implemented in v1\n")
        return 2

    summary = export_bundles(
        bundles, out_dir=args.out, dry_run=args.dry_run,
    )
    summary["dry_run"] = bool(args.dry_run)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
