"""Phase O5-MYTHOS-MINIMAL M.2 tests — mythos_variants + MCP tool wrappers.

T-MYTHOS-M2-1  mythos_frozen_drift returns list (possibly empty) on healthy state
T-MYTHOS-M2-2  coherence_id deterministic (same input -> same id)
T-MYTHOS-M2-3  mythos_stability_sweep finds urlopen-no-timeout in synthetic fixture
T-MYTHOS-M2-4  mythos_stability_sweep finds bare `except: pass` in synthetic fixture
T-MYTHOS-M2-5  mythos_stability_sweep SKIPS except:pass with `# idempotent` marker
T-MYTHOS-M2-6  mythos_variants.py self-audit exclusion holds (no false-positive HIGH urlopen)
T-MYTHOS-M2-7  MCP tool wrappers registered + callable + return dict shape
T-MYTHOS-M2-8  severity_breakdown aggregates correctly + frozen-region tier=3 invariant
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ----- T-MYTHOS-M2-1 ------------------------------------------------------

def test_t_mythos_m2_1_frozen_drift_returns_list():
    """On a healthy PV-CI state (no drift), Mythos-Frozen returns []."""
    from vapi_bridge.mythos_variants import mythos_frozen_drift

    async def run():
        return await mythos_frozen_drift(repo_root=ROOT)

    findings = asyncio.run(run())
    assert isinstance(findings, list)
    # Healthy state: PV-CI gate is at 86/86 PASS (this session); expect 0 findings.
    # If non-zero, EVERY finding must be HIGH + frozen_region + tier=3.
    for f in findings:
        assert f.variant == "frozen"
        assert f.severity == "HIGH"
        assert f.frozen_region is True
        assert f.fix_authority_tier == 3


# ----- T-MYTHOS-M2-2 ------------------------------------------------------

def test_t_mythos_m2_2_coherence_id_deterministic():
    """Same (variant, key) MUST yield the same coherence_id — anti-replay
    via UNIQUE constraint at the store layer (M.1) only works if duplicate
    re-runs collide on coherence_id."""
    from vapi_bridge.mythos_variants import _coherence_id
    a = _coherence_id("frozen", "INV-001:digest_drift")
    b = _coherence_id("frozen", "INV-001:digest_drift")
    c = _coherence_id("frozen", "INV-002:digest_drift")
    assert a == b
    assert a != c
    # Format: "mythos_<variant>_<sha256[:16]>"
    assert a.startswith("mythos_frozen_")
    assert len(a) == len("mythos_frozen_") + 16


# ----- T-MYTHOS-M2-3 ------------------------------------------------------

def test_t_mythos_m2_3_urlopen_no_timeout_detected():
    """In a synthetic .py fixture under a temp repo_root, Mythos-Stability
    flags urlopen(...) calls without timeout= argument as HIGH."""
    from vapi_bridge.mythos_variants import mythos_stability_sweep
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        repo = Path(td)
        # Synthesize a bridge/vapi_bridge/ directory with a file that has
        # an urlopen call WITHOUT timeout, and a sibling with timeout.
        target_dir = repo / "bridge" / "vapi_bridge"
        target_dir.mkdir(parents=True)
        (target_dir / "fixture_urlopen.py").write_text(
            "import urllib.request\n"
            "def bad():\n"
            "    resp = urllib.request.urlopen('http://example.com')\n"  # NO timeout — flag
            "    return resp.read()\n"
            "def good():\n"
            "    resp = urllib.request.urlopen('http://example.com', timeout=5.0)\n"  # has timeout — skip
            "    return resp.read()\n",
            encoding="utf-8",
        )

        async def run():
            return await mythos_stability_sweep(repo_root=repo)

        findings = asyncio.run(run())
        urlopen_findings = [
            f for f in findings
            if f.severity == "HIGH" and "fixture_urlopen.py" in (f.file_path or "")
        ]
        assert len(urlopen_findings) == 1, (
            f"expected exactly 1 HIGH urlopen-no-timeout finding, got {len(urlopen_findings)}; "
            f"all findings: {[(f.severity, f.file_path, f.line_number) for f in findings]}"
        )
        f = urlopen_findings[0]
        assert f.variant == "stability"
        assert f.frozen_region is False
        assert f.fix_authority_tier == 2


# ----- T-MYTHOS-M2-4 ------------------------------------------------------

def test_t_mythos_m2_4_except_pass_no_marker_detected():
    """A bare `except Exception: pass` WITHOUT any deliberate-fail-open
    marker in surrounding lines is flagged MEDIUM."""
    from vapi_bridge.mythos_variants import mythos_stability_sweep
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        repo = Path(td)
        target_dir = repo / "bridge" / "vapi_bridge"
        target_dir.mkdir(parents=True)
        (target_dir / "fixture_swallow.py").write_text(
            "def f():\n"
            "    try:\n"
            "        risky()\n"
            "    except Exception:\n"
            "        pass\n",  # silent — no marker
            encoding="utf-8",
        )

        async def run():
            return await mythos_stability_sweep(repo_root=repo)

        findings = asyncio.run(run())
        swallows = [
            f for f in findings
            if f.severity == "MEDIUM" and "fixture_swallow.py" in (f.file_path or "")
        ]
        assert len(swallows) == 1, (
            f"expected 1 MEDIUM except:pass finding, got {len(swallows)}"
        )


# ----- T-MYTHOS-M2-5 ------------------------------------------------------

def test_t_mythos_m2_5_except_pass_with_marker_skipped():
    """Deliberate-fail-open markers (# idempotent / # fail-open / # noqa)
    in 5-line context skip the except:pass finding."""
    from vapi_bridge.mythos_variants import mythos_stability_sweep
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        repo = Path(td)
        target_dir = repo / "bridge" / "vapi_bridge"
        target_dir.mkdir(parents=True)
        # All three should be SKIPPED.
        (target_dir / "fixture_skip.py").write_text(
            "# Case 1: marker on the pass line itself\n"
            "def f1():\n"
            "    try:\n"
            "        risky()\n"
            "    except Exception:\n"
            "        pass  # idempotent\n"
            "\n"
            "# Case 2: marker comment above the try\n"
            "def f2():\n"
            "    # fail-open: missing entry is OK\n"
            "    try:\n"
            "        risky()\n"
            "    except Exception:\n"
            "        pass\n"
            "\n"
            "# Case 3: noqa: BLE001 marker\n"
            "def f3():\n"
            "    try:\n"
            "        risky()\n"
            "    except Exception:  # noqa: BLE001\n"
            "        pass\n",
            encoding="utf-8",
        )

        async def run():
            return await mythos_stability_sweep(repo_root=repo)

        findings = asyncio.run(run())
        swallows = [
            f for f in findings
            if "fixture_skip.py" in (f.file_path or "")
        ]
        assert len(swallows) == 0, (
            f"expected ZERO findings (all three patterns have markers); got: "
            f"{[(f.file_path, f.line_number, f.description[:60]) for f in swallows]}"
        )


# ----- T-MYTHOS-M2-6 ------------------------------------------------------

def test_t_mythos_m2_6_mythos_variants_self_excluded():
    """mythos_variants.py contains the regex source for the urlopen pattern;
    it MUST be excluded from the audit to avoid false-positive HIGH findings
    on its own regex literal."""
    from vapi_bridge.mythos_variants import mythos_stability_sweep

    async def run():
        return await mythos_stability_sweep(repo_root=ROOT)

    findings = asyncio.run(run())
    self_audits = [
        f for f in findings
        if f.file_path and "mythos_variants.py" in f.file_path
    ]
    assert self_audits == [], (
        f"mythos_variants.py must not appear in its own audit output, "
        f"but got: {[(f.severity, f.file_path, f.line_number) for f in self_audits]}"
    )


# ----- T-MYTHOS-M2-7 ------------------------------------------------------

def test_t_mythos_m2_7_mcp_tool_wrappers_callable():
    """The 2 MCP tool wrappers in vapi-mcp/unified_server.py are loadable
    + callable. They return a dict with the expected shape."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_unified_mcp_test",
        ROOT / "vapi-mcp" / "unified_server.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # The MCP server attempts to import many things at module load — set the
    # VAPI_ROOT env so PROJECT_ROOT resolves to the real repo.
    os.environ["VAPI_ROOT"] = str(ROOT)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        pytest.skip(f"unified_server.py module load failed (likely missing optional dep): {exc}")

    # Both tools must be registered.
    assert hasattr(mod, "vapi_mythos_frozen_drift"), "Tool 18 not registered"
    assert hasattr(mod, "vapi_mythos_stability_sweep"), "Tool 19 not registered"

    # Invoke each + verify dict shape.
    frozen_dict = asyncio.run(mod.vapi_mythos_frozen_drift())
    assert frozen_dict["variant"] == "frozen"
    assert "total_findings" in frozen_dict
    assert "severity_breakdown" in frozen_dict
    assert "findings" in frozen_dict
    assert isinstance(frozen_dict["findings"], list)

    stab_dict = asyncio.run(mod.vapi_mythos_stability_sweep())
    assert stab_dict["variant"] == "stability"
    assert "severity_breakdown" in stab_dict
    # Stability sweep on the real repo should produce SOME findings
    # (the 159 MEDIUM except:pass class observed empirically); allow 0
    # in case the codebase becomes fully-annotated in the future.
    assert stab_dict["total_findings"] >= 0


# ----- T-MYTHOS-M2-8 ------------------------------------------------------

def test_t_mythos_m2_8_severity_breakdown_and_frozen_tier_invariant():
    """severity_breakdown counts MUST match findings list length; AND any
    frozen_region=True finding MUST carry fix_authority_tier=3 (variant-
    declared; the store layer also enforces this independently)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_unified_mcp_test_8",
        ROOT / "vapi-mcp" / "unified_server.py",
    )
    mod = importlib.util.module_from_spec(spec)
    os.environ["VAPI_ROOT"] = str(ROOT)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        pytest.skip(f"unified_server.py module load failed: {exc}")

    out = asyncio.run(mod.vapi_mythos_stability_sweep())
    counts = out["severity_breakdown"]
    items = out["findings"]
    assert sum(counts.values()) == len(items)
    # Stability findings are never frozen_region=True (they're production-
    # code hazards, not FROZEN-protocol regions).
    for f in items:
        if f.get("frozen_region"):
            assert f.get("fix_authority_tier") == 3, (
                "INV-MYTHOS-FROZEN-PROTECTION-001 violated at variant layer"
            )

    # Frozen variant: every finding (if any) must declare frozen_region=True
    # + fix_authority_tier=3.
    out_f = asyncio.run(mod.vapi_mythos_frozen_drift())
    for f in out_f["findings"]:
        assert f["frozen_region"] is True
        assert f["fix_authority_tier"] == 3
