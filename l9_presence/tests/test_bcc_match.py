"""BCC Match (A1-b) v0 tests.

Pins the design §11 acceptance tests + the F-A1b-AUDIT-1 v0 NONE-only rails:
  poison (L9 payload rejected LOUD) · M15 reject (0 authored) · M16 reject (HYGIENE_FAIL) ·
  M17 admit (SYNCHRONIZED + high coherence) · PARTIAL reject · isolation (never writes bcc_l9) ·
  honesty (advisory + population_certified=false) · reference (kas/deferred commitment + PoSP) ·
  chain integrity + monotonic ts · type discriminator required · coherence math · L4 NONE admits ·
  NONE-only enforcement · session-id anti-assertion · NOMINAL-only writes · genesis distinct from bcc_l9.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from l9_presence.bcc_match import (
    BCCMatchConfig,
    MatchHarvester,
    BCCMatchStore,
    MATCH_ARTIFACT_SCHEMA,
    build_match_presence_artifact,
    coherence_fraction,
    compute_bcc_match_hash,
    genesis_bcc_match,
    passes_match_admission,
)
from l9_presence.bcc import genesis_bcc

_SID = "a" * 64


def _posp(verdict="SYNCHRONIZED", sid=_SID, notes=None):
    return {"verdict": verdict, "session_id": sid,
            "kas": {"commitment": "aa" * 32},
            "fusion": {"record_hashes": ["cc" * 32, "dd" * 32]},
            "archive": {"dir": "retina_kf_archive/match17", "id_verified": True},
            "events_roots": {"kas_session_root": "bb" * 32, "retina_perception_root": None},
            "temporal_beacon": {"block_number": 45447322, "block_hash": "ee" * 32},
            "notes": notes or []}


def _kas(verdict="AUTHORED_SESSION", sid=_SID):
    return {"verdict": verdict, "commitment": "aa" * 32, "session_id": sid, "authored_kills": 8}


def _deferred(verdict="DEFERRED_AUTHORED_SESSION", sid=_SID, authored=8, observed=1):
    return {"verdict": verdict, "session_id": sid, "deferred_authored": authored,
            "deferred_observed": observed, "commitment": "aa" * 32}


def _m17_artifact():
    art, reasons = build_match_presence_artifact(
        session_id=_SID, session_display="match17", posp=_posp(), kas=_kas(),
        deferred=_deferred(), authored_clusters=8, eligible_clusters=9, transport="RP")
    assert reasons == []
    assert art is not None
    return art


# ------------------------------------------------------------------- admission / build behavior
def test_m17_admits_synchronized_high_coherence():
    """§11.4 — SYNCHRONIZED + high authored fraction builds one NOMINAL row; verify() true."""
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        rec = h.record(_m17_artifact())
        assert rec is not None and rec["seq"] == 0
        assert h.store.verify() is True
        assert h.status()["match_presence"] == 1


def test_m15_zero_authored_rejected():
    """§11.2 — zero-authored / link-flip style → not built, chain length unchanged."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(), kas=_kas(verdict="INSUFFICIENT_KILLS"),
        deferred=None, authored_clusters=0, eligible_clusters=5)
    assert art is None
    assert any(r.startswith("G5") for r in reasons)


def test_m16_hygiene_fail_rejected():
    """§11.3 — inherited HYGIENE_FAIL → rejected (G6)."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(), kas=_kas(verdict="HYGIENE_FAIL"),
        deferred=None, authored_clusters=8, eligible_clusters=9)
    assert art is None
    assert any(r.startswith("G6") for r in reasons)


def test_partial_surfaces_rejected():
    """§11.5 — PoSP PARTIAL_SURFACES → rejected (G2, SYNCHRONIZED-only)."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(verdict="PARTIAL_SURFACES"), kas=_kas(),
        deferred=_deferred(), authored_clusters=8, eligible_clusters=9)
    assert art is None
    assert any(r.startswith("G2") for r in reasons)


def test_unverifiable_posp_rejected():
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(verdict="UNVERIFIABLE"), kas=_kas(),
        deferred=_deferred(), authored_clusters=8, eligible_clusters=9)
    assert art is None and any(r.startswith("G2") for r in reasons)


