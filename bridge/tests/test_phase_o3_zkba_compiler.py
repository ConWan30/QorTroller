"""Phase O3-ZKBA-TRACK1 — Compiler + GIC Continuity Ledger tests.

Stream Z3 + Z4 + Z7 (compiler portion) of PLAN-VBDIP-0002-ZKBA-PARALLEL-v1.

T-ZKBA-8:  vsd_ui_compiler.compile_artifact byte-stable across two runs
T-ZKBA-9:  vsd_ui_compiler source contains no wall-clock / random / network imports
T-ZKBA-10: GIC Continuity Ledger artifact builds end-to-end (manifest + HTML + DB)
T-ZKBA-11: GIC Continuity Ledger rebuild is idempotent (same output + DB row)
"""
import hashlib
import os
import re
import sys
from pathlib import Path

import pytest

# Add bridge/ + scripts/ to sys.path
_HERE = os.path.dirname(__file__)
_BRIDGE = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import (  # noqa: E402
    compile_artifact,
    canonical_json,
    compute_input_commitment,
    ZKBAManifest,
    _MANIFEST_SCHEMA,
    _COMPILER_VERSION,
)
from zkba_compile_gic_ledger import build_gic_ledger_artifact  # noqa: E402


# ---------------------------------------------------------------------------
# T-ZKBA-8: byte-stable two-run determinism
# ---------------------------------------------------------------------------

def test_t_zkba_8_vsd_compiler_byte_stable_two_runs(tmp_path):
    """Same inputs + same compiler -> identical output bytes + identical
    manifest bytes across two independent compile_artifact() invocations."""
    inputs = {
        "ts_ns": 1778000000000000000,
        "section_a": "alpha content",
        "section_b": 42,
        "items": [1, 2, 3],
    }

    def renderer(d):
        return f"<html><body>{d['section_a']} / {d['section_b']} / {d['items']}</body></html>"

    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"

    m1 = compile_artifact(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=out_a,
        html_renderer=renderer,
    )
    m2 = compile_artifact(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=out_b,
        html_renderer=renderer,
    )

    # Manifest fields independent of output_dir must match
    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.zkba_class == m2.zkba_class
    assert m1.proof_weight == m2.proof_weight
    assert m1.ts_ns == m2.ts_ns
    assert m1.compiler_version == m2.compiler_version
    assert m1.schema == m2.schema == _MANIFEST_SCHEMA

    # HTML byte-equality across runs
    html_a = (out_a / f"{m1.input_commitment_hex}.html").read_bytes()
    html_b = (out_b / f"{m2.input_commitment_hex}.html").read_bytes()
    assert html_a == html_b
    assert hashlib.sha256(html_a).hexdigest() == m1.output_hash_hex


# ---------------------------------------------------------------------------
# T-ZKBA-9: compiler source contains no wall-clock / random / network imports
# ---------------------------------------------------------------------------

def test_t_zkba_9_vsd_compiler_no_wall_clock_imports():
    """Static grep of scripts/vsd_ui_compiler.py for forbidden imports.

    Forbidden: datetime, time, random, urllib, requests, socket, http.client.
    """
    compiler_path = os.path.join(_SCRIPTS, "vsd_ui_compiler.py")
    with open(compiler_path, "r", encoding="utf-8") as f:
        source = f.read()

    forbidden_patterns = [
        r"^import\s+datetime",
        r"^from\s+datetime\s+import",
        r"^import\s+time(?:\s|$)",
        r"^from\s+time\s+import",
        r"^import\s+random",
        r"^from\s+random\s+import",
        r"^import\s+urllib",
        r"^from\s+urllib\s+import",
        r"^import\s+requests",
        r"^from\s+requests\s+import",
        r"^import\s+socket",
        r"^from\s+socket\s+import",
        r"^import\s+http\.client",
        r"^from\s+http\.client\s+import",
    ]

    for pattern in forbidden_patterns:
        # Multi-line; match anywhere in the file
        matches = re.findall(pattern, source, re.MULTILINE)
        assert not matches, (
            f"vsd_ui_compiler.py contains forbidden import matching {pattern!r}: {matches}"
        )

    # Sanity: compiler does import the ZKBA primitive enum (allowed)
    assert "from vapi_bridge.zkba_artifact import" in source

    # Sanity: compiler does have the manifest schema literal
    assert '"vapi-zkba-manifest-v1"' in source


# ---------------------------------------------------------------------------
# T-ZKBA-10: GIC Continuity Ledger artifact builds end-to-end
# ---------------------------------------------------------------------------

