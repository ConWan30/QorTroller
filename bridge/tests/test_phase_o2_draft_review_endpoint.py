"""Phase O2-DRAFT-REVIEW endpoint tests.

Validates GET /operator/operator-agent-drafts + POST
/operator/operator-agent-draft-review return correct shape, honor auth, and
close the disagreement_rate / false_positive_rate measurement loop end-to-end.

  T-O2-DRAFT-REVIEW-EP-1: GET returns paginated shape with agent_id_filter,
                          decision_filter, since_minutes, limit, row_count,
                          drafts[], timestamp; read-key auth required (403 wrong key)
  T-O2-DRAFT-REVIEW-EP-2: GET decision_filter routes correctly:
                          ''/None -> all; 'unreviewed' -> NULL operator_decision;
                          'accept'/'reject'/'overturn_curator' -> respective
  T-O2-DRAFT-REVIEW-EP-3: GET since_minutes filter applied at store layer;
                          0 = no filter; 1440 = last 24h
  T-O2-DRAFT-REVIEW-EP-4: POST records decision; full operator auth (api_key
                          query param; missing/wrong key -> 403 per bridge
                          _check_key contract); reason <10 chars -> 422;
                          bad decision -> 422; missing draft_id -> 404
  T-O2-DRAFT-REVIEW-EP-5: POST end-to-end loop — generator drafts, POST
                          accepts/rejects/overturns; disagreement_rate +
                          false_positive_rate update via store helpers
  T-O2-DRAFT-REVIEW-EP-6: POST idempotency + revision — same decision twice
                          OK; different decision overwrites; reason field
                          updated
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

_BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN_ID = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"
CURATOR_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"


def _build_app(tmp_path: Path):
    """Construct a minimal operator_api app for endpoint testing."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    db = str(tmp_path / "test_o2_draft_review_ep.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db,
        operator_api_key="k_o2_review",
    )
    store = Store(db)
    app = create_operator_app(cfg, store)
    return TestClient(app), store, cfg


def _seed_drafts(store, count: int = 3):
    """Seed `count` drafts under canonical 'anchor_sentry' agent_id."""
    ids: list[int] = []
    for i in range(count):
        rid = store.insert_operator_agent_draft(
            agent_id="anchor_sentry",
            action_category="tool",
            action_name="kms-sign",
            draft_uri=f"draft://commit_hashes/{i:040x}",
            payload_hash=f"{i:064x}",
            payload_bytes=64 + i,
            kms_sig_present=True,
        )
        ids.append(rid)
    return ids