def test_coherence_floor_rejects_below():
    """Below the 0.50 floor → G4 reject; the fraction is reported in the reason."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(), deferred=_deferred(authored=2, observed=8),
        kas=None, authored_clusters=2, eligible_clusters=10)
    assert art is None
    assert any(r.startswith("G4") and "0.200" in r for r in reasons)


def test_coherence_floor_admits_at_boundary():
    """Exactly at the floor admits (>= floor)."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(), deferred=_deferred(authored=5, observed=5),
        kas=None, authored_clusters=5, eligible_clusters=10)
    assert reasons == [] and art is not None
    assert art["admission"]["coherence_fraction"] == 0.5


def test_missing_session_id_rejected():
    art, reasons = build_match_presence_artifact(
        session_id="", posp=_posp(sid=""), kas=_kas(sid=""),
        authored_clusters=8, eligible_clusters=9)
    assert art is None and any(r.startswith("G1") for r in reasons)


def test_posp_id_mismatch_rejected():
    """G3 — PoSP wrapper session_id differs from the artifact session_id."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(sid="f" * 64), kas=_kas(),
        deferred=_deferred(), authored_clusters=8, eligible_clusters=9)
    assert art is None and any(r.startswith("G3") for r in reasons)


def test_posp_mismatch_note_rejected():
    """G3 — a MISMATCH note on the PoSP record poisons admission even if verdict looked ok."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(notes=["kas: session_id MISMATCH (abc… != def…)"]),
        kas=_kas(), deferred=_deferred(), authored_clusters=8, eligible_clusters=9)
    assert art is None and any(r.startswith("G3") for r in reasons)


