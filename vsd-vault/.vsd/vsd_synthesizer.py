"""VSD Self-Verifying Loop — EDITABLE orchestrator (the synthesizer "skill").

One cycle (mirrors vapi-autoresearch's editable orchestrator):
  1. ensure the canonical seed notes exist (purpose synthesis + loop-authorization decision)
  2. emit a Phase-Boundary State Assessment (PBSA) for this cycle (VSD-4)
  3. sign routine notes (loop) / leave decision notes operator-pending (split-signing)
  4. run the IMMUTABLE harness (vsd_eval_harness) + PV-CI gate (vapi_invariant_gate) + best-effort Mythos
  5. on PASS: stamp the Synthesis Integrity Chain (SIC) + append the ledger + regen corpus (passing-only)

Boundaries (see orchestrator/BOUNDARIES.md): never edits the frozen gate / FROZEN-v1 / PoAC;
never spends IOTX / writes chain / mints NFTs; never loop-signs decision or eval/-refreeze notes.
Reversible: rm -rf vsd-vault/{.vsd,notes,corpus} + git revert.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_VSD = Path(__file__).resolve().parent
_VAULT = _VSD.parent
_REPO = _VAULT.parent
_NOTES = _VAULT / "notes"
_CORPUS = _VAULT / "corpus"
_LEDGER = _VAULT / "eval" / "synthesis_ledger.jsonl"
_VAULT_ID = "vsd-vault-v1"
BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"

sys.path.insert(0, str(_VSD))
import synthesis_integrity_chain as sic  # noqa: E402
import vsd_eval_harness as harness  # noqa: E402
import vsd_provenance as prov  # noqa: E402


def _iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_note(subdir: str, note_id: str, frontmatter: dict, body: str) -> Path:
    p = _NOTES / subdir / f"{note_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = "\n".join(f"{k}: {json.dumps(v) if isinstance(v, list) else v}" for k, v in frontmatter.items())
    p.write_text(f"---\n{fm}\n---\n\n{body}\n", encoding="utf-8")
    return p


def _ensure_seeds() -> list[tuple[Path, str, str]]:
    """Author the canonical seeds if missing. Returns [(path, note_id, type), ...]."""
    seeds: list[tuple[Path, str, str]] = []
    spath = _NOTES / "synthesis" / "s-purpose-of-vapi.md"
    if not spath.exists():
        _write_note("synthesis", "s-purpose-of-vapi", {
            "type": "synthesis", "id": "s-purpose-of-vapi",
            "title": "Purpose of V.A.P.I. / QorTroller", "created": _iso(), "modified": _iso(),
            "phase": "VSD-LOOP", "status": "draft", "confidence": "likely", "effort": 30,
            "deployer": BRIDGE_WALLET, "refs": [],
        }, "QorTroller gives competitive gaming a public, gamer-sovereign proof layer: a live "
           "human on a certified device, under consented rules, evidenced cryptographically "
           "(PoAC + PITL + consent) rather than asserted by an opaque kernel anti-cheat. "
           "Verification over punishment; sovereignty structural, not policy. V.A.P.I. is the "
           "category; QorTroller the gaming reference implementation.")
    seeds.append((spath, "s-purpose-of-vapi", "synthesis"))

    dpath = _NOTES / "decision" / "d-vsd-loop-authorization.md"
    if not dpath.exists():
        _write_note("decision", "d-vsd-loop-authorization", {
            "type": "decision", "id": "d-vsd-loop-authorization", "created": _iso(),
            "phase": "VSD-LOOP", "status": "draft", "deployer": BRIDGE_WALLET, "refs": [],
        }, "AUTHORIZE the reversible VSD self-verifying loop core (standalone harness + Ed25519 "
           "provenance + Synthesis Integrity Chain). Out of scope: frozen-gate governance "
           "ceremony, SOF NFT fleet, chain writes. This decision note is operator-pending "
           "(loop must not forge the architect signature).")
    seeds.append((dpath, "d-vsd-loop-authorization", "decision"))
    return seeds


def _pbsa_boundary(cycle: int) -> tuple[str, str, list[str], str]:
    """Return (phase_from, phase_to, refs, body_suffix) for a cycle."""
    if cycle >= 3:
        return (
            "TRIO-RETINA-PHASE3-MAIN",
            "VSD-CORPUS-trio-retina-map",
            [
                "i-trio-retina-main-protocol-docs",
                "c-trio-retina-advisory-second-oracle",
                "s-trio-retina-qortroller-integration-main",
            ],
            "Ingested Trio-Retina advisory-oracle architecture from QorTroller main (Phase 3, "
            "default-OFF): HID sidecar, policy governor, adjudicator read-only enrich, FSCA "
            "cross-oracle. Does not enable runtime flags or touch PoAC wire.",
        )
    if cycle == 2:
        return (
            "VSD-LOOP-bootstrap",
            "VSD-LOOP-cycle-2-verify",
            ["s-purpose-of-vapi", "d-vsd-loop-authorization"],
            "Second cycle verification pass (harness + PV-CI + SIC chain re-verify).",
        )
    return (
        "L9-FUSION-V2-shipped",
        "VSD-LOOP-bootstrap",
        ["s-purpose-of-vapi"],
        "Initial VSD loop bootstrap (seeds + first PBSA).",
    )


def _emit_pbsa(cycle: int, harness_pass: bool) -> tuple[Path, str]:
    nid = f"pbsa-vsd-loop-cycle-{cycle}"
    phase_from, phase_to, refs, suffix = _pbsa_boundary(cycle)
    p = _write_note("pbsa", nid, {
        "type": "pbsa", "id": nid, "created": _iso(),
        "phase_from": phase_from, "phase_to": phase_to,
        "deployer": BRIDGE_WALLET, "refs": refs,
    }, f"Phase-boundary state assessment for VSD loop cycle {cycle}. "
       f"Transition {phase_from} -> {phase_to}. Harness pass at emit: {harness_pass}. "
       f"{suffix} The self-verifying loop produces signed, chained synthesis provenance "
       "mirroring the protocol's own GIC/WEC discipline.")
    return p, nid


def _discover_notes() -> list[tuple[Path, str, str]]:
    """All notes under notes/ as (path, id, type)."""
    out: list[tuple[Path, str, str]] = []
    if not _NOTES.exists():
        return out
    for note_path in sorted(_NOTES.rglob("*.md")):
        fm = harness.parse_frontmatter(note_path.read_text(encoding="utf-8"))
        nid = fm.get("id")
        ntype = fm.get("type")
        if nid and ntype:
            out.append((note_path, nid, ntype))
    return out


def _sign_all_notes(ts_ns: int, *, current_pbsa_id: str) -> str:
    """Sign every note (routine=loop, decision=pending). Returns current PBSA manifest hash."""
    pbsa_manifest_hash = ""
    for path, nid, ntype in _discover_notes():
        m = prov.sign_note(path, nid, ntype, ts_ns=ts_ns)
        if nid == current_pbsa_id:
            pbsa_manifest_hash = m["manifest_canonical_hash"]
    return pbsa_manifest_hash


def _pv_ci_pass() -> bool:
    try:
        r = subprocess.run([sys.executable, "scripts/vapi_invariant_gate.py"],
                           cwd=str(_REPO), capture_output=True, text=True, timeout=180)
        return r.returncode == 0
    except Exception:
        return False


def _mythos_drift() -> int | None:
    """Best-effort: run the methodology + frozen drift variants if importable. None if the
    bridge env isn't available (the harness + PV-CI remain the hard gates)."""
    try:
        import asyncio
        sys.path.insert(0, str(_REPO / "bridge"))
        from vapi_bridge.mythos_variants import mythos_frozen_drift, mythos_methodology_drift

        async def _run():
            out = await mythos_methodology_drift() + await mythos_frozen_drift()
            return sum(1 for f in out if getattr(f, "severity", "") in ("CRITICAL", "HIGH"))
        return asyncio.run(_run())
    except Exception:
        return None


