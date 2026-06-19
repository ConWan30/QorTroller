import unittest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from vapi_bridge.store import Store
from vapi_bridge.operator_api import create_operator_app

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_llm_chat.db"))

def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey_llm"
    cfg.rate_limit_per_minute = 10000
    return cfg

class TestLLMChatEndpoint(unittest.TestCase):
    def setUp(self):
        self.store = _make_store()
        self.cfg = _make_cfg()
        self.app = create_operator_app(self.cfg, self.store)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_llm_chat_bad_key_returns_403(self):
        """POST /agent/llm-chat with wrong api_key returns 403."""
        resp = self.client.post(
            "/agent/llm-chat",
            params={"api_key": "WRONG"},
            json={"messages": [{"role": "user", "content": "Hello"}]}
        )
        self.assertEqual(resp.status_code, 403)

    @patch("requests.post")
    def test_llm_chat_valid_response(self, mock_post):
        """POST /agent/llm-chat with valid key returns 200 and AI response."""
        # Mock successful QuickSilver Pro API response
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "This is a mock response from DeepSeek."
                }
            }]
        }
        mock_post.return_value = mock_response

        resp = self.client.post(
            "/agent/llm-chat",
            params={"api_key": "testkey_llm"},
            json={"messages": [{"role": "user", "content": "Explain QorTroller purpose"}]}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("response", body)
        self.assertEqual(body["response"], "This is a mock response from DeepSeek.")
