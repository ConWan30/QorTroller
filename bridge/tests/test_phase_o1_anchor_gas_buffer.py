"""Phase O1-FRR — Cedar bundle anchor gas buffer hardening tests.

Closes V-check Gap 2 from Phase O1-FRR plan: cedar_bundle_anchor.py
inherited the 1.20 default gas buffer from chain._send_tx instead of
the 1.25 buffer Phase 237.5 Path X established for IoTeX-storage-heavy
operations under elevated gas conditions.

Tests:

  T-O1-FRR-GAS-1: chain.set_agent_scope_root passes gas_buffer_multiplier=1.25
                  to _send_tx (operational layer of dual-anchor).
  T-O1-FRR-GAS-2: chain.update_agent_scope_governance passes 1.25 to _send_tx
                  (governance layer of dual-anchor).
  T-O1-FRR-GAS-3: _send_tx accepts gas_buffer_multiplier kwarg with default
                  1.2 (preserves all existing callers).

The tests are static — they grep the source for the exact 1.25 literal
in the right context.  Behavioral tests would require a full chain
mock + tx send pipeline, which is overkill for verifying a constant.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Mirror Phase O1 C2 test pattern — add bridge/ to sys.path so any
# bridge.* import resolves regardless of pytest invocation cwd.
_BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

import pytest

CHAIN_PY = Path(__file__).resolve().parent.parent / "vapi_bridge" / "chain.py"


def _read_chain_source() -> str:
    assert CHAIN_PY.exists(), f"chain.py not found at {CHAIN_PY}"
    return CHAIN_PY.read_text(encoding="utf-8")


def _extract_function_body(source: str, fn_name: str) -> str:
    """Extract from `async def fn_name(...)` to the next sibling `async def`
    or `def ` at the same indentation level (4 spaces — class method),
    or end-of-file if it's the last method.  Captures both signature line
    and body."""
    pattern = re.compile(
        rf"(    async def {re.escape(fn_name)}\(.*?\n)(.*?)(?=\n    async def |\n    def |\Z)",
        re.DOTALL,
    )
    m = pattern.search(source)
    assert m is not None, f"function {fn_name} not found in chain.py"
    return m.group(1) + m.group(2)


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-GAS-1: set_agent_scope_root uses 1.25 buffer
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_GAS_1_set_agent_scope_root_uses_125_buffer():
    """Operational dual-anchor leg passes gas_buffer_multiplier=1.25."""
    source = _read_chain_source()
    body = _extract_function_body(source, "set_agent_scope_root")

    # Must call _send_tx
    assert "self._send_tx" in body, (
        "set_agent_scope_root no longer routes through _send_tx — "
        "kill-switch + gas buffer guard broken!"
    )

    # Must explicitly pass gas_buffer_multiplier=1.25
    assert "gas_buffer_multiplier=1.25" in body, (
        "set_agent_scope_root does not pass gas_buffer_multiplier=1.25 — "
        "Phase O1-FRR Stream D gas buffer hardening regression!"
    )

    # The 1.25 must be paired with setAgentScopeRoot, not some other call
    # (defensive — multi-call functions could have multiple _send_tx invocations)
    assert "setAgentScopeRoot" in body
    assert body.find("setAgentScopeRoot") < body.find("gas_buffer_multiplier=1.25") + 200


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-GAS-2: update_agent_scope_governance uses 1.25 buffer
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_GAS_2_update_agent_scope_governance_uses_125_buffer():
    """Governance dual-anchor leg passes gas_buffer_multiplier=1.25."""
    source = _read_chain_source()
    body = _extract_function_body(source, "update_agent_scope_governance")

    assert "self._send_tx" in body, (
        "update_agent_scope_governance no longer routes through _send_tx"
    )
    assert "gas_buffer_multiplier=1.25" in body, (
        "update_agent_scope_governance does not pass gas_buffer_multiplier=1.25"
    )
    assert "updateAgentScope" in body
    assert body.find("updateAgentScope") < body.find("gas_buffer_multiplier=1.25") + 200


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-GAS-3: _send_tx accepts gas_buffer_multiplier kwarg
# (extra coverage — validates the API surface itself)
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_GAS_3_send_tx_accepts_gas_buffer_kwarg():
    """_send_tx signature includes gas_buffer_multiplier with default 1.2."""
    source = _read_chain_source()
    sig_pattern = re.compile(
        r"async def _send_tx\(\s*self,\s*tx_func,\s*\*args,\s*"
        r"value:\s*int\s*=\s*0,\s*"
        r"gas_buffer_multiplier:\s*float\s*=\s*1\.2,?\s*\)",
        re.DOTALL,
    )
    assert sig_pattern.search(source), (
        "_send_tx signature does not match expected shape with "
        "gas_buffer_multiplier: float = 1.2 default — Phase O1-FRR "
        "Stream D regression."
    )

    # Default 1.2 preserves all existing callers (verify_single, verify_batch,
    # all 22 chain methods that call _send_tx without override).  Only the
    # two anchor methods upgrade to 1.25.
    assert "tx[\"gas\"] = int(gas_estimate * buf)" in source, (
        "_send_tx no longer applies the buffer multiplier to estimated gas."
    )
