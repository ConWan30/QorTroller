"""Mythos-Frontend-Brand-Drift tests (2026-05-18).

T-MYTHOS-FBD-1  Healthy frontend (post-88c26d4c QorTroller wordmark) yields 0 high-confidence findings
T-MYTHOS-FBD-2  JSX text node >VAPI< pattern detected MEDIUM
T-MYTHOS-FBD-3  HTML <title>VAPI pattern detected MEDIUM
T-MYTHOS-FBD-4  HTML <h1>VAPI pattern detected MEDIUM
T-MYTHOS-FBD-5  Excluded paths (artifacts/, legacy/, crypto/) NOT scanned
T-MYTHOS-FBD-6  Layer C code identifiers (VAPIToken, VITE_VAPI_API_KEY) NOT flagged
T-MYTHOS-FBD-7  Missing frontend/src/ -> fail-open empty list
T-MYTHOS-FBD-8  Coherence-id deterministic across runs
"""
import asyncio
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ----- T-MYTHOS-FBD-1 -----------------------------------------------------

def test_t_mythos_fbd_1_healthy_no_false_positives():
    """Against live frontend after 88c26d4c wordmark fix — expect 0 findings
    in non-artifacts files. If non-zero, every finding must be MEDIUM +
    point at a true display-string drift."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    async def run():
        return await mythos_frontend_brand_drift(repo_root=ROOT)

    findings = asyncio.run(run())
    assert isinstance(findings, list)
    for f in findings:
        assert f.variant == "frontend_brand_drift"
        assert f.severity == "MEDIUM"
        assert f.frozen_region is False
        # Should never flag known Layer C files
        assert "/crypto/" not in (f.file_path or "")
        assert "/artifacts/" not in (f.file_path or "")
        assert "/legacy/" not in (f.file_path or "")
        assert "/manifest/" not in (f.file_path or "")


# ----- T-MYTHOS-FBD-2 -----------------------------------------------------

def test_t_mythos_fbd_2_jsx_text_node_detected():
    """Synthetic JSX with >VAPI< text -> MEDIUM finding."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "frontend" / "src" / "views").mkdir(parents=True)
        (repo / "frontend" / "src" / "views" / "TestView.jsx").write_text(
            "export default () => <header>VAPI Dashboard</header>",
            encoding="utf-8",
        )

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        findings = asyncio.run(run())
        jsx_findings = [f for f in findings if "JSX text node" in f.description]
        assert len(jsx_findings) >= 1
        assert jsx_findings[0].severity == "MEDIUM"
        assert "TestView.jsx" in jsx_findings[0].file_path


# ----- T-MYTHOS-FBD-3 -----------------------------------------------------

def test_t_mythos_fbd_3_html_title_detected():
    """Synthetic HTML with <title>VAPI...</title> -> MEDIUM finding."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "frontend" / "src").mkdir(parents=True)
        (repo / "frontend" / "src" / "test.html").write_text(
            "<html><head><title>VAPI - Test Page</title></head></html>",
            encoding="utf-8",
        )

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        findings = asyncio.run(run())
        title_findings = [f for f in findings if "<title>" in f.description]
        assert len(title_findings) >= 1
        assert title_findings[0].severity == "MEDIUM"


# ----- T-MYTHOS-FBD-4 -----------------------------------------------------

def test_t_mythos_fbd_4_html_heading_detected():
    """Synthetic HTML with <h1>VAPI...</h1> -> MEDIUM finding."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "frontend" / "src").mkdir(parents=True)
        (repo / "frontend" / "src" / "test.html").write_text(
            "<html><body><h1>VAPI - Welcome</h1></body></html>",
            encoding="utf-8",
        )

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        findings = asyncio.run(run())
        heading_findings = [f for f in findings if "<h?>" in f.description or "heading" in f.description]
        assert len(heading_findings) >= 1
        assert heading_findings[0].severity == "MEDIUM"


# ----- T-MYTHOS-FBD-5 -----------------------------------------------------

def test_t_mythos_fbd_5_excluded_paths_not_scanned():
    """Files under artifacts/ / legacy/ / __tests__/ / crypto/ / manifest/
    MUST NOT be scanned — even if they contain display VAPI patterns."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # Create offending files in EACH excluded directory
        for excluded in ("artifacts", "legacy", "__tests__", "crypto", "manifest"):
            d = repo / "frontend" / "src" / excluded
            d.mkdir(parents=True, exist_ok=True)
            (d / "bad.jsx").write_text(
                "export default () => <header>VAPI · BAD</header>",
                encoding="utf-8",
            )

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        findings = asyncio.run(run())
        # Should be ZERO findings — all under excluded paths
        for f in findings:
            assert all(
                excl not in (f.file_path or "")
                for excl in ("/artifacts/", "/legacy/", "/__tests__/",
                            "/crypto/", "/manifest/")
            ), f"Excluded path leaked: {f.file_path}"


# ----- T-MYTHOS-FBD-6 -----------------------------------------------------

def test_t_mythos_fbd_6_layer_c_identifiers_not_flagged():
    """Layer C code identifiers (VAPIToken in a JS import, VITE_VAPI_API_KEY
    in a config read) must NOT trigger any pattern — they're not display
    contexts."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "frontend" / "src" / "views").mkdir(parents=True)
        # Mix of legitimate Layer C references
        (repo / "frontend" / "src" / "views" / "ConfigView.jsx").write_text(
            "import { VAPIToken } from '../contracts'\n"
            "const apiKey = import.meta.env.VITE_VAPI_API_KEY\n"
            "const className = 'vapi-dashboard-card'\n"
            "export default () => <div>{apiKey}</div>",
            encoding="utf-8",
        )

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        findings = asyncio.run(run())
        # NONE of the Layer C refs should fire any of the three patterns
        assert findings == [], f"Unexpected findings on Layer C code: {findings}"


# ----- T-MYTHOS-FBD-7 -----------------------------------------------------

def test_t_mythos_fbd_7_missing_frontend_fail_open():
    """Missing frontend/src/ directory -> returns [] (fail-open)."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # No frontend/ at all

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        findings = asyncio.run(run())
        assert findings == []


# ----- T-MYTHOS-FBD-8 -----------------------------------------------------

def test_t_mythos_fbd_8_coherence_id_deterministic():
    """Same content -> same coherence_id (UNIQUE dedup at store layer)."""
    from vapi_bridge.mythos_variants import mythos_frontend_brand_drift

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "frontend" / "src" / "views").mkdir(parents=True)
        (repo / "frontend" / "src" / "views" / "T.jsx").write_text(
            "export default () => <header>VAPI Dash</header>",
            encoding="utf-8",
        )

        async def run():
            return await mythos_frontend_brand_drift(repo_root=repo)

        ids_a = sorted(f.coherence_id for f in asyncio.run(run()))
        ids_b = sorted(f.coherence_id for f in asyncio.run(run()))

    assert ids_a == ids_b
    assert all(cid.startswith("mythos_frontend_brand_drift_") for cid in ids_a)
