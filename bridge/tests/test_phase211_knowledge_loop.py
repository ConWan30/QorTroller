"""
Phase 211 — Unified Knowledge Loop Tests
T211-1..8

Tests for novel components in vapi-mcp/unified_server.py:
  T211-1: MetaLearner.analyze() with empty entries returns safe defaults
  T211-2: MetaLearner.analyze() identifies invariant_violation as dominant_blocker
  T211-3: HypothesisDeduplicator.check() with no corpus returns is_duplicate=False
  T211-4: _validate_proposal() with all 20 mandatory invariants scores >= 0.70 (PASS)
  T211-5: _validate_proposal() with missing invariants fails with violation list
  T211-6: ExperimentLedger.stats() correctly computes pass_rate from mock log.jsonl
  T211-7: UnifiedWIFCorpus.stats() returns expected structure keys
  T211-8: _wif_fingerprint() is deterministic and distinct for different inputs
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# ── stub web3 / eth_account before any bridge import ─────────────────────────
import types

for _mod in ("web3", "web3.exceptions", "eth_account", "eth_account.messages",
             "web3.middleware", "web3.gas_strategies", "web3.gas_strategies.time_based"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_fake_web3 = sys.modules["web3"]
if not hasattr(_fake_web3, "Web3"):
    class _W3Stub:
        HTTPProvider = lambda *a, **kw: None
        class middleware_onion:
            inject = lambda *a, **kw: None
    _fake_web3.Web3 = _W3Stub

_fake_exc = sys.modules["web3.exceptions"]
if not hasattr(_fake_exc, "ContractLogicError"):
    _fake_exc.ContractLogicError = type("ContractLogicError", (Exception,), {})


# ── helpers to import unified_server without a running bridge ─────────────────

def _import_unified():
    """Import unified_server with PROJECT_ROOT patched to a temp dir."""
    unified_path = ROOT / "vapi-mcp"
    if str(unified_path) not in sys.path:
        sys.path.insert(0, str(unified_path))
    # Set VAPI_ROOT so the server doesn't try to stat production paths
    tmpdir = tempfile.mkdtemp()
    os.environ.setdefault("VAPI_ROOT", tmpdir)
    import importlib
    if "unified_server" in sys.modules:
        mod = sys.modules["unified_server"]
    else:
        import unified_server as mod
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# T211-1: MetaLearner.analyze() with empty entries
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_1_meta_learner_empty():
    """MetaLearner.analyze([]) returns safe defaults, no KeyError."""
    mod = _import_unified()
    result = mod.META.analyze([])

    assert result["dominant_blocker"] == "no_data"
    assert isinstance(result["theme_distribution"], dict)
    # empty-path returns recent_failures / pass_rate_trend, no total_* keys
    assert "pass_rate_trend" in result
    assert result["pass_rate_trend"] == []


# ─────────────────────────────────────────────────────────────────────────────
# T211-2: MetaLearner.analyze() identifies invariant_violation as dominant
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_2_meta_learner_invariant_blocker():
    """MetaLearner correctly identifies invariant_violation when most failures cite MISSING."""
    mod = _import_unified()

    entries = [
        {
            "passed": False,
            "reason": "INVARIANT FAILURE — 2 violations: MISSING: '228 bytes'; MISSING: 'dry_run=True'",
            "invariant_failures": ["MISSING: '228 bytes'", "MISSING: 'dry_run=True'"],
        },
        {
            "passed": False,
            "reason": "INVARIANT FAILURE — MISSING: '0.67' MISSING invariant violation",
            "invariant_failures": ["MISSING: '0.67'"],
        },
        {
            "passed": True,
            "reason": "PASS (score=0.900)",
            "invariant_failures": [],
        },
    ]

    result = mod.META.analyze(entries)

    assert result["dominant_blocker"] == "invariant_violation"
    assert "invariant_violation" in result["theme_distribution"]
    assert result["theme_distribution"]["invariant_violation"] >= 2
    assert result["total_failures"] == 2
    assert result["total_entries"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# T211-3: HypothesisDeduplicator with empty corpus returns not-duplicate
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_3_dedup_empty_corpus():
    """HypothesisDeduplicator.check() with no WIF files returns is_duplicate=False."""
    mod = _import_unified()

    # Override WIF_CORPUS_DIR + WIKI_WHAT_IF_DIR to temp empty dirs
    tmpdir = Path(tempfile.mkdtemp())
    orig_wif = mod.WIF_CORPUS_DIR
    orig_wiki = mod.WIKI_WHAT_IF_DIR
    mod.WIF_CORPUS_DIR   = tmpdir / "empty_wif"
    mod.WIKI_WHAT_IF_DIR = tmpdir / "empty_wiki"

    try:
        result = mod.DEDUP.check(
            probe_type="touchpad_corners",
            phase_candidate="212",
            title_keywords="per-pair probe ensemble",
        )
    finally:
        mod.WIF_CORPUS_DIR   = orig_wif
        mod.WIKI_WHAT_IF_DIR = orig_wiki

    assert result["is_duplicate"] is False
    assert result["confidence"] == "LOW"
    assert result["existing_entries"] == []


# ─────────────────────────────────────────────────────────────────────────────
# T211-4: _validate_proposal passes when all 20 invariants present
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_4_validate_proposal_pass():
    """_validate_proposal() scores >= 0.70 when all 20 invariants are verbatim in text."""
    mod = _import_unified()

    # Build a proposal that contains all 20 mandatory invariants
    invariant_block = "\n".join(mod.MANDATORY_INVARIANTS)
    proposal = f"""Phase 212 candidate — per-pair probe ensemble

