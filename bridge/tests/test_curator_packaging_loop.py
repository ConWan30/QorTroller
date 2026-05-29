"""Data Economy Arc 3 Commit 1 — CuratorPackagingLoop core.

The Curator's post-session packaging orchestrator. DORMANT by default
(curator_packaging_enabled=False); FAIL-OPEN on operational faults (missing
session / aggregation / cooling all DEFER, never error); FAIL-CLOSED on consent
integrity (absent or hash-mismatched manifest ABORTS — no listing). NO autonomous
on-chain action: even full_autonomy only marks a package READY_FOR_SUBMISSION; the
actual marketplace tx is Commit 2's dry-run-gated + operator-fired path.

   T-CPL-1  Data floor raises ProtocolViolationError on any forbidden raw field.
   T-CPL-2  Aggregation below N=10 DEFERS (not an error).
   T-CPL-3  Cooling within 72h DEFERS (not an error).
   T-CPL-4  Consent manifest hash mismatch ABORTS (fail closed).
   T-CPL-5  approval_required autonomy writes the intent to pending_listings.
   T-CPL-6  full_autonomy marks READY_FOR_SUBMISSION (no broadcast, no tx).
   T-CPL-7  Every packaging decision appends an audit-log entry.
   T-CPL-8  Session status is updated on every decision.
   T-CPL-9  Dormant (enabled=False) short-circuits to DISABLED, no reads.
"""
from __future__ import annotations

import time

import pytest

from bridge.vapi_bridge import curator_packaging_loop as cpl
from bridge.vapi_bridge.curator_packaging_loop import (
    CuratorPackagingLoop,
    ProtocolViolationError,
    ConsentTamperError,
)

_DEVICE = "a" * 64
_OLD = time.time() - 100 * 3600       # 100h ago → past the 72h cooling window
_RECENT = time.time() - 1 * 3600      # 1h ago → still cooling


class _Cfg:
    def __init__(self, enabled=True, registry=""):
        self.curator_packaging_enabled = enabled
        self.consent_registry_address = registry


class _Chain:
    def __init__(self, on_chain_hash=None):
        self._hash = on_chain_hash

    def get_consent_manifest_hash(self, device_id):
        return self._hash


class _Store:
    """In-memory stub recording every loop interaction."""

    def __init__(self, *, session=None, manifest=None, n_sessions=50):
        self._session = session
        self._manifest = manifest
        self._n = n_sessions
        self.pending: list[dict] = []
        self.packaging_actions: list[dict] = []
        self.listing_intents: list[dict] = []
        self.session_status_updates: list[tuple] = []

    def get_curator_session_aggregate(self, session_id):
        if self._session is None:
            return None
        return dict(self._session, session_id=session_id)

    def get_curator_consent_manifest(self, device_id):
        return dict(self._manifest) if self._manifest else None

    def count_packageable_sessions(self, device_id):
        return self._n

    def insert_pending_listing(self, intent):
        self.pending.append(dict(intent))
        return len(self.pending)

    def record_curator_listing_intent(self, intent):
        self.listing_intents.append(dict(intent))

    def record_curator_packaging_action(self, entry):
        self.packaging_actions.append(dict(entry))

    def update_curator_session_status(self, session_id, outcome):
        self.session_status_updates.append((session_id, outcome))


def _manifest(autonomy=cpl.AUTONOMY_APPROVAL_REQUIRED, manifest_hash="0xabc", **kw):
    m = {
        "autonomy_level": autonomy,
        "allowed_categories": [1, 2],
        "manifest_hash": manifest_hash,
        "min_sessions": 10,
        "cooling_hours": 72,
    }
    m.update(kw)
    return m


def _session(**kw):
    s = {"device_id": _DEVICE, "ended_at": _OLD, "created_at": _OLD}
    s.update(kw)
    return s


def _loop(store, *, enabled=True, registry="", on_chain_hash=None):
    return CuratorPackagingLoop(
        _Chain(on_chain_hash=on_chain_hash),
        _Cfg(enabled=enabled, registry=registry),
        store,
    )


# ── T-CPL-1 ───────────────────────────────────────────────────────────────────

