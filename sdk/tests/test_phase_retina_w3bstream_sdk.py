"""SDK tests for VAPIRetinaW3bstream (Phase 2 W3bstream validation)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from vapi_sdk import RetinaW3bstreamStatusResult, VAPIRetinaW3bstream  # noqa: E402


def test_w3bstream_status_result_slots():
    r = RetinaW3bstreamStatusResult(validation_enabled=True, latest_exit_code=0)
    assert r.validation_enabled is True
    assert r.latest_exit_code == 0


@patch("urllib.request.urlopen")
def test_w3bstream_status_happy(mock_urlopen):
    body = {
        "retina_w3bstream_validation_enabled": True,
        "retina_w3bstream_enforce_on_ingest": False,
        "latest_exit_code": 0,
        "timestamp": 1.0,
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    result = VAPIRetinaW3bstream("http://localhost:8080", "key").status()
    assert result.validation_enabled is True
    assert result.latest_exit_code == 0
    assert result.error == ""


@patch("urllib.request.urlopen", side_effect=OSError("connection refused"))
def test_w3bstream_status_fail_open(mock_urlopen):
    result = VAPIRetinaW3bstream("http://localhost:8080").status()
    assert result.error
    assert result.latest_exit_code == 0


def test_w3bstream_status_result_defaults():
    r = RetinaW3bstreamStatusResult()
    assert r.validation_enabled is False
    assert r.enforce_on_ingest is False
