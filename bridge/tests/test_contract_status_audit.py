"""HWFL-1 contract-status audit tests — F-CYCLE10-1 Option (b) verifier."""
from __future__ import annotations

from bridge.vapi_bridge.contract_status_audit import (
    ContractStatus,
    audit_contracts,
)

A = "0x" + "1" * 40
B = "0x" + "2" * 40
C = "0x" + "3" * 40
D = "0x" + "4" * 40


# ---------------------------------------------------------------------- T1
def test_explicit_superseded_suffix():
    data = {
        "FooRegistry": A,
        "FooRegistry_superseded": B,
    }
    r = audit_contracts(data)
    by_key = {rec.key: rec for rec in r.records}
    assert by_key["FooRegistry_superseded"].status == ContractStatus.SUPERSEDED
    assert by_key["FooRegistry"].status == ContractStatus.ACTIVE


# ---------------------------------------------------------------------- T2
def test_meta_marked_superseded():
    data = {
        "barregistry": A,
        "_barregistry_superseded_note": "replaced 2026-05-24",
    }
    r = audit_contracts(data)
    by_key = {rec.key: rec for rec in r.records}
    assert by_key["barregistry"].status == ContractStatus.SUPERSEDED
    assert "meta-key" in by_key["barregistry"].reason


# ---------------------------------------------------------------------- T3
def test_version_sibling_heuristic():
    data = {
        "TournamentGate": A,
        "TournamentGateV2": B,
        "TournamentGateV3": C,
    }
    r = audit_contracts(data)
    by_key = {rec.key: rec for rec in r.records}
    # Bare name has higher-version siblings → DEPRECATED-INFERRED
    assert by_key["TournamentGate"].status == ContractStatus.DEPRECATED_INFERRED
    assert by_key["TournamentGate"].superseded_by == "TournamentGateV2"
    # V2 has V3 sibling → also DEPRECATED-INFERRED
    assert by_key["TournamentGateV2"].status == ContractStatus.DEPRECATED_INFERRED
    assert by_key["TournamentGateV2"].superseded_by == "TournamentGateV3"
    # V3 is the latest → ACTIVE
    assert by_key["TournamentGateV3"].status == ContractStatus.ACTIVE


# ---------------------------------------------------------------------- T4
def test_underscore_version_suffix():
    data = {
        "VAPIProtocolLens": A,
        "VAPIProtocolLens_v2": B,
    }
    r = audit_contracts(data)
    by_key = {rec.key: rec for rec in r.records}
    assert by_key["VAPIProtocolLens"].status == ContractStatus.DEPRECATED_INFERRED
    assert by_key["VAPIProtocolLens"].superseded_by == "VAPIProtocolLens_v2"
    assert by_key["VAPIProtocolLens_v2"].status == ContractStatus.ACTIVE


# ---------------------------------------------------------------------- T5
def test_meta_keys_not_counted_as_contracts():
    data = {
        "RealContract": A,
        "_note": "blah",
        "_status": "LIVE",
        "_chainId": 4690,
    }
    r = audit_contracts(data)
    assert r.total == 1
    assert r.records[0].key == "RealContract"


# ---------------------------------------------------------------------- T6
def test_non_addr_values_skipped():
    data = {
        "RealContract": A,
        "SomeConfig": {"nested": "dict"},
        "SomeNumber": 42,
        "ShortHex": "0xdead",  # not 42 chars
    }
    r = audit_contracts(data)
    assert r.total == 1
    assert r.records[0].key == "RealContract"


# ---------------------------------------------------------------------- T7
def test_default_active():
    data = {"Lonely": A, "AlsoLonely": B}
    r = audit_contracts(data)
    assert all(rec.status == ContractStatus.ACTIVE for rec in r.records)
    assert r.active_count == 2


# ---------------------------------------------------------------------- T8
def test_counts_consistent():
    data = {
        "Active1": A,
        "Active2": B,
        "Old_superseded": C,
        "Gate": D,
        "GateV2": "0x" + "5" * 40,
    }
    r = audit_contracts(data)
    assert r.total == 5
    assert r.active_count + r.superseded_count + r.deprecated_inferred_count + r.unknown_count == r.total
    # Old_superseded → SUPERSEDED; Gate → DEPRECATED-INFERRED; GateV2/Active1/Active2 → ACTIVE
    assert r.superseded_count == 1
    assert r.deprecated_inferred_count == 1
    assert r.active_count == 3


# ---------------------------------------------------------------------- T9
def test_markdown_renders_sections_and_honesty_rail():
    data = {"Active1": A, "Old_superseded": B}
    r = audit_contracts(data)
    md = r.to_markdown()
    assert "SUPERSEDED (explicit): 1" in md
    assert "Honesty rail" in md
    assert "heuristic, NOT a fact" in md


# ---------------------------------------------------------------------- T10
def test_markdown_pipe_escape():
    data = {"Weird|Name": A}
    r = audit_contracts(data)
    md = r.to_markdown()
    assert "Weird\\|Name" in md
