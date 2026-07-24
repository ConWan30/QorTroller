import unittest
import tempfile
import os
import sys
from pathlib import Path

# CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): this file was missing the
# sys.path.insert every other test file in this suite has, so it only worked when
# collected after some other file had already put bridge/ on sys.path (order-dependent,
# fails standalone or under a different collection order).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from vapi_bridge.store import Store
from vapi_bridge.operator_api import create_operator_app

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_local_tools.db"))

def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey_tools"
    cfg.rate_limit_per_minute = 10000
    return cfg

# Need MagicMock
from unittest.mock import MagicMock

class TestLocalToolsEndpoint(unittest.TestCase):
    def setUp(self):
        self.store = _make_store()
        self.cfg = _make_cfg()
        self.app = create_operator_app(self.cfg, self.store)
        self.client = TestClient(self.app, raise_server_exceptions=True)

    def test_local_tools_bad_key_returns_403(self):
        """POST /agent/local-host/execute with wrong api_key returns 403."""
        resp = self.client.post(
            "/agent/local-host/execute",
            params={"api_key": "WRONG"},
            json={"tool": "list_files", "arguments": {}}
        )
        self.assertEqual(resp.status_code, 403)

    def test_local_tools_list_files(self):
        """POST /agent/local-host/execute list_files returns list of repository files."""
        resp = self.client.post(
            "/agent/local-host/execute",
            params={"api_key": "testkey_tools"},
            json={"tool": "list_files", "arguments": {}}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("result", body)
        self.assertIsInstance(body["result"], list)
        # Verify cli_chat.py or similar file is in the result
        files = body["result"]
        self.assertTrue(any("cli_chat.py" in f for f in files) or len(files) > 0)

    def test_local_tools_read_file(self):
        """POST /agent/local-host/execute read_file reads valid files inside repo."""
        # CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): cli_chat.py is untracked
        # local scratch content (never committed -- confirmed via `git ls-files`), so it
        # doesn't exist in a fresh checkout and this test could never have passed in real
        # CI. qortroller_daemon.py is tracked and genuinely contains "QorTrollerAI".
        resp = self.client.post(
            "/agent/local-host/execute",
            params={"api_key": "testkey_tools"},
            json={"tool": "read_file", "arguments": {"path": "qortroller_daemon.py"}}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("result", body)
        self.assertIn("QorTrollerAI", body["result"])

    def test_local_tools_read_file_path_traversal(self):
        """POST /agent/local-host/execute read_file rejects path traversal outside root."""
        resp = self.client.post(
            "/agent/local-host/execute",
            params={"api_key": "testkey_tools"},
            json={"tool": "read_file", "arguments": {"path": "../../../passwd"}}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("result", body)
        self.assertIn("Access denied", body["result"])

    def test_local_tools_git_history(self):
        """POST /agent/local-host/execute git_history returns recent commit logs."""
        resp = self.client.post(
            "/agent/local-host/execute",
            params={"api_key": "testkey_tools"},
            json={"tool": "git_history", "arguments": {}}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("result", body)
        self.assertIsInstance(body["result"], str)

    def test_local_tools_unknown_tool(self):
        """POST /agent/local-host/execute returns error message for unknown tools."""
        resp = self.client.post(
            "/agent/local-host/execute",
            params={"api_key": "testkey_tools"},
            json={"tool": "make_coffee", "arguments": {}}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("result", body)
        self.assertIn("Unknown tool", body["result"])
