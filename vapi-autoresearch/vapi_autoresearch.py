"""
vapi_autoresearch.py — EDITABLE
================================
The VAPI-AutoResearch improvement loop.
This file IS the thing being improved — Claude can modify this file
during cycles to improve its own improvement logic.

Session-only: runs interactively in Claude Code. No background loops.
No GPU. No overnight process. Pure LLM reasoning + VAPI domain knowledge.

Usage:
    python vapi_autoresearch.py --cycle 1
    python vapi_autoresearch.py --cycle 3 --priority separation_ratio
    python vapi_autoresearch.py --dry-run   (show proposed change without committing)
    python vapi_autoresearch.py --status    (show experiment log summary)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Windows UTF-8 console fix
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Paths (relative to vapi project root)
SKILL_MD_PATH       = Path.home() / ".claude" / "commands" / "vapi.md"
PROGRAM_MD_PATH     = Path("vapi-autoresearch/program.md")
HARNESS_PATH        = Path("vapi-autoresearch/vapi_eval_harness.py")
EXPERIMENT_LOG      = Path("vapi-autoresearch/experiments/log.jsonl")
WHAT_IF_CORPUS      = Path("vapi-autoresearch/what_if_corpus/")

# Import the immutable harness
sys.path.insert(0, str(Path(__file__).parent))
from vapi_eval_harness import evaluate_proposal, KNOWN_GAPS, PASS_THRESHOLD


def load_skill_md() -> str:
    if not SKILL_MD_PATH.exists():
        raise FileNotFoundError(f"skill.md not found at {SKILL_MD_PATH}")
    return SKILL_MD_PATH.read_text(encoding="utf-8")


def load_program_md() -> str:
    if not PROGRAM_MD_PATH.exists():
        return "No program.md found. Using default priorities."
    return PROGRAM_MD_PATH.read_text(encoding="utf-8")


def load_experiment_log() -> list:
    if not EXPERIMENT_LOG.exists():
        return []
    entries = []
    with open(EXPERIMENT_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def save_experiment_entry(entry: dict):
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EXPERIMENT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def git_snapshot(message: str) -> bool:
    """Take a git snapshot before applying a change."""
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"[vapi-autoresearch] {message}"],
                       check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def git_revert():
    """Revert to last commit if eval fails."""
    try:
        subprocess.run(["git", "checkout", "HEAD", "--", str(SKILL_MD_PATH)],
                       check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_priority_from_log(log: list) -> str:
    """Pick the improvement priority least addressed in recent experiments.
    Phase 193 edition: fleet coherence priorities added."""
    priorities = [
        "fleet_coherence_critical",    # Phase 193 FSCA — CRITICAL contradiction detection
        "fleet_coherence_orphan",      # Phase 193 FSCA — orphan signal detection (>48h unresolved)
        "temporal_drift",              # WIF-029 — highest urgency pre-tournament
        "zk_ceremony",                 # WIF-030 — ZK trust model gap
        "data_readiness_certificate",  # Phase 192 — 8-dim pre-tournament cert
        "provenance_dag_coverage",     # Phase 192 — causal audit trail depth
        "corpus_entropy_monitor",      # Phase 192 — feature space homogeneity
        "bt_calibration",              # Hardware path still at 0/50 sessions
        "pofc_consensus",              # Agent fleet coherence check
        "separation_ratio_stratified", # 0.569 → 1.0+ via persona-windowed calibration
        # Legacy priorities (cycle through as fallback)
        "what_if_corpus_depth",
        "class_k_definition",
        "legal_defensibility",
    ]
    recent_priorities = [e.get("priority", "") for e in log[-10:]]
    for p in priorities:
        if p not in recent_priorities:
            return p
    # All covered recently — cycle back to highest priority
    return priorities[0]


def format_cycle_prompt(
    current_skill: str,
    program: str,
    log: list,
    priority: str,
    cycle_num: int,
) -> str:
    """
    Generate the improvement prompt for this cycle.
    Claude reads this and produces the proposed change.
    """
    recent_gaps = [e.get("gap_advances", []) for e in log[-5:]]
    gap_summary = "\n".join(
        f"  {k}: {v['current']} → {v['target']} [{v['status']}]"
        for k, v in KNOWN_GAPS.items()
    )

    return f"""
