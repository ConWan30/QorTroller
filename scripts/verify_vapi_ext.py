"""
VAPI-EXT Verification Script — Phase 204+

Verifies that the VAPI-EXT sub-protocol extensibility layer is correctly installed.
All assertions must pass before VAPI_MOBILE and PRAGMA_JUDGE development begins.

Run as:
    python scripts/verify_vapi_ext.py
"""
import sys
import os

# Ensure bridge package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bridge"))

from vapi_bridge.sub_protocol_registry import SubProtocolRegistry
from vapi_bridge.coherence_rules.loader import CoherenceRuleLoader
from vapi_bridge.tool_registry import ToolRegistry

reg = SubProtocolRegistry.instance()
rules = CoherenceRuleLoader.load_all()
tools = ToolRegistry.instance().get_all_tools()

print(f"Registered protocols: {list(reg.get_registered().keys())}")
print(f"Loaded coherence rules: {len(rules)}")
print(f"Registered tools: {len(tools)}")

# Assertions — all must pass

assert "VAPI_CORE" in reg.get_registered(), "VAPI_CORE not registered"

vapi_core_cfg = reg.get("VAPI_CORE")
assert vapi_core_cfg is not None, "VAPI_CORE config is None"
assert vapi_core_cfg.tool_range == (1, 149), f"VAPI_CORE tool_range wrong: {vapi_core_cfg.tool_range}"
assert vapi_core_cfg.agent_range == (1, 36), f"VAPI_CORE agent_range wrong: {vapi_core_cfg.agent_range}"

assert len(rules) == 18, f"Expected 18 coherence rules, got {len(rules)}"
assert len(tools) == 0, (
    f"Expected 0 tools (ToolRegistry not pre-populated until BridgeAgent.__init__), "
    f"got {len(tools)}"
)

# Register tools from manifest to verify the registry mechanism works
from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
ToolRegistry.instance().register_tool_range(VAPI_CORE_TOOLS)
tools = ToolRegistry.instance().get_all_tools()
assert len(tools) == 149, f"Expected 149 tools after manifest registration, got {len(tools)}"

# Verify guard fields are present on all applicable rules (not silently dropped)
rules_with_guard = [r for r in rules if r.guard is not None]
print(f"Rules with guard lambdas: {len(rules_with_guard)}")
assert len(rules_with_guard) >= 1, "At least one rule should have a guard (Phase 204 IOSWARM rule)"

# Verify the specific IOSWARM guard rule
ioswarm_rules = [r for r in rules if r.name == "IOSWARM_ACTIVE_NO_ADJUDICATIONS"]
assert len(ioswarm_rules) == 1, "IOSWARM_ACTIVE_NO_ADJUDICATIONS not found"
assert ioswarm_rules[0].guard is not None, "IOSWARM guard was dropped — regression"
assert callable(ioswarm_rules[0].guard), "IOSWARM guard is not callable"

# Verify rule categories
contradiction_rules = [r for r in rules if r.category == "CONTRADICTION"]
orphan_rules = [r for r in rules if r.category == "ORPHAN"]
inversion_rules = [r for r in rules if r.category == "INVERSION"]
assert len(contradiction_rules) == 8, f"Expected 8 CONTRADICTION rules, got {len(contradiction_rules)}"
assert len(orphan_rules) == 6, f"Expected 6 ORPHAN rules, got {len(orphan_rules)}"
assert len(inversion_rules) == 4, f"Expected 4 INVERSION rules, got {len(inversion_rules)}"

# Verify tool range ownership
owner = reg.tool_range_owner(1)
assert owner == "VAPI_CORE", f"Tool #1 owner should be VAPI_CORE, got {owner}"
owner_149 = reg.tool_range_owner(149)
assert owner_149 == "VAPI_CORE", f"Tool #149 owner should be VAPI_CORE, got {owner_149}"
owner_150 = reg.tool_range_owner(150)
assert owner_150 is None, f"Tool #150 should have no owner yet, got {owner_150}"

print("\nVAPI-EXT verification PASSED — gateway open for VAPI_MOBILE and PRAGMA_JUDGE")
