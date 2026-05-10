"""Phase O2-DRAFT-REVIEW SDK tests.

Verifies VAPIDraftReview client wraps GET /operator/operator-agent-drafts +
POST /operator/operator-agent-draft-review correctly. Uses an in-process
FastAPI TestClient via a tiny urllib monkey-patch shim so the SDK's stdlib
urllib.request calls hit the test app rather than a real network endpoint.

  T-O2-DRAFT-REVIEW-SDK-1: list_drafts shape + filter pass-through
  T-O2-DRAFT-REVIEW-SDK-2: review_draft happy path returns row update
  T-O2-DRAFT-REVIEW-SDK-3: review_draft 422/404 errors surface through
                            DraftReviewSubmitResult.error
  T-O2-DRAFT-REVIEW-SDK-4: list_drafts network error surfaces in
                            DraftReviewListResult.error (never raises)
"""
from __future__ import annotations

import dataclasses
import sys
import threading
import time
from pathlib import Path

import pytest

# Add bridge/ + sdk/ to sys.path so direct imports work from this test.
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "bridge", ROOT / "sdk"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(scope="module")
def live_app():
    """Start the operator_app via FastAPI in a background thread on a
    free port. Yields (base_url, store, api_key)."""
    import socket
    from fastapi.testclient import TestClient
    import uvicorn

    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    # Pick a free port
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    db_path = str(ROOT / "bridge" / f".tmp_o2_review_sdk_{port}.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db_path,
        operator_api_key="k_o2_sdk",
    )
    store = Store(db_path)
    app = create_operator_app(cfg, store)

    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
    ))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    # Wait for server to come up.
    deadline = time.time() + 5.0
    import urllib.request
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/operator/operator-agent-drafts",
                headers={"x-api-key": "k_o2_sdk"},
            )
            with urllib.request.urlopen(req, timeout=0.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        raise RuntimeError("test server failed to start")

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, store, "k_o2_sdk"

    # Tell uvicorn to stop; daemon thread cleans itself up.
    server.should_exit = True
    th.join(timeout=5.0)
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


def _seed_drafts(store, count: int):
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


def test_T_O2_DRAFT_REVIEW_SDK_1_list_drafts_shape(live_app):
    from vapi_sdk import VAPIDraftReview

    base_url, store, api_key = live_app
    # Clear any leftover state by re-seeding fresh drafts.
    _seed_drafts(store, count=3)

    client = VAPIDraftReview(base_url, api_key=api_key)
    result = client.list_drafts(decision="unreviewed", limit=20)

    assert result.error is None
    assert result.row_count >= 3
    assert isinstance(result.drafts, list)
    assert len(result.drafts) >= 3
    assert result.decision_filter == "unreviewed"
    assert result.limit == 20


def test_T_O2_DRAFT_REVIEW_SDK_2_review_draft_happy_path(live_app):
    from vapi_sdk import VAPIDraftReview

    base_url, store, api_key = live_app
    ids = _seed_drafts(store, count=1)
    client = VAPIDraftReview(base_url, api_key=api_key)

    res = client.review_draft(
        draft_id=ids[0],
        decision="accept",
        reason="operator approved this commit signature",
    )
    assert res.error is None
    assert res.accepted is True
    assert res.draft_id == ids[0]
    assert res.decision == "accept"
    assert res.row is not None
    assert res.row["operator_decision"] == "accept"


def test_T_O2_DRAFT_REVIEW_SDK_3_review_draft_validation_errors(live_app):
    from vapi_sdk import VAPIDraftReview

    base_url, store, api_key = live_app
    ids = _seed_drafts(store, count=1)
    client = VAPIDraftReview(base_url, api_key=api_key)

    # Short reason -> 422
    r422 = client.review_draft(
        draft_id=ids[0], decision="accept", reason="short",
    )
    assert r422.error is not None
    assert "422" in r422.error or "10" in r422.error.lower()

    # Bad decision -> 422
    r422_dec = client.review_draft(
        draft_id=ids[0], decision="garbage",
        reason="this reason is plenty long enough",
    )
    assert r422_dec.error is not None
    assert "422" in r422_dec.error or "decision" in r422_dec.error.lower()

    # Missing draft_id -> 404
    r404 = client.review_draft(
        draft_id=99999, decision="accept",
        reason="operator approved this commit signature",
    )
    assert r404.error is not None
    assert "404" in r404.error or "not found" in r404.error.lower()


def test_T_O2_DRAFT_REVIEW_SDK_4_network_errors_never_raise():
    """When the bridge is unreachable, the SDK returns Result with error
    populated and never raises (matches existing SDK fail-open contract)."""
    from vapi_sdk import VAPIDraftReview

    client = VAPIDraftReview("http://127.0.0.1:1", api_key="x")  # invalid port
    listing = client.list_drafts()
    assert listing.error is not None
    assert listing.row_count == 0
    assert listing.drafts == []

    submit = client.review_draft(
        draft_id=1, decision="accept",
        reason="operator approved this commit signature",
    )
    assert submit.error is not None
    assert submit.accepted is False
    assert submit.draft_id == 1