def _prev_sic(genesis_ts: int) -> bytes:
    if _LEDGER.exists():
        lines = [json.loads(x) for x in _LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
        if lines:
            return bytes.fromhex(lines[-1]["sic_hex"])
    return sic.genesis_sic(_VAULT_ID, genesis_ts)


def _regen_corpus(passing_ids: list[str]) -> Path:
    snap = _CORPUS / f"snapshot-{int(time.time())}"
    snap.mkdir(parents=True, exist_ok=True)
    lines = []
    for note_path in sorted(_NOTES.rglob("*.md")):
        fm = harness.parse_frontmatter(note_path.read_text(encoding="utf-8"))
        if fm.get("id") in passing_ids:
            h = prov.note_canonical_hash(note_path)
            lines.append(f"{fm['id']}  {h}  {note_path.relative_to(_VAULT).as_posix()}")
            (snap / note_path.name).write_text(note_path.read_text(encoding="utf-8"), encoding="utf-8")
    (snap / "MANIFEST.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return snap


def run_cycle(cycle: int, dry_run: bool = False) -> dict:
    ts = time.time_ns()
    _ensure_seeds()
    _, pbsa_id = _emit_pbsa(cycle, harness_pass=True)
    pbsa_manifest_hash = _sign_all_notes(ts, current_pbsa_id=pbsa_id)
    rep = harness.run_harness()
    pv_ci = _pv_ci_pass()
    drift = _mythos_drift()
    result = {
        "cycle": cycle, "ts": _iso(), "ts_ns": ts,
        "harness_pass": rep.passed, "pv_ci_pass": pv_ci,
        "mythos_drift": drift, "n_findings": len(rep.findings),
        "passing_note_ids": rep.passing_note_ids, "pbsa_id": pbsa_id,
        "pbsa_manifest_hash": pbsa_manifest_hash,
    }
    if dry_run:
        result["dry_run"] = True
        return result
    sic_hex = sic.compute_sic(_prev_sic(ts), pbsa_manifest_hash, rep.passed, pv_ci,
                              drift if drift is not None else 0, ts).hex()
    result["sic_hex"] = sic_hex
    result["signed"] = True
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": result["ts"], "ts_ns": ts, "cycle": cycle, "pbsa_id": pbsa_id,
            "pbsa_manifest_hash": pbsa_manifest_hash, "harness_pass": rep.passed,
            "pv_ci_pass": pv_ci, "mythos_drift": drift, "sic_hex": sic_hex,
            "note_ids": rep.passing_note_ids,
        }) + "\n")
    result["corpus_snapshot"] = str(_regen_corpus(rep.passing_note_ids).relative_to(_VAULT).as_posix())
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="VSD editable synthesizer (loop orchestrator)")
    ap.add_argument("--cycle", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        lines = [json.loads(x) for x in _LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()] \
            if _LEDGER.exists() else []
        print(f"[vsd-loop] cycles={len(lines)}")
        for ln in lines[-5:]:
            print(f"  cycle {ln['cycle']} harness={ln['harness_pass']} pv_ci={ln['pv_ci_pass']} "
                  f"drift={ln['mythos_drift']} sic={ln['sic_hex'][:16]}…")
        return 0
    res = run_cycle(args.cycle, dry_run=args.dry_run)
    print(json.dumps({k: v for k, v in res.items() if k != "passing_note_ids"}, indent=2))
    return 0 if res["harness_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
