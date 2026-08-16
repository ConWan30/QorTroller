"""Tests for LLM router orchestration with QS + LOCAL failover.

Tests router orchestration, provider failover, provenance tracking,
and health monitoring.
"""
from __future__ import annotations

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.llm_routing.router_orchestrator import (
    LLMRouter,
    RouterConfig,
    LLMProvider,
    RouterResult,
    ProvenanceRecord
)
from vapi_bridge.llm_routing.local_client import LocalLLMClient
from vapi_bridge.llm_routing.qs_client import QuickSilverClient


class TestLLMRouter:
    """Test LLM router orchestration."""
    
    @pytest.fixture
    def mock_store(self):
        """Create a mock store for testing."""
        store = Mock()
        store.insert_llm_provenance = Mock()
        return store
    
    @pytest.fixture
    def router_config(self):
        """Create router configuration for testing."""
        return RouterConfig(
            primary_provider=LLMProvider.QUICKSILVER,
            secondary_provider=LLMProvider.LOCAL_NIM,
            auto_failover_enabled=True,
            max_failures_before_failover=2,
            enable_provenance=True
        )
    
    @pytest.fixture
    def router(self, mock_store, router_config):
        """Create an LLM router for testing."""
        with patch('vapi_bridge.llm_routing.router_orchestrator.QuickSilverClient'), \
             patch('vapi_bridge.llm_routing.router_orchestrator.LocalLLMClient'):
            router = LLMRouter(router_config, mock_store)
            return router
    
    def test_router_initialization(self, router, router_config):
        """Test that router initializes correctly."""
        assert router._config == router_config
        assert router._config.auto_failover_enabled is True
        assert router._config.enable_provenance is True
    
    def test_route_request_primary_success(self, router):
        """Test successful routing to primary provider."""
        # Mock successful primary provider
        router._qs_client = Mock()
        router._qs_client.generate = AsyncMock(return_value="QS response")
        router._provider_health[LLMProvider.QUICKSILVER]["healthy"] = True
        
        result = asyncio.run(router.route_request(
            prompt="test prompt",
            system_prompt="test system"
        ))
        
        assert result.success is True
        assert result.content == "QS response"
        assert result.provider == LLMProvider.QUICKSILVER
        assert result.provenance.provider == LLMProvider.QUICKSILVER
        assert result.provenance.success is True
    
    def test_route_request_failover_to_secondary(self, router):
        """Test failover to secondary provider when primary fails."""
        # Mock failing primary provider
        router._qs_client = Mock()
        router._qs_client.generate = AsyncMock(side_effect=Exception("QS failed"))
        router._provider_health[LLMProvider.QUICKSILVER]["healthy"] = True
        
        # Mock successful secondary provider
        router._local_client = Mock()
        router._local_client.generate = AsyncMock(return_value="NIM response")
        router._provider_health[LLMProvider.LOCAL_NIM]["healthy"] = True
        
        result = asyncio.run(router.route_request(
            prompt="test prompt",
            system_prompt="test system"
        ))
        
        assert result.success is True
        assert result.content == "NIM response"
        assert result.provider == LLMProvider.LOCAL_NIM
        assert result.provenance.fallback_triggered is True
        assert result.provenance.fallback_from == LLMProvider.QUICKSILVER
    
    def test_route_request_fallback_content(self, router):
        """Test fallback content when both providers fail."""
        # Mock both providers failing
        router._qs_client = Mock()
        router._qs_client.generate = AsyncMock(side_effect=Exception("QS failed"))
        router._local_client = Mock()
        router._local_client.generate = AsyncMock(side_effect=Exception("NIM failed"))
        
        result = asyncio.run(router.route_request(
            prompt="test prompt",
            system_prompt="test system",
            fallback_content="fallback content"
        ))
        
        assert result.success is True
        assert result.content == "fallback content"
        assert result.provider == LLMProvider.FALLBACK
    
    def test_provider_health_tracking(self, router):
        """Test provider health tracking."""
        # Initially both providers healthy
        health = router.get_provider_health()
        assert health["quicksilver"]["healthy"] is True
        assert health["local_nim"]["healthy"] is True
        
        # Simulate primary provider failures
        router._record_provider_failure(LLMProvider.QUICKSILVER)
        router._record_provider_failure(LLMProvider.QUICKSILVER)
        
        # Primary should now be unhealthy
        health = router.get_provider_health()
        assert health["quicksilver"]["healthy"] is False
        assert health["quicksilver"]["failures"] == 2
    
    def test_provenance_tracking(self, router):
        """Test provenance tracking for calls."""
        # Mock successful primary provider
        router._qs_client = Mock()
        router._qs_client.generate = AsyncMock(return_value="test response")
        router._provider_health[LLMProvider.QUICKSILVER]["healthy"] = True
        
        result = asyncio.run(router.route_request(
            prompt="test prompt",
            system_prompt="test system"
        ))
        
        assert result.provenance.call_id is not None
        assert result.provenance.provider == LLMProvider.QUICKSILVER
        assert result.provenance.success is True
        assert result.provenance.prompt_hash != ""
        assert result.provenance.response_hash != ""
        
        # Verify provenance was stored
        router._store.insert_llm_provenance.assert_called_once()
    
    def test_provenance_summary(self, router):
        """Test provenance summary generation."""
        summary = router.get_provenance_summary(hours=24)
        
        assert "period_hours" in summary
        assert "total_calls" in summary
        assert "success_rate" in summary
        assert "provider_distribution" in summary


