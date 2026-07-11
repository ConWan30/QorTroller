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
# W1-D: hard-returns False UNTIL the greenfield VAPIWorldModelConsentRegistry is deployed and
# WORLD_MODEL_CONSENT_REGISTRY_ADDRESS is set (Phase-2 promote, INC-4). With the env set, this
# performs the read-only isWorldModelConsentGranted(gamer) view-call — the gamer's own on-chain
# signature is the ONLY thing that can flip it. Env unset -> v1 behavior byte-identical.
_WMC_SELECTOR = "0xf92ce72a"   # isWorldModelConsentGranted(address) — keccak-computed 2026-07-11
_DEFAULT_RPC = "https://babel-api.testnet.iotex.io"


def world_model_consent_present(gamer_address: str) -> bool:
    """False when no registry is configured (W1-D deferral, v1 byte-identical); otherwise the
    LIVE on-chain consent state for `gamer_address`. Fail-closed: any RPC/parse error -> False
    (real data never exports on a broken consent read)."""
    registry = os.environ.get("WORLD_MODEL_CONSENT_REGISTRY_ADDRESS", "").strip()
    if not registry or not gamer_address:
        return False
    try:
        import urllib.request
        g = gamer_address[2:] if gamer_address.startswith("0x") else gamer_address
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                           "params": [{"to": registry,
                                       "data": _WMC_SELECTOR + g.rjust(64, "0")}, "latest"]}).encode()
        req = urllib.request.Request(
            os.environ.get("WMP_RPC_URL", _DEFAULT_RPC), data=body,
            headers={"Content-Type": "application/json", "User-Agent": "qortroller-wmp-export"})
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read()).get("result") or "0x"
        return out != "0x" and int(out, 16) == 1
    except Exception:  # noqa: BLE001 — fail-closed: no consent read, no export
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


