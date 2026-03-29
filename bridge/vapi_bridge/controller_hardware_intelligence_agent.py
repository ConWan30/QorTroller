"""
VAPI Phase 136 — ControllerHardwareIntelligenceAgent (Agent #17)

Multi-controller hardware abstraction and capability intelligence layer.

This agent provides:
- Controller auto-detection (USB HID enumeration, BLE scanning)
- Capability matrix mapping (PITL layer availability per controller)
- Tier eligibility determination (Attested vs Standard)
- Transport negotiation (USB 1000Hz vs BT 250Hz vs proprietary)
- Per-controller threshold calibration tracks
- GSR grip addon detection and integration

Architecture:
    USB HID Enumeration -> VID/PID Matching -> ControllerProfile Lookup
    BLE Scanning -> Name Prefix Matching -> ControllerProfile Lookup
    -> Capability Matrix -> PITL Layer Availability -> Tier Eligibility
    -> Transport Negotiation -> Calibration Track Selection

Integration Points:
- DeviceProfileRegistry: Extends with capability matrix
- AgentSupervisor: Health monitoring via controller_detection_log
- SessionAdjudicator: Queries for available layers, adjusts weights
- CalibrationIntelligenceAgent: Per-controller threshold tracks
- TournamentActivationChainAgent: Tier compatibility validation

Author: VAI-LABS
Phase: 136
Date: 2026-03-29
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------

class PITLLayerStatus(Enum):
    """PITL layer availability status"""
    FULL = "full"           # All features available
    PARTIAL = "partial"     # Some features available
    NONE = "none"           # Layer unavailable
    ALWAYS = "always"       # Always available (L0, L1, L2, L3, L5)

class TournamentTier(Enum):
    """Tournament eligibility tiers"""
    ATTESTED = "attested"     # Highest trust: L0-L6 full
    STANDARD = "standard"     # Standard trust: L0-L5 minimum
    FALLBACK = "fallback"     # Advisory only: L0-L3

class TransportType(Enum):
    """Transport types with their characteristics"""
    USB_1000HZ = "usb_1000hz"
    BLE_250HZ = "ble_250hz"
    XBOX_WIRELESS = "xbox_wireless"
    DUALSENSE_WIRELESS = "dualsense_wireless"
    PROPRIETARY_1000HZ = "proprietary_1000hz"

class ControllerType(Enum):
    """Supported controller types"""
    SONY_DUALSHOCK_EDGE = "sony_dualshock_edge_v1"
    MICROSOFT_XBOX_SERIES_X = "microsoft_xbox_series_x"
    NINTENDO_SWITCH_PRO = "nintendo_switch_pro"
    SONY_DUALSHOCK_4 = "sony_dualshock_4"
    GENERIC = "generic"

# PITL Layer requirements
PITL_LAYERS = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]

# Tier requirements
TIER_REQUIREMENTS = {
    TournamentTier.ATTESTED: {
        "min_layers": ["L0", "L1", "L2", "L3", "L4", "L5", "L6"],
        "L6_status": PITLLayerStatus.FULL,
        "L4_status": PITLLayerStatus.FULL,
        "transport_min_hz": 1000,
        "phci_certified": True,
    },
    TournamentTier.STANDARD: {
        "min_layers": ["L0", "L1", "L2", "L3", "L5"],
        "L6_status": None,  # Optional
        "L4_status": None,  # Can be partial
        "transport_min_hz": 250,
        "phci_certified": False,  # Optional
    },
    TournamentTier.FALLBACK: {
        "min_layers": ["L0", "L1", "L2", "L3"],
        "L6_status": PITLLayerStatus.NONE,
        "L4_status": PITLLayerStatus.NONE,
        "transport_min_hz": 0,
        "phci_certified": False,
    },
}

# Full L4 feature count (Edge controller)
L4_FULL_FEATURES = 13

# Controller-specific L4 feature masks
# Order: [gyro_std_x, gyro_std_y, gyro_std_z, gyro_corr_xy, accel_entropy, accel_std,
#          touchpad_entropy, touchpad_var_x, touchpad_var_y, 
#          trigger_resist_l2, trigger_resist_r2, press_timing_jitter, resting_grip]
L4_FEATURE_MASKS = {
    ControllerType.SONY_DUALSHOCK_EDGE: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # 13 features
    ControllerType.MICROSOFT_XBOX_SERIES_X: [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1],  # 7 features
    ControllerType.NINTENDO_SWITCH_PRO: [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1],  # 7 features
    ControllerType.SONY_DUALSHOCK_4: [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1],  # 11 features
    ControllerType.GENERIC: [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1],  # 7 features
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ControllerCapabilities:
    """Feature capabilities for a controller"""
    # Core features
    touchpad: Dict[str, Any] = field(default_factory=dict)
    triggers: Dict[str, Any] = field(default_factory=dict)
    gyroscope: Dict[str, Any] = field(default_factory=dict)
    accelerometer: Dict[str, Any] = field(default_factory=dict)
    gsr_grip_addon: Dict[str, Any] = field(default_factory=dict)
    
    # Additional features
    hd_rumble: Dict[str, Any] = field(default_factory=dict)
    lightbar: Dict[str, Any] = field(default_factory=dict)
    impulse_triggers: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ControllerProfile:
    """Complete controller profile with capabilities and metadata"""
    # Identity
    id: str
    display_name: str
    manufacturer: str
    model: str
    controller_type: ControllerType
    
    # USB identification
    usb_vid: int
    usb_pid: int
    usb_interface: int
    usb_report_size: int
    usb_report_layout: str
    
    # BLE identification
    ble_service_uuid: Optional[str] = None
    ble_report_char_uuid: Optional[str] = None
    ble_name_prefix: Optional[str] = None
    
    # Transport capabilities
    transport_usb_hz: int = 1000
    transport_ble_hz: int = 250
    transport_proprietary: List[Dict[str, Any]] = field(default_factory=list)
    
    # PITL layer availability
    pitl_l4_status: PITLLayerStatus = PITLLayerStatus.FULL
    pitl_l6_status: PITLLayerStatus = PITLLayerStatus.FULL
    
    # Capabilities
    capabilities: ControllerCapabilities = field(default_factory=ControllerCapabilities)
    
    # Tier eligibility
    phci_certified: bool = False
    tier_standard: bool = True
    tier_attested: bool = False
    
    # Calibration configuration
    battery_types: List[str] = field(default_factory=list)
    l4_feature_count: int = 13
    l4_feature_mask: List[int] = field(default_factory=lambda: [1] * 13)
    l4_notes: str = ""
    l6_notes: str = ""
    
    # Certification
    phci_certification_date: Optional[str] = None
    phci_certification_version: Optional[str] = None

@dataclass
class DetectedController:
    """Instance of a detected controller with runtime info"""
    # Identification
    controller_id: str
    profile: ControllerProfile
    
    # Connection info
    transport: TransportType
    connection_type: str  # "usb", "ble", "proprietary"
    port_path: Optional[str] = None  # USB port path or BLE address
    
    # Runtime state
    connected_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)
    
    # Quality metrics
    latency_ms: Optional[float] = None
    jitter_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    
    # Features active
    features_active: Dict[str, bool] = field(default_factory=dict)
    
    # Tier eligibility (computed at detection)
    tier_eligibility: Dict[str, bool] = field(default_factory=dict)
    pitl_available: List[str] = field(default_factory=list)

@dataclass
class TierEligibilityResult:
    """Result of tier eligibility check"""
    controller_id: str
    controller_type: ControllerType
    
    tier_standard: bool
    tier_attested: bool
    
    available_layers: List[str]
    missing_layers_attested: List[str]
    
    reasons: Dict[str, str]  # tier -> reason if ineligible

@dataclass
class TransportValidationResult:
    """Result of transport quality validation"""
    controller_id: str
    transport: TransportType
    requested_tier: TournamentTier
    
    # Metrics
    p99_latency_ms: float
    jitter_ms: float
    packet_loss_pct: float
    samples: int
    duration_sec: float
    
    # Compliance
    tier_compliance: Dict[str, bool]
    status: str  # "PASS", "WARNING", "FAIL"
    recommendation: str

# ---------------------------------------------------------------------------
# Canonical Controller Profiles
# ---------------------------------------------------------------------------

CANONICAL_PROFILES: Dict[str, ControllerProfile] = {
    "sony_dualshock_edge_v1": ControllerProfile(
        id="sony_dualshock_edge_v1",
        display_name="Sony DualShock Edge (CFI-ZCP1)",
        manufacturer="Sony",
        model="CFI-ZCP1",
        controller_type=ControllerType.SONY_DUALSHOCK_EDGE,
        usb_vid=0x054C,
        usb_pid=0x0DF2,
        usb_interface=3,
        usb_report_size=64,
        usb_report_layout="sony_dualsense_edge",
        ble_service_uuid="00001124-0000-1000-8000-00805f9b34fb",
        ble_report_char_uuid="00002a4d-0000-1000-8000-00805f9b34fb",
        ble_name_prefix="DualSense Edge",
        transport_usb_hz=1000,
        transport_ble_hz=250,
        pitl_l4_status=PITLLayerStatus.FULL,
        pitl_l6_status=PITLLayerStatus.FULL,
        capabilities=ControllerCapabilities(
            touchpad={"present": True, "size": [1920, 1080], "multi_touch": True, "pressure": False},
            triggers={"type": "adaptive", "l2_adaptive": True, "r2_adaptive": True, "mode_count": 3},
            gyroscope={"present": True, "axes": 3, "precision": 16, "range_dps": 2000, "sample_rate_hz": 1000},
            accelerometer={"present": True, "axes": 3, "precision": 16, "range_g": 16, "sample_rate_hz": 1000},
            gsr_grip_addon={"capable": True, "interface": "usb_passthrough"},
        ),
        phci_certified=True,
        tier_standard=True,
        tier_attested=True,
        battery_types=["touchpad", "trigger", "gameplay", "resting_grip"],
        l4_feature_count=13,
        l4_feature_mask=[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        l4_notes="Full biometric suite (touchpad + gyro + accel + adaptive triggers)",
        l6_notes="Full adaptive trigger resistance measurement",
        phci_certification_date="2026-01-15",
        phci_certification_version="PHCI-2026.1",
    ),
    
    "microsoft_xbox_series_x": ControllerProfile(
        id="microsoft_xbox_series_x",
        display_name="Microsoft Xbox Series X Controller",
        manufacturer="Microsoft",
        model="Series X",
        controller_type=ControllerType.MICROSOFT_XBOX_SERIES_X,
        usb_vid=0x045E,
        usb_pid=0x0B12,
        usb_interface=0,
        usb_report_size=18,
        usb_report_layout="microsoft_xinput",
        ble_service_uuid="00001124-0000-1000-8000-00805f9b34fb",
        ble_report_char_uuid="00002a4d-0000-1000-8000-00805f9b34fb",
        ble_name_prefix="Xbox Wireless Controller",
        transport_usb_hz=1000,
        transport_ble_hz=250,
        transport_proprietary=[{"name": "xbox_wireless", "hz": 1000, "latency_ms": 2.0}],
        pitl_l4_status=PITLLayerStatus.PARTIAL,
        pitl_l6_status=PITLLayerStatus.NONE,
        capabilities=ControllerCapabilities(
            touchpad={"present": False},
            triggers={"type": "impulse", "l2_adaptive": False, "r2_adaptive": False, "l2_impulse": True, "r2_impulse": True},
            gyroscope={"present": True, "axes": 3, "precision": 16, "range_dps": 2000, "sample_rate_hz": 1000, "notes": "Elite 2 only"},
            accelerometer={"present": True, "axes": 3, "precision": 16, "range_g": 16, "sample_rate_hz": 1000, "notes": "Elite 2 only"},
            gsr_grip_addon={"capable": False},
            impulse_triggers={"present": True, "l2": True, "r2": True},
        ),
        phci_certified=False,
        tier_standard=True,
        tier_attested=False,
        battery_types=["gameplay", "trigger"],
        l4_feature_count=7,
        l4_feature_mask=[1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1],
        l4_notes="Gyro-only L4 (no touchpad features). Elite 2 required for gyro.",
        l6_notes="L6 DISABLED - no adaptive trigger resistance measurement",
    ),
    
    "nintendo_switch_pro": ControllerProfile(
        id="nintendo_switch_pro",
        display_name="Nintendo Switch Pro Controller",
        manufacturer="Nintendo",
        model="HAC-013",
        controller_type=ControllerType.NINTENDO_SWITCH_PRO,
        usb_vid=0x057E,
        usb_pid=0x2009,
        usb_interface=0,
        usb_report_size=64,
        usb_report_layout="nintendo_switch_pro",
        ble_service_uuid="00001124-0000-1000-8000-00805f9b34fb",
        ble_report_char_uuid="00002a4d-0000-1000-8000-00805f9b34fb",
        ble_name_prefix="Pro Controller",
        transport_usb_hz=1000,
        transport_ble_hz=250,
        pitl_l4_status=PITLLayerStatus.PARTIAL,
        pitl_l6_status=PITLLayerStatus.NONE,
        capabilities=ControllerCapabilities(
            touchpad={"present": False},
            triggers={"type": "standard", "l2_adaptive": False, "r2_adaptive": False},
            gyroscope={"present": True, "axes": 3, "precision": 16, "range_dps": 2000, "sample_rate_hz": 1000, "notes": "Best-in-class gyro"},
            accelerometer={"present": True, "axes": 3, "precision": 16, "range_g": 16, "sample_rate_hz": 1000},
            gsr_grip_addon={"capable": False},
            hd_rumble={"present": True, "l2": True, "r2": True, "frequency_range": [0, 1250]},
        ),
        phci_certified=False,
        tier_standard=True,
        tier_attested=False,
        battery_types=["gameplay"],
        l4_feature_count=6,
        l4_feature_mask=[1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0],
        l4_notes="Best-in-class gyro, no touchpad. Excellent for gyro-only L4.",
        l6_notes="L6 DISABLED - HD rumble not equivalent to adaptive triggers",
    ),
    
    "sony_dualshock_4": ControllerProfile(
        id="sony_dualshock_4",
        display_name="Sony DualShock 4",
        manufacturer="Sony",
        model="CUH-ZCT2",
        controller_type=ControllerType.SONY_DUALSHOCK_4,
        usb_vid=0x054C,
        usb_pid=0x05C4,
        usb_interface=0,
        usb_report_size=64,
        usb_report_layout="sony_dualshock_4",
        ble_service_uuid="00001124-0000-1000-8000-00805f9b34fb",
        ble_report_char_uuid="00002a4d-0000-1000-8000-00805f9b34fb",
        ble_name_prefix="Wireless Controller",
        transport_usb_hz=1000,
        transport_ble_hz=250,
        pitl_l4_status=PITLLayerStatus.FULL,
        pitl_l6_status=PITLLayerStatus.PARTIAL,
        capabilities=ControllerCapabilities(
            touchpad={"present": True, "size": [1200, 800], "multi_touch": True, "pressure": False, "notes": "Smaller than Edge"},
            triggers={"type": "standard", "l2_adaptive": False, "r2_adaptive": False},
            gyroscope={"present": True, "axes": 3, "precision": 16, "range_dps": 2000, "sample_rate_hz": 1000},
            accelerometer={"present": True, "axes": 3, "precision": 16, "range_g": 16, "sample_rate_hz": 1000},
            gsr_grip_addon={"capable": False},
            lightbar={"present": True, "rgb": True, "player_id": True},
        ),
        phci_certified=True,
        tier_standard=True,
        tier_attested=False,
        battery_types=["touchpad", "gameplay", "trigger"],
        l4_feature_count=11,
        l4_feature_mask=[1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1],
        l4_notes="Touchpad available but smaller surface area than Edge",
        l6_notes="L6 PARTIAL - trigger latency only (no resistance measurement)",
        phci_certification_date="2024-06-01",
        phci_certification_version="PHCI-2024.2",
    ),
}

# ---------------------------------------------------------------------------
# ControllerHardwareIntelligenceAgent Class
# ---------------------------------------------------------------------------

class ControllerHardwareIntelligenceAgent:
    """
    Phase 136 — ControllerHardwareIntelligenceAgent (Agent #17)
    
    Provides hardware abstraction intelligence for multi-controller support.
    
    Key Methods:
    - detect_controllers(): USB/BT enumeration and profiling
    - get_controller_profile(): Capability matrix lookup
    - get_tier_eligibility(): Check tournament tier compatibility
    - negotiate_transport(): Select transport for tier requirements
    - get_pitl_layer_availability(): Map controller to PITL layers
    - validate_transport_quality(): Measure latency/jitter for tier compliance
    """
    
    def __init__(self, cfg=None, store=None, bus=None):
        """
        Initialize the ControllerHardwareIntelligenceAgent.
        
        Args:
            cfg: Configuration object
            store: Data store for persistence
            bus: Message bus for publishing events
        """
        self._cfg = cfg
        self._store = store
        self._bus = bus
        
        # Load canonical profiles
        self._profiles = CANONICAL_PROFILES
        
        # Runtime state
        self._detected_controllers: Dict[str, DetectedController] = {}
        
        log.info("ControllerHardwareIntelligenceAgent initialized (Phase 136)")
        log.info("Loaded %d canonical controller profiles", len(self._profiles))
    
    # -----------------------------------------------------------------------
    # Detection Methods
    # -----------------------------------------------------------------------
    
    async def detect_controllers(self) -> List[DetectedController]:
        """
        Detect all connected controllers via USB HID and BLE.
        
        Returns:
            List of DetectedController instances
        """
        detected = []
        
        # USB HID enumeration
        usb_controllers = await self._detect_usb_controllers()
        detected.extend(usb_controllers)
        
        # BLE scanning
        ble_controllers = await self._detect_ble_controllers()
        detected.extend(ble_controllers)
        
        # Update runtime registry
        for controller in detected:
            self._detected_controllers[controller.controller_id] = controller
        
        # Log detection event
        log.info("Detected %d controllers (%d USB, %d BLE)", 
                 len(detected), len(usb_controllers), len(ble_controllers))
        
        # Persist to store if available
        if self._store:
            for controller in detected:
                self._persist_detection(controller)
        
        return detected
    
    async def _detect_usb_controllers(self) -> List[DetectedController]:
        """
        Enumerate USB HID devices and match against profiles.
        
        Returns:
            List of USB-connected DetectedController instances
        """
        detected = []
        
        try:
            import hid
            
            # Enumerate all HID devices
            devices = hid.enumerate()
            
            for device in devices:
                vid = device.get("vendor_id")
                pid = device.get("product_id")
                interface = device.get("interface_number")
                path = device.get("path")
                
                # Match against profiles
                for profile_id, profile in self._profiles.items():
                    if vid == profile.usb_vid and pid == profile.usb_pid:
                        # Found matching controller
                        controller_id = f"{profile_id}_{path.decode('utf-8', errors='ignore') if path else 'unknown'}"
                        
                        detected_controller = DetectedController(
                            controller_id=controller_id,
                            profile=profile,
                            transport=TransportType.USB_1000HZ,
                            connection_type="usb",
                            port_path=path.decode('utf-8', errors='ignore') if path else None,
                        )
                        
                        # Compute tier eligibility
                        detected_controller.tier_eligibility = self._compute_tier_eligibility(profile)
                        detected_controller.pitl_available = self._get_available_pitl_layers(profile)
                        
                        detected.append(detected_controller)
                        log.debug("Detected USB controller: %s (%s)", 
                                  profile.display_name, controller_id)
                        break
                        
        except ImportError:
            log.warning("hid library not available, skipping USB detection")
        except Exception as e:
            log.error("USB detection error: %s", e)
        
        return detected
    
    async def _detect_ble_controllers(self) -> List[DetectedController]:
        """
        Scan for BLE controllers and match against profiles.
        
        Returns:
            List of BLE-connected DetectedController instances
        """
        detected = []
        
        try:
            # BLE scanning requires bleak library
            # This is a placeholder - actual implementation would use BleakScanner
            log.debug("BLE scanning not yet implemented (requires bleak)")
            
        except ImportError:
            log.debug("bleak library not available, skipping BLE detection")
        except Exception as e:
            log.error("BLE detection error: %s", e)
        
        return detected
    
    def _persist_detection(self, controller: DetectedController):
        """
        Persist controller detection to store.
        
        Args:
            controller: DetectedController to persist
        """
        if not self._store:
            return
        
        try:
            self._store.insert_controller_detection_log(
                controller_id=controller.controller_id,
                profile_id=controller.profile.id,
                transport=controller.transport.value,
                connection_type=controller.connection_type,
                port_path=controller.port_path,
                detected_at=controller.connected_at,
                tier_standard=controller.tier_eligibility.get("standard", False),
                tier_attested=controller.tier_eligibility.get("attested", False),
                pitl_available=json.dumps(controller.pitl_available),
            )
        except Exception as e:
            log.debug("Failed to persist detection: %s", e)
    
    # -----------------------------------------------------------------------
    # Profile and Capability Methods
    # -----------------------------------------------------------------------
    
    def get_controller_profile(self, profile_id: str) -> Optional[ControllerProfile]:
        """
        Get controller profile by ID.
        
        Args:
            profile_id: Profile identifier
            
        Returns:
            ControllerProfile or None if not found
        """
        return self._profiles.get(profile_id)
    
    def get_all_profiles(self) -> Dict[str, ControllerProfile]:
        """
        Get all canonical controller profiles.
        
        Returns:
            Dictionary of profile_id -> ControllerProfile
        """
        return self._profiles.copy()
    
    def _get_available_pitl_layers(self, profile: ControllerProfile) -> List[str]:
        """
        Determine available PITL layers for a controller profile.
        
        Universal layers (always available):
        - L0: Physical presence (connection, battery)
        - L1: PoAC chain integrity
        - L2: HID-XInput Oracle
        - L3: Behavioral ML
        - L5: Temporal rhythm
        
        Conditional layers:
        - L4: Requires gyro OR touchpad
        - L6: Requires adaptive triggers
        
        Args:
            profile: ControllerProfile to check
            
        Returns:
            List of available PITL layer identifiers
        """
        layers = ["L0", "L1", "L2", "L3", "L5"]  # Universal
        
        # L4 availability
        if profile.pitl_l4_status == PITLLayerStatus.FULL:
            layers.append("L4")
        elif profile.pitl_l4_status == PITLLayerStatus.PARTIAL:
            layers.append("L4_partial")
        
        # L6 availability
        if profile.pitl_l6_status == PITLLayerStatus.FULL:
            layers.append("L6")
        elif profile.pitl_l6_status == PITLLayerStatus.PARTIAL:
            layers.append("L6_partial")
        
        return layers
    
    def _compute_tier_eligibility(self, profile: ControllerProfile) -> Dict[str, bool]:
        """
        Compute tournament tier eligibility for a controller profile.
        
        Attested Tier Requirements:
        - L0-L6 ALL available (full PITL stack)
        - L6 MUST be FULL (adaptive triggers mandatory)
        - Controller MUST be PHCI-certified
        
        Standard Tier Requirements:
        - L0-L5 minimum
        - L4 may be partial
        - L6 optional
        
        Args:
            profile: ControllerProfile to check
            
        Returns:
            Dictionary with tier eligibility flags
        """
        available_layers = self._get_available_pitl_layers(profile)
        
        # Standard tier: requires L0-L5 minimum
        is_standard = all(layer in available_layers or layer == "L4" 
                         for layer in ["L0", "L1", "L2", "L3", "L5"])
        
        # Attested tier: requires L6 FULL + PHCI certification
        is_attested = (
            "L6" in available_layers and  # Must be FULL, not PARTIAL
            profile.phci_certified and
            profile.pitl_l6_status == PITLLayerStatus.FULL
        )
        
        return {
            "standard": is_standard,
            "attested": is_attested,
            "available_layers": available_layers,
        }
    
    def get_tier_eligibility(self, controller_id: str) -> Optional[TierEligibilityResult]:
        """
        Get tier eligibility for a detected controller.
        
        Args:
            controller_id: Controller identifier
            
        Returns:
            TierEligibilityResult or None if controller not found
        """
        controller = self._detected_controllers.get(controller_id)
        if not controller:
            return None
        
        profile = controller.profile
        eligibility = self._compute_tier_eligibility(profile)
        available = self._get_available_pitl_layers(profile)
        
        # Determine missing layers for Attested
        missing_attested = []
        if not eligibility["attested"]:
            for layer in ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]:
                if layer not in available and layer != "L4":
                    missing_attested.append(layer)
                elif layer == "L4" and profile.pitl_l4_status != PITLLayerStatus.FULL:
                    missing_attested.append("L4_full")
                elif layer == "L6" and profile.pitl_l6_status != PITLLayerStatus.FULL:
                    missing_attested.append("L6_full")
        
        return TierEligibilityResult(
            controller_id=controller_id,
            controller_type=profile.controller_type,
            tier_standard=eligibility["standard"],
            tier_attested=eligibility["attested"],
            available_layers=available,
            missing_layers_attested=missing_attested,
            reasons=self._get_ineligibility_reasons(profile, eligibility),
        )
    
    def _get_ineligibility_reasons(self, profile: ControllerProfile, 
                                    eligibility: Dict[str, bool]) -> Dict[str, str]:
        """
        Get human-readable reasons for tier ineligibility.
        
        Args:
            profile: ControllerProfile
            eligibility: Eligibility flags
            
        Returns:
            Dictionary of tier -> reason
        """
        reasons = {}
        
        if not eligibility["attested"]:
            reasons_list = []
            if profile.pitl_l6_status != PITLLayerStatus.FULL:
                reasons_list.append("L6 adaptive triggers not available")
            if not profile.phci_certified:
                reasons_list.append("PHCI certification required")
            reasons["attested"] = "; ".join(reasons_list) if reasons_list else "Unknown"
        
        return reasons
    
    # -----------------------------------------------------------------------
    # Transport Methods
    # -----------------------------------------------------------------------
    
    def negotiate_transport(self, controller_id: str, 
                           requested_tier: TournamentTier) -> Optional[TransportType]:
        """
        Negotiate appropriate transport for tournament tier requirements.
        
        Attested tier: Requires 1000Hz transport
        Standard tier: Accepts 250Hz with BT-specific thresholds
        
        Args:
            controller_id: Controller identifier
            requested_tier: Desired tournament tier
            
        Returns:
            Recommended TransportType or None if incompatible
        """
        controller = self._detected_controllers.get(controller_id)
        if not controller:
            return None
        
        profile = controller.profile
        
        # Check tier eligibility first
        eligibility = self._compute_tier_eligibility(profile)
        if requested_tier == TournamentTier.ATTESTED and not eligibility["attested"]:
            log.warning("Controller %s not eligible for Attested tier", controller_id)
            return None
        
        # Attested tier: Must use 1000Hz transport
        if requested_tier == TournamentTier.ATTESTED:
            if controller.transport in [TransportType.USB_1000HZ, 
                                       TransportType.XBOX_WIRELESS,
                                       TransportType.DUALSENSE_WIRELESS]:
                return controller.transport
            
            # Try to upgrade to USB if currently on BLE
            if controller.transport == TransportType.BLE_250HZ:
                # Check if USB available
                log.info("Attempting USB upgrade for Attested tier")
                return TransportType.USB_1000HZ
            
            return None
        
        # Standard tier: Current transport acceptable
        if requested_tier == TournamentTier.STANDARD:
            return controller.transport
        
        return None
    
    async def validate_transport_quality(self, controller_id: str,
                                        requested_tier: TournamentTier,
                                        sample_count: int = 1000) -> Optional[TransportValidationResult]:
        """
        Validate transport quality meets tier requirements.
        
        Measures:
        - p99 latency
        - Jitter (standard deviation)
        - Packet loss
        
        Attested Requirements:
        - p99 latency < 2ms
        - Jitter < 0.5ms
        - Packet loss = 0%
        
        Standard Requirements:
        - p99 latency < 5ms
        - Jitter < 1ms
        - Packet loss < 0.1%
        
        Args:
            controller_id: Controller identifier
            requested_tier: Tournament tier to validate against
            sample_count: Number of samples to collect
            
        Returns:
            TransportValidationResult with metrics and compliance
        """
        controller = self._detected_controllers.get(controller_id)
        if not controller:
            return None
        
        # This is a placeholder - actual implementation would:
        # 1. Send ping reports to controller
        # 2. Measure round-trip time
        # 3. Collect latency distribution
        # 4. Compute statistics
        
        # Simulated metrics for now
        transport = controller.transport
        
        if transport == TransportType.USB_1000HZ:
            p99_latency = 1.2
            jitter = 0.3
            packet_loss = 0.0
        elif transport == TransportType.BLE_250HZ:
            p99_latency = 4.5
            jitter = 0.8
            packet_loss = 0.05
        else:
            p99_latency = 2.0
            jitter = 0.5
            packet_loss = 0.0
        
        # Check compliance
        tier_compliance = {}
        
        if requested_tier == TournamentTier.ATTESTED:
            tier_compliance["attested"] = (
                p99_latency < 2.0 and 
                jitter < 0.5 and 
                packet_loss == 0.0
            )
            tier_compliance["standard"] = True
        else:
            tier_compliance["standard"] = (
                p99_latency < 5.0 and 
                jitter < 1.0 and 
                packet_loss < 0.1
            )
            tier_compliance["attested"] = False
        
        # Determine status
        if requested_tier == TournamentTier.ATTESTED:
            if tier_compliance["attested"]:
                status = "PASS"
                recommendation = "Transport meets Attested tier requirements"
            else:
                status = "FAIL"
                recommendation = "Transport insufficient for Attested tier; use USB"
        else:
            if tier_compliance["standard"]:
                status = "PASS"
                recommendation = "Transport meets Standard tier requirements"
            else:
                status = "WARNING"
                recommendation = "Transport quality degraded; consider USB"
        
        return TransportValidationResult(
            controller_id=controller_id,
            transport=transport,
            requested_tier=requested_tier,
            p99_latency_ms=p99_latency,
            jitter_ms=jitter,
            packet_loss_pct=packet_loss,
            samples=sample_count,
            duration_sec=sample_count / 1000,  # At 1000Hz
            tier_compliance=tier_compliance,
            status=status,
            recommendation=recommendation,
        )
    
    # -----------------------------------------------------------------------
    # Calibration Methods
    # -----------------------------------------------------------------------
    
    def get_calibration_composite_key(self, controller_id: str, 
                                      battery_type: str,
                                      transport: Optional[TransportType] = None) -> str:
        """
        Generate composite key for per-controller calibration tracks.
        
        Format: {profile_id}_{battery_type}_{transport_type}
        
        Examples:
        - sony_dualshock_edge_v1_touchpad_usb_1000hz
        - microsoft_xbox_series_x_gameplay_usb_1000hz
        
        Args:
            controller_id: Controller identifier
            battery_type: Battery/usage type
            transport: Transport type (uses detected if None)
            
        Returns:
            Composite key string
        """
        controller = self._detected_controllers.get(controller_id)
        if not controller:
            return ""
        
        profile_id = controller.profile.id
        transport_type = (transport or controller.transport).value
        
        return f"{profile_id}_{battery_type}_{transport_type}"
    
    def get_l4_feature_mask(self, controller_id: str) -> List[int]:
        """
        Get L4 feature mask for a controller.
        
        The feature mask determines which biometric features are available
        for Mahalanobis distance calculation.
        
        Args:
            controller_id: Controller identifier
            
        Returns:
            List of 0/1 integers indicating feature availability
        """
        controller = self._detected_controllers.get(controller_id)
        if not controller:
            return [0] * L4_FULL_FEATURES
        
        return controller.profile.l4_feature_mask
    
    def get_l4_feature_count(self, controller_id: str) -> int:
        """
        Get number of available L4 features for a controller.
        
        Args:
            controller_id: Controller identifier
            
        Returns:
            Number of available features (7-13)
        """
        mask = self.get_l4_feature_mask(controller_id)
        return sum(mask)
    
    # -----------------------------------------------------------------------
    # Agent Interface Methods (for AgentSupervisor)
    # -----------------------------------------------------------------------
    
    async def run_detection_cycle(self) -> Dict[str, Any]:
        """
        Run one detection cycle (for background agent loop).
        
        Returns:
            Detection results summary
        """
        detected = await self.detect_controllers()
        
        return {
            "timestamp": time.time(),
            "controllers_detected": len(detected),
            "controller_ids": [c.controller_id for c in detected],
            "attested_eligible": sum(1 for c in detected 
                                    if c.tier_eligibility.get("attested", False)),
            "standard_eligible": sum(1 for c in detected 
                                    if c.tier_eligibility.get("standard", False)),
        }
    
    def get_detected_controllers(self) -> Dict[str, DetectedController]:
        """
        Get all currently detected controllers.
        
        Returns:
            Dictionary of controller_id -> DetectedController
        """
        return self._detected_controllers.copy()
    
    def get_controller_by_id(self, controller_id: str) -> Optional[DetectedController]:
        """
        Get a specific detected controller.
        
        Args:
            controller_id: Controller identifier
            
        Returns:
            DetectedController or None
        """
        return self._detected_controllers.get(controller_id)

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def get_canonical_profiles() -> Dict[str, ControllerProfile]:
    """
    Get all canonical controller profiles.
    
    Returns:
        Dictionary of profile_id -> ControllerProfile
    """
    return CANONICAL_PROFILES.copy()

def get_phci_certified_controllers() -> List[ControllerProfile]:
    """
    Get all PHCI-certified controllers.
    
    Returns:
        List of PHCI-certified ControllerProfile instances
    """
    return [p for p in CANONICAL_PROFILES.values() if p.phci_certified]

def get_attested_eligible_controllers() -> List[ControllerProfile]:
    """
    Get all controllers eligible for Attested tier.
    
    Returns:
        List of Attested-eligible ControllerProfile instances
    """
    return [p for p in CANONICAL_PROFILES.values() if p.tier_attested]

# ---------------------------------------------------------------------------
# Module Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Simple test when run directly
    logging.basicConfig(level=logging.INFO)
    
    agent = ControllerHardwareIntelligenceAgent()
    
    print("=" * 60)
    print("VAPI ControllerHardwareIntelligenceAgent (Agent #17)")
    print("=" * 60)
    print()
    
    print("Canonical Profiles:")
    for profile_id, profile in CANONICAL_PROFILES.items():
        print(f"\n  {profile_id}:")
        print(f"    Name: {profile.display_name}")
        print(f"    VID/PID: {profile.usb_vid:04X}:{profile.usb_pid:04X}")
        print(f"    PHCI Certified: {profile.phci_certified}")
        print(f"    Tier Attested: {profile.tier_attested}")
        print(f"    Tier Standard: {profile.tier_standard}")
        print(f"    L4 Features: {profile.l4_feature_count}")
        print(f"    L4 Status: {profile.pitl_l4_status.value}")
        print(f"    L6 Status: {profile.pitl_l6_status.value}")
    
    print()
    print(f"\nPHCI Certified: {len(get_phci_certified_controllers())} controllers")
    print(f"Attested Eligible: {len(get_attested_eligible_controllers())} controllers")
    
    # Run async detection test
    async def test_detection():
        print("\nRunning controller detection...")
        detected = await agent.detect_controllers()
        print(f"Detected {len(detected)} controllers")
        for c in detected:
            print(f"  - {c.controller_id}: {c.profile.display_name}")
    
    asyncio.run(test_detection())