def test_T_CPL_1_data_floor_raises_on_forbidden_fields():
    loop = _loop(_Store())
    for bad in cpl.FORBIDDEN_FIELDS:
        with pytest.raises(ProtocolViolationError):
            loop._apply_data_floor({"device_id": _DEVICE, bad: [1, 2, 3]})
    # A clean aggregate passes through unchanged.
    clean = {"device_id": _DEVICE, "trigger_sector_histogram": [0, 1]}
    assert loop._apply_data_floor(clean) is clean


# ── T-CPL-2 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_2_aggregation_below_floor_defers():
    store = _Store(session=_session(), manifest=_manifest(), n_sessions=4)
    res = await _loop(store).on_session_complete("sess-1")
    assert res["outcome"] == cpl.OUTCOME_DEFERRED_AGGREGATION
    assert res["have"] == 4 and res["need"] == 10
    assert store.pending == []          # nothing listed on a deferral


# ── T-CPL-3 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_3_cooling_within_window_defers():
    store = _Store(session=_session(ended_at=_RECENT, created_at=_RECENT),
                   manifest=_manifest(), n_sessions=50)
    res = await _loop(store).on_session_complete("sess-2")
    assert res["outcome"] == cpl.OUTCOME_DEFERRED_COOLING
    assert res["available_at"] > time.time()
    assert store.pending == []


# ── T-CPL-4 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_4_consent_hash_mismatch_aborts():
    # Registry set + claimed manifest hash diverges from on-chain authority.
    store = _Store(session=_session(), manifest=_manifest(manifest_hash="0xCLAIMED"),
                   n_sessions=50)
    loop = _loop(store, registry="0xRegistry", on_chain_hash="0xONCHAIN")
    with pytest.raises(ConsentTamperError):
        await loop.on_session_complete("sess-3")
    assert store.pending == []          # tamper never lists


@pytest.mark.asyncio
async def test_T_CPL_4b_missing_manifest_aborts():
    store = _Store(session=_session(), manifest=None, n_sessions=50)
    with pytest.raises(ConsentTamperError):
        await _loop(store).on_session_complete("sess-3b")


# ── T-CPL-5 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_5_approval_required_writes_pending():
    store = _Store(session=_session(),
                   manifest=_manifest(autonomy=cpl.AUTONOMY_APPROVAL_REQUIRED),
                   n_sessions=50)
    res = await _loop(store).on_session_complete("sess-4")
    assert res["outcome"] == cpl.OUTCOME_PENDING_APPROVAL
    assert len(store.pending) == 1
    assert store.pending[0]["session_id"] == "sess-4"
    assert store.pending[0]["consent_policy_hash"] == "0xabc"
    assert store.listing_intents == []  # not auto-listed; queued for the gamer


# ── T-CPL-6 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_6_full_autonomy_ready_no_broadcast():
    store = _Store(session=_session(),
                   manifest=_manifest(autonomy=cpl.AUTONOMY_FULL),
                   n_sessions=50)
    res = await _loop(store).on_session_complete("sess-5")
    assert res["outcome"] == cpl.OUTCOME_READY_FOR_SUBMISSION
    # full_autonomy means no human approval STEP — not an autonomous tx. The
    # package is recorded as ready; nothing is queued for approval and no chain
    # broadcast occurs (the loop holds no broadcast path at all).
    assert store.pending == []
    assert len(store.listing_intents) == 1


# ── T-CPL-7 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_7_audit_entry_on_every_decision():
    # Defer, pending, and ready each append exactly one audit entry.
    for n, autonomy, expect in (
        (4, cpl.AUTONOMY_APPROVAL_REQUIRED, cpl.OUTCOME_DEFERRED_AGGREGATION),
        (50, cpl.AUTONOMY_APPROVAL_REQUIRED, cpl.OUTCOME_PENDING_APPROVAL),
        (50, cpl.AUTONOMY_FULL, cpl.OUTCOME_READY_FOR_SUBMISSION),
    ):
        store = _Store(session=_session(), manifest=_manifest(autonomy=autonomy),
                       n_sessions=n)
        loop = _loop(store)
        await loop.on_session_complete("sess-audit")
        assert len(store.packaging_actions) == 1
        assert store.packaging_actions[0]["outcome"] == expect
        assert len(loop.audit_log) == 1          # local audit surface too


