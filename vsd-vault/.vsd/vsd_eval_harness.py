"""VSD Self-Verifying Loop — IMMUTABLE synthesis harness (the deterministic checker).

The synthesis-domain twin of scripts/vapi_invariant_gate.py: a standalone, declarative-ground-
truth (eval/INVARIANTS.md) + executable checker that gates the editable orchestrator. It walks
notes/ and enforces the checkable VSD invariants:

  VSD-2  every routine note has a manifest that Ed25519-verifies; decision notes have a
         pending (operator) manifest with a valid content binding.
  VSD-3  honesty fields are HARNESS-CHECKED, not advisory prose: confidence in the 8 estimative
         words, integer effort, deployer == bridge wallet.
  VSD-4  at least one PBSA note exists (every cycle emits a phase-boundary assessment).
  VSD-5  reports the passing-note set so the orchestrator can regenerate corpus = passing-only.

Pure stdlib + vsd_provenance (Ed25519). Does NOT import or edit the frozen vapi_invariant_gate.py.
`python vsd-vault/.vsd/vsd_eval_harness.py --report` -> exit 0 (clean) / 1 (any CRITICAL|HIGH).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vsd_provenance as prov  # noqa: E402

_VAULT = Path(__file__).resolve().parent.parent
_NOTES = _VAULT / "notes"
_MANIFESTS = _VAULT / "manifests" / "notes"
BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"

# VSD-3: the 8 Kesselman estimative words (the only legal confidence values)
CONFIDENCE_WORDS = frozenset({
    "certain", "highly-likely", "likely", "possible",
    "unlikely", "highly-unlikely", "almost-certainly-not", "remote",
})
ROUTINE_TYPES = prov.ROUTINE_TYPES
ALL_TYPES = ROUTINE_TYPES | {"decision"}
# honesty fields required on claim/synthesis (the assertive note types)
HONESTY_TYPES = frozenset({"claim", "synthesis"})


@dataclass
class Finding:
    severity: str   # CRITICAL | HIGH | LOW
    note: str
    invariant: str
    message: str


@dataclass
class HarnessReport:
    findings: list[Finding] = field(default_factory=list)
    passing_note_ids: list[str] = field(default_factory=list)
    n_notes: int = 0

    @property
    def passed(self) -> bool:
        return not any(f.severity in ("CRITICAL", "HIGH") for f in self.findings)


def parse_frontmatter(text: str) -> dict:
    """Minimal YAML-frontmatter scalar parser (stdlib-only). [] -> empty list; ints coerced."""
    out: dict = {}
    if not text.startswith("---"):
        return out
    body = text.split("---", 2)
    if len(body) < 3:
        return out
    for line in body[1].splitlines():
        line = line.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v in ("[]", ""):
            out[k] = [] if v == "[]" else ""
        elif v.lstrip("-").isdigit():
            out[k] = int(v)
        else:
            out[k] = v
    return out


def _latest_manifest(note_id: str) -> Path | None:
    d = _MANIFESTS / note_id
    if not d.exists():
        return None
    revs = sorted(d.glob("*.manifest.json"))
    return revs[-1] if revs else None


def check_note(note_path: Path) -> tuple[list[Finding], bool]:
    """Check one note; returns (findings, passes) where passes means harness-clean."""
    fnd: list[Finding] = []
    try:
        rel = note_path.relative_to(_VAULT).as_posix()
    except ValueError:
        rel = note_path.as_posix()
    fm = parse_frontmatter(note_path.read_text(encoding="utf-8"))
    ntype = fm.get("type")
    nid = fm.get("id")
    if ntype not in ALL_TYPES:
        fnd.append(Finding("CRITICAL", rel, "SCHEMA", f"unknown/missing type {ntype!r}"))
        return fnd, False
    if not nid:
        fnd.append(Finding("CRITICAL", rel, "SCHEMA", "missing id"))
        return fnd, False
    # VSD-3 honesty fields (claim/synthesis)
    if ntype in HONESTY_TYPES:
        if fm.get("confidence") not in CONFIDENCE_WORDS:
            fnd.append(Finding("HIGH", rel, "VSD-3",
                               f"confidence {fm.get('confidence')!r} not in the 8 estimative words"))
        if not isinstance(fm.get("effort"), int):
            fnd.append(Finding("HIGH", rel, "VSD-3", "effort must be an integer (minutes)"))
        if fm.get("deployer") != BRIDGE_WALLET:
            fnd.append(Finding("HIGH", rel, "VSD-3", "deployer must be the bridge wallet"))
    # VSD-2 provenance manifest
    man = _latest_manifest(nid)
    if man is None:
        fnd.append(Finding("HIGH", rel, "VSD-2", f"no provenance manifest for {nid}"))
        return fnd, False
    ok, reason = prov.verify_note(note_path, man)
    if not ok:
        fnd.append(Finding("HIGH", rel, "VSD-2", f"manifest verify failed: {reason}"))
        return fnd, False
    # routine note must be loop-SIGNED; decision must be pending (not loop-forged)
    import json as _j
    m = _j.loads(man.read_text(encoding="utf-8"))
    if ntype in ROUTINE_TYPES and not m.get("signed"):
        fnd.append(Finding("HIGH", rel, "VSD-2", "routine note is unsigned"))
        return fnd, False
    if ntype == "decision" and m.get("signed"):
        fnd.append(Finding("CRITICAL", rel, "VSD-2", "decision note was loop-signed (must be operator)"))
        return fnd, False
    return fnd, True


def run_harness() -> HarnessReport:
    rep = HarnessReport()
    if not _NOTES.exists():
        rep.findings.append(Finding("CRITICAL", "notes/", "VAULT", "notes/ tree missing"))
        return rep
    for note_path in sorted(_NOTES.rglob("*.md")):
        rep.n_notes += 1
        fnd, passes = check_note(note_path)
        rep.findings.extend(fnd)
        if passes:
            fm = parse_frontmatter(note_path.read_text(encoding="utf-8"))
            rep.passing_note_ids.append(fm.get("id"))
    # VSD-4 + required seeds
    pbsa_dir = _NOTES / "pbsa"
    has_pbsa = pbsa_dir.exists() and any(pbsa_dir.glob("*.md"))
    if not has_pbsa:
        rep.findings.append(Finding("HIGH", "notes/pbsa/", "VSD-4", "no PBSA note present"))
    if not (_NOTES / "synthesis" / "s-purpose-of-vapi.md").exists():
        rep.findings.append(Finding("HIGH", "notes/synthesis/", "SEED",
                                    "required seed s-purpose-of-vapi.md missing"))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description="VSD immutable synthesis harness")
    ap.add_argument("--report", action="store_true")
    ap.parse_args()
    rep = run_harness()
    print(f"[vsd-harness] notes={rep.n_notes} passing={len(rep.passing_note_ids)} "
          f"findings={len(rep.findings)} -> {'PASS' if rep.passed else 'FAIL'}")
    for f in rep.findings:
        print(f"  [{f.severity}] {f.invariant} {f.note}: {f.message}")
    return 0 if rep.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
