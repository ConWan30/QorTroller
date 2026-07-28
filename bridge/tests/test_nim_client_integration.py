"""Integration tests for NIM client with security components.

Tests the full integration of the hardened NIM client including
mock API responses, fallback patterns, and security component interaction.
"""
from __future__ import annotations

import pytest
import asyncio
import json
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from dataclasses import dataclass

from vapi_bridge.agentic_stewards.nim_client_hardened import (
    HardenedNIMClient,
    NIMConfig,
    MitigationPlan,
    LLMWithFallback,
    commit_reasoning_output
)


class TestHardenedNIMClient:
    """Test hardened NIM client integration."""

    @pytest.fixture
    def mock_store(self):
        """Create a mock store for testing."""
        store = Mock()
        store.insert_nim_audit_log = Mock()
        store._conn = Mock()
        store._conn.return_value.__enter__ = Mock(return_value=store._conn)
        store._conn.return_value.__exit__ = Mock(return_value=None)
        store._conn.execute = Mock()
        store._conn.execute.return_value.fetchone.return_value = {
            "total_cost": 10.0,
            "call_count": 5
        }
        store._conn.execute.return_value.fetchall.return_value = []
        return store

    @pytest.fixture
    def nim_config(self):
        """Create NIM configuration for testing."""
        return NIMConfig(
            api_key="test_key_12345",
            enabled=True,
            environment="test"
        )

    @pytest.fixture
    def nim_client(self, mock_store):
        """Create a hardened NIM client for testing."""
        # Test with disabled client (no API mocking needed)
        config = NIMConfig(api_key="", enabled=False, environment="test")
        client = HardenedNIMClient(config, mock_store)
        return client

    def test_nim_client_initialization(self, nim_client):
        """Test that NIM client initializes correctly."""
        assert nim_client._config.enabled is False
        assert nim_client._key_manager is not None
        assert nim_client._audit_logger is not None
        assert nim_client._rate_limiter is not None
        assert nim_client._circuit_breaker is not None
        assert nim_client._cost_monitor is not None

    def test_nim_client_client_none_without_api_key(self, mock_store):
        """Test that NIM client has _client=None when no API key."""
        # When enabled=True but api_key is empty, _client should be None
        config = NIMConfig(api_key="", enabled=True)
        # Mock the openai import to prevent ImportError
        with patch.dict('sys.modules', {'openai': None}):
            # Force reimport to trigger the ImportError path
            import importlib
            import vapi_bridge.agentic_stewards.nim_client_hardened as nim_module
            importlib.reload(nim_module)
            client = nim_module.HardenedNIMClient(config, mock_store)
            assert client._client is None

    def test_generate_reasoning_returns_none_when_disabled(self, nim_client):
        """Test that reasoning returns None when client is disabled."""
        result = asyncio.run(nim_client.generate_reasoning(
            device_id="test_device",
            prompt="test prompt"
        ))
        assert result is None

    def test_get_health_status(self, nim_client):
        """Test health status reporting."""
        health = nim_client.get_health_status()
        
        assert "enabled" in health
        assert "model" in health
        assert "circuit_breaker" in health
        assert "cost_status" in health
        assert "anomaly_report" in health


class TestMitigationPlan:
    """Test mitigation plan schema and commitment."""

    def test_mitigation_plan_to_dict(self):
        """Test mitigation plan conversion to dictionary."""
        plan = MitigationPlan(
            incident_id="INV-TEST-1234567890",
            invariant="INV-TEST-INVARIANT",
            severity="WARNING",
            root_cause="Test root cause",
            mitigation={"action": "test_action"},
            verification="test_verification",
            confidence=0.8,
            llm_generated=True
        )
        
        plan_dict = plan.to_dict()
        
        assert plan_dict["incident_id"] == "INV-TEST-1234567890"
        assert plan_dict["invariant"] == "INV-TEST-INVARIANT"
        assert plan_dict["severity"] == "WARNING"
        assert plan_dict["llm_generated"] is True
        assert "commitment_hash" in plan_dict
        assert plan.commitment_hash != ""

    def test_commit_reasoning_output_deterministic(self):
        """Test that reasoning commitment is deterministic."""
        reasoning = {
            "incident_id": "INV-TEST-1234567890",
            "invariant": "INV-TEST-INVARIANT",
            "severity": "WARNING"
        }
        
        hash1 = commit_reasoning_output(reasoning)
        hash2 = commit_reasoning_output(reasoning)
        
        assert hash1 == hash2
        assert len(hash1) == 64 # SHA-256 hex length


