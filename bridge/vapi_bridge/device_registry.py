"""
VAPI Phase 19 + 136 — Device Profile Registry with Controller Intelligence

DeviceProfileRegistry resolves the active DeviceProfile for the current
bridge session. Resolution priority:

    1. Explicit override via cfg.device_profile_id (env: DEVICE_PROFILE_ID)
    2. Auto-detect from connected USB HID devices (VID/PID matching)
    3. Default fallback: sony_dualshock_edge_v1

Phase 136 Enhancement:
- Integration with ControllerHardwareIntelligenceAgent (Agent #17)
- Capability matrix enrichment for multi-controller support
- PITL layer availability mapping
- Tier eligibility determination

The registry is instantiated once in DualShockTransport._init_hardware() and
held as self._device_profile. The bridge's sensor_commitment size and
schema_version are then driven by the resolved profile.

This module is the entry point for hardware partner integrations: registering
a new DeviceProfile in controller/profiles/ is all that's needed to make VAPI
support a new controller model.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

log = logging.getLogger(__name__)

# Phase 136: Import ControllerHardwareIntelligenceAgent for capability enrichment
try:
    from .controller_hardware_intelligence_agent import (
        ControllerHardwareIntelligenceAgent,
        ControllerProfile,
        TournamentTier,
    )
    _CONTROLLER_INTELLIGENCE_AVAILABLE = True
except ImportError:
    _CONTROLLER_INTELLIGENCE_AVAILABLE = False
    log.debug("ControllerHardwareIntelligenceAgent not available (Phase 136 pending)")

# ---------------------------------------------------------------------------
# Registry class
# ---------------------------------------------------------------------------

class DeviceProfileRegistry:
    """
    Loads DeviceProfile objects from controller/profiles/ and resolves the
    active profile for the current session.
    
    Phase 136: Extended with ControllerHardwareIntelligenceAgent integration
    for multi-controller capability matrix support.

    Parameters
    ----------
    controller_dir : Path
        Path to the controller/ directory (added to sys.path if needed).
        Typically: Path(__file__).parents[3] / "controller"
    """

    def __init__(self, controller_dir: Path) -> None:
        self._controller_dir = controller_dir
        controller_dir_str = str(controller_dir)
        if controller_dir_str not in sys.path:
            sys.path.insert(0, controller_dir_str)

        # Import the profiles package (controller/profiles/__init__.py)
        try:
            from profiles import get_profile, detect_profile, all_profiles  # type: ignore
            self._get_profile    = get_profile
            self._detect_profile = detect_profile
            self._all_profiles   = all_profiles
            log.debug(
                "DeviceProfileRegistry loaded %d profiles",
                len(all_profiles()),
            )
        except ImportError as exc:
            raise RuntimeError(
                f"Cannot import controller profiles from {controller_dir}: {exc}"
            ) from exc
        
        # Phase 136: Initialize ControllerHardwareIntelligenceAgent
        self._controller_intelligence: Optional[ControllerHardwareIntelligenceAgent] = None
        if _CONTROLLER_INTELLIGENCE_AVAILABLE:
            try:
                self._controller_intelligence = ControllerHardwareIntelligenceAgent()
                log.debug("ControllerHardwareIntelligenceAgent initialized (Phase 136)")
            except Exception as exc:
                log.warning("Failed to initialize ControllerHardwareIntelligenceAgent: %s", exc)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def resolve(self, cfg) -> "DeviceProfile":
        """
        Resolve the active DeviceProfile for the current session.

        Priority:
            1. cfg.device_profile_id — explicit override (DEVICE_PROFILE_ID env var).
               If set and recognised, this profile is used unconditionally.
            2. Auto-detect from connected USB HID devices.
               Enumerates hid.enumerate() and matches VID/PID against the index.
            3. Default: sony_dualshock_edge_v1 (the primary PHCI-certified device).

        Phase 136: Profile enriched with capability matrix from 
        ControllerHardwareIntelligenceAgent.

        Parameters
        ----------
        cfg : Config
            Bridge configuration object. Reads device_profile_id and
            auto_detect_device attributes (both optional, see config.py).

        Returns
        -------
        DeviceProfile
            The resolved profile. Never raises — always returns a valid profile.
        """
        # Priority 1: explicit override
        profile_id = getattr(cfg, "device_profile_id", "")
        if profile_id:
            try:
                profile = self._get_profile(profile_id)
                log.info(
                    "Device profile (explicit override): %s (PHCI=%s)",
                    profile.display_name, profile.phci_tier.name,
                )
                # Phase 136: Enrich with capability matrix
                enriched = self._enrich_profile(profile)
                return enriched
            except KeyError:
                log.warning(
                    "DEVICE_PROFILE_ID=%r not found — falling back to auto-detect",
                    profile_id,
                )

        # Priority 2: auto-detect from HID enumeration
        if getattr(cfg, "auto_detect_device", True):
            detected = self._try_detect_hid()
            if detected is not None:
                log.info(
                    "Device profile (auto-detected VID/PID): %s (PHCI=%s)",
                    detected.display_name, detected.phci_tier.name,
                )
                # Phase 136: Enrich with capability matrix
                enriched = self._enrich_profile(detected)
                return enriched

        # Priority 3: default to DualSense Edge
        default = self._get_profile("sony_dualshock_edge_v1")
        log.info(
            "Device profile (default): %s (PHCI=%s)",
            default.display_name, default.phci_tier.name,
        )
        # Phase 136: Enrich with capability matrix
        enriched = self._enrich_profile(default)
        return enriched
    
    def _enrich_profile(self, base_profile: "DeviceProfile") -> "DeviceProfile":
        """
        Phase 136: Enrich base DeviceProfile with capability matrix from
        ControllerHardwareIntelligenceAgent.
        
        Adds:
        - PITL layer availability
        - Tier eligibility flags
        - Feature capabilities
        - Calibration configuration
        
        Args:
            base_profile: Base DeviceProfile from controller/profiles/
            
        Returns:
            Enriched DeviceProfile with capability matrix
        """
        if not self._controller_intelligence:
            # Agent not available, return base profile
            return base_profile
        
        try:
            # Look up canonical profile by VID/PID
            canonical = None
            for cp in self._controller_intelligence.get_all_profiles().values():
                if cp.usb_vid == getattr(base_profile, 'vid', None) and \
                   cp.usb_pid == getattr(base_profile, 'pid', None):
                    canonical = cp
                    break
            
            if not canonical:
                # No matching canonical profile, return base
                return base_profile
            
            # Enrich base profile with canonical capabilities
            # Note: This uses dynamic attribute attachment for backwards compatibility
            # In production, DeviceProfile dataclass would be extended
            
            # Attach capability matrix
            base_profile._vapi_capability_matrix = {
                "controller_type": canonical.controller_type.value,
                "pitl_layers": self._controller_intelligence._get_available_pitl_layers(canonical),
                "tier_eligibility": self._controller_intelligence._compute_tier_eligibility(canonical),
                "l4_feature_count": canonical.l4_feature_count,
                "l4_feature_mask": canonical.l4_feature_mask,
                "battery_types": canonical.battery_types,
                "capabilities": {
                    "touchpad": canonical.capabilities.touchpad,
                    "triggers": canonical.capabilities.triggers,
                    "gyroscope": canonical.capabilities.gyroscope,
                    "accelerometer": canonical.capabilities.accelerometer,
                },
            }
            
            log.debug("Enriched profile %s with capability matrix (Phase 136)", 
                     base_profile.profile_id)
            
        except Exception as exc:
            log.debug("Failed to enrich profile: %s", exc)
        
        return base_profile
    
    def get_profile_with_intelligence(self, profile_id: str) -> Optional[ControllerProfile]:
        """
        Phase 136: Get controller profile with full intelligence from 
        ControllerHardwareIntelligenceAgent.
        
        Args:
            profile_id: Profile identifier
            
        Returns:
            ControllerProfile with capability matrix, or None if not available
        """
        if not self._controller_intelligence:
            return None
        
        return self._controller_intelligence.get_controller_profile(profile_id)
    
    def get_tier_eligibility(self, base_profile: "DeviceProfile") -> Dict[str, Any]:
        """
        Phase 136: Get tier eligibility for a controller profile.
        
        Args:
            base_profile: DeviceProfile to check
            
        Returns:
            Tier eligibility dictionary
        """
        if not self._controller_intelligence:
            # Fallback: assume Standard tier only if PHCI not certified
            return {
                "standard": True,
                "attested": getattr(base_profile, 'phci_tier', None) == 'ATTESTED',
                "available_layers": ["L0", "L1", "L2", "L3", "L5"],
            }
        
        # Find canonical profile
        for cp in self._controller_intelligence.get_all_profiles().values():
            if cp.usb_vid == getattr(base_profile, 'vid', None) and \
               cp.usb_pid == getattr(base_profile, 'pid', None):
                return self._controller_intelligence._compute_tier_eligibility(cp)
        
        # Unknown profile, assume Standard tier
        return {"standard": True, "attested": False, "available_layers": []}

    def get_profile(self, profile_id: str) -> "DeviceProfile":
        """Return a DeviceProfile by profile_id. Raises KeyError if not found."""
        return self._get_profile(profile_id)

    def all_profiles(self) -> list:
        """Return all registered DeviceProfile objects."""
        return self._all_profiles()
    
    def all_profiles_with_intelligence(self) -> Dict[str, ControllerProfile]:
        """
        Phase 136: Return all canonical controller profiles with intelligence.
        
        Returns:
            Dictionary of profile_id -> ControllerProfile
        """
        if not self._controller_intelligence:
            return {}
        
        return self._controller_intelligence.get_all_profiles()

    # ------------------------------------------------------------------
    # HID auto-detection
    # ------------------------------------------------------------------

    def _try_detect_hid(self) -> "Optional[DeviceProfile]":
        """
        Enumerate connected USB HID devices and return the first profile match.

        Returns None if hid is unavailable or no matching device is found.
        Errors are silently swallowed — auto-detection is a best-effort feature.
        """
        try:
            import hid  # type: ignore
            for device_info in hid.enumerate():
                vid = device_info.get("vendor_id", 0)
                pid = device_info.get("product_id", 0)
                profile = self._detect_profile(vid, pid)
                if profile is not None:
                    log.debug(
                        "HID auto-detect: VID=0x%04X PID=0x%04X → %s",
                        vid, pid, profile.profile_id,
                    )
                    return profile
        except Exception as exc:
            log.debug("HID auto-detection unavailable: %s", exc)
        return None
