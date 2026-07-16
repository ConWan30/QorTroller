"""A2A-STEWARD-EVOLVE B1 — Guardian PCRA (Protocol Claim Residue Auditor).

The novel autonomous task for Guardian (the 0-IOTX autonomous steward): treat the engineering NARRATIVE
as a first-class integrity surface. No steward does this today — FSCA watches fleet coherence, the
honesty-board tracks weekly snapshots, Mythos curates CLAUDE.md — but nobody audits the `docs/a2a/**`
A2A transcript tree + `audits/**` bankings against the machine oracles. PCRA drafts (never acts) findings
where a written claim has drifted from measured reality.

Residue classes (v0 — mechanically precise, high-confidence):
  CEILING_OVERCLAIM  a scanned surface asserts a capability the oracle denies (e.g. text implies presence
                     is proven / poep flipped while `poep_enabled=False`).
  STALE_ANCHOR       a claimed anchor/figure drifts from its live oracle (wallet, contract count, PV-CI).
  UNBANKED_BUILD     an A2A round claims SHIP/PASS with no corresponding audits/** banking.
(v0.1 named-not-dropped: ORPHAN_CLAIM (claim-extraction NLP), MAY_CLAIM_VIOLATION (per-product registry).)

RAILS: PCRA emits DRAFTS ONLY (local records, gitignored) — never git, never chain, never an act. It does
NOT self-grade; precision is later scored by SEL (B4) on operator accept/overturn. Gated by
`cfg.pcra_enabled` (default False). Pure detectors (testable) + a read-only repo adapter.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

SCHEMA = "qortroller-pcra-v0"
RESIDUE_CLASSES = ("CEILING_OVERCLAIM", "STALE_ANCHOR", "UNBANKED_BUILD")


@dataclass(frozen=True)
class OverclaimRule:
    """If `pattern` matches a surface AND oracle[oracle_key] != expect -> the surface over-claims."""
    pattern: str
    oracle_key: str
    expect: bool
    label: str
    severity: str = "HIGH"


# Default rules — the presence/flip discipline this whole codebase guards. Extend as new gates appear.
DEFAULT_OVERCLAIM_RULES = (
    OverclaimRule(r"poep[_ ]?enabled\s*(?:=|:|is)?\s*true|presence\s+(?:is\s+)?proven|flip(?:ped)?\s+"
                  r"poep|presence\s+verified\b", "poep_enabled", True, "presence/poep-flip asserted"),
    OverclaimRule(r"l6b[_ ]?enabled\s*(?:=|:|is)?\s*true|reflex\s+gate\s+(?:reached|met)\b",
                  "l6b_enabled", True, "L6B gate/flip asserted"),
    OverclaimRule(r"tournament[- ]?block\s+ready|separation\s+ratio\s*>\s*1\.0\s+for\s+hard",
                  "tournament_block_ready", True, "tournament-BLOCK readiness asserted"),
)


@dataclass(frozen=True)
class PcraFinding:
    residue_class: str
    claim_id: str                      # stable id: "<path>#<label>"
    severity: str
    evidence_refs: list                # file paths / oracle keys
    measured_vs_claimed: dict
    note: str
    schema: str = field(default=SCHEMA)


# --- pure detectors -------------------------------------------------------------------------------

# Negation / hedge markers near a match => the surface DISCUSSES the capability honestly (or refutes it),
# it does not ASSERT it. Guards against the dominant false-positive: this codebase's honest-negative docs
# ("poep_enabled stays False", "the flip is NOT earned", "not yet") constantly name the capability.
_NEGATION = re.compile(
    r"\b(?:not|no|never|false|stays?\s+false|refus\w*|declin\w*|held|without|isn'?t|aren'?t|"
    r"won'?t|can'?t|cannot|doesn'?t|don'?t|un\w*|deferred|gated|pending|would|if\b|until|"
    r"stays?\s+off|remain\w*\s+false|"
    # definitional / hypothetical markers => the surface DEFINES or DISCUSSES the claim, not asserts it
    r"propos\w*|at\s+stake|hypothetic\w*|example|e\.g|means?\b|in\s+order\s+to|to\s+even|claim\s+at)\b"
    r"|⇒|=>|→", re.IGNORECASE)
_NEG_WINDOW = 90   # chars each side of a match to inspect for negation/hedge


def detect_ceiling_overclaim(surfaces: list[dict], oracles: dict,
                             rules: tuple = DEFAULT_OVERCLAIM_RULES) -> list[PcraFinding]:
    """surfaces: [{path, text}]; oracles: {key: bool}. A surface over-claims when it AFFIRMATIVELY asserts
    a capability the oracle denies AND no negation/hedge sits within the match window (honest-negative
    prose must not trip). Missing oracle key -> treated as False (fail-closed).

    HONEST LIMIT (grok round-04): the negation/hedge window is a RECALL-CAPPED PRECISION AID, not a
    semantic assert-vs-deny classifier. It can (a) SUPPRESS a real affirmative overclaim that happens to
    sit within 90 chars of a hedge word ('if'/'held'/'until'/'un*'), and (b) still trip on bare config
    literals with no hedge. That is acceptable for a DRAFTER whose precision is scored externally by SEL
    on operator accept/overturn — PCRA proposes, it does not adjudicate. A false negative here is a missed
    draft, not a false claim; a false positive is a reviewable draft, not an action."""
    out: list[PcraFinding] = []
    for s in surfaces:
        text = str(s.get("text", ""))
        for r in rules:
            if bool(oracles.get(r.oracle_key, False)) == r.expect:
                continue
            m = re.search(r.pattern, text, re.IGNORECASE)
            if not m:
                continue
            window = text[max(0, m.start() - _NEG_WINDOW): m.end() + _NEG_WINDOW]
            if _NEGATION.search(window):
                continue          # honest discussion / refutation, not an assertion -> skip
            out.append(PcraFinding(
                residue_class="CEILING_OVERCLAIM", claim_id=f"{s.get('path')}#{r.oracle_key}",
                severity=r.severity, evidence_refs=[s.get("path"), f"oracle:{r.oracle_key}"],
                measured_vs_claimed={"claimed": r.label, "oracle_key": r.oracle_key,
                                     "oracle_value": bool(oracles.get(r.oracle_key, False)),
                                     "expected_for_claim": r.expect},
                note=f"surface AFFIRMATIVELY asserts '{r.label}' (no nearby negation) but oracle "
                     f"{r.oracle_key}={bool(oracles.get(r.oracle_key, False))}"))
    return out


def detect_stale_anchor(claimed_anchors: dict, live_anchors: dict) -> list[PcraFinding]:
    """claimed_anchors / live_anchors: {name: value}. Any name present in BOTH whose values differ is a
    stale anchor (the doc figure drifted from the live oracle)."""
    out: list[PcraFinding] = []
    for name, live in live_anchors.items():
        if name in claimed_anchors and str(claimed_anchors[name]) != str(live):
            out.append(PcraFinding(
                residue_class="STALE_ANCHOR", claim_id=f"anchor#{name}", severity="MED",
                evidence_refs=[f"anchor:{name}"],
                measured_vs_claimed={"anchor": name, "claimed": claimed_anchors[name], "live": live},
                note=f"anchor {name} claims {claimed_anchors[name]!r} but live is {live!r}"))
    return out


def detect_unbanked_build(a2a_rounds: list[dict], banked_tags: set) -> list[PcraFinding]:
    """a2a_rounds: [{path, ship: bool, tag}]. A round claiming SHIP/PASS whose build tag has no banking in
    audits/** is an unbanked build (a PASS asserted without a persisted audit record)."""
    out: list[PcraFinding] = []
    for r in a2a_rounds:
        if r.get("ship") and r.get("tag") and r["tag"] not in banked_tags:
            out.append(PcraFinding(
                residue_class="UNBANKED_BUILD", claim_id=f"{r.get('path')}#{r['tag']}", severity="LOW",
                evidence_refs=[r.get("path")],
                measured_vs_claimed={"tag": r["tag"], "claims_ship": True, "banked": False},
                note=f"A2A round claims SHIP for '{r['tag']}' with no audits/** banking"))
    return out


def detect_residue(*, surfaces: list[dict], oracles: dict, claimed_anchors: dict, live_anchors: dict,
                   a2a_rounds: list[dict], banked_tags: set,
                   rules: tuple = DEFAULT_OVERCLAIM_RULES) -> dict:
    """Run all v0 detectors -> the PCRA draft set. Pure; ordered most-severe first."""
    findings = (detect_ceiling_overclaim(surfaces, oracles, rules)
                + detect_stale_anchor(claimed_anchors, live_anchors)
                + detect_unbanked_build(a2a_rounds, banked_tags))
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: order.get(f.severity, 3))
    return {
        "schema": SCHEMA,
        "steward": "guardian",
        "task": "PCRA",
        "n_findings": len(findings),
        "by_class": {c: sum(1 for f in findings if f.residue_class == c) for c in RESIDUE_CLASSES},
        "findings": [asdict(f) for f in findings],
        "note": "DRAFTS ONLY — Guardian drafts, the operator acts. No git/chain write, no self-grading; "
                "precision is scored later by SEL on operator accept/overturn. poep/kill-switch untouched.",
    }


def scan_repo(cfg, repo_root) -> dict:  # pragma: no cover - read-only file/oracle adapter
    """Read-only repo adapter, gated by cfg.pcra_enabled (disabled marker when off).

    HONEST SCOPE (grok round-04): this v0 adapter wires ONLY the CEILING_OVERCLAIM detector (surfaces vs
    live flag oracles). The STALE_ANCHOR and UNBANKED_BUILD *pure detectors* are built + tested, but their
    repo adapters (SENSOR-A/live-figure extraction; A2A SHIP-tag ↔ audits banking) are v0.1 — this function
    does NOT invoke them (it would pass empty inputs and silently emit nothing, which is why they are
    excluded here rather than pretended). Drafts are returned IN-MEMORY; there is no persistence emitter in
    v0 (draft JSONL / Guardian drafting-loop hook are v0.1). Never git, never chain.
    """
    from pathlib import Path
    if not bool(getattr(cfg, "pcra_enabled", False)):
        return {"schema": SCHEMA, "enabled": False, "note": "pcra_enabled=False (opt-in capability)"}
    root = Path(repo_root)
    surfaces = []
    for sub in ("docs/a2a", "audits"):
        d = root / sub
        if d.exists():
            for p in list(d.rglob("*.md"))[:400] + list(d.rglob("*.txt"))[:400]:
                try:
                    surfaces.append({"path": str(p.relative_to(root)), "text": p.read_text(encoding="utf-8")})
                except Exception:  # noqa: BLE001
                    pass
    oracles = {
        "poep_enabled": bool(getattr(cfg, "poep_enabled", False)),
        "l6b_enabled": bool(getattr(cfg, "l6b_enabled", False)),
        # static reflection of the known-open hard-BLOCK gate (separation ratio < 1.0); v0.1 wires a live
        # separation-ratio oracle so this self-updates when/if the gate clears.
        "tournament_block_ready": False,
    }
    findings = detect_ceiling_overclaim(surfaces, oracles)
    return {
        "schema": SCHEMA, "enabled": True, "steward": "guardian", "task": "PCRA",
        "adapter_scope": "CEILING_OVERCLAIM only (v0); STALE_ANCHOR + UNBANKED_BUILD detectors ready, "
                         "repo adapters v0.1",
        "n_findings": len(findings),
        "findings": [asdict(f) for f in findings],
        "note": "DRAFTS ONLY, in-memory (no persistence emitter in v0) — Guardian drafts, the operator "
                "acts; no self-grading (SEL scores precision later); no git/chain; poep/kill-switch untouched.",
    }