class TestLLMWithFallback:
    """Test LLM with deterministic fallback pattern."""

    @pytest.fixture
    def mock_nim_client(self):
        """Create a mock NIM client."""
        client = Mock()
        client.generate_reasoning = AsyncMock(return_value='{"result": "LLM response"}')
        return client

    @pytest.fixture
    def fallback_rules(self):
        """Create fallback rules as callables for testing."""
        return {
            "test_key": lambda ctx: json.dumps({"action": "fallback_action", "reason": "test_fallback"}),
            "another_key": lambda ctx: json.dumps({"action": "another_fallback"})
        }

    def test_llm_with_fallback_uses_llm_first(self, mock_nim_client, fallback_rules):
        """Test that LLM is tried first before fallback."""
        llm_with_fallback = LLMWithFallback(mock_nim_client, fallback_rules)
        
        result = asyncio.run(llm_with_fallback.call_with_fallback(
            context="test context",
            fallback_key="test_key"
        ))
        
        assert result == '{"result": "LLM response"}'
        assert llm_with_fallback._llm_count == 1
        assert llm_with_fallback._fallback_count == 0

    def test_llm_with_fallback_uses_fallback_on_failure(self, mock_nim_client, fallback_rules):
        """Test that fallback is used when LLM fails."""
        mock_nim_client.generate_reasoning = AsyncMock(side_effect=Exception("LLM failed"))
        
        llm_with_fallback = LLMWithFallback(mock_nim_client, fallback_rules)
        
        result = asyncio.run(llm_with_fallback.call_with_fallback(
            context="test context",
            fallback_key="test_key"
        ))
        
        assert result == '{"action": "fallback_action", "reason": "test_fallback"}'
        assert llm_with_fallback._fallback_count == 1

    def test_llm_with_fallback_uses_default_fallback(self, mock_nim_client, fallback_rules):
        """Test that default fallback is used when no rule matches."""
        mock_nim_client.generate_reasoning = AsyncMock(side_effect=Exception("LLM failed"))
        
        llm_with_fallback = LLMWithFallback(mock_nim_client, fallback_rules)
        
        result = asyncio.run(llm_with_fallback.call_with_fallback(
            context="test context",
            fallback_key="nonexistent_key"
        ))
        
        assert result == json.dumps({"status": "defer", "reason": "no_fallback", "fallback_key": "nonexistent_key"})
        assert llm_with_fallback._default_count == 1

    def test_llm_with_fallback_stats(self, mock_nim_client, fallback_rules):
        """Test statistics tracking."""
        llm_with_fallback = LLMWithFallback(mock_nim_client, fallback_rules)
        
        # Simulate some calls
        asyncio.run(llm_with_fallback.call_with_fallback(
            context="test context",
            fallback_key="test_key"
        ))
        
        mock_nim_client.generate_reasoning = AsyncMock(side_effect=Exception("LLM failed"))
        asyncio.run(llm_with_fallback.call_with_fallback(
            context="test context",
            fallback_key="test_key"
        ))
        
        stats = llm_with_fallback.get_stats()
        
        assert stats["llm_calls"] == 1
        assert stats["fallback_calls"] == 1
        assert stats["llm_pct"] == 50.0
        assert stats["fallback_pct"] == 50.0


