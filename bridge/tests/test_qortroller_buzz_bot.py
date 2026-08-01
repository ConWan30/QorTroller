"""Tests for Phase 1 Buzz bot Nostr wiring + Phase 4 !ea ACP bridge."""
import os
import secrets
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_buzz_bot as bot


@pytest.fixture
def cfg():
    """Minimal BotConfig with a random test key."""
    return bot.BotConfig(
        relay_url="ws://localhost:3000",
        channel_ids=["chan-1"],
        matches_channel_id="matches-1",
        bot_name="Test Bot",
        bot_about="test",
        device_id="",
        ioid_token="",
        bridge_base_url="http://localhost:8000",
        bridge_api_key="",
        bot_privkey=secrets.token_hex(32),
        owner_attested=False,
        helper_path="/nonexistent/helper",
        cli_path="/nonexistent/cli",
        status_interval=30,
        command_poll_interval=10,
        session_digest_interval=120,
    )


def test_whoami_returns_hex_pubkey(cfg):
    pubkey = bot._whoami(cfg)
    assert len(pubkey) == 64
    int(pubkey, 16)  # valid hex


def test_sign_event_nostr_sdk(cfg):
    if not bot._NOSTR_SDK:
        pytest.skip("nostr-sdk not installed")
    from nostr_sdk import Keys

    keys = Keys.parse(cfg.bot_privkey)
    event = bot._sign_event(keys, 9, "hello", [["h", "chan-1"]])
    assert event.verify()
    assert event.kind().as_u16() == 9
    assert event.content() == "hello"


def test_handle_command_ea_routes_to_acp(cfg):
    with mock.patch.object(bot, "_run_acp_eval", return_value="PV-CI PASS — 188") as mock_eval:
        content, tags = bot.handle_command("!ea health", cfg, "operatorpubkey")
        assert "PASS" in content
        mock_eval.assert_called_once()
        _, call_pubkey, call_content = mock_eval.call_args[0]
        assert call_pubkey == "operatorpubkey"
        assert call_content.startswith("@EA")
        assert ["acp_tool", "buzz_ea"] in tags


def test_handle_command_ea_acp_unavailable(cfg):
    with mock.patch.object(bot, "_run_acp_eval", return_value=None):
        content, tags = bot.handle_command("!ea health", cfg)
        assert "unavailable or rejected" in content


def test_handle_command_status(cfg):
    state = {
        "rig_state": "ALL_READY",
        "bridge_health": "healthy",
        "oracle_enabled": True,
    }
    with mock.patch.object(bot, "_read_rig_state", return_value=state):
        content, tags = bot.handle_command("!status", cfg)
        assert "ALL_READY" in content


def test_claim_register_list():
    from buzz_claim_register import main

    rc = main(["--register", str(REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register.json"), "list"])
    assert rc == 0


def test_claim_register_check_approved_phrase():
    from buzz_claim_register import check_phrase

    result = check_phrase("Candidate presence was observed", REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register.json")
    assert result["approved"] is True
    assert result["best_match"]["row_id"] == "R-04"


def test_claim_register_check_blocked():
    from buzz_claim_register import check_phrase

    result = check_phrase("Humanity is cryptographically proven", REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register.json")
    assert result["approved"] is False
    assert result["best_match"]["row_id"] == "R-10"


def test_claim_register_forbidden():
    from buzz_claim_register import check_phrase

    result = check_phrase("100% fair and unhackable", REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register.json")
    assert result["approved"] is False
    assert "100% fair" in result["forbidden_hits"]
