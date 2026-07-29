"""
QorTrollerAI (vapi_llm_client) tests.

All HTTP is mocked — no network call is made. Covers API-key resolution from the
environment, the request payload each helper builds, response unwrapping, and
the fail-soft None return on transport/parse errors.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.vapi_llm_client import QorTrollerAI

_ENDPOINT = "https://api.quicksilverpro.io/v1/chat/completions"


def _resp(content="verdict: HUMAN"):
    resp = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _client(api_key="test-key"):
    with patch.dict(os.environ, {"QUICKSILVER_API_KEY": api_key}, clear=False), \
         patch("vapi_bridge.vapi_llm_client.load_dotenv"):
        return QorTrollerAI()


class TestApiKeyResolution(unittest.TestCase):

    def test_key_read_from_environment(self):
        self.assertEqual(_client("env-key").api_key, "env-key")

    def test_missing_key_falls_back_to_default(self):
        env = {k: v for k, v in os.environ.items() if k != "QUICKSILVER_API_KEY"}
        with patch.dict(os.environ, env, clear=True), \
             patch("vapi_bridge.vapi_llm_client.load_dotenv"):
            client = QorTrollerAI()
        self.assertTrue(client.api_key)


class TestPostCompletion(unittest.TestCase):

    def test_request_shape(self):
        client = _client("k1")
        with patch("vapi_bridge.vapi_llm_client.requests.post", return_value=_resp()) as post:
            out = client._post_completion("sys prompt", "user content")

        self.assertEqual(out, "verdict: HUMAN")
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertEqual(url, _ENDPOINT)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer k1")
        self.assertEqual(kwargs["json"]["model"], "deepseek-v4-flash")
        self.assertEqual(
            kwargs["json"]["messages"],
            [
                {"role": "system", "content": "sys prompt"},
                {"role": "user", "content": "user content"},
            ],
        )
        # Local proxies are bypassed to avoid DNS resolution failures.
        self.assertEqual(kwargs["proxies"], {"http": None, "https": None})

    def test_transport_error_returns_none(self):
        with patch(
            "vapi_bridge.vapi_llm_client.requests.post", side_effect=OSError("no route")
        ):
            self.assertIsNone(_client()._post_completion("s", "u"))

    def test_http_error_returns_none(self):
        resp = _resp()
        resp.raise_for_status.side_effect = RuntimeError("500")
        with patch("vapi_bridge.vapi_llm_client.requests.post", return_value=resp):
            self.assertIsNone(_client()._post_completion("s", "u"))

    def test_malformed_response_returns_none(self):
        resp = MagicMock()
        resp.json.return_value = {"unexpected": True}
        with patch("vapi_bridge.vapi_llm_client.requests.post", return_value=resp):
            self.assertIsNone(_client()._post_completion("s", "u"))


class TestHelpers(unittest.TestCase):

    def test_evaluate_session_integrity_prompt(self):
        client = _client()
        with patch("vapi_bridge.vapi_llm_client.requests.post", return_value=_resp()) as post:
            self.assertEqual(
                client.evaluate_session_integrity({"L4": 0.9}), "verdict: HUMAN"
            )
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertIn("Final Integrity Judge", messages[0]["content"])
        self.assertIn("{'L4': 0.9}", messages[1]["content"])

    def test_generate_scouting_report_prompt(self):
        client = _client()
        with patch("vapi_bridge.vapi_llm_client.requests.post", return_value=_resp()) as post:
            client.generate_scouting_report({"replay": "abc"})
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertIn("Player Profiling Engine", messages[0]["content"])
        self.assertIn("scouting report", messages[1]["content"])

    def test_generic_chat_stringifies_payload(self):
        client = _client()
        with patch("vapi_bridge.vapi_llm_client.requests.post", return_value=_resp()) as post:
            client.generic_chat("be terse", {"a": 1})
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertEqual(messages[0]["content"], "be terse")
        self.assertEqual(messages[1]["content"], "{'a': 1}")


class TestMultiTurnChat(unittest.TestCase):

    def test_history_is_passed_through_with_model_override(self):
        history = [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "hello"},
        ]
        client = _client("k2")
        with patch(
            "vapi_bridge.vapi_llm_client.requests.post", return_value=_resp("hi")
        ) as post:
            self.assertEqual(client.chat(history, model="custom-model"), "hi")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["messages"], history)
        self.assertEqual(kwargs["json"]["model"], "custom-model")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer k2")

    def test_chat_error_returns_none(self):
        with patch(
            "vapi_bridge.vapi_llm_client.requests.post", side_effect=OSError("down")
        ):
            self.assertIsNone(_client().chat([{"role": "user", "content": "x"}]))


if __name__ == "__main__":
    unittest.main()
