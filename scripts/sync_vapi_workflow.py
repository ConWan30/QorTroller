"""
sync_vapi_workflow.py — VAPI WORKFLOW.v2 Sync Recovery Script (Phase 223 rewrite)

PURPOSE: Keeps VAPI-WORKFLOW.v2 context files synchronized with CLAUDE.md (single source of truth).
         Run after every phase completion. Prevents drift after Claude session disconnects.

USAGE:
    python scripts/sync_vapi_workflow.py              # full sync
    python scripts/sync_vapi_workflow.py --check      # check drift only, no writes
    python scripts/sync_vapi_workflow.py --phase-only # update phase/test counts only

TRIGGERS:
    - Manually: After every phase COMPLETE
    - Automatically: Via PostToolUse hook in settings.json (Write on CLAUDE.md)
    - Recovery: At session start when drift detected

WIF-026 MITIGATION: Closes context drift after Claude session disconnect.
Pattern: CLAUDE.md is the single source of truth; WORKFLOW.v2 files are derived views.

Phase 223 FIXES:
  - SDK regex now matches 3+ digits (was 2-3 digits, missed 484+)
  - Bridge regex now matches 4+ digits (was 3-4 digits, missed 2308+)
  - update_context_test_counts() uses actual table format with bold+comma counts
  - Added update_agents_md() for VAPI_AGENTS.md phase header sync
  - Added update_invariants_md() for VAPI_INVARIANTS.md phase header sync
  - PostToolUse hook should NOT use head -5 (errors were being suppressed)
"""

import re
import sys
import os
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
WORKFLOW_DIR = REPO_ROOT / "VAPI-WORKFLOW.v2"
CONTEXT_MD = WORKFLOW_DIR / "VAPI_CONTEXT.md"
MEMORY_MD = WORKFLOW_DIR / "VAPI_MEMORY.md"
AGENTS_MD = WORKFLOW_DIR / "VAPI_AGENTS.md"
INVARIANTS_MD = WORKFLOW_DIR / "VAPI_INVARIANTS.md"


# ── Extraction ─────────────────────────────────────────────────────────────────
def extract_claude_md_state(claude_md_path: Path) -> dict:
    """
    Extracts key state values from CLAUDE.md header.
    Returns dict with: phase_num, phase_desc, bridge, hardhat, sdk, agents, separation_ratio
    """
    text = claude_md_path.read_text(encoding="utf-8")
    state = {}

    # Current phase: Phase NNN — Description
    m = re.search(r"Current phase: Phase (\d+) — ([^\n(]+)", text)
    if m:
        state["phase_num"] = int(m.group(1))
        state["phase_desc"] = m.group(2).strip()

    # Bridge test count — matches "Bridge: 2328" or "Bridge 2328" (4+ digits)
    m = re.search(r"Bridge[:\s]+(\d{4,})\b", text)
    if m:
        state["bridge"] = int(m.group(1))

    # Hardhat: "Hardhat: 496" or "Hardhat 496" (3+ digits)
    m = re.search(r"Hardhat[:\s]+(\d{3,})\b", text)
    if m:
        state["hardhat"] = int(m.group(1))

    # SDK: "SDK: 484" or "SDK 484" (3+ digits — Phase 223 fix: was \d{2,3})
    m = re.search(r"\bSDK[:\s]+(\d{3,})\b", text)
    if m:
        state["sdk"] = int(m.group(1))

    # Agent count from header: "agents NN unchanged" or "agents NN→NN" in Current phase line
    # Search the Current phase line specifically to avoid matching buried phase descriptions
    _phase_line_m = re.search(r"Current phase:.*?agents\s+(\d+)", text)
    if _phase_line_m:
        state["agents"] = int(_phase_line_m.group(1))
    else:
        m = re.search(r"(\d+)\s+agents\b", text)
        if m:
            state["agents"] = int(m.group(1))

    # Contracts count: "45 contracts" or "contracts 45"
    m = re.search(r"(\d+)\s+contracts?\b", text, re.IGNORECASE)
    if not m:
        m = re.search(r"contracts?\s+(\d+)\b", text, re.IGNORECASE)
    if m:
        state["contracts"] = int(m.group(1))

    # Separation ratio — touchpad_corners latest
    m = re.search(r"separation ratio.*?(\d+\.\d+).*?touchpad_corners", text, re.IGNORECASE)
    if m:
        state["separation_touchpad"] = float(m.group(1))

    return state


def extract_workflow_state(context_md_path: Path) -> dict:
    """Extracts current state from VAPI_CONTEXT.md for drift comparison."""
    if not context_md_path.exists():
        return {}
    text = context_md_path.read_text(encoding="utf-8")
    state = {}

    m = re.search(r"\*\*Active Phase\*\*: Phase (\d+)", text)
    if m:
        state["phase_num"] = int(m.group(1))

    # Table format: | Bridge pytest | **2,184** | or | Bridge pytest | 2184 |
    m = re.search(r"\| Bridge pytest \| \*?\*?[\d,]+\*?\*?", text)
    if m:
        digits = re.search(r"[\d,]+", m.group(0).split("|")[-1])
        if digits:
            state["bridge"] = int(digits.group(0).replace(",", ""))

    m = re.search(r"\| SDK tests \| \*?\*?[\d,]+", text)
    if m:
        digits = re.search(r"[\d,]+", m.group(0).split("|")[-1])
        if digits:
            state["sdk"] = int(digits.group(0).replace(",", ""))

    return state