# ── T-CPL-8 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_8_session_status_updated():
    store = _Store(session=_session(),
                   manifest=_manifest(autonomy=cpl.AUTONOMY_FULL), n_sessions=50)
    await _loop(store).on_session_complete("sess-6")
    assert store.session_status_updates == [("sess-6", cpl.OUTCOME_READY_FOR_SUBMISSION)]


# ── T-CPL-9 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CPL_9_dormant_short_circuits():
    store = _Store(session=_session(), manifest=_manifest(), n_sessions=50)
    res = await _loop(store, enabled=False).on_session_complete("sess-7")
    assert res["outcome"] == cpl.OUTCOME_DISABLED
    # Dormant must not read session data, list, or audit.
    assert store.pending == []
    assert store.packaging_actions == []
    assert store.session_status_updates == []


# ─── Commit 2 — CuratorListingBuilder (T-CLB-1..6) ──────────────────────────────
"""Commit 2 — tier-gated, category-encrypted, operator-fired listing builder.

   T-CLB-1  Proof generation succeeds for default-ON tiers 1-2.
   T-CLB-2  Tier 3/4 proof requires the explicit consent flag (else fail-closed).
   T-CLB-3  Encryption uses a DISTINCT key per buyer category (round-trips; one
            category's key never decrypts another's ciphertext).
   T-CLB-4  submit_listing dry-runs by default (no broadcast) + broadcasts only
            when dry_run=False, kill-switch off, and a marketplace handle exists.
   T-CLB-5  Listing rejected when the buyer category is not in the consent policy.
   T-CLB-6  Listing metadata always carries the consent_policy_hash.
"""
from bridge.vapi_bridge.curator_packaging_loop import (
    CuratorListingBuilder,
    BuyerCategoryRejected,
    CategoryKeyUnavailable,
)


class _Prover:
    """Deterministic stand-in for PITLProver (mock-mode equivalent)."""

    def generate_proof(self, *, features_dict, device_id, l5_humanity,
                       e4_drift, inference_result, epoch):
        return (b"\x01" * 256, 111, 222, 333)


class _Cfg2:
    def __init__(self, master_key="master-secret", paused=True):
        self.curator_category_master_key = master_key
        self.chain_submission_paused = paused


class _Marketplace:
    def __init__(self):
        self.calls = []

    async def create_listing(self, **kw):
        self.calls.append(kw)
        return {"error": "", "tx_hash": "0xdeadbeef", "row_id": 1}


def _builder(master_key="master-secret", paused=True, marketplace=None):
    return CuratorListingBuilder(
        _Cfg2(master_key=master_key, paused=paused),
        prover=_Prover(),
        marketplace=marketplace,
    )


def _sess():
    return {"device_id": _DEVICE, "session_id": "sess-clb",
            "features": {"micro_tremor_accel_variance": 1.0},
            "l5_humanity": 0.8, "e4_drift": 0.1,
            "inference_result": 0x20, "epoch": 100}


# ── T-CLB-1 ───────────────────────────────────────────────────────────────────

def test_T_CLB_1_default_tiers_generate():
    b = _builder()
    m = _manifest()  # no tier-3/4 consent flags
    assert b._permitted_proof_tiers(m) == (1, 2)
    for tier in (cpl.PROOF_TIER_SKILL_RANKING, cpl.PROOF_TIER_TRAJECTORY):
        pkg = b.generate_proof_package(_sess(), tier, m)
        assert pkg["tier"] == tier
        assert len(pkg["proof"]) == 256
        assert pkg["feature_commitment"] == 111


# ── T-CLB-2 ───────────────────────────────────────────────────────────────────

def test_T_CLB_2_high_tier_requires_consent():
    b = _builder()
    base = _manifest()
    # Without the flag, tier 3/4 are NOT permitted → fail closed.
    for tier in (cpl.PROOF_TIER_CONTEXT_PERFORMANCE, cpl.PROOF_TIER_FULL_SESSION):
        with pytest.raises(cpl.ProtocolViolationError):
            b.generate_proof_package(_sess(), tier, base)
    # With explicit flags, they become permitted.
    consented = _manifest(allow_context_performance_proof=True,
                          allow_full_session_proof=True)
    assert b._permitted_proof_tiers(consented) == (1, 2, 3, 4)
    assert b.generate_proof_package(_sess(), 3, consented)["tier"] == 3
    assert b.generate_proof_package(_sess(), 4, consented)["tier"] == 4