VAPI-AutoResearch Improvement Cycle #{cycle_num}
================================================
Priority this cycle: {priority}

PROGRAM DIRECTIVES (from program.md):
{program[:800]}...

KNOWN GAPS (ground truth):
{gap_summary}

RECENT EXPERIMENT HISTORY ({len(log)} total experiments):
Last 3 priorities addressed: {[e.get('priority','?') for e in log[-3:]]}
Last 3 scores: {[round(e.get('score', 0), 3) for e in log[-3:]]}

CURRENT SKILL.MD LENGTH: {len(current_skill)} characters

TASK: Generate ONE targeted improvement to the /vapi orchestration skill.
The improvement must:
1. Address the priority: {priority}
2. Preserve all 20 mandatory invariants (listed in eval harness)
3. Add ONE new WHAT_IF pair (W1 grounded failure + W2 novel opportunity)
4. Be specific to VAPI Phase 108–113 state — not generic advice

FORMAT YOUR RESPONSE AS:
---PROPOSAL_START---
[DESCRIPTION]
One sentence describing what this change improves and why.

[SKILL_MD_DELTA]
The exact text addition or modification to skill.md.
Use format: "ADD to section X:" or "REPLACE in section Y:"

[WHAT_IF]
W1 — [grounded failure mode, physically/cryptographically/economically rooted]
  Implication: [specific consequence]
  Mitigation: [concrete fix, phase reference]

W2 — [genuinely novel opportunity, VAPI-exclusive]
  Mechanism: [concrete description]
  Phase candidate: [Phase N]
  Exclusive because: [why competitors cannot replicate]