def test_t_zkba_10_gic_continuity_ledger_artifact_builds(tmp_path):
    """build_gic_ledger_artifact() produces a manifest + HTML file +
    inserts a row into zkba_artifact_log."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_zkba_10.db")
    store = Store(db_path)

    out_dir = tmp_path / "gic_continuity_ledger"
    ts_ns = 1778000000000000000

    # Use override fixtures so we don't need a populated grind chain
    fake_head = "a" * 64
    fake_links = [
        {"index": 0, "host_state": "EXCLUSIVE_USB", "verdict": "FLAG", "ch_short": "deadbeefcafe"},
        {"index": 1, "host_state": "EXCLUSIVE_USB", "verdict": "FLAG", "ch_short": "beefcafe0123"},
    ]

    manifest = build_gic_ledger_artifact(
        store=store,
        grind_session_id="grind_test_z10",
        output_dir=out_dir,
        ts_ns=ts_ns,
        chain_head_hex_override=fake_head,
        links_summary_override=fake_links,
    )

    assert isinstance(manifest, ZKBAManifest)
    assert manifest.schema == _MANIFEST_SCHEMA
    assert manifest.zkba_class == int(ZKBAClass.GIC)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.compiler_version == _COMPILER_VERSION
    assert manifest.ts_ns == ts_ns
    assert len(manifest.input_commitment_hex) == 64
    assert len(manifest.output_hash_hex) == 64

    # HTML file exists at the expected path
    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex
    assert b"GIC Continuity Ledger" in html_bytes
    assert fake_head.encode() in html_bytes

    # Manifest file exists alongside HTML
    manifest_path = html_path.with_suffix(".manifest.json")
    assert manifest_path.exists()

    # zkba_artifact_log row inserted
    # The ZKBA commitment is computed from compute_zkba_commitment(GIC, CHAIN_ONLY, (head,), ts_ns).
    # We can re-derive it to verify the DB row.
    from vapi_bridge.zkba_artifact import compute_zkba_commitment
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(bytes.fromhex(fake_head),),
        ts_ns=ts_ns,
    )
    row = store.get_zkba_artifact_status(expected_zkba.hex())
    assert row is not None
    assert row["zkba_class"] == int(ZKBAClass.GIC)
    assert row["proof_weight"] == int(ProofWeightClass.CHAIN_ONLY)
    assert row["anchor_tx_hash"] is None   # Track 1 invariant: not anchored


# ---------------------------------------------------------------------------
# T-ZKBA-11: GIC Continuity Ledger rebuild is idempotent
# ---------------------------------------------------------------------------

def test_t_zkba_11_gic_continuity_ledger_rebuild_idempotent(tmp_path):
    """Calling build_gic_ledger_artifact() twice with the same inputs
    produces the same manifest fields, writes the same HTML bytes, and
    does NOT add a duplicate DB row (UNIQUE on commitment_hex)."""
    from vapi_bridge.store import Store

    db_path = str(tmp_path / "test_zkba_11.db")
    store = Store(db_path)

    out_dir = tmp_path / "gic_continuity_ledger"
    ts_ns = 1778000000000000000
    fake_head = "b" * 64
    fake_links = [
        {"index": 0, "host_state": "EXCLUSIVE_USB", "verdict": "FLAG", "ch_short": "1234567890ab"},
    ]

    m1 = build_gic_ledger_artifact(
        store=store,
        grind_session_id="grind_test_z11",
        output_dir=out_dir,
        ts_ns=ts_ns,
        chain_head_hex_override=fake_head,
        links_summary_override=fake_links,
    )
    m2 = build_gic_ledger_artifact(
        store=store,
        grind_session_id="grind_test_z11",
        output_dir=out_dir,
        ts_ns=ts_ns,
        chain_head_hex_override=fake_head,
        links_summary_override=fake_links,
    )

    # Identical manifests across builds
    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex
    assert m1.output_path == m2.output_path

    # DB: re-derive ZKBA commitment and assert exactly 1 row in zkba_artifact_log
    from vapi_bridge.zkba_artifact import compute_zkba_commitment
    expected_zkba = compute_zkba_commitment(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(bytes.fromhex(fake_head),),
        ts_ns=ts_ns,
    )
    with store._conn() as conn:
        cnt = conn.execute(
            "SELECT COUNT(*) FROM zkba_artifact_log WHERE commitment_hex=?",
            (expected_zkba.hex(),),
        ).fetchone()[0]
    assert int(cnt) == 1, "UNIQUE(commitment_hex) should prevent duplicate insert"
