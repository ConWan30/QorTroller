"""Phase B freeze ceremony (Step B-pre) — T-FREEZE-* tests.

Verifies the first-time QorTroller-namespace freeze infrastructure: the parallel
mythos_qortroller_crypto_drift scanner + QorTroller frozensets, the
qortroller_commitment_family_count canonical fact, and the new PV-CI invariants
— while confirming the VAPI Layer-C surfaces are UNTOUCHED (FC-(a)).

The cryptographic SEAL (allowlist Merkle-root regen via `--generate`) is the
operator-gated Step A; these tests verify the code-level Step-B-pre build.

T-FREEZE-1..7.
"""
from __future__ import annotations

import asyncio
import sys
import types as _types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
for _p in (PROJECT_ROOT, BRIDGE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _d = _types.ModuleType("dotenv")
    _d.load_dotenv = lambda *a, **k: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _d

from vapi_bridge import mythos_variants as mv  # noqa: E402

_GATE_SRC = (PROJECT_ROOT / "scripts" / "vapi_invariant_gate.py").read_text(encoding="utf-8")


# T-FREEZE-1: QorTroller frozen-family frozenset = exactly ③'s 2 tags (= 1 family)
def test_t_freeze_1_qortroller_frozen_family_tags():
    assert mv._QORTROLLER_FROZEN_FAMILY_TAGS == frozenset({
        b"QORTROLLER-IPACT-RENEWAL-v1",
        b"QORTROLLER-IPACT-RENEWAL-GENESIS-v1",
    })


# T-FREEZE-2: CHALLENGE is a known CAPABILITY tag (not a frozen family → not counted)
def test_t_freeze_2_challenge_is_capability_not_family():
    assert b"QORTROLLER-IPACT-CHALLENGE-v1" in mv._QORTROLLER_KNOWN_CAPABILITY_TAGS
    assert b"QORTROLLER-IPACT-CHALLENGE-v1" not in mv._QORTROLLER_FROZEN_FAMILY_TAGS


# T-FREEZE-3: parallel scanner discovers ③'s tags + CHALLENGE with 0 findings (healthy)
def test_t_freeze_3_qortroller_scanner_clean():
    findings = asyncio.run(mv.mythos_qortroller_crypto_drift())
    assert len(findings) == 0, [getattr(f, "description", f) for f in findings]


# T-FREEZE-4: VAPI scanner + frozenset UNTOUCHED — 12 families, 0 findings (FC-(a))
def test_t_freeze_4_vapi_namespace_untouched():
    assert len(mv._PATTERN_017_FROZEN_TAGS) == 12
    findings = asyncio.run(mv.mythos_crypto_drift())
    assert len(findings) == 0, [getattr(f, "description", f) for f in findings]


# T-FREEZE-5: qortroller_commitment_family_count canonical fact = "1"; VAPI fact = "12"
def test_t_freeze_5_count_facts():
    from vapi_bridge import doc_consistency_registry as reg
    facts = {f.name: f for f in reg.REGISTRY}
    assert "qortroller_commitment_family_count" in facts
    assert facts["qortroller_commitment_family_count"].current_value == "1"
    assert facts["frozen_v1_commitment_family_count"].current_value == "12"


# T-FREEZE-6: the 11 new PV-CI invariants are declared (+ INV-MYTHOS-FAMILIES-001 preserved)
def test_t_freeze_6_pvci_invariants_declared():
    for expected in [
        "INV-COMPOSITE-SIG-PREFIX-001", "INV-COMPOSITE-SIG-LABELS-001",
        "INV-COMPOSITE-SIG-ENVELOPE-001", "INV-COMPOSITE-SIG-PUBKEY-LEN-001",
        "INV-COMPOSITE-SIG-PUBKEY-FORMAT-001", "INV-IPACT-RENEWAL-DOMAIN-001",
        "INV-IPACT-RENEWAL-GENESIS-001", "INV-IPACT-RENEWAL-EPOCH-001",
        "INV-IPACT-RENEWAL-PREIMAGE-001", "INV-IPACT-CHALLENGE-001",
        "INV-QORTROLLER-FAMILIES-001",
    ]:
        assert f'id="{expected}"' in _GATE_SRC, f"missing invariant {expected}"
    assert 'id="INV-MYTHOS-FAMILIES-001"' in _GATE_SRC  # VAPI invariant preserved


# T-FREEZE-7: namespace separation — no QorTroller tag leaked into VAPI frozensets,
# and the QorTroller frozenset name does NOT contain the VAPI-pinned substring
# (the collision the rename fixed: INV-MYTHOS-FAMILIES-001 must match exactly once).
def test_t_freeze_7_namespace_separation():
    for tag in mv._PATTERN_017_FROZEN_TAGS:
        assert not tag.startswith(b"QORTROLLER-"), tag
    for tag in mv._QORTROLLER_FROZEN_FAMILY_TAGS | mv._QORTROLLER_KNOWN_CAPABILITY_TAGS:
        assert tag.startswith(b"QORTROLLER-"), tag
    # collision guard: the QorTroller frozenset declaration name must not contain
    # the VAPI INV-MYTHOS-FAMILIES-001 pinned substring "_PATTERN_017_FROZEN_TAGS"
    mv_src = (BRIDGE_DIR / "vapi_bridge" / "mythos_variants.py").read_text(encoding="utf-8")
    assert "_QORTROLLER_FROZEN_FAMILY_TAGS" in mv_src
    assert "_QORTROLLER_PATTERN_017_FROZEN_TAGS" not in mv_src  # renamed away from the collision
