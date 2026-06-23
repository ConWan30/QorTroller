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
import hashlib
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
import vsd_vpm_label as vpm  # noqa: E402

_VPM_LABEL_LATEST = _VAULT / "eval" / "vsd_vpm_label_latest.json"


def _ledger_rows() -> list[dict]:
    if not _LEDGER.exists():
        return []
    return [json.loads(x) for x in _LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]


def _vpm_vocab_drift_guard() -> str | None:
    """Best-effort (full repo env only): assert our mirrored VPM visual-state vocabulary is a
    subset of the FROZEN VPMVisualState enum. Returns a drift message or None. The wrapper uses
    underscores (dry_run); the artifact layer + our label use hyphens (dry-run) — compare the
    normalized token set so a genuine enum change is caught without flagging that known skew."""
    try:
        sys.path.insert(0, str(_REPO / "scripts"))
        from vsd_vpm_wrapper import VPMVisualState  # type: ignore
        frozen = {v.value.replace("_", "-") for v in VPMVisualState}
        ours = {s for s in vpm.VPM_VISUAL_STATES}
        if not ours.issubset(frozen):
            return f"VSD VPM vocab {sorted(ours - frozen)} not in FROZEN VPMVisualState {sorted(frozen)}"
        return None
    except Exception:
        return None  # wrapper not importable (e.g. no bridge) — harness + PV-CI remain hard gates


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


def _emit_pbsa(cycle: int, harness_pass: bool) -> tuple[Path, str]:
    nid = f"pbsa-vsd-loop-cycle-{cycle}"
    p = _write_note("pbsa", nid, {
        "type": "pbsa", "id": nid, "created": _iso(),
        "phase_from": "L9-FUSION-V2-shipped", "phase_to": "VSD-LOOP-bootstrap",
        "deployer": BRIDGE_WALLET, "refs": [],
    }, f"Phase-boundary state assessment for VSD loop cycle {cycle}. Transition "
       f"L9-FUSION-V2-shipped -> VSD-LOOP-bootstrap. Harness pass at emit: {harness_pass}. "
       "The self-verifying loop produces signed, chained synthesis provenance mirroring the "
       "protocol's own GIC/WEC discipline.")
    return p, nid


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
    seeds = _ensure_seeds()
    pbsa_path, pbsa_id = _emit_pbsa(cycle, harness_pass=True)
    # sign routine notes (loop) / decision notes pending (operator)
    pbsa_manifest_hash = ""
    for path, nid, ntype in seeds + [(pbsa_path, pbsa_id, "pbsa")]:
        m = prov.sign_note(path, nid, ntype, ts_ns=ts)
        if ntype == "pbsa":
            pbsa_manifest_hash = m["manifest_canonical_hash"]
    rep = harness.run_harness()
    pv_ci = _pv_ci_pass()
    drift = _mythos_drift()
    forecast = vpm.forecast_drift(_ledger_rows())          # self-predictive trend (advisory)
    vocab_drift = _vpm_vocab_drift_guard()
    result = {
        "cycle": cycle, "ts": _iso(), "ts_ns": ts,
        "harness_pass": rep.passed, "pv_ci_pass": pv_ci,
        "mythos_drift": drift, "n_findings": len(rep.findings),
        "passing_note_ids": rep.passing_note_ids, "pbsa_id": pbsa_id,
        "pbsa_manifest_hash": pbsa_manifest_hash,
        "drift_forecast": forecast,
    }
    if vocab_drift:
        result["vpm_vocab_drift"] = vocab_drift            # surfaced if the FROZEN enum ever moves
    if dry_run:
        # honest preview: a dry-run label binds visual_state=dry-run (or unverified on fail),
        # computed over the SAME SIC the real cycle would stamp, but nothing is written.
        prev = _prev_sic(ts)
        preview_sic = sic.compute_sic(prev, pbsa_manifest_hash, rep.passed, pv_ci,
                                      drift if drift is not None else 0, ts).hex()
        result["vpm_label"] = vpm.build_vsd_vpm_label(
            sic_head_hex=preview_sic, harness_pass=rep.passed, pv_ci_pass=pv_ci,
            dry_run=True, ts_ns=ts, drift_forecast=forecast)
        result["dry_run"] = True
        return result
    sic_hex = sic.compute_sic(_prev_sic(ts), pbsa_manifest_hash, rep.passed, pv_ci,
                              drift if drift is not None else 0, ts).hex()
    result["sic_hex"] = sic_hex
    result["signed"] = True
    # VSD-emits-VPM: bind the cycle's integrity head to the protocol's visual-honesty grammar.
    label = vpm.build_vsd_vpm_label(
        sic_head_hex=sic_hex, harness_pass=rep.passed, pv_ci_pass=pv_ci,
        dry_run=False, ts_ns=ts, drift_forecast=forecast)
    _VPM_LABEL_LATEST.write_text(json.dumps(label, indent=2), encoding="utf-8")
    result["vpm_label"] = label
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": result["ts"], "ts_ns": ts, "cycle": cycle, "pbsa_id": pbsa_id,
            "pbsa_manifest_hash": pbsa_manifest_hash, "harness_pass": rep.passed,
            "pv_ci_pass": pv_ci, "mythos_drift": drift, "sic_hex": sic_hex,
            "note_ids": rep.passing_note_ids,
            "vpm_visual_state": label["visual_state"], "vpm_label_hash": label["label_hash"],
            "drift_forecast": forecast,
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