def _build_real_bundle(args) -> "ProvenanceBundle":
    """Phase-2 real-data path (INC-3): thread the regenerated matrix + the committed VHR proof
    + recency + consent into the UNTOUCHED assembler. The matrix input is the private-inputs
    JSON `scripts/wmp_regen_matrix.py` emits (its root was kill-checked byte-equal against the
    real proof's public input at INC-0)."""
    from vapi_bridge.replay_proof_pipeline.groth16_prover import _encode_proof
    from vapi_bridge.replay_proof_pipeline.pre_processor import SanitizedReplayMatrix
    from vapi_bridge.wmp.bundle_assembler import BundleAssembler

    priv = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    mx = priv["matrix"]
    public_list = json.loads(Path(args.vhr_public).read_text(encoding="utf-8"))
    proof_json = json.loads(Path(args.vhr_proof).read_text(encoding="utf-8"))
    # FROZEN INV-VHR-005 public order (output-first).
    order = ("replayProofToken", "sanitizedTraceRoot", "poacChainRoot",
             "consentPolicyHash", "humanityThreshold", "vhpCommitment")
    public = {k: str(public_list[i]) for i, k in enumerate(order)}

    matrix = SanitizedReplayMatrix(
        session_id=args.session_id, ticks=int(mx["ticks"]),
        stick_L_sector=bytes.fromhex(mx["stick_L_sector"]),
        stick_R_sector=bytes.fromhex(mx["stick_R_sector"]),
        trigger_L_state=bytes.fromhex(mx["trigger_L_state"]),
        trigger_R_state=bytes.fromhex(mx["trigger_R_state"]),
        button_mask=bytes.fromhex(mx["button_mask"]),
        imu_gravity_sector=bytes.fromhex(mx["imu_gravity_sector"]),
        poac_chain_root=bytes.fromhex(priv["poacChainRoot"][2:]
                                      if str(priv["poacChainRoot"]).startswith("0x")
                                      else priv["poacChainRoot"]),
        vhp_token_id=0, humanity_prob_floor=float(public["humanityThreshold"]) / 1000.0,
        session_verdict=args.session_verdict,
    )
    humanity = {"proof_type": "VAPI-REPLAY-PROOF-v1",
                "proof_bytes_hex": _encode_proof(proof_json).hex(),
                "public_inputs": public,
                "sanitized_trace_root": public["sanitizedTraceRoot"],
                "verifier_address": args.verifier_address,
                "deferred": False, "deferred_reason": ""}
    if args.recency_open and args.recency_close:
        recency = {"open_block": int(args.recency_open),
                   "open_block_hash": args.recency_open_hash,
                   "close_block": int(args.recency_close),
                   "close_block_hash": args.recency_close_hash,
                   "registry_address": args.beacon_registry}
    else:
        # Honest deferral: no anchored open/close pair supplied — the bundle carries an empty
        # registry and the verifier reads BEACON_REGISTRY_NOT_DEPLOYED. Never fabricated.
        recency = {"open_block": 0, "open_block_hash": "", "close_block": 0,
                   "close_block_hash": "", "registry_address": ""}
    consent = {"registry_address": args.consent_manifest_registry,
               "gamer_address": args.gamer,
               "manifest_hash": args.consent_manifest_hash,
               "world_model_dimension": "GRANTED",
               "world_model_registry": os.environ.get(
                   "WORLD_MODEL_CONSENT_REGISTRY_ADDRESS", "")}
    extra = None
    if args.strata_band:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from l9_presence.skill_strata import wmp_metadata
        extra = wmp_metadata(args.strata_band)   # UC-2 hook; DataFloorViolationError guard applies
    return BundleAssembler().assemble(sanitized_matrix=matrix, humanity_proof=humanity,
                                      recency=recency, consent=consent, synthetic=False,
                                      extra_metadata=extra)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wmp_export",
        description="WMP-2 exporter (fixtures + Phase-2 real path behind the consent gate).",
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
                   help="Gamer wallet address (the on-chain consent subject).")
    # ── Phase-2 real path (INC-3) ──────────────────────────────────────
    p.add_argument("--real", action="store_true",
                   help="Export ONE real bundle. Requires the on-chain world-model consent "
                        "view-call to return True for --gamer (WMP-4 deployed + granted).")
    p.add_argument("--matrix", type=Path, default=None,
                   help="private-inputs JSON from scripts/wmp_regen_matrix.py")
    p.add_argument("--vhr-proof", type=Path, default=None, help="snarkjs proof.json")
    p.add_argument("--vhr-public", type=Path, default=None, help="snarkjs public.json")
    p.add_argument("--session-id", default="")
    p.add_argument("--session-verdict", default="HUMAN")
    p.add_argument("--verifier-address", default="")
    p.add_argument("--recency-open", type=int, default=0)
    p.add_argument("--recency-open-hash", default="")
    p.add_argument("--recency-close", type=int, default=0)
    p.add_argument("--recency-close-hash", default="")
    p.add_argument("--beacon-registry",
                   default="0x962440312a995b21d4E203bE6d93021CC22bA051")
    p.add_argument("--consent-manifest-registry",
                   default="0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743")
    p.add_argument("--consent-manifest-hash", default="")
    p.add_argument("--strata-band", default="",
                   help="optional UC-2 band label (rides as extra_metadata)")
    args = p.parse_args(argv)

    # ── deferred-export guard ──────────────────────────────────────────
    # Real-data export gate: the on-chain consent view-call (env-configured) or hard-False.
    real_data_ok = world_model_consent_present(args.gamer)
    if args.real:
        if not real_data_ok:
            sys.stderr.write(
                "[wmp_export] REFUSING --real export — on-chain world-model consent is NOT "
                "granted for this gamer (or WORLD_MODEL_CONSENT_REGISTRY_ADDRESS is unset).\n"
                "  Deploy WMP-4 + run contracts/scripts/set-world-model-consent.js first.\n")
            return 2
        for req_name in ("matrix", "vhr_proof", "vhr_public", "session_id", "gamer"):
            if not getattr(args, req_name):
                sys.stderr.write(f"[wmp_export] --real requires --{req_name.replace('_', '-')}\n")
                return 2
        bundles = [_build_real_bundle(args)]
    elif not real_data_ok and not args.allow_fixtures:
        sys.stderr.write(
            "[wmp_export] REFUSING real-data export — world-model consent "
            "is DEFERRED in v1 (W1-D).\n"
            "  v1 requires --allow-fixtures plus --fixture-corpus PATH.\n"
            "  See docs/world-model-provenance.md §W1-D for the deferral\n"
            "  rationale and the Phase-2 promote path.\n"
        )
        return 2
    # ── fixtures path ──────────────────────────────────────────────────
    elif args.allow_fixtures:
        if args.fixture_corpus is None:
            sys.stderr.write("[wmp_export] --allow-fixtures requires --fixture-corpus PATH\n")
            return 2
        bundles = _load_fixture_corpus(args.fixture_corpus)
    else:
        # Consent readable but no mode selected — demand explicitness, never guess.
        sys.stderr.write("[wmp_export] choose --real (one real bundle) or --allow-fixtures\n")
        return 2

    summary = export_bundles(
        bundles, out_dir=args.out, dry_run=args.dry_run,
    )
    summary["dry_run"] = bool(args.dry_run)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
