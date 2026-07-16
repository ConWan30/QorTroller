"""A2A-STEWARD-EVOLVE B4 — SEL-v0 tests. Pins the external-label scorer, the graduation gate, the
tamper-evident candidate chain, and the LOAD-BEARING anti-self-scoring rail: a steward cannot graduate
its own task-class by labeling its own drafts.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_sel import (
    _DOMAIN,
    SCHEMA,
    chain_head,
    graduation_report_from_store,
    is_external_label,
    recommend_graduation,
    score_task_class,
)


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _entry(steward="guardian", task_class="PCRA", label="ACCEPTED",
           source="operator_decision", src_agent="operator", ts=1):
    return {"steward": steward, "task_class": task_class, "label": label,
            "label_source": source, "label_source_agent": src_agent, "ts_ns": ts}


def _n(label="ACCEPTED", k=20, src_agent="operator", **over):
    return [_entry(label=label, src_agent=src_agent, ts=i + 1, **over) for i in range(k)]


# --- external-label rail ---------------------------------------------------------------------------

def test_external_label_accepts_operator_sourced_operator_decision():
    assert is_external_label(_entry(steward="guardian", source="operator_decision",
                                    src_agent="operator")) is True


def test_external_label_rejects_self_source():
    # a steward labeling its OWN draft is not an external label
    assert is_external_label(_entry(steward="guardian", src_agent="guardian")) is False


def test_external_label_rejects_case_spoofed_self_source():
    # grok round-07 F2: 'Guardian' != 'guardian' must NOT slip past the self-check
    assert is_external_label(_entry(steward="guardian", source="challenge_graph",
                                    src_agent="Guardian")) is False


def test_operator_decision_only_from_operator():
    # grok round-07 F1: a peer steward cannot source an operator_decision label
    assert is_external_label(_entry(steward="guardian", source="operator_decision",
                                    src_agent="sentry")) is False


def test_adversarial_holdout_rejects_peer_steward():
    # a peer steward is NOT a holdout oracle -> collusion via holdout is blocked
    assert is_external_label(_entry(steward="guardian", source="adversarial_holdout",
                                    src_agent="sentry")) is False
    # a genuine non-steward oracle IS accepted
    assert is_external_label(_entry(steward="guardian", source="adversarial_holdout",
                                    src_agent="holdout_oracle")) is True


def test_challenge_graph_accepts_peer_steward_challenger():
    assert is_external_label(_entry(steward="sentry", source="challenge_graph",
                                    src_agent="guardian")) is True


def test_external_label_rejects_unknown_label_or_source():
    assert is_external_label(_entry(label="NOPE")) is False
    assert is_external_label(_entry(source="self_pat")) is False


# --- scoring ---------------------------------------------------------------------------------------

def test_precision_is_positives_over_labeled():
    entries = _n("ACCEPTED", 15) + _n("OVERTURNED", 5)
    s = score_task_class(entries, steward="guardian", task_class="PCRA")
    assert s["positives"] == 15 and s["negatives"] == 5
    assert abs(s["precision"] - 0.75) < 1e-9
    assert s["n_rejected_labels"] == 0


def test_self_labels_excluded_from_score_and_counted():
    entries = _n("ACCEPTED", 10, src_agent="operator") + _n("ACCEPTED", 10, src_agent="guardian")
    s = score_task_class(entries, steward="guardian", task_class="PCRA")
    assert s["n_external_labels"] == 10        # only the operator-sourced ones count
    assert s["n_rejected_labels"] == 10
    assert s["precision"] == 1.0


# --- graduation gate -------------------------------------------------------------------------------

def test_graduates_on_external_precision_over_floor():
    r = recommend_graduation(_n("ACCEPTED", 20), steward="guardian", task_class="PCRA")
    assert r["graduation_recommendation"] == "GRADUATE_TASK_CLASS"
    assert r["candidate"] is True and r["domain_tag"] == "VAPI-SEL-v0"


def test_holds_below_min_samples():
    r = recommend_graduation(_n("ACCEPTED", 10), steward="guardian", task_class="PCRA")
    assert r["graduation_recommendation"] == "HOLD_INSUFFICIENT_SAMPLES"


def test_holds_below_precision_floor():
    entries = _n("ACCEPTED", 10) + _n("OVERTURNED", 10)
    r = recommend_graduation(entries, steward="guardian", task_class="PCRA")
    assert r["graduation_recommendation"] == "HOLD_BELOW_PRECISION"


def test_steward_cannot_graduate_by_self_labeling():
    # THE load-bearing rail: 30 self-authored ACCEPTED labels must NOT graduate the steward
    self_flood = _n("ACCEPTED", 30, src_agent="guardian")
    r = recommend_graduation(self_flood, steward="guardian", task_class="PCRA")
    assert r["graduation_recommendation"] == "HOLD_INSUFFICIENT_SAMPLES"
    assert r["score"]["n_external_labels"] == 0
    assert r["score"]["n_rejected_labels"] == 30


def test_peer_collusion_cannot_graduate():
    # grok round-07 F1: Sentry rubber-stamping Guardian's PCRA via holdout must NOT graduate Guardian
    collusion = _n("ACCEPTED", 30, steward="guardian", source="adversarial_holdout", src_agent="sentry")
    r = recommend_graduation(collusion, steward="guardian", task_class="PCRA")
    assert r["graduation_recommendation"] == "HOLD_INSUFFICIENT_SAMPLES"
    assert r["score"]["n_external_labels"] == 0
    assert r["score"]["n_rejected_labels"] == 30


def test_cannot_graduate_without_operator_labels():
    # grok round-07 F4: 20 holdout-oracle ACCEPTED with ZERO operator decisions must not graduate
    entries = _n("ACCEPTED", 20, source="adversarial_holdout", src_agent="holdout_oracle")
    r = recommend_graduation(entries, steward="guardian", task_class="PCRA")
    assert r["graduation_recommendation"] == "HOLD_NO_OPERATOR_LABELS"


def test_challenge_survival_requirement_when_enabled():
    # with the requirement on (B5 assurance mode), external precision alone is not enough
    base = _n("ACCEPTED", 20, steward="sentry", task_class="MPJA")
    r = recommend_graduation(base, steward="sentry", task_class="MPJA",
                             require_challenge_survival=True)
    assert r["graduation_recommendation"] == "HOLD_NO_CHALLENGE_SURVIVAL"
    # add a survived peer challenge (challenger != scored steward) -> graduates
    entries = base + [_entry(steward="sentry", task_class="MPJA", label="CHALLENGE_SURVIVED",
                             source="challenge_graph", src_agent="guardian", ts=99)]
    r2 = recommend_graduation(entries, steward="sentry", task_class="MPJA",
                              require_challenge_survival=True)
    assert r2["graduation_recommendation"] == "GRADUATE_TASK_CLASS"


def test_a_fallen_challenge_blocks_graduation_when_required():
    entries = _n("ACCEPTED", 20) + [_entry(label="CHALLENGE_FELL", source="challenge_graph",
                                           src_agent="curator", ts=99)]
    r = recommend_graduation(entries, steward="guardian", task_class="PCRA",
                             require_challenge_survival=True)
    assert r["graduation_recommendation"] == "HOLD_NO_CHALLENGE_SURVIVAL"


# --- candidate chain -------------------------------------------------------------------------------

def test_chain_genesis_and_determinism():
    assert chain_head([]) == hashlib.sha256(_DOMAIN + b"-GENESIS").hexdigest()
    a = chain_head(_n("ACCEPTED", 5))
    b = chain_head(_n("ACCEPTED", 5))
    assert a == b


def test_chain_is_order_and_tamper_sensitive():
    base = _n("ACCEPTED", 4)
    tampered = list(base)
    tampered[2] = {**tampered[2], "label": "OVERTURNED"}
    assert chain_head(base) != chain_head(tampered)
    assert chain_head(base) != chain_head(list(reversed(base)))


# --- rails -----------------------------------------------------------------------------------------

def test_graduation_never_grants_spend():
    r = recommend_graduation(_n("ACCEPTED", 20), steward="curator", task_class="DPIG")
    assert r["schema"] == SCHEMA
    assert "NEVER any IOTX spend" in r["grants_if_accepted"]
    assert "never grants spend autonomy" in r["note"] and "not FROZEN" in r["note"]


# --- adapter (stub, default-off) --------------------------------------------------------------------

def test_adapter_disabled_by_default():
    r = graduation_report_from_store(store=None, cfg=_Cfg(sel_enabled=False))
    assert r["enabled"] is False


def test_adapter_enabled_is_an_honest_stub():
    r = graduation_report_from_store(store=None, cfg=_Cfg(sel_enabled=True))
    assert r["enabled"] is True and r["candidate"] is True
    assert "STUB" in r["adapter_scope"] and "refuses to fabricate" in r["note"]