# ── Sync Operations ────────────────────────────────────────────────────────────
def check_drift(claude_state: dict, workflow_state: dict) -> list[str]:
    """Returns list of drift items. Empty = no drift."""
    drifts = []
    if claude_state.get("phase_num") != workflow_state.get("phase_num"):
        drifts.append(
            f"PHASE: CLAUDE.md={claude_state.get('phase_num')} "
            f"CONTEXT.md={workflow_state.get('phase_num')}"
        )
    if claude_state.get("bridge") != workflow_state.get("bridge"):
        drifts.append(
            f"BRIDGE: CLAUDE.md={claude_state.get('bridge')} "
            f"CONTEXT.md={workflow_state.get('bridge')}"
        )
    if claude_state.get("sdk") != workflow_state.get("sdk"):
        drifts.append(
            f"SDK: CLAUDE.md={claude_state.get('sdk')} "
            f"CONTEXT.md={workflow_state.get('sdk')}"
        )
    return drifts


def update_context_phase(context_md_path: Path, claude_state: dict) -> bool:
    """Updates Active Phase line in VAPI_CONTEXT.md."""
    text = context_md_path.read_text(encoding="utf-8")
    new_phase_line = (
        f"**Active Phase**: Phase {claude_state['phase_num']} — "
        f"{claude_state.get('phase_desc', 'COMPLETE')}"
    )
    updated = re.sub(
        r"\*\*Active Phase\*\*: Phase \d+ — [^\n]+",
        new_phase_line,
        text,
    )
    if updated == text:
        return False
    context_md_path.write_text(updated, encoding="utf-8")
    return True


def update_context_test_counts(context_md_path: Path, claude_state: dict) -> bool:
    """Updates the test suite status table in VAPI_CONTEXT.md.

    Handles both bold-comma format: | Bridge pytest | **2,336** | ✅ PASS | 2026-04-17 |
    and plain format:               | Bridge pytest | 2336 | ✅ PASS | 2026-04-17 |
    """
    text = context_md_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    bridge = claude_state.get("bridge", "?")
    sdk = claude_state.get("sdk", "?")
    hardhat = claude_state.get("hardhat", "?")

    # Format large numbers with comma and bold: **2,336**
    def _fmt(n):
        if isinstance(n, int) and n >= 1000:
            return f"**{n:,}**"
        return str(n)

    updated = text

    # Bridge pytest — matches both bold-comma and plain formats
    updated = re.sub(
        r"(\| Bridge pytest \|) \*?\*?[\d,]+\*?\*? (\| ✅ PASS \|) [^\|]+(\|)",
        rf"\1 {_fmt(bridge)} \2 {today} \3",
        updated,
    )
    # SDK tests
    updated = re.sub(
        r"(\| SDK tests \|) \*?\*?[\d,]+\*?\*?(?:\s*\([^)]+\))? (\| ✅ PASS \|) [^\|]+(\|)",
        rf"\1 {_fmt(sdk)} \2 {today} \3",
        updated,
    )
    # Hardhat tests
    updated = re.sub(
        r"(\| Hardhat tests \|) \*?\*?[\d,]+\*?\*? (\| ✅ PASS \|) [^\|]+(\|)",
        rf"\1 {_fmt(hardhat)} \2 {today} \3",
        updated,
    )
    if updated == text:
        return False
    context_md_path.write_text(updated, encoding="utf-8")
    return True


def update_context_next_phase(context_md_path: Path, claude_state: dict) -> bool:
    """Updates Next Phase line."""
    text = context_md_path.read_text(encoding="utf-8")
    next_phase = claude_state["phase_num"] + 1
    updated = re.sub(
        r"\*\*Next Phase\*\*: Phase \d+ \([^\)]+\)",
        f"**Next Phase**: Phase {next_phase} (TBD — user approval required)",
        text,
    )
    if updated == text:
        return False
    context_md_path.write_text(updated, encoding="utf-8")
    return True


def update_agents_md(agents_md_path: Path, claude_state: dict) -> bool:
    """Updates phase reference in VAPI_AGENTS.md SYNC NOTE line.

    Targets: > **SYNC NOTE**: ... Protocol at Phase NNN COMPLETE.
    """
    if not agents_md_path.exists():
        return False
    text = agents_md_path.read_text(encoding="utf-8")
    phase = claude_state.get("phase_num", "?")
    agents = claude_state.get("agents", "?")
    today = datetime.now().strftime("%Y-%m-%d")

    # Update SYNC NOTE line (may contain "Protocol at Phase NNN COMPLETE")
    updated = re.sub(
        r"(> \*\*SYNC NOTE\*\*:.*?Protocol at Phase )\d+( COMPLETE\.)",
        rf"\g<1>{phase}\2",
        text,
    )
    # Update agent fleet count line: "VAPI operates **36 specialized agents**"
    updated = re.sub(
        r"VAPI operates \*\*\d+ specialized agents\*\*",
        f"VAPI operates **{agents} specialized agents**",
        updated,
    )
    # Update header dry_run/agents/phase summary line if present
    updated = re.sub(
        r"(dry_run=True.*?agents.*?;.*?Phase )\d+( COMPLETE)",
        rf"\g<1>{phase}\2",
        updated,
    )
    if updated == text:
        return False
    agents_md_path.write_text(updated, encoding="utf-8")
    return True