# --------------------------------------------------------------------------
# T-O2-DRAFT-REVIEW-EP-1: GET shape + read-key auth
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_REVIEW_EP_1_get_shape_and_auth(tmp_path):
    client, store, _ = _build_app(tmp_path)
    _seed_drafts(store, count=3)

    # Wrong key -> 403
    r_bad = client.get(
        "/operator/operator-agent-drafts",
        headers={"x-api-key": "wrong"},
    )
    assert r_bad.status_code == 403, f"expected 403; got {r_bad.status_code}"

    # Correct key -> 200 with full shape
    r = client.get(
        "/operator/operator-agent-drafts",
        headers={"x-api-key": "k_o2_review"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for k in (
        "agent_id_filter", "decision_filter", "since_minutes",
        "limit", "row_count", "drafts", "timestamp",
    ):
        assert k in body, f"missing key {k!r} in response"
    assert body["row_count"] == 3
    assert len(body["drafts"]) == 3
    assert body["limit"] == 50  # default


# --------------------------------------------------------------------------
# T-O2-DRAFT-REVIEW-EP-2: decision_filter routing
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_REVIEW_EP_2_decision_filter_routing(tmp_path):
    client, store, _ = _build_app(tmp_path)
    ids = _seed_drafts(store, count=5)

    # Mark 2 accept, 1 reject, 1 overturn_curator, 1 unreviewed
    store.record_operator_decision(draft_id=ids[0], decision="accept", reason="approved by op review")
    store.record_operator_decision(draft_id=ids[1], decision="accept", reason="approved by op review2")
    store.record_operator_decision(draft_id=ids[2], decision="reject", reason="incorrect commit hash signed")
    store.record_operator_decision(draft_id=ids[3], decision="overturn_curator", reason="verdict reversed after recheck")
    # ids[4] remains NULL

    headers = {"x-api-key": "k_o2_review"}

    # Empty filter (all) -> 5 drafts
    r_all = client.get("/operator/operator-agent-drafts", headers=headers).json()
    assert r_all["row_count"] == 5

    # 'accept' -> 2
    r_acc = client.get(
        "/operator/operator-agent-drafts",
        params={"decision": "accept"},
        headers=headers,
    ).json()
    assert r_acc["row_count"] == 2
    assert all(d["operator_decision"] == "accept" for d in r_acc["drafts"])

    # 'reject' -> 1
    r_rej = client.get(
        "/operator/operator-agent-drafts",
        params={"decision": "reject"},
        headers=headers,
    ).json()
    assert r_rej["row_count"] == 1
    assert r_rej["drafts"][0]["operator_decision"] == "reject"

    # 'overturn_curator' -> 1
    r_ov = client.get(
        "/operator/operator-agent-drafts",
        params={"decision": "overturn_curator"},
        headers=headers,
    ).json()
    assert r_ov["row_count"] == 1

    # 'unreviewed' -> 1 (NULL operator_decision)
    r_un = client.get(
        "/operator/operator-agent-drafts",
        params={"decision": "unreviewed"},
        headers=headers,
    ).json()
    assert r_un["row_count"] == 1
    assert r_un["drafts"][0]["operator_decision"] is None
    assert r_un["decision_filter"] == "unreviewed"


# --------------------------------------------------------------------------
# T-O2-DRAFT-REVIEW-EP-3: since_minutes filter
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_REVIEW_EP_3_since_minutes_filter(tmp_path):
    client, store, _ = _build_app(tmp_path)
    _seed_drafts(store, count=3)

    headers = {"x-api-key": "k_o2_review"}

    # since_minutes=0 -> no filter -> 3
    r0 = client.get(
        "/operator/operator-agent-drafts",
        params={"since_minutes": 0},
        headers=headers,
    ).json()
    assert r0["row_count"] == 3
    assert r0["since_minutes"] == 0

    # since_minutes=1440 -> 24h window includes recent rows -> 3
    r1 = client.get(
        "/operator/operator-agent-drafts",
        params={"since_minutes": 1440},
        headers=headers,
    ).json()
    assert r1["row_count"] == 3
    assert r1["since_minutes"] == 1440

    # Out-of-range since_minutes -> 422 (capped at 43200)
    r_bad = client.get(
        "/operator/operator-agent-drafts",
        params={"since_minutes": 99999},
        headers=headers,
    )
    assert r_bad.status_code == 422


# --------------------------------------------------------------------------
# T-O2-DRAFT-REVIEW-EP-4: POST validation (auth + reason + decision + 404)
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_REVIEW_EP_4_post_validation(tmp_path):
    client, store, _ = _build_app(tmp_path)
    ids = _seed_drafts(store, count=1)

    # Missing api_key -> 401 (full operator auth)
    r_no_key = client.post(
        "/operator/operator-agent-draft-review",
        params={
            "draft_id": ids[0],
            "decision": "accept",
            "reason": "approved by operator review",
        },
    )
    assert r_no_key.status_code == 403, f"got {r_no_key.status_code} body={r_no_key.text}"

    # Wrong key -> 401
    r_wrong = client.post(
        "/operator/operator-agent-draft-review",
        params={
            "draft_id": ids[0],
            "decision": "accept",
            "reason": "approved by operator review",
            "api_key": "wrong",
        },
    )
    assert r_wrong.status_code == 403

    # Bad decision -> 422
    r_bad_dec = client.post(
        "/operator/operator-agent-draft-review",
        params={
            "draft_id": ids[0],
            "decision": "garbage",
            "reason": "approved by operator review",
            "api_key": "k_o2_review",
        },
    )
    assert r_bad_dec.status_code == 422
    assert "decision" in r_bad_dec.text

    # Reason <10 chars -> 422
    r_short = client.post(
        "/operator/operator-agent-draft-review",
        params={
            "draft_id": ids[0],
            "decision": "accept",
            "reason": "short",
            "api_key": "k_o2_review",
        },
    )
    assert r_short.status_code == 422
    assert "10" in r_short.text or "reason" in r_short.text.lower()

    # Missing draft_id (id=99999 doesn't exist) -> 404
    r_missing = client.post(
        "/operator/operator-agent-draft-review",
        params={
            "draft_id": 99999,
            "decision": "accept",
            "reason": "approved by operator review",
            "api_key": "k_o2_review",
        },
    )
    assert r_missing.status_code == 404


# --------------------------------------------------------------------------
# T-O2-DRAFT-REVIEW-EP-5: POST end-to-end disagreement + false-positive
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_REVIEW_EP_5_end_to_end_rates(tmp_path):
    """Verifies the watcher's rate computations integrate end-to-end with
    the POST endpoint -- the loop closure that justifies this entire phase."""
    client, store, _ = _build_app(tmp_path)
    sentry_ids = _seed_drafts(store, count=10)

    headers_full = {}  # full auth uses query param
    base_params = {"api_key": "k_o2_review"}

    # 8 accept + 2 reject -> Sentry disagreement_rate = 2/10 = 20%
    for i in range(8):
        r = client.post(
            "/operator/operator-agent-draft-review",
            params={**base_params, "draft_id": sentry_ids[i], "decision": "accept",
                    "reason": "operator approved this commit signature"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["accepted"] is True
        assert body["decision"] == "accept"
        assert body["row"]["operator_decision"] == "accept"

    for i in range(8, 10):
        r = client.post(
            "/operator/operator-agent-draft-review",
            params={**base_params, "draft_id": sentry_ids[i], "decision": "reject",
                    "reason": "operator rejected -- wrong commit hash"},
        )
        assert r.status_code == 200

    rate = store.compute_operator_agent_disagreement_rate(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert rate == pytest.approx(2 / 10)

    # Also seed 1 Curator draft + 1 overturn_curator
    cid = store.insert_operator_agent_draft(
        agent_id="curator",
        action_category="skill",
        action_name="marketplace-listing-review",
        draft_uri="draft://listing_reviews/abc/verdict",
        payload_hash="c" * 64,
        payload_bytes=42,
    )
    r_ov = client.post(
        "/operator/operator-agent-draft-review",
        params={**base_params, "draft_id": cid, "decision": "overturn_curator",
                "reason": "operator reversed verdict after re-checking anchor freshness"},
    )
    assert r_ov.status_code == 200
    assert r_ov.json()["decision"] == "overturn_curator"

    fp_rate = store.compute_operator_agent_false_positive_rate(
        agent_id="curator", since_seconds=86400,
    )
    assert fp_rate == pytest.approx(1.0)  # 1 of 1 reviewed -> 100% FP


# --------------------------------------------------------------------------
# T-O2-DRAFT-REVIEW-EP-6: POST idempotency + revision
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_REVIEW_EP_6_idempotency_and_revision(tmp_path):
    client, store, _ = _build_app(tmp_path)
    ids = _seed_drafts(store, count=1)

    base_params = {"api_key": "k_o2_review"}

    # accept -> success
    r1 = client.post(
        "/operator/operator-agent-draft-review",
        params={**base_params, "draft_id": ids[0], "decision": "accept",
                "reason": "operator approved this commit signature"},
    )
    assert r1.status_code == 200

    # accept again with same reason -> still 200 (idempotent)
    r2 = client.post(
        "/operator/operator-agent-draft-review",
        params={**base_params, "draft_id": ids[0], "decision": "accept",
                "reason": "operator approved this commit signature"},
    )
    assert r2.status_code == 200

    # Revise to reject -> overwrite previous decision
    r3 = client.post(
        "/operator/operator-agent-draft-review",
        params={**base_params, "draft_id": ids[0], "decision": "reject",
                "reason": "operator changed mind after deeper review"},
    )
    assert r3.status_code == 200
    assert r3.json()["row"]["operator_decision"] == "reject"
    assert "deeper review" in (r3.json()["row"]["operator_disagreement_reason"] or "")
