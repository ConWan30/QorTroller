"""A2A-STEWARD-EVOLVE — PCRA evidence-loop Inc-1 tests. Pins the deterministic (dedup-safe) payload,
the claim_id-keyed audit_id, the audit-drafting reuse, and the default-OFF gate.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_pcra_draft import (
    build_pcra_draft_payload,
    pcra_labels_from_draft_rows,
    persist_pcra_findings,
    stale_anchor_findings,
)
from bridge.vapi_bridge.steward_sel import (
    is_external_label,
    recommend_graduation,
    score_task_class,
)
# use the REAL URI construction so tests exercise the prod sanitization path (grok round-12)
from bridge.vapi_bridge.operator_agent_guardian_drafting import (
    GUARDIAN_AUDIT_DRAFT_PREFIX,
    _safe_id_segment,
)


def _real_uri(claim_id: str) -> str:
    """The exact URI draft_audit_entry persists for a PCRA finding (post _safe_id_segment)."""
    return GUARDIAN_AUDIT_DRAFT_PREFIX + _safe_id_segment(f"pcra:{claim_id}")


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeDraftResult:
    def __init__(self, draft_id, draft_uri):
        self.draft_id = draft_id
        self.draft_uri = draft_uri


class _FakeGuardianGenerator:
    """Records draft_audit_entry calls; mimics the store's (agent_id, payload_hash) dedup by hashing the
    canonical payload so identical payloads collapse to one 'row'."""
    def __init__(self):
        self.calls = []
        self._rows_by_hash = {}
        self._next_id = 1

    def draft_audit_entry(self, *, audit_id, audit_payload, audit_kind):
        import hashlib
        import json
        self.calls.append({"audit_id": audit_id, "audit_payload": audit_payload, "audit_kind": audit_kind})
        h = hashlib.sha256(json.dumps(audit_payload, sort_keys=True).encode()).hexdigest()
        if h in self._rows_by_hash:
            rid = self._rows_by_hash[h]           # dedup: return existing row id (store INSERT OR IGNORE)
        else:
            rid = self._next_id
            self._rows_by_hash[h] = rid
            self._next_id += 1
        # build the URI the REAL way (post _safe_id_segment) so tests can't drift from prod (grok round-12)
        return _FakeDraftResult(rid, GUARDIAN_AUDIT_DRAFT_PREFIX + _safe_id_segment(audit_id))


_STALE = {"residue_class": "STALE_ANCHOR", "claim_id": "anchor#wallet_iotx", "severity": "MED",
          "measured_vs_claimed": {"anchor": "wallet_iotx", "claimed": "32.078", "live": "28.441"},
          "evidence_refs": ["anchor:wallet_iotx"], "note": "wallet drift"}
_CEIL = {"residue_class": "CEILING_OVERCLAIM", "claim_id": "docs/a2a/x.md#poep_enabled", "severity": "HIGH",
         "measured_vs_claimed": {"oracle_key": "poep_enabled", "oracle_value": False},
         "evidence_refs": ["docs/a2a/x.md"], "note": "presence asserted"}


# --- deterministic payload (dedup rail) ------------------------------------------------------------

def test_payload_is_deterministic_no_wallclock():
    a = build_pcra_draft_payload(_STALE)
    b = build_pcra_draft_payload(_STALE)
    assert a == b                       # identical across calls -> same hash -> store dedups
    assert a["ts_ns"] == 0              # content-addressed, not time-stamped
    assert a["task_class"] == "PCRA" and a["claim_id"] == "anchor#wallet_iotx"


def test_different_findings_differ():
    assert build_pcra_draft_payload(_STALE) != build_pcra_draft_payload(_CEIL)


def test_changed_live_value_is_a_new_finding():
    drifted = {**_STALE, "measured_vs_claimed": {**_STALE["measured_vs_claimed"], "live": "27.900"}}
    assert build_pcra_draft_payload(_STALE) != build_pcra_draft_payload(drifted)


# --- persist ---------------------------------------------------------------------------------------

def test_gated_off_by_default():
    r = persist_pcra_findings(_FakeGuardianGenerator(), [_STALE, _CEIL], cfg=_Cfg(pcra_enabled=False))
    assert r["enabled"] is False and r["n_persisted"] == 0


def test_persists_via_audit_drafting_with_claim_id_uri():
    gen = _FakeGuardianGenerator()
    r = persist_pcra_findings(gen, [_STALE, _CEIL], cfg=_Cfg(pcra_enabled=True))
    assert r["enabled"] is True and r["n_findings"] == 2 and r["n_persisted"] == 2
    assert all(c["audit_kind"] == "pcra" for c in gen.calls)
    assert gen.calls[0]["audit_id"] == "pcra:anchor#wallet_iotx"
    # real persisted URI is post-sanitization: pcra_<sanitized claim> (grok round-12)
    assert r["draft_uris"][0] == "draft://audit_entries/pcra_anchor_wallet_iotx"
    assert "LOCAL handler" in r["note"] and "0-IOTX" in r["note"]


def test_rescanning_same_finding_dedups_to_one_row():
    # grok round-11 F1: 3 re-scans of the same stale anchor must NOT create 3 distinct rows
    gen = _FakeGuardianGenerator()
    for _ in range(3):
        persist_pcra_findings(gen, [_STALE], cfg=_Cfg(pcra_enabled=True))
    assert len(gen.calls) == 3                       # persister was invoked 3x
    assert len(gen._rows_by_hash) == 1               # ...but the store dedups to ONE row


def test_finding_without_claim_id_is_skipped():
    gen = _FakeGuardianGenerator()
    r = persist_pcra_findings(gen, [{"residue_class": "STALE_ANCHOR", "claim_id": ""}],
                              cfg=_Cfg(pcra_enabled=True))
    assert r["n_findings"] == 1 and r["n_persisted"] == 0 and gen.calls == []


# --- STALE_ANCHOR adapter --------------------------------------------------------------------------

def test_stale_anchor_adapter_emits_dicts_for_drifted_anchors():
    findings = stale_anchor_findings({"wallet_iotx": "32.078", "contracts": "66"},
                                     {"wallet_iotx": "28.441", "contracts": "69"})
    assert len(findings) == 2
    assert all(f["residue_class"] == "STALE_ANCHOR" for f in findings)
    ids = {f["claim_id"] for f in findings}
    assert ids == {"anchor#wallet_iotx", "anchor#contracts"}
    # dicts flow straight into the persister
    gen = _FakeGuardianGenerator()
    r = persist_pcra_findings(gen, findings, cfg=_Cfg(pcra_enabled=True))
    assert r["n_persisted"] == 2


def test_stale_anchor_adapter_clean_when_aligned():
    assert stale_anchor_findings({"contracts": "69"}, {"contracts": "69"}) == []


# --- Inc-2: reviewed drafts -> SEL labels ----------------------------------------------------------

def _row(uri, decision, created_at=100.0, decided_at=None, action="audit-drafting"):
    r = {"draft_uri": uri, "operator_decision": decision, "action_name": action, "created_at": created_at}
    if decided_at is not None:
        r["operator_decision_at"] = decided_at
    return r


def test_maps_accept_and_reject():
    rows = [_row(_real_uri("anchor#wallet_iotx"), "accept"),
            _row(_real_uri("docs/x.md#poep_enabled"), "reject")]
    labels = pcra_labels_from_draft_rows(rows)
    by_uri = {l["claim_uri"]: l["label"] for l in labels}
    assert by_uri[_real_uri("anchor#wallet_iotx")] == "ACCEPTED"
    assert by_uri[_real_uri("docs/x.md#poep_enabled")] == "OVERTURNED"
    assert all(l["label_source_agent"] == "operator" for l in labels)


def test_real_sanitized_uri_round_trips_to_a_label():
    # grok round-12 adversarial: the REAL persisted URI (pcra_<sanitized>) must yield a label — this is the
    # exact prod path the "pcra:" prefix bug broke. anchor#wallet_iotx -> pcra_anchor_wallet_iotx
    uri = _real_uri("anchor#wallet_iotx")
    assert uri == "draft://audit_entries/pcra_anchor_wallet_iotx"
    labels = pcra_labels_from_draft_rows([_row(uri, "accept")])
    assert len(labels) == 1 and labels[0]["label"] == "ACCEPTED"


def test_excludes_unreviewed_and_overturn_curator_and_non_pcra():
    rows = [_row(_real_uri("a"), "none"),                                 # unreviewed
            _row(_real_uri("b"), "overturn_curator"),                     # curator FP metric, not PCRA
            _row("draft://audit_entries/sweep_c", "accept"),              # not a PCRA URI
            _row(_real_uri("d"), "accept", action="pda-attestation-anchor")]  # not audit-drafting
    assert pcra_labels_from_draft_rows(rows) == []


def test_dedups_one_label_per_uri_latest_decision():
    # same claim re-reviewed: reject at t=100 then accept at t=200 -> ONE label, the latest (ACCEPTED)
    uri = _real_uri("anchor#wallet_iotx")
    rows = [_row(uri, "reject", decided_at=100.0), _row(uri, "accept", decided_at=200.0)]
    labels = pcra_labels_from_draft_rows(rows)
    assert len(labels) == 1 and labels[0]["label"] == "ACCEPTED"


def test_produced_labels_are_valid_sel_external_labels():
    labels = pcra_labels_from_draft_rows([_row(_real_uri("a"), "accept")])
    assert all(is_external_label(l) for l in labels)   # operator-sourced -> authentic in SEL


def test_end_to_end_score_and_graduation():
    rows = [_row(_real_uri(f"claim{i}"), "accept") for i in range(20)]
    labels = pcra_labels_from_draft_rows(rows)
    s = score_task_class(labels, steward="guardian", task_class="PCRA")
    assert s["n_external_labels"] == 20 and s["precision"] == 1.0
    g = recommend_graduation(labels, steward="guardian", task_class="PCRA")
    assert g["graduation_recommendation"] == "GRADUATE_TASK_CLASS"
