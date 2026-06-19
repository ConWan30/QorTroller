"""Tier 1 daemon self-honesty primitives — verify_artifact, post-output verification,
methodology retrieval, adversarial_verify."""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from _daemon_tools_schema import (  # noqa: E402
    MethodologyRegistry,
    OUTPUT_PRODUCING_TOOLS,
    adversarial_verify,
    build_mixin_module,
    expected_shape_for_output_tool,
    reconstruct_from_removal_diff,
    resolve_output_artifact_path,
    run_post_output_verification,
    verify_artifact,
)


class TestVerifyArtifact:
    def test_missing_file_fails(self, tmp_path):
        r = verify_artifact(str(tmp_path / "nope.py"), {"exists": True})
        assert r["ok"] is False
        assert any("missing" in f.lower() for f in r["failures"])

    def test_valid_python_passes(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text("class FooMixin:\n    def bar(self):\n        pass\n", encoding="utf-8")
        r = verify_artifact(str(p), {"python_valid": True, "class_name": "FooMixin"})
        assert r["ok"] is True

    def test_invalid_python_fails(self, tmp_path):
        p = tmp_path / "bad.py"
        p.write_text("class Broken\n", encoding="utf-8")
        r = verify_artifact(str(p), {"python_valid": True})
        assert r["ok"] is False


class TestOutputProducingTools:
    def test_output_tools_frozenset(self):
        assert "extract_with_diff" in OUTPUT_PRODUCING_TOOLS
        assert "propose_edit" in OUTPUT_PRODUCING_TOOLS

    def test_resolve_extract_with_diff_result(self):
        result = (
            "EXTRACTED (diff-oracle, deterministic):\n"
            "  artifact: docs/_daemon_proposals/newfile_20260618_test.proposed\n"
        )
        art, diff = resolve_output_artifact_path(
            "extract_with_diff",
            {"diff_path": "docs/_daemon_proposals/foo.diff", "class_name": "X"},
            result,
            str(REPO_ROOT),
        )
        assert art.endswith(".proposed")
        assert diff == "docs/_daemon_proposals/foo.diff"

    def test_run_post_output_verification_ok(self, tmp_path):
        p = tmp_path / "m.py"
        p.write_text("class M:\n    pass\n", encoding="utf-8")
        rel = os.path.relpath(p, tmp_path)
        r = run_post_output_verification(
            "write_file",
            {"path": rel},
            f"OK: wrote 10 chars to {rel}",
            str(tmp_path),
        )
        assert r["ran"] is True
        assert r["ok"] is True

    def test_expected_shape_extract(self):
        shape = expected_shape_for_output_tool(
            "extract_with_diff",
            {"class_name": "SnapMixin"},
            "x.proposed",
            str(REPO_ROOT),
        )
        assert shape["python_valid"] is True
        assert shape["class_name"] == "SnapMixin"


class TestMethodologyRegistry:
    def test_query_for_task_matches_extraction(self, tmp_path):
        reg_path = tmp_path / "meth.json"
        reg = MethodologyRegistry(str(reg_path))
        entries = reg.query_for_task(["Extract snapshots_grind mixin via propose_edit"])
        assert "VERBATIM_RELOCATION" in entries
        assert "FROZEN_SURFACE_TOUCH" in entries

    def test_format_for_prompt_includes_commit(self, tmp_path):
        reg_path = tmp_path / "meth.json"
        reg = MethodologyRegistry(str(reg_path))
        entries = reg.query_for_task(["mixin"])
        text = MethodologyRegistry.format_for_prompt(entries)
        assert "VERBATIM_RELOCATION" in text
        assert "agent_commit" in text or "commit `" in text


class TestAdversarialVerify:
    def test_diff_oracle_round_trip(self, tmp_path):
        removed = ["    def snap(self):", "        return 1"]
        diff_text = "\n".join([
            "--- a/bridge/vapi_bridge/store/_core.py",
            "+++ b/bridge/vapi_bridge/store/_core.py",
            "@@ -1,3 +1,1 @@",
            "-    def snap(self):",
            "-        return 1",
        ])
        diff_path = tmp_path / "cut.diff"
        diff_path.write_text(diff_text, encoding="utf-8")
        module = build_mixin_module("SnapMixin", removed)
        proposed = tmp_path / "out.proposed"
        proposed.write_text(module, encoding="utf-8")
        av = adversarial_verify(
            str(proposed),
            diff_path=str(diff_path),
            class_name="SnapMixin",
            repo_root=str(tmp_path),
        )
        assert av["ok"] is True
        assert av["method"] == "diff_oracle"
        assert av["artifact_hash"] == av["reconstructed_hash"]

    def test_tampered_proposed_fails(self, tmp_path):
        removed = ["    def snap(self):", "        return 1"]
        diff_text = "-    def snap(self):\n-        return 1\n"
        diff_path = tmp_path / "cut.diff"
        diff_path.write_text(diff_text, encoding="utf-8")
        module = build_mixin_module("SnapMixin", removed)
        proposed = tmp_path / "out.proposed"
        proposed.write_text(module + "# tampered\n", encoding="utf-8")
        av = adversarial_verify(
            str(proposed),
            diff_path=str(diff_path),
            class_name="SnapMixin",
        )
        assert av["ok"] is False

    def test_unified_diff_attest(self, tmp_path):
        diff_path = tmp_path / "p.diff"
        diff_path.write_text("--- a/foo.py\n+++ b/foo.py\n", encoding="utf-8")
        av = adversarial_verify(str(diff_path))
        assert av["ok"] is True
        assert av["method"] == "diff_attest"


class TestLoadDaemonAgentId:
    def test_provisional_default(self):
        from _daemon_tools_schema import load_daemon_agent_id
        fake_pub = "ab" * 32
        aid, mode, _ = load_daemon_agent_id(fake_pub)
        assert mode == "provisional"
        assert len(aid) == 32
        assert aid == hashlib.sha256(bytes.fromhex(fake_pub)).digest()
