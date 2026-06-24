"""Tests for F5 provenance-quadrille assembler (read-only fusion of GIC + WEC + CORPUS + SIC)."""
from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vapi_bridge.provenance_quadrille import (  # noqa: E402
    ChainStatus, QuadrilleVerdict, SCHEMA_VERSION, VPM_VISUAL_STATES, CHAIN_ORDER,
    verify_chain_leg, assemble_quadrille, verify_attestation, compute_unified_root,
)

_G = "11" * 32
_W = "22" * 32
_C = "33" * 32
_S = "44" * 32


def _intact():
    return {
        "gic": ChainStatus(_G, True, 100),
        "wec": ChainStatus(_W, True, 12),
        "corpus": ChainStatus(_C, True, 7),
        "sic": ChainStatus(_S, True, 8),
    }


# ── leg-level ────────────────────────────────────────────────────────────────

def test_leg_happy():
    assert verify_chain_leg("gic", ChainStatus(_G, True, 100)).ok


def test_leg_empty_chain_insufficient():
    r = verify_chain_leg("sic", ChainStatus(None, True, 0))
    assert r.ok is False and "no established head" in r.reason


def test_leg_broken_not_ok():
    r = verify_chain_leg("gic", ChainStatus(_G, False, 100))
    assert r.ok is False and "not intact" in r.reason


def test_leg_malformed_head():
    assert verify_chain_leg("wec", ChainStatus("nothex", True, 5)).ok is False


# ── fusion verdicts ──────────────────────────────────────────────────────────

def test_all_intact_is_live_with_unified_root():
    att = assemble_quadrille(_intact(), grind_session_id="grind_phase235_v1", ts_ns=100)
    assert att.verdict == QuadrilleVerdict.QUADRILLE_INTACT.value
    assert att.visual_state == "live"
    assert att.unified_root == compute_unified_root([_G, _W, _C, _S])
    ok, reason = verify_attestation(asdict(att))
    assert ok and "verified" in reason


def test_one_broken_chain_is_broken_and_unverified():
    ch = _intact()
    ch["wec"] = ChainStatus(_W, False, 12)        # operational chain broke
    att = assemble_quadrille(ch, grind_session_id="g", ts_ns=100)
    assert att.verdict == QuadrilleVerdict.QUADRILLE_BROKEN.value
    assert att.visual_state == "unverified"
    assert att.unified_root is None               # never anchor a broken quadrille


def test_missing_chain_is_insufficient():
    ch = _intact()
    del ch["sic"]                                 # methodology chain absent
    att = assemble_quadrille(ch, grind_session_id="g", ts_ns=100)
    assert att.verdict == QuadrilleVerdict.INSUFFICIENT.value
    assert att.visual_state == "unverified" and att.unified_root is None


def test_empty_chain_is_insufficient_not_broken():
    ch = _intact()
    ch["corpus"] = ChainStatus(None, True, 0)     # genesis-only / not yet established
    att = assemble_quadrille(ch, grind_session_id="g", ts_ns=100)
    assert att.verdict == QuadrilleVerdict.INSUFFICIENT.value


# ── honesty rails ────────────────────────────────────────────────────────────

def test_label_never_claims_zk_or_anchor():
    att = assemble_quadrille(_intact(), grind_session_id="g", ts_ns=100)
    il = att.vpm_label["integrity_label"]
    assert il["zk_verified"] is False and il["on_chain_anchor"] is False
    assert att.vpm_label["anchor_status"] == "none"


def test_unified_root_only_when_intact():
    att = assemble_quadrille(_intact(), grind_session_id="g", ts_ns=100)
    assert att.unified_root is not None
    ch = _intact(); ch["gic"] = ChainStatus(_G, False, 100)
    assert assemble_quadrille(ch, grind_session_id="g", ts_ns=100).unified_root is None


def test_overclaim_rejected_on_verify():
    """Hand-edit a broken quadrille to claim `live` → verify must reject (anti-overclaim)."""
    import hashlib, json
    ch = _intact(); ch["wec"] = ChainStatus(_W, False, 12)
    att = asdict(assemble_quadrille(ch, grind_session_id="g", ts_ns=100))
    att["visual_state"] = "live"
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    att["attestation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = verify_attestation(att)
    assert ok is False and "overclaim" in reason


def test_forged_unified_root_rejected():
    """Tamper the unified_root on an intact attestation → verify recomputes and rejects."""
    import hashlib, json
    att = asdict(assemble_quadrille(_intact(), grind_session_id="g", ts_ns=100))
    att["unified_root"] = "ff" * 32
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    att["attestation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = verify_attestation(att)
    assert ok is False and "unified_root" in reason


def test_smuggled_unified_root_on_broken_rejected():
    """A non-intact attestation must not carry a unified_root."""
    import hashlib, json
    ch = _intact(); ch["sic"] = ChainStatus(_S, False, 8)
    att = asdict(assemble_quadrille(ch, grind_session_id="g", ts_ns=100))
    att["unified_root"] = compute_unified_root([_G, _W, _C, _S])
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    att["attestation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = verify_attestation(att)
    assert ok is False and "unified_root" in reason


def test_body_tamper_rejected():
    att = asdict(assemble_quadrille(_intact(), grind_session_id="g", ts_ns=100))
    att["grind_session_id"] = "different"
    ok, reason = verify_attestation(att)
    assert ok is False and "tamper" in reason


def test_deterministic():
    a = assemble_quadrille(_intact(), grind_session_id="g", ts_ns=100)
    b = assemble_quadrille(_intact(), grind_session_id="g", ts_ns=100)
    assert a.attestation_hash == b.attestation_hash and a.unified_root == b.unified_root


def test_chain_order_fixes_unified_root():
    """Unified root is order-fixed (CHAIN_ORDER), not sensitive to dict insertion order."""
    ch = {k: _intact()[k] for k in ("sic", "corpus", "wec", "gic")}  # reversed insertion
    att = assemble_quadrille(ch, grind_session_id="g", ts_ns=100)
    assert att.unified_root == compute_unified_root([_G, _W, _C, _S])


def test_module_is_chain_and_numpy_free():
    """Packaging-only: no chain, no numpy import in the assembler module."""
    import ast, inspect
    from vapi_bridge import provenance_quadrille as M
    tree = ast.parse(inspect.getsource(M))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "numpy" not in imported and "web3" not in imported
    assert imported <= {"hashlib", "json", "dataclasses", "enum", "typing", "__future__"}


def test_no_frozen_byte_tag_introduced():
    """Guard the FROZEN-family discipline: the module must NOT introduce a real b"VAPI-..."
    byte-literal domain tag (which would register as a new commitment family / trip crypto drift).
    Checks actual bytes CONSTANTS via AST — the docstring legitimately mentions the avoided form."""
    import ast, inspect
    from vapi_bridge import provenance_quadrille as M
    tree = ast.parse(inspect.getsource(M))
    bytes_consts = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, bytes)]
    assert not any(b.startswith(b"VAPI-") for b in bytes_consts)


def test_visual_state_vocab_subset_of_frozen_vpm():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    try:
        from vsd_vpm_wrapper import VPMVisualState
    except Exception as exc:
        import pytest
        pytest.skip(f"vsd_vpm_wrapper not importable: {exc}")
    frozen = {v.value.replace("_", "-") for v in VPMVisualState}
    assert set(VPM_VISUAL_STATES).issubset(frozen)
