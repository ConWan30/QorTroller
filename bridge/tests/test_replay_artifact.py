"""Tests for scripts/replay_artifact.py — Reproducibility Receipt verifier.

Exercises every verdict path against fresh temp directories. Manifest is
synthesized in-test (no dependency on bridge runtime state).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "replay_artifact.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("replay_artifact", SCRIPT_PATH)
replay_artifact = importlib.util.module_from_spec(_spec)  # type: ignore
# Register in sys.modules BEFORE exec_module so @dataclass(slots=True) can
# resolve cls.__module__ correctly on Python 3.13+.
sys.modules["replay_artifact"] = replay_artifact
_spec.loader.exec_module(replay_artifact)  # type: ignore


def _write_zkba_pair(
    tmp_path: Path,
    html_body: str,
    *,
    override_hash: str | None = None,
    override_schema: str | None = None,
    drop_field: str | None = None,
) -> Path:
    """Write a synthetic <commit>.html + <commit>.manifest.json pair.

    Returns the manifest path. By default, output_hash matches the HTML.
    """
    html_bytes = html_body.encode("utf-8")
    commit = hashlib.sha256(html_bytes).hexdigest()
    html_path = tmp_path / f"{commit}.html"
    html_path.write_text(html_body, encoding="utf-8")

    manifest = {
        "schema": override_schema or replay_artifact.ZKBA_SCHEMA,
        "zkba_class": 4,  # HARDWARE
        "proof_weight": 1,  # CHAIN_ONLY
        "output_path": f"{commit}.html",
        "output_hash_hex": override_hash if override_hash is not None else commit,
        "input_commitment_hex": "a" * 64,
        "compiler_version": "0.1.0",
        "ts_ns": 1778900000000000000,
    }
    if drop_field:
        manifest.pop(drop_field, None)

    mpath = tmp_path / f"{commit}.manifest.json"
    mpath.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return mpath


# ---- T-REPLAY-1: byte-identical pair -> PASS exit 0 -------------------

def test_t_replay_1_matching_pair_returns_pass():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mpath = _write_zkba_pair(tmp_path, "<html>test artifact</html>")
        result = replay_artifact.verify_manifest(mpath)

        assert result.overall_verdict == "PASS"
        assert result.structural_ok
        assert result.html_present
        assert result.output_hash_match


# ---- T-REPLAY-2: mismatched output_hash -> FAIL_OUTPUT_HASH_MISMATCH ---

def test_t_replay_2_hash_mismatch_returns_fail():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Override the hash to a wrong (but well-formed) value.
        mpath = _write_zkba_pair(
            tmp_path, "<html>test</html>",
            override_hash="b" * 64,
        )
        result = replay_artifact.verify_manifest(mpath)

        assert result.overall_verdict == "FAIL_OUTPUT_HASH_MISMATCH"
        assert result.structural_ok  # structurally valid; just hash diverges
        assert result.output_hash_match is False


# ---- T-REPLAY-3: HTML tampered post-emission -> hash mismatch detected ---

def test_t_replay_3_tampered_html_detected():
    """If an attacker modifies the HTML on disk after the manifest is
    pinned, output_hash recomputation surfaces the divergence."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mpath = _write_zkba_pair(tmp_path, "<html>original</html>")

        # Tamper: rewrite the HTML body but keep the manifest pinned.
        html_path = tmp_path / mpath.name.replace(".manifest.json", ".html")
        html_path.write_text("<html>TAMPERED</html>", encoding="utf-8")

        result = replay_artifact.verify_manifest(mpath)
        assert result.overall_verdict == "FAIL_OUTPUT_HASH_MISMATCH"


# ---- T-REPLAY-4: unknown schema -> FAIL_STRUCTURAL --------------------

def test_t_replay_4_unknown_schema_fails_structural():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mpath = _write_zkba_pair(
            tmp_path, "<html>x</html>",
            override_schema="vapi-imposter-v1",
        )
        result = replay_artifact.verify_manifest(mpath)
        assert result.overall_verdict == "FAIL_STRUCTURAL"
        assert any("unknown schema" in e for e in result.structural_errors)