def update_invariants_md(invariants_md_path: Path, claude_state: dict) -> bool:
    """Updates phase reference in VAPI_INVARIANTS.md SYNC NOTE line."""
    if not invariants_md_path.exists():
        return False
    text = invariants_md_path.read_text(encoding="utf-8")
    phase = claude_state.get("phase_num", "?")

    # Look for any "Phase NNN COMPLETE" in sync-note lines
    updated = re.sub(
        r"(> \*\*SYNC NOTE\*\*:.*?Phase )\d+( COMPLETE)",
        rf"\g<1>{phase}\2",
        text,
    )
    # Also update any "Protocol at Phase NNN" reference
    updated = re.sub(
        r"(Protocol at Phase )\d+( COMPLETE)",
        rf"\g<1>{phase}\2",
        updated,
    )
    if updated == text:
        return False
    invariants_md_path.write_text(updated, encoding="utf-8")
    return True


def append_memory_sync_note(memory_md_path: Path, claude_state: dict, drifts: list[str]) -> bool:
    """Appends a sync recovery note to VAPI_MEMORY.md if there was drift."""
    if not drifts:
        return False
    if not memory_md_path.exists():
        return False
    text = memory_md_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    phase = claude_state.get("phase_num", "?")
    bridge = claude_state.get("bridge", "?")
    sdk = claude_state.get("sdk", "?")

    sync_entry = f"""
### {today}: WORKFLOW SYNC — Phase {phase} drift recovered

**Trigger**: sync_vapi_workflow.py automatic recovery
**Drift detected**: {'; '.join(drifts)}
**Corrected to**: Phase {phase} | Bridge {bridge} | SDK {sdk}
**Action**: VAPI_CONTEXT.md phase/test counts updated from CLAUDE.md ground truth.

---
"""
    # Insert after "## 1. Session Outcomes (Chronological, Newest First)"
    marker = "## 1. Session Outcomes (Chronological, Newest First)\n"
    if marker in text:
        updated = text.replace(marker, marker + sync_entry, 1)
        memory_md_path.write_text(updated, encoding="utf-8")
        return True
    return False


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    check_only = "--check" in sys.argv
    phase_only = "--phase-only" in sys.argv

    print(f"[sync_vapi_workflow] Reading CLAUDE.md...", flush=True)
    if not CLAUDE_MD.exists():
        print(f"ERROR: CLAUDE.md not found at {CLAUDE_MD}", file=sys.stderr)
        sys.exit(1)

    claude_state = extract_claude_md_state(CLAUDE_MD)
    workflow_state = extract_workflow_state(CONTEXT_MD)

    print(f"[sync_vapi_workflow] CLAUDE.md state: {claude_state}", flush=True)
    print(f"[sync_vapi_workflow] CONTEXT.md state: {workflow_state}", flush=True)

    drifts = check_drift(claude_state, workflow_state)

    if not drifts:
        print("[sync_vapi_workflow] No drift detected — WORKFLOW.v2 files are current.", flush=True)
        return

    print(f"[sync_vapi_workflow] DRIFT DETECTED ({len(drifts)} items):", flush=True)
    for d in drifts:
        print(f"  {d}", flush=True)

    if check_only:
        print("[sync_vapi_workflow] --check mode: no writes performed.", flush=True)
        sys.exit(1)

    # Apply updates
    changed = []
    if update_context_phase(CONTEXT_MD, claude_state):
        changed.append("CONTEXT.md active phase")
    if update_context_test_counts(CONTEXT_MD, claude_state):
        changed.append("CONTEXT.md test counts")
    if update_context_next_phase(CONTEXT_MD, claude_state):
        changed.append("CONTEXT.md next phase")
    if not phase_only:
        if append_memory_sync_note(MEMORY_MD, claude_state, drifts):
            changed.append("MEMORY.md sync note")
        if update_agents_md(AGENTS_MD, claude_state):
            changed.append("AGENTS.md phase ref")
        if update_invariants_md(INVARIANTS_MD, claude_state):
            changed.append("INVARIANTS.md phase ref")

    if changed:
        print(f"[sync_vapi_workflow] Updated: {', '.join(changed)}", flush=True)
    else:
        print(
            "[sync_vapi_workflow] WARNING: Drift found but no table patterns matched.\n"
            "    Run manually: python scripts/sync_vapi_workflow.py --check",
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    main()