def test_kas_session_id_anti_assertion():
    """G6 — a KAS whose session_id != the artifact's is refused (anti-assertion, PoSP precedent)."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(), kas=_kas(sid="9" * 64),
        deferred=_deferred(), authored_clusters=8, eligible_clusters=9)
    assert art is None and any("mismatch" in r for r in reasons)


def test_deferred_only_authorship_admits():
    """The RP card-free path: no live KAS, deferred DEFERRED_AUTHORED_SESSION carries admission."""
    art, reasons = build_match_presence_artifact(
        session_id=_SID, posp=_posp(), kas=None, deferred=_deferred(),
        authored_clusters=8, eligible_clusters=9)
    assert reasons == [] and art is not None
    assert art["admission"]["authorship_tier"] == "DEFERRED"


def test_authorship_tier_both():
    art = _m17_artifact()
    assert art["admission"]["authorship_tier"] == "BOTH"


# ------------------------------------------------------------------- v0 NONE-only + honesty rails
def test_v0_feature_contract_is_none():
    """§11 (L4 NONE still admits) + F-A1b-AUDIT-1 — v0 always emits NONE/dim=0."""
    art = _m17_artifact()
    fc = art["feature_contract"]
    assert fc["name"] == "NONE" and fc["dim"] == 0 and fc["vector"] == [] and fc["keys"] == []


def test_honesty_fields_frozen():
    """§11.7 — every row carries advisory=true, cert_scope=developer_self, population_certified=false."""
    art = _m17_artifact()
    assert art["advisory"] is True
    assert art["cert_scope"] == "developer_self"
    assert art["population_certified"] is False


def test_reference_and_bind_present():
    """§11.8 — artifact references a kas/deferred commitment + PoSP SYNCHRONIZED."""
    art = _m17_artifact()
    refs = art["assertion_refs"]
    assert refs["posp_verdict"] == "SYNCHRONIZED"
    assert refs["kas_commitment"] or refs["deferred_verdict"]
    assert art["admission"]["posp_commitment_refs"].get("kas")
    # named roots travel, either honestly None
    assert "kas_session_root" in refs and "retina_perception_root" in refs


# ------------------------------------------------------------------- harvester / store rails
def test_poison_l9_payload_rejected_loud():
    """§11.1 — an L9 3-float payload cannot be silently written into the match chain (raises)."""
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        with pytest.raises(ValueError):
            h.record({"type": "l9", "features": [0.31, 1.2, 0.6]})
        assert h.store.load() == []          # chain untouched


def test_non_none_feature_contract_rejected_loud():
    """F-A1b-AUDIT-1 — a smuggled L4 vector (name != NONE) is refused LOUD in v0."""
    art = _m17_artifact()
    art["feature_contract"] = {"name": "L4_SESSION_V13", "dim": 13, "keys": [], "vector": [0.0] * 13}
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        with pytest.raises(ValueError):
            h.record(art)


def test_population_certified_true_rejected_loud():
    art = _m17_artifact()
    art["population_certified"] = True
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        with pytest.raises(ValueError):
            h.record(art)


def test_type_discriminator_required():
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        with pytest.raises(ValueError):
            h.record({"schema": MATCH_ARTIFACT_SCHEMA})           # no type


def test_dormant_is_noop():
    """Default-OFF → record() returns None and writes nothing."""
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=False, out_dir=d))
        assert h.record(_m17_artifact()) is None
        assert h.store.load() == []


def test_degraded_quality_not_written():
    """§6.3 — NOMINAL-only writes; a non-NOMINAL quality_code is rejected (returns None)."""
    art = _m17_artifact()
    art["admission"]["quality_code"] = 0x10        # DEGRADED
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        assert h.record(art) is None
        assert h.store.load() == []


def test_chain_integrity_and_monotonic_ts():
    with tempfile.TemporaryDirectory() as d:
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        r0 = h.record(_m17_artifact())
        r1 = h.record(_m17_artifact())
        assert r1["seq"] == 1 and r1["ts_ns"] > r0["ts_ns"]
        assert r1["prev_hash"] == r0["bcc_match_hash"]
        assert h.store.verify() is True


def test_tamper_detected():
    with tempfile.TemporaryDirectory() as d:
        store = BCCMatchStore(d)
        store.append({"type": "match_presence", "x": 1}, 0x01, 0x01)
        # corrupt the on-disk payload
        with open(store.path, "r", encoding="utf-8") as fh:
            line = fh.read()
        with open(store.path, "w", encoding="utf-8") as fh:
            fh.write(line.replace('"x": 1', '"x": 2'))
        assert store.verify() is False


def test_isolation_writes_only_match_dir():
    """§11.6 — after harvest, only bcc_match/ is written; no bcc_l9 file appears."""
    with tempfile.TemporaryDirectory() as base:
        match_dir = os.path.join(base, "bcc_match")
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=match_dir))
        h.record(_m17_artifact())
        assert os.path.isfile(os.path.join(match_dir, "bcc_match_chain.jsonl"))
        assert not os.path.exists(os.path.join(base, "bcc_l9"))
        # the store's only path is under its own out_dir
        assert h.store.path.startswith(match_dir)


def test_genesis_distinct_from_bcc_l9():
    """D-A1b-2 — different genesis so the two lanes cannot be concatenated by accident."""
    assert genesis_bcc_match() != genesis_bcc()


def test_hash_formula_twin_layout():
    """Formula-twin of bcc.compute_bcc_hash: same 74-byte preimage layout, different genesis."""
    g = genesis_bcc_match()
    h = compute_bcc_match_hash(g, "ab" * 32, 0x01, 0x01, 1)
    assert isinstance(h, str) and len(h) == 64


def test_coherence_fraction_math():
    assert coherence_fraction(8, 9) == pytest.approx(8 / 9)
    assert coherence_fraction(0, 5) == 0.0          # guarded; G5 rejects this upstream anyway
    assert coherence_fraction(5, 0) == 5.0          # max(1,·) guard; unreachable post-G5


def test_admission_reasons_accumulate():
    """A fully-broken input reports every failed gate, not just the first."""
    ok, reasons = passes_match_admission(
        session_id="", posp={"verdict": "UNVERIFIABLE"}, kas={"verdict": "HYGIENE_FAIL"},
        deferred=None, authored_clusters=0, eligible_clusters=0)
    assert ok is False
    heads = {r.split(":")[0] for r in reasons}
    assert {"G1", "G2", "G5", "G6"}.issubset(heads)
