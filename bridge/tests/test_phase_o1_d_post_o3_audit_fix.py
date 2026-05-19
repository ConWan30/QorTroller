"""Tests for the 2026-05-19 post-O3 audit fixes + reconstruction primitive.

Born from the Path 2 verification investigation that resolved the
local-DB-empty vs on-chain-canonical-truth state discrepancy.

  T-POST-O3-FIX-1  _norm_hex normalizes bytes input to lowercase hex string
  T-POST-O3-FIX-2  _norm_hex normalizes 0x-prefix str input
  T-POST-O3-FIX-3  _norm_hex normalizes None to empty string
  T-POST-O3-FIX-4  Section 2 live field is hex-rendered after Fix B
  T-POST-O3-FIX-5  Reconstruction script imports cleanly + has expected helpers
  T-POST-O3-FIX-6  Reconstruction _verify_scope_root_matches_canonical accepts match
  T-POST-O3-FIX-7  Reconstruction _verify_scope_root_matches_canonical rejects mismatch
  T-POST-O3-FIX-8  PROJECT_ROOT in unified_server.py resolves to absolute path

Wallet-free; no live chain reads; no DB writes outside test temp dirs.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))


# ----- T-POST-O3-FIX-1 ----------------------------------------------------

def test_t_post_o3_fix_1_norm_hex_bytes():
    """_norm_hex must accept bytes input (defends against bytes-vs-str
    TypeError that previously crashed Section 2)."""
    from operator_initiative_post_o3_audit import _norm_hex
    result = _norm_hex(b"\xc0\xbc\xde\xe8")
    assert result == "c0bcdee8"


# ----- T-POST-O3-FIX-2 ----------------------------------------------------

def test_t_post_o3_fix_2_norm_hex_str_with_0x():
    """_norm_hex strips 0x prefix and lowercases."""
    from operator_initiative_post_o3_audit import _norm_hex
    assert _norm_hex("0xC0BCDEE8") == "c0bcdee8"
    assert _norm_hex("0xc0bcdee8") == "c0bcdee8"
    assert _norm_hex("c0bcdee8") == "c0bcdee8"


# ----- T-POST-O3-FIX-3 ----------------------------------------------------

def test_t_post_o3_fix_3_norm_hex_none():
    """_norm_hex returns empty string for None / empty input."""
    from operator_initiative_post_o3_audit import _norm_hex
    assert _norm_hex(None) == ""
    assert _norm_hex("") == ""


# ----- T-POST-O3-FIX-4 ----------------------------------------------------

def test_t_post_o3_fix_4_section_2_live_field_hex():
    """After Fix B, Section 2 should store entry['live'] as hex string
    (e.g., '0xc0bcdee8…'), not as bytes-repr or raw bytes object."""
    # Inspect the source — confirm the bytes-to-hex conversion exists
    source = (ROOT / "scripts" / "operator_initiative_post_o3_audit.py").read_text(
        encoding="utf-8"
    )
    assert 'live_hex = "0x" + live_raw.hex()' in source, \
        "Section 2 must convert bytes to hex before storing entry['live']"
    assert "isinstance(live_raw, (bytes, bytearray))" in source, \
        "Section 2 must check live_raw type before .hex() call"


# ----- T-POST-O3-FIX-5 ----------------------------------------------------

def test_t_post_o3_fix_5_reconstruction_script_imports():
    """The reconstruction script imports cleanly + exposes expected helpers."""
    import reconstruct_operator_activation_log as recon
    assert hasattr(recon, "reconstruct"), "reconstruct() async fn missing"
    assert hasattr(recon, "_verify_scope_root_matches_canonical"), \
        "verification helper missing"
    assert hasattr(recon, "CEREMONY_TX_HASHES"), \
        "ceremony tx hashes constant missing"
    assert hasattr(recon, "BUNDLE_PATHS"), \
        "bundle paths constant missing"
    # All 3 agents represented
    assert set(recon.CEREMONY_TX_HASHES.keys()) == {
        "anchor_sentry", "guardian", "curator"
    }
    assert set(recon.BUNDLE_PATHS.keys()) == {
        "anchor_sentry", "guardian", "curator"
    }


# ----- T-POST-O3-FIX-6 ----------------------------------------------------

def test_t_post_o3_fix_6_verify_canonical_match():
    """_verify_scope_root_matches_canonical returns (True, 'match') when
    the on-chain hex matches the canonical pin."""
    import reconstruct_operator_activation_log as recon
    # Use the canonical pin verbatim
    import operator_initiative_post_o3_audit as audit_mod
    sentry_pin = audit_mod._EXPECTED_O3_ACTING_MERKLES["anchor_sentry"]
    ok, msg = recon._verify_scope_root_matches_canonical("anchor_sentry", sentry_pin)
    assert ok is True, f"verification should pass for canonical pin: {msg}"
    assert msg == "match"
    # Also passes with no-0x-prefix form
    ok, msg = recon._verify_scope_root_matches_canonical(
        "anchor_sentry", sentry_pin.replace("0x", ""),
    )
    assert ok is True
    # And case-insensitive
    ok, msg = recon._verify_scope_root_matches_canonical(
        "anchor_sentry", sentry_pin.upper(),
    )
    assert ok is True


# ----- T-POST-O3-FIX-7 ----------------------------------------------------

def test_t_post_o3_fix_7_verify_canonical_reject_mismatch():
    """_verify_scope_root_matches_canonical returns (False, reason) when
    the on-chain hex does NOT match the canonical pin. Defense-in-depth."""
    import reconstruct_operator_activation_log as recon
    bad_hex = "0x" + "ff" * 32
    ok, msg = recon._verify_scope_root_matches_canonical("anchor_sentry", bad_hex)
    assert ok is False
    assert "!=" in msg or "canonical" in msg.lower()
    # Also fails for unknown agent
    ok, msg = recon._verify_scope_root_matches_canonical("unknown_agent", "0xaa")
    assert ok is False
    assert "no canonical pin" in msg


# ----- T-POST-O3-FIX-8 ----------------------------------------------------

def test_t_post_o3_fix_8_project_root_absolute():
    """vapi-mcp/unified_server.py must resolve PROJECT_ROOT to an absolute
    path so MCP server CWD does not affect path resolution."""
    source = (ROOT / "vapi-mcp" / "unified_server.py").read_text(encoding="utf-8")
    # Must include the absolute-path resolution pattern
    assert "_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]" in source, \
        "PROJECT_ROOT must anchor to repo root via __file__ resolution"
    # Must NOT use the previous CWD-relative form alone
    assert 'PROJECT_ROOT = Path(os.environ.get("VAPI_ROOT", str(_DEFAULT_PROJECT_ROOT)))' in source, \
        "PROJECT_ROOT must default to absolute repo root, not Path(\".\")"