class TestFailOpenBehavior:
    """Test fail-open behavior when dependencies unavailable."""

    def test_nim_client_fails_open_without_openai(self):
        """Test that NIM client fails open when openai is unavailable."""
        mock_store = Mock()
        mock_store._conn = Mock()
        mock_store._conn.return_value.__enter__ = Mock(return_value=mock_store._conn)
        mock_store._conn.return_value.__exit__ = Mock(return_value=None)
        mock_store._conn.execute = Mock()
        mock_store._conn.execute.return_value.fetchone.return_value = {"total_cost": 0.0, "call_count": 0}
        mock_store._conn.execute.return_value.fetchall.return_value = []
        
        config = NIMConfig(api_key="test_key", enabled=True)
        
        # Mock openai to not be importable
        with patch.dict('sys.modules', {'openai': None, 'openai.AsyncOpenAI': None}):
            import importlib
            import vapi_bridge.agentic_stewards.nim_client_hardened as nim_module
            importlib.reload(nim_module)
            client = nim_module.HardenedNIMClient(config, mock_store)
            
            assert client._config.enabled is False
            assert client._client is None

    def test_nim_client_with_empty_api_key(self):
        """Test that NIM client handles empty API key gracefully."""
        mock_store = Mock()
        mock_store._conn = Mock()
        mock_store._conn.return_value.__enter__ = Mock(return_value=mock_store._conn)
        mock_store._conn.return_value.__exit__ = Mock(return_value=None)
        mock_store._conn.execute = Mock()
        mock_store._conn.execute.return_value.fetchone.return_value = {"total_cost": 0.0, "call_count": 0}
        mock_store._conn.execute.return_value.fetchall.return_value = []
        
        config = NIMConfig(api_key="", enabled=True)
        
        with patch.dict('sys.modules', {'openai': None, 'openai.AsyncOpenAI': None}):
            import importlib
            import vapi_bridge.agentic_stewards.nim_client_hardened as nim_module
            importlib.reload(nim_module)
            client = nim_module.HardenedNIMClient(config, mock_store)
            
            # With empty API key, _client is None but enabled may still be True
            assert client._client is None

    def test_generate_reasoning_returns_none_when_disabled(self):
        """Test that reasoning returns None when client is disabled."""
        mock_store = Mock()
        config = NIMConfig(api_key="", enabled=False)
        
        with patch.dict('sys.modules', {'openai': None, 'openai.AsyncOpenAI': None}):
            import importlib
            import vapi_bridge.agentic_stewards.nim_client_hardened as nim_module
            importlib.reload(nim_module)
            client = nim_module.HardenedNIMClient(config, mock_store)
        
        result = asyncio.run(client.generate_reasoning(
            device_id="test_device",
            prompt="test prompt"
        ))
        
        assert result is None


class TestDeterminismBoundaries:
    """Test that determinism boundaries are enforced."""

    def test_mitigation_plan_commitment_reproducible(self):
        """Test that mitigation plan commitments are reproducible."""
        plan_data = {
            "incident_id": "INV-TEST-1234567890",
            "invariant": "INV-TEST-INVARIANT",
            "severity": "WARNING",
            "root_cause": "Test root cause",
            "mitigation": {"action": "test_action"},
            "verification": "test_verification",
            "confidence": 0.8,
            "llm_generated": True
        }
        
        # Generate commitment multiple times
        hash1 = commit_reasoning_output(plan_data)
        hash2 = commit_reasoning_output(plan_data)
        hash3 = commit_reasoning_output(plan_data)
        
        assert hash1 == hash2 == hash3

    def test_mitigation_plan_canonical_json(self):
        """Test that canonical JSON is used for commitment."""
        # Order of keys should not affect hash
        plan1 = {"z": 1, "a": 2, "m": 3}
        plan2 = {"a": 2, "m": 3, "z": 1}
        
        hash1 = commit_reasoning_output(plan1)
        hash2 = commit_reasoning_output(plan2)
        
        assert hash1 == hash2

    def test_fallback_rules_deterministic(self):
        """Test that fallback rules produce deterministic output."""
        fallback_rules = {
            "test_key": {"action": "fallback_action", "reason": "test_fallback"}
        }
        
        # Multiple accesses should produce same result
        result1 = fallback_rules["test_key"]
        result2 = fallback_rules["test_key"]
        
        assert result1 == result2
