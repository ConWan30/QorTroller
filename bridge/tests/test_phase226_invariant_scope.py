"""Phase 226 — Invariant Scope Expansion (INV-019..022).

Tests verify that the provenance hash computation code in
scripts/vapi_invariant_gate.py is now frozen by the invariant gate.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
GATE_SCRIPT = REPO_ROOT / "scripts" / "vapi_invariant_gate.py"
ALLOWLIST_PATH = REPO_ROOT / ".github" / "INVARIANTS_ALLOWLIST.json"
STORE_PATH = REPO_ROOT / "bridge" / "vapi_bridge" / "store.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load_gate():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vapi_invariant_gate", GATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# T226-1: INVARIANTS list now contains exactly 86 entries
def test_t226_1_invariants_count():
    gate = _load_gate()
    assert len(gate.INVARIANTS) == 173


# T226-2: INV-019 matches _compute_governance_provenance_hash in gate script
def test_t226_2_inv019_compute_fn():
    gate = _load_gate()
    inv019 = next(i for i in gate.INVARIANTS if i.id == "INV-019")
    text = GATE_SCRIPT.read_text(encoding="utf-8")
    matches = [l for l in text.splitlines() if re.search(inv019.pattern, l, re.IGNORECASE)]
    assert len(matches) >= inv019.min_matches, f"INV-019 found {len(matches)} matches (expected >= {inv019.min_matches})"


# T226-3: INV-020 matches ts_ns.to_bytes(8, "big") in gate script
def test_t226_3_inv020_ts_ns():
    gate = _load_gate()
    inv020 = next(i for i in gate.INVARIANTS if i.id == "INV-020")
    text = GATE_SCRIPT.read_text(encoding="utf-8")
    matches = [l for l in text.splitlines() if re.search(inv020.pattern, l, re.IGNORECASE)]
    assert len(matches) >= inv020.min_matches, f"INV-020 found {len(matches)} matches (expected >= {inv020.min_matches})"


# T226-4: INV-021 matches _fetch_latest_provenance_hash in gate script
def test_t226_4_inv021_fetch_fn():
    gate = _load_gate()
    inv021 = next(i for i in gate.INVARIANTS if i.id == "INV-021")
    text = GATE_SCRIPT.read_text(encoding="utf-8")
    matches = [l for l in text.splitlines() if re.search(inv021.pattern, l, re.IGNORECASE)]
    assert len(matches) >= inv021.min_matches, f"INV-021 found {len(matches)} matches (expected >= {inv021.min_matches})"


# T226-5: INV-022 matches governance_provenance_chain in store.py
def test_t226_5_inv022_store_table():
    gate = _load_gate()
    inv022 = next(i for i in gate.INVARIANTS if i.id == "INV-022")
    text = STORE_PATH.read_text(encoding="utf-8")
    matches = [l for l in text.splitlines() if re.search(inv022.pattern, l, re.IGNORECASE)]
    assert len(matches) >= inv022.min_matches, f"INV-022 found {len(matches)} matches (expected >= {inv022.min_matches})"


# T226-6: INVARIANTS_ALLOWLIST.json has 86 entries after regeneration
def test_t226_6_allowlist_has_86_entries():
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    assert len(allowlist) == 173
    assert "INV-019" in allowlist
    assert "INV-020" in allowlist
    assert "INV-021" in allowlist
    assert "INV-022" in allowlist


# T226-7: run_gate() exits 0 — all 86 invariants pass current codebase
def test_t226_7_gate_pass():
    gate = _load_gate()
    results = gate.check_invariants()
    allowlist = gate.load_allowlist()
    failures = []
    for r in results:
        aid = r["id"]
        if not r["file_found"]:
            failures.append(f"{aid}: FILE_NOT_FOUND")
        elif not r["pattern_matched"]:
            failures.append(f"{aid}: pattern_not_matched")
        elif aid in allowlist and allowlist[aid]["digest"] != r["digest"]:
            failures.append(f"{aid}: DIGEST_MISMATCH")
    assert failures == [], f"Gate failures: {failures}"


# T226-8: compute_allowlist_hash() reflects new 86-entry allowlist
def test_t226_8_allowlist_hash_86_entries():
    gate = _load_gate()
    h = gate.compute_allowlist_hash()
    # Must be a 64-char hex string (not zeros sentinel)
    assert len(h) == 64
    assert h != "0" * 64
    # Allowlist file must have 86 entries for this hash to be correct
    allowlist = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    assert len(allowlist) == 173
