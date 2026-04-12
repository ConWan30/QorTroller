"""
Tests for FederationBus namespace isolation — VAPI-EXT Step 2.

15+ tests covering:
  - register_namespace() success
  - NamespaceConflictError on duplicate prefix/different owner
  - Idempotent re-registration (same prefix, same owner)
  - validate_event_namespace() passes for registered owner
  - validate_event_namespace() raises NamespaceViolationError on mismatch
  - Unregistered prefix events pass through (backward compat)
  - Module-level helpers
  - FederationBus instance methods delegate to module registry
  - publish_namespaced() validates before publishing
"""
from __future__ import annotations

import asyncio
import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.federation_bus import (
    FederationBus,
    NamespaceConflictError,
    NamespaceViolationError,
    _NAMESPACE_REGISTRY,
    register_namespace,
    validate_event_namespace,
)


# ---------------------------------------------------------------------------
# Fixture: clean namespace registry per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_namespaces():
    _NAMESPACE_REGISTRY._reset()
    yield
    _NAMESPACE_REGISTRY._reset()


# ---------------------------------------------------------------------------
# T-EXT-NS-1: register_namespace() — module-level helper
# ---------------------------------------------------------------------------

class TestRegisterNamespace:
    def test_register_new_prefix(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        assert _NAMESPACE_REGISTRY.get_owner("mobile.") == "VAPI_MOBILE"

    def test_register_multiple_prefixes(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        register_namespace("pragma.", "PRAGMA_JUDGE")
        assert _NAMESPACE_REGISTRY.get_owner("mobile.") == "VAPI_MOBILE"
        assert _NAMESPACE_REGISTRY.get_owner("pragma.") == "PRAGMA_JUDGE"

    def test_idempotent_same_owner(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        register_namespace("mobile.", "VAPI_MOBILE")  # no error
        assert _NAMESPACE_REGISTRY.get_owner("mobile.") == "VAPI_MOBILE"

    def test_conflict_different_owner_raises(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        with pytest.raises(NamespaceConflictError, match="already owned"):
            register_namespace("mobile.", "PRAGMA_JUDGE")

    def test_empty_prefix_raises(self):
        with pytest.raises(ValueError):
            register_namespace("", "VAPI_MOBILE")

    def test_empty_owner_raises(self):
        with pytest.raises(ValueError):
            register_namespace("mobile.", "")


# ---------------------------------------------------------------------------
# T-EXT-NS-2: validate_event_namespace() — module-level helper
# ---------------------------------------------------------------------------

class TestValidateEventNamespace:
    def test_valid_owner_passes(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        validate_event_namespace("mobile.session_verified", "VAPI_MOBILE")  # no error

    def test_wrong_owner_raises_violation(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        with pytest.raises(NamespaceViolationError, match="owned by"):
            validate_event_namespace("mobile.session_verified", "PRAGMA_JUDGE")

    def test_unregistered_prefix_passes_backward_compat(self):
        # VAPI_CORE events (no registered prefix) always pass through
        validate_event_namespace("separation_ratio_breakthrough", "VAPI_CORE")  # no error

    def test_vapi_core_event_not_blocked(self):
        # Core events that predated namespacing pass through no matter what
        register_namespace("mobile.", "VAPI_MOBILE")
        validate_event_namespace("fleet_coherence_detected", "VAPI_CORE")  # no error

    def test_event_must_start_with_prefix(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        # Event that ends with prefix but doesn't start with it — treated as unregistered
        validate_event_namespace("core.mobile.event", "VAPI_CORE")  # passes (not "mobile." prefix)


# ---------------------------------------------------------------------------
# T-EXT-NS-3: FederationBus instance method delegation
# ---------------------------------------------------------------------------

class TestFederationBusInstanceMethods:
    """FederationBus instance methods should delegate to the module _NAMESPACE_REGISTRY."""

    def _make_bus(self):
        """Create a minimal FederationBus with stub dependencies."""
        store = type("S", (), {"get_federation_clusters": lambda s, **kw: []})()
        net = type("N", (), {"detect_clusters": lambda s: []})()
        cfg = type("C", (), {"federation_api_key": "", "federation_peers": ""})()
        return FederationBus(store=store, network_detector=net, chain=None, cfg=cfg)

    def test_register_namespace_via_instance(self):
        bus = self._make_bus()
        bus.register_namespace("mobile.", "VAPI_MOBILE")
        assert _NAMESPACE_REGISTRY.get_owner("mobile.") == "VAPI_MOBILE"

    def test_validate_via_instance_passes(self):
        bus = self._make_bus()
        bus.register_namespace("mobile.", "VAPI_MOBILE")
        bus.validate_event_namespace("mobile.event", "VAPI_MOBILE")  # no error

    def test_validate_via_instance_raises(self):
        bus = self._make_bus()
        bus.register_namespace("mobile.", "VAPI_MOBILE")
        with pytest.raises(NamespaceViolationError):
            bus.validate_event_namespace("mobile.event", "WRONG_OWNER")

    def test_static_method_same_registry_as_module_helper(self):
        register_namespace("pragma.", "PRAGMA_JUDGE")
        assert _NAMESPACE_REGISTRY.get_owner("pragma.") == "PRAGMA_JUDGE"
        # FederationBus.validate_event_namespace sees the same registry
        FederationBus.validate_event_namespace("pragma.ruling_committed", "PRAGMA_JUDGE")


# ---------------------------------------------------------------------------
# T-EXT-NS-4: publish_namespaced() validates before dispatching
# ---------------------------------------------------------------------------

class TestPublishNamespaced:
    def _make_bus(self):
        store = type("S", (), {"get_federation_clusters": lambda s, **kw: []})()
        net = type("N", (), {"detect_clusters": lambda s: []})()
        cfg = type("C", (), {"federation_api_key": "", "federation_peers": ""})()
        return FederationBus(store=store, network_detector=net, chain=None, cfg=cfg)

    @pytest.mark.asyncio
    async def test_publish_namespaced_valid_calls_agent_bus(self):
        bus = self._make_bus()
        register_namespace("mobile.", "VAPI_MOBILE")

        published = []

        class MockAgentBus:
            async def publish(self, event_type, payload, source):
                published.append((event_type, payload, source))

        await bus.publish_namespaced(
            event_type="mobile.session_verified",
            payload={"device_id": "abc"},
            source="MobileSessionAgent",
            owner="VAPI_MOBILE",
            agent_bus=MockAgentBus(),
        )
        assert len(published) == 1
        assert published[0][0] == "mobile.session_verified"

    @pytest.mark.asyncio
    async def test_publish_namespaced_wrong_owner_raises(self):
        bus = self._make_bus()
        register_namespace("mobile.", "VAPI_MOBILE")

        class MockAgentBus:
            async def publish(self, event_type, payload, source):
                pass

        with pytest.raises(NamespaceViolationError):
            await bus.publish_namespaced(
                event_type="mobile.session_verified",
                payload={},
                source="BogusAgent",
                owner="WRONG_OWNER",
                agent_bus=MockAgentBus(),
            )

    @pytest.mark.asyncio
    async def test_publish_namespaced_unregistered_prefix_ok(self):
        """Unregistered prefix events publish without error (backward compat)."""
        bus = self._make_bus()

        published = []

        class MockAgentBus:
            async def publish(self, event_type, payload, source):
                published.append(event_type)

        await bus.publish_namespaced(
            event_type="fleet_coherence_detected",
            payload={},
            source="FleetSignalCoherenceAgent",
            owner="VAPI_CORE",
            agent_bus=MockAgentBus(),
        )
        assert "fleet_coherence_detected" in published


# ---------------------------------------------------------------------------
# T-EXT-NS-5: get_all() registry view
# ---------------------------------------------------------------------------

class TestRegistryView:
    def test_get_all_returns_registered_namespaces(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        register_namespace("pragma.", "PRAGMA_JUDGE")
        all_ns = _NAMESPACE_REGISTRY.get_all()
        assert all_ns["mobile."] == "VAPI_MOBILE"
        assert all_ns["pragma."] == "PRAGMA_JUDGE"

    def test_get_all_returns_copy(self):
        register_namespace("mobile.", "VAPI_MOBILE")
        result = _NAMESPACE_REGISTRY.get_all()
        result["injected."] = "MALICIOUS"  # modifying the copy should not affect registry
        assert _NAMESPACE_REGISTRY.get_owner("injected.") is None