W1 — Failure mode: separation_ratio pathways blocked by P2/P3 proximity.
  Mechanism: more touchpad_corners doesn't help because 0.362 is structural.
  TOURNAMENT BLOCKER: all pairs must be ratio > 1.0, non-negotiable.
  Invariants: 228 bytes wire format, SHA-256(raw[:164]) chain hash,
  7.009 anomaly threshold, 5.367 continuity, Poseidon(8), nPublic=5,
  BLOCK_QUORUM=0.67, GSR_ENABLED=false, L6B_ENABLED=false,
  dry_run=True default, NOMINAL sessions only for stable EMA,
  soulbound VHP, never hard gate for advisory codes.
  Phase 98 W1: threshold 0.60 was reachable by ClassJ (CLOSED Phase 147).
  separation ratio 0.362 free-form baseline (W1-009).

W2 — Opportunity: exclusive_because requires PITL stack + PoAC.

Mandatory invariants:
{invariant_block}
"""

    result = mod._validate_proposal(proposal)

    assert result["passed"] is True
    assert result["score"] >= 0.70
    assert result["invariant_failures"] == []
    assert "PASS" in result["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# T211-5: _validate_proposal fails with missing invariants
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_5_validate_proposal_fail():
    """_validate_proposal() fails when mandatory invariants are missing."""
    mod = _import_unified()

    # A proposal with no invariants at all
    minimal_proposal = "This is a Phase 212 proposal about separation ratio improvements."

    result = mod._validate_proposal(minimal_proposal)

    assert result["passed"] is False
    # Must have multiple violations — all 20 invariants should be missing
    assert len(result["invariant_failures"]) >= 15
    # Score should be low (invariants weight = 0.30, all missing → inv_score=0.0)
    assert result["score"] < 0.50
    assert "INVARIANT FAILURE" in result["reason"]
    # Specific critical invariants must be in violation list
    failure_text = " ".join(result["invariant_failures"])
    assert "228 bytes" in failure_text
    assert "SHA-256(raw[:164])" in failure_text
    assert "BLOCK_QUORUM=0.67" in failure_text


# ─────────────────────────────────────────────────────────────────────────────
# T211-6: ExperimentLedger.stats() from real log.jsonl
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_6_experiment_ledger_stats():
    """ExperimentLedger correctly computes pass_rate from a synthetic log.jsonl."""
    mod = _import_unified()

    tmpdir = Path(tempfile.mkdtemp())
    log_path = tmpdir / "log.jsonl"

    entries = [
        {"timestamp": "2026-04-01T00:00:00", "passed": True,  "score": 0.90, "reason": "PASS"},
        {"timestamp": "2026-04-02T00:00:00", "passed": False, "score": 0.40, "reason": "FAIL"},
        {"timestamp": "2026-04-03T00:00:00", "passed": True,  "score": 0.75, "reason": "PASS"},
        {"timestamp": "2026-04-04T00:00:00", "passed": True,  "score": 0.80, "reason": "PASS"},
    ]
    log_path.write_text(
        "\n".join(json.dumps(e) for e in entries),
        encoding="utf-8",
    )

    # Patch EXPERIMENT_LOG
    orig = mod.EXPERIMENT_LOG
    mod.EXPERIMENT_LOG = log_path
    # Create a fresh ledger that uses the new path
    ledger = mod.ExperimentLedger()

    try:
        stats = ledger.stats()
    finally:
        mod.EXPERIMENT_LOG = orig

    assert stats["total"] == 4
    assert stats["passed"] == 3
    assert stats["failed"] == 1
    assert abs(stats["pass_rate"] - 0.75) < 0.01
    assert abs(stats["mean_score"] - (0.90 + 0.40 + 0.75 + 0.80) / 4) < 0.01
    assert "score_distribution" in stats


# ─────────────────────────────────────────────────────────────────────────────
# T211-7: UnifiedWIFCorpus.stats() returns expected keys
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_7_unified_wif_corpus_stats():
    """UnifiedWIFCorpus.stats() returns the expected top-level keys."""
    mod = _import_unified()

    stats = mod.UNIFIED_WIF.stats()

    assert "total_deduplicated" in stats
    assert "by_source" in stats
    assert "what_if_corpus_files" in stats
    assert isinstance(stats["total_deduplicated"], int)
    assert stats["total_deduplicated"] >= 0

    # by_source values must be non-negative integers
    for source, count in stats["by_source"].items():
        assert isinstance(count, int)
        assert count >= 0


# ─────────────────────────────────────────────────────────────────────────────
# T211-8: _wif_fingerprint is deterministic and distinct
# ─────────────────────────────────────────────────────────────────────────────
def test_t211_8_wif_fingerprint_determinism():
    """_wif_fingerprint is deterministic for same input and distinct for different inputs."""
    mod = _import_unified()

    text_a = "W1: ioSwarm node-pool homogeneity collapses MINT_QUORUM=0.80 guarantee. Phase 110."
    text_b = "W2: Per-pair probe ensemble gate selects optimal probe per player pair. Phase 212."
    text_c = "W1: ioSwarm node-pool homogeneity collapses MINT_QUORUM=0.80 guarantee. Phase 110."

    fp_a1 = mod._wif_fingerprint(text_a)
    fp_a2 = mod._wif_fingerprint(text_a)  # same input twice
    fp_b  = mod._wif_fingerprint(text_b)
    fp_c  = mod._wif_fingerprint(text_c)  # same content as text_a

    # Deterministic
    assert fp_a1 == fp_a2, "fingerprint must be deterministic for same input"
    # Content-equal texts get same fingerprint
    assert fp_a1 == fp_c, "identical content must produce identical fingerprint"
    # Different content → different fingerprint
    assert fp_a1 != fp_b, "different content must produce distinct fingerprint"
    # All fingerprints are 16 hex chars
    assert len(fp_a1) == 16
    assert len(fp_b)  == 16
    assert all(c in "0123456789abcdef" for c in fp_a1)
