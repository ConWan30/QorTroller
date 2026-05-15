"""Mythos PR Gate tests — wrapper script + workflow YAML structure.

T-PR-GATE-1  Wrapper script imports cleanly + has expected main() entry
T-PR-GATE-2  _is_blocking rules: CRITICAL always blocks; HIGH+frozen blocks;
             HIGH non-frozen / MEDIUM / LOW do NOT block.
T-PR-GATE-3  _gh_annotation emits well-formed GitHub Actions annotation.
T-PR-GATE-4  Healthy main → script main() returns exit 0.
T-PR-GATE-5  Workflow YAML has expected triggers + run script reference.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


# ---------------------------------------------------------------------------
# T-PR-GATE-1
# ---------------------------------------------------------------------------

def test_t_pr_gate_1_script_imports():
    """The wrapper script must import cleanly + expose main()."""
    import run_mythos_pr_gate as mod
    assert callable(getattr(mod, "main", None))
    assert callable(getattr(mod, "_gh_annotation", None))
    assert callable(getattr(mod, "_is_blocking", None))


# ---------------------------------------------------------------------------
# T-PR-GATE-2
# ---------------------------------------------------------------------------

def test_t_pr_gate_2_is_blocking_rules():
    """Blocking-rule matrix:
        CRITICAL                       → blocks
        HIGH + frozen_region=True      → blocks
        HIGH + frozen_region=False     → DOES NOT block
        MEDIUM (any frozen_region)     → DOES NOT block
        LOW (any frozen_region)        → DOES NOT block
    """
    import run_mythos_pr_gate as mod
    from vapi_bridge.mythos_cadence_engine import MythosFindingResult

    base = dict(
        variant="frozen",
        description="t",
        recommended_fix="t",
        coherence_id="mythos_frozen_t",
    )

    assert mod._is_blocking(
        MythosFindingResult(**base, severity="CRITICAL", frozen_region=False)
    ) is True
    assert mod._is_blocking(
        MythosFindingResult(**base, severity="CRITICAL", frozen_region=True)
    ) is True
    assert mod._is_blocking(
        MythosFindingResult(**base, severity="HIGH", frozen_region=True)
    ) is True
    assert mod._is_blocking(
        MythosFindingResult(**base, severity="HIGH", frozen_region=False)
    ) is False
    assert mod._is_blocking(
        MythosFindingResult(**base, severity="MEDIUM", frozen_region=True)
    ) is False
    assert mod._is_blocking(
        MythosFindingResult(**base, severity="MEDIUM", frozen_region=False)
    ) is False
    assert mod._is_blocking(
        MythosFindingResult(**base, severity="LOW", frozen_region=True)
    ) is False


# ---------------------------------------------------------------------------
# T-PR-GATE-3
# ---------------------------------------------------------------------------

def test_t_pr_gate_3_gh_annotation_shape():
    """_gh_annotation must:
        - start with `::error`/`::warning`/`::notice` per severity ladder
        - include `title=Mythos-<variant>/<severity>` exactly
        - escape newlines in description as `%0A`
    """
    import run_mythos_pr_gate as mod
    from vapi_bridge.mythos_cadence_engine import MythosFindingResult

    # CRITICAL → ::error
    crit = MythosFindingResult(
        variant="frozen",
        severity="CRITICAL",
        description="line1\nline2",
        recommended_fix="t",
        coherence_id="mythos_frozen_x",
        file_path="bridge/vapi_bridge/codec.py",
        line_number=42,
        frozen_region=True,
    )
    out = mod._gh_annotation(crit)
    assert out.startswith("::error "), f"want ::error, got: {out[:30]!r}"
    assert "title=Mythos-frozen/CRITICAL" in out
    assert "file=bridge/vapi_bridge/codec.py" in out
    assert "line=42" in out
    assert "line1%0Aline2" in out, "newlines must be %0A-escaped"

    # MEDIUM → ::warning
    med = MythosFindingResult(
        variant="crypto",
        severity="MEDIUM",
        description="m",
        recommended_fix="t",
        coherence_id="mythos_crypto_x",
        frozen_region=False,
    )
    assert mod._gh_annotation(med).startswith("::warning ")

    # LOW → ::notice
    low = MythosFindingResult(
        variant="corpus",
        severity="LOW",
        description="l",
        recommended_fix="t",
        coherence_id="mythos_corpus_x",
        frozen_region=False,
    )
    assert mod._gh_annotation(low).startswith("::notice ")

    # HIGH + frozen=True → ::error; HIGH + frozen=False → ::warning
    high_frozen = MythosFindingResult(
        variant="frozen",
        severity="HIGH",
        description="h",
        recommended_fix="t",
        coherence_id="mythos_frozen_y",
        frozen_region=True,
    )
    assert mod._gh_annotation(high_frozen).startswith("::error ")
    high_nonfrozen = MythosFindingResult(
        variant="frozen",
        severity="HIGH",
        description="h",
        recommended_fix="t",
        coherence_id="mythos_frozen_z",
        frozen_region=False,
    )
    assert mod._gh_annotation(high_nonfrozen).startswith("::warning ")


# ---------------------------------------------------------------------------
# T-PR-GATE-4
# ---------------------------------------------------------------------------

def test_t_pr_gate_4_main_exit_0_on_healthy_repo(capsys):
    """On the healthy live repo, main() MUST return exit code 0
    (no CRITICAL or HIGH frozen findings)."""
    import run_mythos_pr_gate as mod
    rc = mod.main([])
    captured = capsys.readouterr()
    assert rc == 0, (
        f"main() should return 0 on healthy repo but got {rc}. Output:\n"
        f"{captured.out}\n{captured.err}"
    )
    # Summary line must appear
    assert "TOTAL_BLOCKING = 0" in captured.out


# ---------------------------------------------------------------------------
# T-PR-GATE-5
# ---------------------------------------------------------------------------

def test_t_pr_gate_5_workflow_yaml_structure():
    """Workflow file must:
        - exist at .github/workflows/vapi-mythos-pr-gate.yml
        - trigger on pull_request to main
        - run scripts/run_mythos_pr_gate.py
        - request pull-requests:write permission (for comment-on-failure)
    """
    wf = ROOT / ".github" / "workflows" / "vapi-mythos-pr-gate.yml"
    assert wf.is_file(), f"workflow file missing at {wf}"
    text = wf.read_text(encoding="utf-8")

    assert "name: VAPI Mythos PR Gate" in text
    assert "pull_request:" in text
    assert "branches: [main]" in text
    assert "scripts/run_mythos_pr_gate.py" in text
    # Permission needed for comment-on-failure
    assert "pull-requests: write" in text
    # The comment-on-failure step must reference both gate dimensions
    assert "Mythos-Frozen" in text
    assert "Mythos-Crypto" in text