# ---- T-REPLAY-5: missing required field -> FAIL_STRUCTURAL ------------

def test_t_replay_5_missing_field_fails_structural():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mpath = _write_zkba_pair(
            tmp_path, "<html>y</html>",
            drop_field="compiler_version",
        )
        result = replay_artifact.verify_manifest(mpath)
        assert result.overall_verdict == "FAIL_STRUCTURAL"
        assert any("compiler_version" in e for e in result.structural_errors)


# ---- T-REPLAY-6: missing HTML file -> FAIL_STRUCTURAL ------------------

def test_t_replay_6_missing_html_fails_structural():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mpath = _write_zkba_pair(tmp_path, "<html>z</html>")

        # Delete the HTML; manifest now points at a missing file.
        html_path = tmp_path / mpath.name.replace(".manifest.json", ".html")
        html_path.unlink()

        result = replay_artifact.verify_manifest(mpath)
        assert result.overall_verdict == "FAIL_STRUCTURAL"
        assert result.html_present is False


# ---- T-REPLAY-7: malformed JSON manifest -> FAIL_STRUCTURAL ------------

def test_t_replay_7_malformed_manifest_fails_structural():
    with tempfile.TemporaryDirectory() as tmp:
        mpath = Path(tmp) / "bad.manifest.json"
        mpath.write_text("{not json", encoding="utf-8")
        result = replay_artifact.verify_manifest(mpath)
        assert result.overall_verdict == "FAIL_STRUCTURAL"


# ---- T-REPLAY-8: invalid hex format (output_hash) -> FAIL_STRUCTURAL ---

def test_t_replay_8_bad_hash_format_fails_structural():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mpath = _write_zkba_pair(
            tmp_path, "<html>a</html>",
            override_hash="not_hex_at_all",
        )
        result = replay_artifact.verify_manifest(mpath)
        assert result.overall_verdict == "FAIL_STRUCTURAL"
        assert any("64-char lowercase hex" in e for e in result.structural_errors)


# ---- T-REPLAY-9: --dir mode aggregates across many manifests ----------

def test_t_replay_9_dir_mode_aggregates():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # 3 PASSing artifacts under a nested structure.
        for i, body in enumerate([
            "<html>a</html>", "<html>b</html>", "<html>c</html>",
        ]):
            sub = tmp_path / f"sub_{i}"
            sub.mkdir()
            _write_zkba_pair(sub, body)

        exit_code = replay_artifact.main(["--dir", str(tmp_path), "--json"])
        assert exit_code == 0


# ---- T-REPLAY-10: aggregate exit-code priority ------------------------

def test_t_replay_10_aggregate_exit_code_priority():
    """When a directory has BOTH hash-mismatch and structural fails,
    hash-mismatch (exit 1) takes priority over structural (exit 2)
    because hash-mismatch indicates active tamper, structural may be
    incomplete data."""
    results = [
        replay_artifact.CheckResult(overall_verdict="FAIL_STRUCTURAL"),
        replay_artifact.CheckResult(overall_verdict="FAIL_OUTPUT_HASH_MISMATCH"),
        replay_artifact.CheckResult(overall_verdict="PASS"),
    ]
    assert replay_artifact._aggregate_exit_code(results) == 1


# ---- T-REPLAY-11: FROZEN schema string constants pinned ---------------

def test_t_replay_11_frozen_schema_constants():
    """The two schema strings are FROZEN per INV-ZKBA-003 and
    INV-VPM-COMPILER-002. Catch accidental rename at PR time."""
    assert replay_artifact.ZKBA_SCHEMA == "vapi-zkba-manifest-v1"
    assert replay_artifact.VPM_SCHEMA == "vapi-vpm-artifact-v1"


# ---- T-REPLAY-12: nonexistent path via CLI returns exit 4 -------------

def test_t_replay_12_nonexistent_cli_path_returns_4():
    exit_code = replay_artifact.main(["/nonexistent/path/foo.manifest.json"])
    assert exit_code == 4