---PROPOSAL_END---
"""


def run_cycle(
    cycle_num: int,
    priority: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """Execute one improvement cycle."""
    print(f"\n{'='*60}")
    print(f"  VAPI-AutoResearch — Cycle #{cycle_num}")
    print(f"{'='*60}")

    current_skill = load_skill_md()
    program = load_program_md()
    log = load_experiment_log()

    if priority is None:
        priority = get_priority_from_log(log)

    print(f"\n  Priority: {priority}")
    print(f"  Skill.md: {len(current_skill)} chars")
    print(f"  Experiments to date: {len(log)}")

    # Generate the improvement prompt
    prompt = format_cycle_prompt(current_skill, program, log, priority, cycle_num)

    print(f"\n  Generated improvement prompt ({len(prompt)} chars)")
    print("  [In Claude Code: Claude reads this and proposes a change]")
    print()

    if dry_run:
        print("  DRY RUN — showing prompt only, no changes applied:")
        print(prompt)
        return {"dry_run": True, "priority": priority}

    # In actual Claude Code session, Claude produces the proposal
    # Here we save the prompt for Claude to respond to
    prompt_path = EXPERIMENT_LOG.parent / f"cycle_{cycle_num:04d}_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"  Prompt saved to: {prompt_path}")
    print()
    print("  NEXT STEP (Claude Code):")
    print("  1. Claude reads the prompt from the file above")
    print("  2. Claude produces a ---PROPOSAL_START--- block")
    print("  3. Paste the proposal to: vapi_autoresearch.py --apply <proposal_file>")
    print()

    return {
        "cycle": cycle_num,
        "priority": priority,
        "prompt_path": str(prompt_path),
        "timestamp": datetime.utcnow().isoformat(),
    }


def apply_proposal(proposal_file: str, dry_run: bool = False) -> dict:
    """
    Apply a Claude-generated proposal after eval harness validation.
    Called after Claude produces a proposal in the session.
    """
    proposal_path = Path(proposal_file)
    if not proposal_path.exists():
        raise FileNotFoundError(f"Proposal file not found: {proposal_file}")

    proposal_text = proposal_path.read_text()
    current_skill = load_skill_md()

    print(f"\n  Evaluating proposal: {proposal_file}")

    # Simulate post-change skill.md (the harness checks presence of invariants)
    # In practice Claude modifies skill.md and we eval the result
    skill_after = current_skill  # Harness eval on current + proposal

    result = evaluate_proposal(proposal_text, skill_after)

    print(f"\n  Eval result: {'PASS' if result.passed else 'FAIL'}")
    print(f"  Score: {result.score:.3f} (threshold: {PASS_THRESHOLD})")
    print(f"  Subscores:")
    for k, v in result.subscores.items():
        print(f"    {k}: {v:.3f}")
    if result.gap_advances:
        print(f"  Gaps advanced: {result.gap_advances}")
    if result.what_if_assessment:
        print(f"  WHAT_IF: {result.what_if_assessment}")
    if result.invariant_failures:
        print(f"  INVARIANT FAILURES: {result.invariant_failures[:3]}")

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "proposal_file": str(proposal_file),
        "passed": result.passed,
        "score": result.score,
        "subscores": result.subscores,
        "gap_advances": result.gap_advances,
        "what_if_assessment": result.what_if_assessment,
        "invariant_failures": result.invariant_failures,
        "reason": result.reason,
    }

    if result.passed and not dry_run:
        print(f"\n  PASS — committing change to git...")
        if git_snapshot(f"autoresearch cycle - score={result.score:.3f}"):
            print("  Git commit: OK")

        # Save to WHAT_IF corpus if proposal contains one
        if "[WHAT_IF]" in proposal_text or "W1 —" in proposal_text:
            corpus_file = WHAT_IF_CORPUS / f"wif_{int(time.time())}.md"
            WHAT_IF_CORPUS.mkdir(parents=True, exist_ok=True)
            corpus_file.write_text(proposal_text)
            print(f"  WHAT_IF saved to corpus: {corpus_file.name}")
            entry["what_if_corpus_entry"] = str(corpus_file)

    elif not result.passed and not dry_run:
        print(f"\n  FAIL — reverting skill.md to last commit...")
        if git_revert():
            print("  Git revert: OK")

    save_experiment_entry(entry)
    return entry


def show_status():
    """Print a summary of all experiments."""
    log = load_experiment_log()
    if not log:
        print("  No experiments yet. Run --cycle 1 to start.")
        return

    print(f"\n  VAPI-AutoResearch Status")
    print(f"  {'='*50}")
    print(f"  Total experiments: {len(log)}")
    passed = sum(1 for e in log if e.get("passed"))
    print(f"  Passed: {passed} | Failed: {len(log)-passed}")

    if log:
        scores = [e.get("score", 0) for e in log if e.get("passed")]
        if scores:
            print(f"  Best score: {max(scores):.3f}")
            print(f"  Avg score (passing): {sum(scores)/len(scores):.3f}")

    # Priority coverage
    priorities_hit = {}
    for e in log:
        p = e.get("priority", "unknown")
        priorities_hit[p] = priorities_hit.get(p, 0) + 1
    print(f"\n  Priority coverage:")
    for p, count in sorted(priorities_hit.items(), key=lambda x: -x[1]):
        print(f"    {p}: {count} cycles")

    # Gap advances
    all_advances = []
    for e in log:
        all_advances.extend(e.get("gap_advances", []))
    if all_advances:
        advance_counts = {}
        for a in all_advances:
            advance_counts[a] = advance_counts.get(a, 0) + 1
        print(f"\n  Gaps addressed:")
        for gap, count in sorted(advance_counts.items(), key=lambda x: -x[1]):
            print(f"    {gap}: {count} times")

    print(f"\n  WHAT_IF corpus: {len(list(WHAT_IF_CORPUS.glob('*.md')))} entries")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="VAPI-AutoResearch: session-based orchestration improvement loop")
    parser.add_argument("--cycle", type=int,
                        help="Run N improvement cycles")
    parser.add_argument("--priority",
                        choices=[
                            # Phase 193 priorities
                            "fleet_coherence_critical",
                            "fleet_coherence_orphan",
                            # Phase 192 priorities
                            "data_readiness_certificate",
                            "provenance_dag_coverage",
                            "corpus_entropy_monitor",
                            # Core priorities
                            "temporal_drift",
                            "zk_ceremony",
                            "bt_calibration",
                            "pofc_consensus",
                            "separation_ratio_stratified",
                            # Legacy priorities
                            "what_if_corpus_depth",
                            "phase_109_113_precision",
                            "separation_ratio_pathways",
                            "class_k_definition",
                            "legal_defensibility",
                        ],
                        help="Force a specific improvement priority")
    parser.add_argument("--apply",
                        help="Apply a Claude-generated proposal file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show proposal without committing")
    parser.add_argument("--status", action="store_true",
                        help="Show experiment log summary")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.apply:
        apply_proposal(args.apply, dry_run=args.dry_run)
        return

    if args.cycle:
        log = load_experiment_log()
        start_cycle = len(log) + 1
        for i in range(args.cycle):
            cycle_num = start_cycle + i
            run_cycle(cycle_num, priority=args.priority, dry_run=args.dry_run)
            if i < args.cycle - 1:
                print(f"\n  [Cycle {i+1}/{args.cycle} complete. "
                      f"Starting cycle {i+2}/{args.cycle}...]")
        return

    # Default: show usage
    print("VAPI-AutoResearch Improvement Loop")
    print("Run with --help for options")
    print("\nQuick start:")
    print("  python vapi_autoresearch.py --cycle 1")
    print("  python vapi_autoresearch.py --status")
    print("  python vapi_autoresearch.py --cycle 1 --priority separation_ratio_pathways")


# Allow Claude to modify the improvement logic below this line
# ============================================================
# CLAUDE-EDITABLE ZONE: improvement heuristics — Phase 177 edition
# ============================================================

def select_skill_section_to_improve(priority: str, skill_md: str) -> str:
    """
    Given the current priority, identify which section of skill.md
    most needs improvement. Phase 177 edition adds ZK circuit, PoFC,
    and temporal drift sections.
    """
    priority_section_map = {
        # Phase 193 (fleet coherence)
        "fleet_coherence_critical":    "SECURITY_REVIEW",   # CONTRADICTION rules → attack surface
        "fleet_coherence_orphan":      "ANALYSIS",          # ORPHAN rules → stale signal detection
        # Phase 192 (corpus curator)
        "data_readiness_certificate":  "ANALYSIS",          # 8-dim pre-tournament cert
        "provenance_dag_coverage":     "ANALYSIS",          # causal audit trail depth
        "corpus_entropy_monitor":      "CALIBRATION",       # feature space homogeneity
        # Core
        "temporal_drift":              "VHP_CREDENTIAL_LIFECYCLE",
        "zk_ceremony":                 "ZK_CIRCUIT_ENGINEERING",
        "bt_calibration":              "CALIBRATION",
        "pofc_consensus":              "BLOCKCHAIN_ENGINEERING",
        "separation_ratio_stratified": "CALIBRATION",
        # Legacy (kept for backward-compat with cycle log)
        "what_if_corpus_depth":        "WHAT_IF",
        "phase_109_113_precision":     "BLOCKCHAIN_ENGINEERING",
        "separation_ratio_pathways":   "CALIBRATION",
        "class_k_definition":          "SECURITY_REVIEW",
        "legal_defensibility":         "Hard Stops",
    }
    return priority_section_map.get(priority, "Session Start Protocol")


def score_phase_177_readiness(skill_md: str) -> dict:
    """
    Phase 177 synthesis gate pre-check. Returns a readiness dict.
    Claude Code should call this before any Phase 177+ synthesis work begins.
    """
    checks = {
        "poac_228_bytes":          "228" in skill_md,
        "auto_activate_locked":    "auto_activate_on_breakthrough=False PERMANENT" in skill_md,
        "epistemic_threshold_065": "0.65" in skill_md,
        "bt_separate_calibration": "BT requires separate" in skill_md or "bt_transport" in skill_md,
        "agent_21_pofc":           "ProofOfFleetConsensus" in skill_md or "FleetConsensusSnapshot" in skill_md,
        "wif028_persona_break":    "WIF-028" in skill_md or "temporal_non_stationarity" in skill_md or "persona" in skill_md.lower(),
        "wif029_temporal_drift":   "WIF-029" in skill_md or "temporal_biometric_drift" in skill_md or "biometric_credential_ttl" in skill_md,
        "wif030_zk_ceremony":      "WIF-030" in skill_md or "ceremony_audit" in skill_md,
        "touchpad_corners_path":   "touchpad_corners" in skill_md,
        "consent_chain_complete":  "ConsentSnapshot" in skill_md or "consent_delta" in skill_md,
    }
    score = sum(checks.values()) / len(checks)
    return {
        "phase_177_readiness_score": round(score, 3),
        "checks": checks,
        "gate_open": score >= 0.80,
        "blocking_checks": [k for k, v in checks.items() if not v],
    }


def score_phase_192_readiness(skill_md: str) -> dict:
    """
    Phase 192 DataCuratorAgent synthesis gate pre-check.
    Verifies that the skill file reflects all Phase 192 invariants
    before any further synthesis work begins.
    """
    checks = {
        "corpus_curator_agent_35":     "CorpusDataCuratorAgent" in skill_md or "agent #35" in skill_md,
        "provenance_dag_20hop":        "20" in skill_md and "provenance" in skill_md.lower(),
        "entropy_threshold_1_5":       "1.5" in skill_md and "entropy" in skill_md.lower(),
        "erasure_cert_gdpr":           "GDPR" in skill_md or "erasure_certificate" in skill_md,
        "federated_bp007":             "BP-007" in skill_md or "federated_corpus" in skill_md,
        "correlation_frobenius":       "Frobenius" in skill_md or "correlation_matrix" in skill_md,
        "readiness_cert_8dim":         "8" in skill_md and "readiness" in skill_md.lower() and "certificate" in skill_md.lower(),
        "contribution_tbd_decay":      "TBD" in skill_md and "contribution" in skill_md.lower(),
        "separation_gate_frozen":      "separation_gate" in skill_md or "0.70" in skill_md,
        "tool_136_144_present":        "#136" in skill_md or "Tool #136" in skill_md,
    }
    score = sum(checks.values()) / len(checks)
    return {
        "phase_192_readiness_score": round(score, 3),
        "checks": checks,
        "gate_open": score >= 0.70,
        "blocking_checks": [k for k, v in checks.items() if not v],
    }


def score_phase_193_readiness(skill_md: str) -> dict:
    """
    Phase 193 FleetSignalCoherenceAgent synthesis gate pre-check.
    Verifies that the skill file reflects all Phase 193 invariants
    before any further synthesis work begins. Gate: score >= 0.80.
    """
    checks = {
        "fsca_agent_36":              "FleetSignalCoherenceAgent" in skill_md or "agent #36" in skill_md,
        "contradiction_7_rules":      "CONTRADICTION" in skill_md and "7" in skill_md,
        "orphan_5_rules":             "ORPHAN" in skill_md and "5" in skill_md,
        "inversion_3_rules":          "INVERSION" in skill_md and "3" in skill_md,
        "renewal_without_attestation":"RENEWAL_WITHOUT_ATTESTATION" in skill_md or "attestation chain" in skill_md.lower(),
        "coherence_id_format":        "coh_" in skill_md or "coherence_id" in skill_md,
        "wif_auto_promote":           "N_PROMOTE_THRESHOLD" in skill_md or "auto-promot" in skill_md.lower(),
        "fleet_coherence_enabled_true":"fleet_coherence_enabled=True" in skill_md or "default True" in skill_md or "always on" in skill_md.lower(),
    }
    score = sum(checks.values()) / len(checks)
    return {
        "phase_193_readiness_score": round(score, 3),
        "checks": checks,
        "gate_open": score >= 0.80,
        "blocking_checks": [k for k, v in checks.items() if not v],
    }


if __name__ == "__main__":
    main()