class TestLocalLLMClient:
    """Test local NIM client adapter."""
    
    def test_local_client_initialization(self):
        """Test local client initialization."""
        with patch('vapi_bridge.llm_routing.local_client.HardenedNIMClient'):
            client = LocalLLMClient()
            assert client is not None
    
    def test_local_client_generate(self):
        """Test local client generation."""
        with patch('vapi_bridge.llm_routing.local_client.HardenedNIMClient') as mock_nim:
            mock_nim_instance = Mock()
            mock_nim_instance.generate_reasoning = AsyncMock(return_value="NIM response")
            mock_nim.return_value = mock_nim_instance
            
            client = LocalLLMClient()
            result = asyncio.run(client.generate("test prompt", "test system"))
            
            assert result == "NIM response"
    
    def test_local_client_availability(self):
        """Test local client availability check."""
        with patch('vapi_bridge.llm_routing.local_client.HardenedNIMClient') as mock_nim:
            mock_nim_instance = Mock()
            mock_nim_instance.config = Mock()
            mock_nim_instance.config.enabled = True
            mock_nim.return_value = mock_nim_instance
            
            client = LocalLLMClient()
            assert client.is_available() is True


class TestQuickSilverClient:
    """Test QuickSilver client adapter."""
    
    def test_qs_client_initialization(self):
        """Test QuickSilver client initialization."""
        with patch('vapi_bridge.llm_routing.qs_client.QorTrollerAI'):
            client = QuickSilverClient()
            assert client is not None
    
    def test_qs_client_generate(self):
        """Test QuickSilver client generation."""
        with patch('vapi_bridge.llm_routing.qs_client.QorTrollerAI') as mock_qs:
            mock_qs_instance = Mock()
            mock_qs_instance.generic_chat = Mock(return_value="QS response")
            mock_qs.return_value = mock_qs_instance
            
            client = QuickSilverClient()
            result = asyncio.run(client.generate("test prompt", "test system"))
            
            assert result == "QS response"
    
    def test_qs_client_availability(self):
        """Test QuickSilver client availability check."""
        with patch('vapi_bridge.llm_routing.qs_client.QorTrollerAI'):
            client = QuickSilverClient()
            assert client.is_available() is True


class TestProvenanceRecord:
    """Test provenance record schema."""
    
    def test_provenance_record_creation(self):
        """Test provenance record creation."""
        record = ProvenanceRecord(
            call_id="test_call_id",
            timestamp=1234567890.0,
            provider=LLMProvider.QUICKSILVER,
            model="test_model",
            prompt_hash="abc123",
            response_hash="def456",
            token_count=100,
            latency_ms=500.0,
            success=True
        )
        
        assert record.call_id == "test_call_id"
        assert record.provider == LLMProvider.QUICKSILVER
        assert record.success is True
        assert record.fallback_triggered is False