# ── T-CLB-3 ───────────────────────────────────────────────────────────────────

def test_T_CLB_3_per_category_key_isolation():
    b = _builder()
    k_acad = b._category_key(cpl.BUYER_CATEGORY_ACADEMIC)
    k_brand = b._category_key(cpl.BUYER_CATEGORY_BRAND)
    assert len(k_acad) == 32 and k_acad != k_brand          # distinct keys
    assert b._category_key(cpl.BUYER_CATEGORY_ACADEMIC) == k_acad  # deterministic

    enc = b.encrypt_package(b"payload-bytes", cpl.BUYER_CATEGORY_ACADEMIC)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    # Correct category key round-trips.
    assert AESGCM(k_acad).decrypt(enc["nonce"], enc["ciphertext"], None) == b"payload-bytes"
    # A different category's key CANNOT decrypt it (Layer-4 damage bounding).
    with pytest.raises(Exception):
        AESGCM(k_brand).decrypt(enc["nonce"], enc["ciphertext"], None)

    # No master key → fail closed (never ship plaintext).
    with pytest.raises(CategoryKeyUnavailable):
        _builder(master_key="").encrypt_package(b"x", cpl.BUYER_CATEGORY_ACADEMIC)


# ── T-CLB-4 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CLB_4_submit_dry_run_default_and_gated_broadcast():
    meta = {"consent_policy_hash": "0xabc", "buyer_category": 1}
    # Default: dry-run, no broadcast, no marketplace contact.
    mkt = _Marketplace()
    res = await _builder(marketplace=mkt).submit_listing(
        "0xseller", meta, price_iotx=5.0, consent_bitmask=8)
    assert res["dry_run"] is True and res["broadcast"] is False
    assert mkt.calls == []

    # dry_run=False but kill-switch ON → refuse, still no broadcast.
    res = await _builder(paused=True, marketplace=mkt).submit_listing(
        "0xseller", meta, price_iotx=5.0, consent_bitmask=8, dry_run=False)
    assert res["broadcast"] is False and "kill-switch" in res["error"]
    assert mkt.calls == []

    # dry_run=False + kill-switch OFF + marketplace present → broadcast (stub).
    res = await _builder(paused=False, marketplace=mkt).submit_listing(
        "0xseller", meta, price_iotx=5.0, consent_bitmask=8, dry_run=False)
    assert res["broadcast"] is True and res["tx_hash"] == "0xdeadbeef"
    assert len(mkt.calls) == 1 and mkt.calls[0]["seller_address"] == "0xseller"


# ── T-CLB-5 ───────────────────────────────────────────────────────────────────

def test_T_CLB_5_buyer_category_not_in_policy_rejected():
    b = _builder()
    m = _manifest(allowed_categories=[1, 2])
    b.assert_buyer_category_allowed(1, m)              # permitted → no raise
    with pytest.raises(BuyerCategoryRejected):
        b.assert_buyer_category_allowed(4, m)          # BRAND not allowed
    with pytest.raises(BuyerCategoryRejected):
        b.assert_buyer_category_allowed(3, _manifest(allowed_categories=[]))


# ── T-CLB-6 ───────────────────────────────────────────────────────────────────

def test_T_CLB_6_metadata_carries_consent_policy_hash():
    b = _builder()
    m = _manifest(manifest_hash="0xPOLICY", allowed_categories=[1, 2])
    pkg = b.generate_proof_package(_sess(), 1, m)
    meta = b.build_listing_metadata(_sess(), m, pkg, cpl.BUYER_CATEGORY_ACADEMIC)
    assert meta["consent_policy_hash"] == "0xPOLICY"
    assert meta["buyer_category"] == 1
    assert meta["proof_tier"] == 1
    assert meta["schema"] == "vapi-curator-listing-v1"
