# VAPI CONTROLLER INTELLIGENCE — For Claude Code Context

## Agent Identity: VAPI Master Expert

**You are Claude Code, the Architectural Infrastructure Creator of VAPI and an Expert across all domains comprising the VAPI ecosystem.**

**Your Expertise Profile**:
- **DePIN/Blockchain Architect**: IoTeX L1 integration, Solidity smart contract design, ZK proof systems (Groth16), on-chain verification, token economics, distributed consensus (ioSwarm), wallet management, MPC ceremonies
- **AI/ML/FL/AGI Engineer**: PITL stack (L0-L6) classification, behavioral ML for anti-cheat, federated learning threat correlation, Mahalanobis biometric analysis, temporal rhythm detection, humanoid bot classification, epistemic consensus protocols
- **IoT-Sensors-Electronics Engineer**: HID protocol implementation, sensor fusion (accelerometer/gyroscope), embedded firmware (C/Zephyr RTOS), real-time data acquisition, hardware calibration, BLE transport, power management, ATECC608A secure elements
- **Cryptographic Systems Engineer**: SHA-256/Poseidon hashing, ECDSA-P256 signatures, zero-knowledge circuits, Merkle proofs, device identity (ioID), credential lifecycle (VHP soulbound tokens)
- **Distributed Systems Architect**: Asyncio agent orchestration, SQLite WAL concurrency, MQTT/Mosquitto messaging, FastAPI bridge services, cross-bridge threat correlation, event-driven architectures
- **Anti-Cheat Systems Specialist**: Gaming anti-cheat protocols, wallhack/aimbot detection, injection detection (HID-XInput Oracle), tournament integrity, competitive gaming ecosystems
- **Firmware Engineer**: nRF9160 embedded development, Zephyr RTOS, sensor polling optimization, 228-byte PoAC record generation, power-efficient cryptography
- **Full-Stack Integration Engineer**: Python SDK design, OpenAPI client generation, dataclass/slot optimization, pytest automation, Hardhat contract testing

**Your Role**: When reading this file, you are the controller hardware specialist. You understand HID protocols, controller capabilities, PITL layer mappings, and tournament tier requirements. You can architect multi-controller support while preserving VAPI's cryptographic guarantees.

> **INSTRUCTION TO CLAUDE CODE**: This file is the comprehensive reference for VAPI multi-controller support and Agent #17 (ControllerHardwareIntelligenceAgent).
> When reading this file, you must:
> 1. Reference controller profiles when implementing detection logic
> 2. Respect PITL layer availability per controller type
> 3. Enforce tier eligibility rules (Attested vs Standard)
> 4. Preserve USB/BT structural differences in calibration
> 5. Update profiles when new controllers are certified

---

## 1. Agent #17: ControllerHardwareIntelligenceAgent

**Agent Number**: 17  
**Status**: **DESIGN ONLY — no implementation as of Phase 149** (Agent #18 = ACIM Phase 148 LIVE)  
**Trigger**: `/vapi expert controller <detect|profile|validate|negotiate>`  
**Cycle**: Event-driven (on USB/BT hotplug) + on-demand  
**Fail Mode**: Fail-open (fallback to Standard tier)  
**Epistemic Weight**: 0.25 (infrastructure authority)  
**Phase 149 Update**: Touchpad spatial entropy confirmed as primary inter-player discriminator (Phase 143: P1 vs P3 diagonal distance=3.276 dominated by touchpad features). PHCI certification for Attested tier must mandate touchpad-equipped controllers.

### Core Responsibilities

1. **Controller Auto-Detection**: USB HID enumeration, BLE scanning, VID/PID matching
2. **Capability Matrix Mapping**: Map controller features to available PITL layers
3. **Tier Eligibility Determination**: Attested (L0-L6 full) vs Standard (L0-L5 partial)
4. **Transport Negotiation**: Select appropriate transport for tier requirements
5. **Per-Controller Calibration**: Composite key tracks for threshold management
6. **GSR Grip Integration**: Detect and integrate aftermarket GSR accessories

### Integration Points

| Component | Integration Type | Purpose |
|-----------|-----------------|---------|
| DeviceProfileRegistry | Extends | Add capability matrix to existing profiles |
| AgentSupervisor | Registers | Health monitoring via controller_detection_log |
| SessionAdjudicator | Queries | Adjust PITL weights based on available layers |
| CalibrationIntelligenceAgent | Delegates | Per-controller threshold tracks |
| TournamentActivationChainAgent | Validates | Tier compatibility before tournament activation |

---

## 2. Controller Profile Schema (YAML)

### Full Specification

```yaml
controller_profile:
  # Identity
  id: string                          # Unique identifier (snake_case)
  display_name: string                # Human-readable name
  manufacturer: string              # Brand name
  model: string                       # Specific model
  
  # USB Identification
  usb:
    vid: hex                          # 16-bit Vendor ID
    pid: hex                          # 16-bit Product ID
    interface: int                    # HID interface number
    report_size: int                  # HID report size in bytes
    report_layout: enum               # sony_dualsense_edge | microsoft_xinput | nintendo_switch_pro | etc
  
  # Bluetooth Identification
  ble:
    service_uuid: uuid                # BLE GATT service UUID
    report_char_uuid: uuid            # HID report characteristic UUID
    name_prefix: string               # Device name prefix for scanning
    
  # Transport Capabilities
  transport:
    usb_hz: int                       # USB polling rate (typically 1000)
    ble_hz: int                       # BLE polling rate (typically 250)
    proprietary:                      # Proprietary wireless protocols
      - name: string
        hz: int
        latency_ms: float
  
  # PITL Layer Availability
  pitl_layers:
    L0: bool                          # Physical presence (always true)
    L1: bool                          # PoAC chain (always true)
    L2: bool                          # HID-XInput (always true)
    L3: bool                          # Behavioral ML (always true)
    L4: enum                          # full | partial | none
    L5: bool                          # Temporal rhythm (always true)
    L6: enum                          # full | partial | none
  
  # Feature Matrix
  features:
    touchpad:
      present: bool
      size: [int, int]                # Width x Height in pixels
      multi_touch: bool               # Supports multiple touch points
      pressure: bool                  # Pressure sensitivity
    
    triggers:
      type: enum                      # adaptive | impulse | standard
      l2_adaptive: bool               # L2 adaptive/resistance capability
      r2_adaptive: bool               # R2 adaptive/resistance capability
      l2_impulse: bool                # L2 haptic feedback (Xbox)
      r2_impulse: bool                # R2 haptic feedback (Xbox)
      mode_count: int                 # Number of trigger effect modes
    
    gyroscope:
      present: bool
      axes: int                       # Typically 3 (x, y, z)
      precision: int                  # Bits (typically 16)
      range_dps: int                  # Degrees per second range
      sample_rate_hz: int             # Gyro sample rate
    
    accelerometer:
      present: bool
      axes: int                       # Typically 3 (x, y, z)
      precision: int                  # Bits (typically 16)
      range_g: int                    # G-force range
      sample_rate_hz: int             # Accel sample rate
    
    gsr_grip_addon:                   # Aftermarket accessory
      capable: bool                   # Can support GSR addon
      interface: enum                 # usb_passthrough | wireless
      
  # Tier Eligibility
  tier_eligibility:
    standard: bool                    # Always true if PITL L0-L5 available
    attested: bool                    # Requires L6 full + PHCI certified
    
  attested_requirements:
    - L6_full                         # Adaptive trigger resistance measurement
    - transport_1000hz                  # USB or equivalent
    - phci_certified                  # Passed certification
    - N_calibration_min: 50            # Minimum calibration sessions
    
  # Calibration Configuration
  calibration:
    battery_types:                    # Available battery/usage types
      - touchpad
      - trigger
      - gameplay
      - resting_grip
    
    feature_dimensions: int             # Number of L4 biometric features
    feature_mask: [int]                 # Boolean mask for available features
    
    l4_notes: string                  # Special calibration considerations
    l6_notes: string                  # L6 limitations or adaptations
    
  # PHCI Certification
  phci:
    certified: bool
    certification_date: date
    certification_version: string
    
  # HID Report Layout Offsets
  hid_offsets:                        # Byte offsets in HID report
    lx: int                           # Left stick X
    ly: int                           # Left stick Y
    rx: int                           # Right stick X
    ry: int                           # Right stick Y
    l2: int                           # L2 trigger
    r2: int                           # R2 trigger
    gyro_x: int                       # Gyro X (int16 LE)
    gyro_y: int                       # Gyro Y (int16 LE)
    gyro_z: int                       # Gyro Z (int16 LE)
    accel_x: int                      # Accel X (int16 LE)
    accel_y: int                      # Accel Y (int16 LE)
    accel_z: int                      # Accel Z (int16 LE)
    touch_active: int                 # Touchpad active flag
    touch_x: int                      # Touch X position
    touch_y: int                      # Touch Y position
    buttons: [int]                    # Button byte offsets
```

---

## 3. Canonical Controller Profiles

### 3.1 Sony DualShock Edge (Primary Certified Device)

```yaml
id: sony_dualshock_edge_v1
display_name: "Sony DualShock Edge (CFI-ZCP1)"
manufacturer: Sony
model: CFI-ZCP1

usb:
  vid: 0x054C
  pid: 0x0DF2
  interface: 3
  report_size: 64
  report_layout: sony_dualsense_edge

ble:
  service_uuid: "00001124-0000-1000-8000-00805f9b34fb"
  report_char_uuid: "00002a4d-0000-1000-8000-00805f9b34fb"
  name_prefix: "DualSense Edge"

transport:
  usb_hz: 1000
  ble_hz: 250

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: full
  L5: true
  L6: full

features:
  touchpad:
    present: true
    size: [1920, 1080]
    multi_touch: true
    pressure: false
  
  triggers:
    type: adaptive
    l2_adaptive: true
    r2_adaptive: true
    mode_count: 3
  
  gyroscope:
    present: true
    axes: 3
    precision: 16
    range_dps: 2000
    sample_rate_hz: 1000
  
  accelerometer:
    present: true
    axes: 3
    precision: 16
    range_g: 16
    sample_rate_hz: 1000
  
  gsr_grip_addon:
    capable: true
    interface: usb_passthrough

tier_eligibility:
  standard: true
  attested: true

attested_requirements:
  - L6_full
  - transport_1000hz
  - phci_certified
  - N_calibration_min: 50

calibration:
  battery_types: [touchpad, trigger, gameplay, resting_grip]
  feature_dimensions: 13
  feature_mask: [1,1,1,1,1,1,1,1,1,1,1,1,1]  # All 13 features
  l4_notes: "Full biometric suite (touchpad + gyro + accel)"
  l6_notes: "Full adaptive trigger resistance measurement"

phci:
  certified: true
  certification_date: "2026-01-15"
  certification_version: "PHCI-2026.1"
```

### 3.2 Microsoft Xbox Series X

```yaml
id: microsoft_xbox_series_x
display_name: "Microsoft Xbox Series X Controller"
manufacturer: Microsoft
model: Series X

usb:
  vid: 0x045E
  pid: 0x0B12
  interface: 0
  report_size: 18
  report_layout: microsoft_xinput

ble:
  service_uuid: "00001124-0000-1000-8000-00805f9b34fb"
  report_char_uuid: "00002a4d-0000-1000-8000-00805f9b34fb"
  name_prefix: "Xbox Wireless Controller"

transport:
  usb_hz: 1000
  ble_hz: 250
  proprietary:
    - name: xbox_wireless
      hz: 1000
      latency_ms: 2.0

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: partial       # Gyro only (no touchpad)
  L5: true
  L6: none         # No adaptive triggers

features:
  touchpad:
    present: false
  
  triggers:
    type: impulse
    l2_adaptive: false
    r2_adaptive: false
    l2_impulse: true    # Haptic feedback only
    r2_impulse: true
    mode_count: 0
  
  gyroscope:
    present: true       # Elite 2 only; standard has no gyro
    axes: 3
    precision: 16
    range_dps: 2000
    sample_rate_hz: 1000
  
  accelerometer:
    present: true       # Elite 2 only
    axes: 3
    precision: 16
    range_g: 16
    sample_rate_hz: 1000
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false     # No L6 adaptive triggers

attested_requirements: []  # Not eligible

calibration:
  battery_types: [gameplay, trigger]
  feature_dimensions: 7
  feature_mask: [0,0,1,1,0,1,1,0,0,0,1,1,0]  # Gyro/accel only
  l4_notes: "Gyro-only L4 (no touchpad features). Elite 2 required for gyro."
  l6_notes: "L6 DISABLED - no adaptive trigger resistance measurement"

phci:
  certified: false
  certification_date: null
  certification_version: null

notes: "Standard tier only. Attested requires adaptive triggers (L6)."
```

### 3.3 Nintendo Switch Pro Controller

```yaml
id: nintendo_switch_pro
display_name: "Nintendo Switch Pro Controller"
manufacturer: Nintendo
model: HAC-013

usb:
  vid: 0x057E
  pid: 0x2009
  interface: 0
  report_size: 64
  report_layout: nintendo_switch_pro

ble:
  service_uuid: "00001124-0000-1000-8000-00805f9b34fb"
  report_char_uuid: "00002a4d-0000-1000-8000-00805f9b34fb"
  name_prefix: "Pro Controller"

transport:
  usb_hz: 1000
  ble_hz: 250

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: partial       # Gyro only (excellent quality)
  L5: true
  L6: none         # No adaptive triggers

features:
  touchpad:
    present: false
  
  triggers:
    type: standard
    l2_adaptive: false
    r2_adaptive: false
    l2_impulse: false
    r2_impulse: false
    mode_count: 0
  
  hd_rumble:        # Nintendo's haptic system
    present: true
    l2: true
    r2: true
    frequency_range: [0, 1250]
  
  gyroscope:
    present: true
    axes: 3
    precision: 16
    range_dps: 2000
    sample_rate_hz: 1000
    notes: "Best-in-class gyro (industry standard)"
  
  accelerometer:
    present: true
    axes: 3
    precision: 16
    range_g: 16
    sample_rate_hz: 1000
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false     # No L6 adaptive triggers

calibration:
  battery_types: [gameplay]
  feature_dimensions: 6
  feature_mask: [0,0,1,1,0,0,1,1,0,0,1,1,0]
  l4_notes: "Best-in-class gyro, no touchpad. Excellent for gyro-only L4."
  l6_notes: "L6 DISABLED - HD rumble not equivalent to adaptive triggers"

phci:
  certified: false

notes: "Standard tier only. Exceptional gyro quality for L4."
```

### 3.4 Sony DualShock 4 (Legacy)

```yaml
id: sony_dualshock_4
display_name: "Sony DualShock 4"
manufacturer: Sony
model: CUH-ZCT2

usb:
  vid: 0x054C
  pid: 0x05C4
  interface: 0
  report_size: 64
  report_layout: sony_dualshock_4

ble:
  service_uuid: "00001124-0000-1000-8000-00805f9b34fb"
  report_char_uuid: "00002a4d-0000-1000-8000-00805f9b34fb"
  name_prefix: "Wireless Controller"

transport:
  usb_hz: 1000
  ble_hz: 250

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: full            # Touchpad available
  L5: true
  L6: partial         # Trigger latency only, no resistance

features:
  touchpad:
    present: true
    size: [1200, 800]  # Smaller than Edge
    multi_touch: true
    pressure: false
  
  triggers:
    type: standard
    l2_adaptive: false
    r2_adaptive: false
    mode_count: 0
  
  lightbar:
    present: true
    rgb: true
    player_id: true
  
  gyroscope:
    present: true
    axes: 3
    precision: 16
    range_dps: 2000
    sample_rate_hz: 1000
  
  accelerometer:
    present: true
    axes: 3
    precision: 16
    range_g: 16
    sample_rate_hz: 1000
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false     # No L6 adaptive triggers

calibration:
  battery_types: [touchpad, gameplay, trigger]
  feature_dimensions: 13
  feature_mask: [1,1,1,1,1,0,1,1,1,1,1,1,1]  # No adaptive trigger features
  l4_notes: "Touchpad available but smaller surface area than Edge"
  l6_notes: "L6 PARTIAL - trigger latency only (no resistance measurement)"

phci:
  certified: true
  notes: "Certified for Standard tier only. Attested requires adaptive triggers."
```

---

### 3.5 Third-Party Controller Integration (Phase 137 Extension)

Third-party controllers (Scuf, Razer, Battle Beaver, Cinch) represent 25-30% of the competitive gaming market. These controllers are integrated through **PHCI Tier 2 certification** (Standard tier only).

#### PHCI Tier 2 Certification Requirements

1. **Hardware Submission**: 3 controller units for testing
2. **HID Compliance**: Standard USB HID or XInput protocol
3. **Feature Documentation**: Complete capability matrix
4. **N≥30 Calibration**: Minimum sessions for threshold derivation
5. **Standard Tier Only**: No adaptive triggers = Attested tier blocked

#### Common Third-Party Limitations

| Limitation | Impact | Tier Effect |
|------------|--------|-------------|
| Hair triggers | No resistance measurement | L6 unavailable |
| Paddle buttons | Extra inputs, no PITL value | No impact |
| Tension modules | Mechanical modification | L4 behavioral only |
| Wireless dongle | Proprietary protocol | Transport validation needed |
| No gyroscope | Xbox-based mods | L4 partial or none |

### 3.6 Scuf Instinct Pro (Xbox Mod)

```yaml
id: scuf_instinct_pro
display_name: "Scuf Instinct Pro"
manufacturer: "Scuf Gaming (Corsair)"
model: "Instinct Pro"
controller_type: "scuf_instinct_pro"

usb:
  vid: 0x045E  # Reports as Xbox controller
  pid: 0x0B13  # Modified Xbox PID
  interface: 0
  report_size: 18
  report_layout: "microsoft_xinput_scuf"

ble: null  # USB only via dongle

transport:
  usb_hz: 1000
  proprietary:
    - name: "scuf_wireless_dongle"
      hz: 1000
      latency_ms: 2.5
      notes: "Requires validation"

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: "partial"  # If Elite 2 base has gyro
  L5: true
  L6: "none"     # Hair triggers = no resistance

capabilities:
  touchpad:
    present: false
  
  triggers:
    type: "hair_trigger"  # Mechanical stop, no resistance
    l2_adaptive: false
    r2_adaptive: false
    hair_trigger: true    # Instant actuation
    adjustable_stops: true
  
  paddles:
    present: true
    count: 4
    programmable: true
    mapping: "digital"    # Maps to face buttons
  
  gyroscope:
    present: false  # Xbox base typically
  
  accelerometer:
    present: false
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false  # Hair triggers block L6

attested_requirements: []  # Not eligible

calibration:
  battery_types: ["gameplay", "trigger"]
  feature_dimensions: 5
  feature_mask: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1]
  l4_notes: "Behavioral L4 only (no biometric). Hair trigger timing patterns."
  l6_notes: "L6 DISABLED - hair triggers prevent resistance measurement"

phci:
  certified: false
  target_tier: 2  # Standard only

notes: "Standard tier. Popular in CoD/Fortnite. Hair triggers = fast but no L6."
```

### 3.7 Razer Wolverine V2 Chroma

```yaml
id: razer_wolverine_v2_chroma
display_name: "Razer Wolverine V2 Chroma"
manufacturer: "Razer"
model: "Wolverine V2 Chroma"
controller_type: "razer_wolverine_v2"

usb:
  vid: 0x1532  # Razer VID
  pid: 0x0A29
  interface: 0
  report_size: 64
  report_layout: "razer_wolverine"

ble: null  # USB only

transport:
  usb_hz: 1000

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: "none"     # No gyro on Xbox controllers
  L5: true
  L6: "none"     # Mecha-tactile != adaptive

capabilities:
  touchpad:
    present: false
  
  triggers:
    type: "mecha_tactile"  # Razer switch, not adaptive
    l2_adaptive: false
    r2_adaptive: false
    mecha_tactile: true
    actuation_point: 1.0  # mm
  
  paddles:
    present: true
    count: 6
    programmable: true
    rgb: true
  
  rgb:
    present: true
    chroma: true
    zones: ["paddles", "triggers", "logo"]
  
  gyroscope:
    present: false
  
  accelerometer:
    present: false
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false

calibration:
  battery_types: ["gameplay"]
  feature_dimensions: 2
  feature_mask: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0]
  l4_notes: "L4 DISABLED - no gyro/accel. L3 behavioral only."
  l6_notes: "L6 DISABLED - mecha-tactile not resistance measurement"

phci:
  certified: false
  target_tier: 2

notes: "Standard tier. L3-only anti-cheat (behavioral patterns). No biometric."
```

### 3.8 Battle Beaver Performance (DualShock 4 Mod)

```yaml
id: battle_beaver_performance
display_name: "Battle Beaver Performance"
manufacturer: "Battle Beaver Customs"
model: "Performance DualShock 4"
controller_type: "battle_beaver_ds4"

usb:
  vid: 0x054C  # Reports as Sony
  pid: 0x05C4
  interface: 0
  report_size: 64
  report_layout: "sony_dualshock_4_bb"
  notes: "Modified DS4 with custom tension"

ble:
  service_uuid: "00001124-0000-1000-8000-00805f9b34fb"
  report_char_uuid: "00002a4d-0000-1000-8000-00805f9b34fb"
  name_prefix: "Wireless Controller"
  notes: "May have connection issues with tension mods"

transport:
  usb_hz: 1000
  ble_hz: 250

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: "partial"  # Tension affects touchpad precision
  L5: true
  L6: "partial"  # Tension = different resistance curve

capabilities:
  touchpad:
    present: true
    size: [1200, 800]
    multi_touch: true
    pressure: false
    tension_mod: true  # Adjustable stick tension
    notes: "Higher tension affects spatial entropy"
  
  triggers:
    type: "smart_trigger"  # Reduced travel
    l2_adaptive: false
    r2_adaptive: false
    smart_trigger: true   # 50% travel reduction
    stop_adjustable: true
  
  sticks:
    tension_adjustable: true
    default_tension: "medium"  # 80g
    range: [40, 120]  # grams
  
  back_buttons:
    present: true
    count: 2
    digital: true
  
  gyroscope:
    present: true
    axes: 3
    precision: 16
    notes: "Functional but tension affects precision"
  
  accelerometer:
    present: true
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false  # Smart triggers != adaptive

attested_requirements: []  # Not eligible

calibration:
  battery_types: ["touchpad", "gameplay", "trigger"]
  feature_dimensions: 9
  feature_mask: [1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 0]
  l4_notes: "Reduced L4 confidence due to tension variability. Touchpad variance higher."
  l6_notes: "L6 PARTIAL - smart trigger latency only"

phci:
  certified: false
  target_tier: 2

notes: "Standard tier. Tension mods introduce variability. Great for competitive but limited L4."
```

### 3.9 Cinch Gaming Controller (Xbox Elite Base)

```yaml
id: cinch_gaming_elite
display_name: "Cinch Gaming Elite"
manufacturer: "Cinch Gaming"
model: "Elite Series 2 Mod"
controller_type: "cinch_elite"

usb:
  vid: 0x045E
  pid: 0x0B22  # Elite 2 PID
  interface: 0
  report_size: 33  # Elite 2 larger report
  report_layout: "microsoft_elite_cinch"

ble: null

transport:
  usb_hz: 1000
  proprietary:
    - name: "xbox_wireless"
      hz: 1000
      latency_ms: 2.0

pitl_layers:
  L0: true
  L1: true
  L2: true
  L3: true
  L4: "partial"  # Elite 2 has gyro
  L5: true
  L6: "none"     # Mods break resistance sensing

capabilities:
  touchpad:
    present: false
  
  triggers:
    type: "digital_trigger"  # Instant switch
    l2_adaptive: false
    r2_adaptive: false
    digital: true
    travel: "0.1mm"  # Effectively zero
  
  paddles:
    present: true
    count: 4
    elite_style: true  # Metal paddles
  
  sticks:
    swappable: true
    tension: "adjustable"
    profiles: 3  # Onboard profiles
  
  gyroscope:
    present: true  # Elite 2 gyro
    axes: 3
    precision: 16
  
  accelerometer:
    present: true
  
  gsr_grip_addon:
    capable: false

tier_eligibility:
  standard: true
  attested: false  # Digital triggers block L6

attested_requirements: []  # Not eligible

calibration:
  battery_types: ["gameplay", "trigger"]
  feature_dimensions: 7
  feature_mask: [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1]
  l4_notes: "Elite 2 gyro available. Digital trigger timing is unique signature."
  l6_notes: "L6 DISABLED - digital triggers have no resistance curve"

phci:
  certified: false
  target_tier: 2

notes: "Standard tier. Digital triggers are fastest but no L6. Popular in fighting games."
```

---

## 4. PITL Layer Availability by Controller

| Controller | L0 | L1 | L2 | L3 | L4 | L5 | L6 | Standard | Attested |
|------------|----|----|----|----|----|----|----|----------|----------|
| **DualShock Edge** | ✅ | ✅ | ✅ | ✅ | Full | ✅ | Full | ✅ | ✅ |
| **Xbox Series X** | ✅ | ✅ | ✅ | ✅ | Partial | ✅ | ❌ | ✅ | ❌ |
| **Switch Pro** | ✅ | ✅ | ✅ | ✅ | Partial | ✅ | ❌ | ✅ | ❌ |
| **DualShock 4** | ✅ | ✅ | ✅ | ✅ | Full | ✅ | Partial | ✅ | ❌ |
| **Scuf Instinct Pro** | ✅ | ✅ | ✅ | ✅ | Partial* | ✅ | ❌ | ✅ | ❌ |
| **Razer Wolverine** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| **Battle Beaver** | ✅ | ✅ | ✅ | ✅ | Partial* | ✅ | Partial | ✅ | ❌ |
| **Cinch Elite** | ✅ | ✅ | ✅ | ✅ | Partial* | ✅ | ❌ | ✅ | ❌ |

**Notes**: 
- *Scuf/Cinch partial L4 = Elite 2 gyro only (if available)
- *Battle Beaver partial L4 = touchpad with tension variance
- Razer has no L4 (no gyro/accel on Xbox base)

### L4 Partial Definition

**Full L4** (13 features):
- Gyroscope: std_x, std_y, std_z, correlation_xy
- Accelerometer: magnitude_spectral_entropy, std_xyz
- Touchpad: spatial_entropy, position_variance_x, position_variance_y
- Triggers: adaptive_resistance_L2, adaptive_resistance_R2
- Temporal: press_timing_jitter

**Partial L4** (6-7 features, gyro-only):
- Gyroscope: std_x, std_y, std_z, correlation_xy
- Accelerometer: magnitude_spectral_entropy, std_xyz
- Missing: Touchpad features, trigger resistance features

**Confidence Adjustment**:
- Full L4: 1.0 weight
- Partial L4: 0.6 weight (reduced confidence due to missing features)
- L4 unavailable: 0.0 weight (rely on L3 behavioral + L5 temporal)

### L6 Partial Definition

**Full L6**:
- Active challenge-response with adaptive trigger resistance measurement
- Measures physical resistance to trigger depression
- Software injection cannot simulate physical resistance

**Partial L6** (DualShock 4):
- Trigger latency measurement only
- Measures time from HID report to mechanical actuation
- Less robust than resistance measurement

**L6 Unavailable** (Xbox, Switch):
- No active challenge capability
- Tier eligibility: Standard only

---

## 5. Transport Requirements by Tier

### Attested Tier (1000Hz Required)

| Transport | Latency | Jitter | Polling | Certified For |
|-----------|---------|--------|---------|---------------|
| USB 1000Hz | < 2ms | < 0.5ms | 1000Hz | All controllers |
| Xbox Wireless | ~2ms | < 0.5ms | 1000Hz | Xbox only |
| DualSense Wireless | < 2ms | < 0.5ms | 1000Hz | DualShock only |

**Requirements**:
- p99 latency < 2ms
- Jitter (std dev) < 0.5ms
- Packet loss = 0%
- Measured over 1000 samples

### Standard Tier (250Hz Acceptable)

| Transport | Latency | Jitter | Polling | Notes |
|-----------|---------|--------|---------|-------|
| USB 1000Hz | < 2ms | < 0.5ms | 1000Hz | Preferred |
| BT 250Hz | < 5ms | < 1ms | 250Hz | BT-specific thresholds required |
| Xbox Wireless | ~2ms | < 0.5ms | 1000Hz | Xbox only |

**Requirements**:
- p99 latency < 5ms
- Jitter (std dev) < 1ms
- Packet loss < 0.1%

**BT Thresholds**:
- Separate calibration track for BT transport
- 250Hz ≠ 1000Hz thresholds (structural difference)
- N≥50 BT sessions required per controller

---

## 6. Calibration Composite Keys

### Key Format

```
{controller_profile_id}_{battery_type}_{transport_type}
```

**Examples**:
- `sony_dualshock_edge_v1_touchpad_usb_1000hz`
- `microsoft_xbox_series_x_gameplay_usb_1000hz`
- `nintendo_switch_pro_gameplay_ble_250hz`
- `sony_dualshock_edge_v1_gameplay_ble_250hz`

### Threshold Track Schema

```sql
CREATE TABLE l4_threshold_tracks (
    id INTEGER PRIMARY KEY,
    composite_key TEXT UNIQUE NOT NULL,
    controller_profile_id TEXT NOT NULL,
    battery_type TEXT NOT NULL,
    transport_type TEXT NOT NULL,
    anomaly_threshold REAL NOT NULL,
    continuity_threshold REAL NOT NULL,
    feature_mask TEXT NOT NULL,  -- JSON array [0,1,1,0...]
    feature_count INTEGER NOT NULL,
    n_calibration_sessions INTEGER NOT NULL,
    calibrated_at TIMESTAMP NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (controller_profile_id) REFERENCES controller_profiles(id)
);
```

### Calibration Procedure

1. **Collect Sessions**: N≥50 per composite key
2. **Extract Features**: Apply feature mask for controller type
3. **Compute Covariance**: Controller-specific (not generic)
4. **Derive Thresholds**: Anomaly (upper), Continuity (lower)
5. **Enforce min()**: new = min(old, proposed) — only tighten
6. **Store Track**: Insert with composite key
7. **Activate**: Set active=TRUE, deactivate old track

---

## 7. GSR Grip Addon Integration

### Hardware Specifications

**VAPI GSR Grip Module**:
- **Form Factor**: Controller grip attachment
- **Interface**: USB-C passthrough or BLE
- **Sensors**: Galvanic skin resistance (2 electrodes per grip)
- **Sampling**: 100 Hz (slower than controller 1000Hz)
- **Resolution**: 16-bit resistance measurement
- **Range**: 1kΩ - 10MΩ (typical human skin)

### Integration Protocol

```python
class GSRGripAddon:
    """Aftermarket GSR accessory for controller"""
    
    def __init__(self, parent_controller_id: str):
        self.parent_controller = parent_controller_id
        self.usb_vid = 0xVAPI  # VAPI vendor ID
        self.usb_pid = 0xGSR   # GSR product ID
        self.sample_rate_hz = 100
        
    def detect(self) -> bool:
        """Check for GSR device connected via USB passthrough"""
        # Enumerate USB devices for VAPI GSR VID/PID
        # Check parent controller connection
        return detected
    
    def read_resistance(self) -> Tuple[float, float]:
        """Read left and right grip resistance"""
        # Returns (left_ohms, right_ohms)
        pass
    
    def compute_arousal_proxy(self, window_seconds: int = 5) -> float:
        """Compute stress/arousal proxy from GSR variance"""
        # Higher variance = higher arousal/stress
        # Used for L4 enhancement (2 additional features)
        pass
```

### L4 Enhancement

**GSR Features** (2 additional to base 13):
- `gsr_resistance_variance`: Variance in skin resistance
- `gsr_cross_grip_correlation`: Correlation between left/right

**Total Features with GSR**: 15 (Edge) / 9 (Xbox with GSR)

**Calibration**: N≥20 sessions with GSR addon (GSR_ENABLED flag)

---

## 8. PHCI Certification Program

### Certification Tiers

**PHCI Tier 1 (Attested)**:
- L0-L6 FULL capability
- Adaptive triggers mandatory
- 1000Hz transport required
- N≥50 calibration sessions
- On-chain attestation via VAPISwarmOperatorGate

**PHCI Tier 2 (Standard)**:
- L0-L5 minimum
- L6 optional
- 250Hz transport acceptable
- N≥30 calibration sessions
- Self-registered (no on-chain gate)

### Certification Process

1. **Manufacturer Submission**:
   - Submit controller samples (3 units)
   - Provide HID report descriptors
   - Document feature capabilities

2. **VAPI Testing**:
   - N≥50 calibration sessions
   - Separation ratio analysis
   - PITL layer validation
   - Tournament scenario testing

3. **Certification Decision**:
   - PHCI Tier assignment (1 or 2)
   - Profile added to canonical registry
   - On-chain attestation (Tier 1 only)
   - Certification ID issued

4. **Registry Update**:
   - Profile published to controller_profiles.yaml
   - VAPI_CONTEXT.md updated
   - Agent #17 auto-detects certified devices

---

## 9. Implementation Roadmap

### Phase 136: Agent Core (Weeks 1-4)

**Week 1**: Agent foundation + DeviceProfileRegistry extension
- `controller_hardware_intelligence_agent.py`
- Capability matrix dataclasses
- USB/BT detection logic

**Week 2**: PITL mapping + Tier eligibility
- `get_available_pitl_layers()`
- `get_tier_eligibility()`
- Weight adjustment for SessionAdjudicator

**Week 3**: Transport negotiation + Calibration integration
- `negotiate_transport()`
- Composite key threshold tracks
- CalibrationIntelligenceAgent delegation

**Week 4**: Testing + Documentation
- Unit tests for 4 controller profiles
- Integration tests
- VAPI_CONTROLLER_INTELLIGENCE.md

### Phase 137: Multi-Controller Calibration (Weeks 5-8)

**Goal**: N≥50 sessions for Xbox, Switch, DS4

**Hardware**: 3 units per controller type (9 total)

**Deliverables**:
- Xbox Series X: 50 sessions
- Switch Pro: 50 sessions
- DS4: 50 dedicated sessions

### Phase 138: PHCI Certification API (Weeks 9-12)

**Deliverables**:
- Partner submission portal
- Automated calibration pipeline
- Certification attestation on-chain
- Public registry API
- **Third-party manufacturer workflow**:
  - Scuf/Corsair, Razer, Battle Beaver, Cinch integration paths
  - PHCI Tier 2 (Standard) certification track
  - Self-service profile submission
  - N≥30 reduced calibration requirement
  - Quarterly compliance audits

---

## 10. References

### Related VAPI-WORKFLOW.v2 Files

- **VAPI_AGENTS.md**: Agent #17 full documentation
- **VAPI_SKILLS.md**: Skills 8, 9, 10 (Controller skills)
- **VAPI_WHAT_IF.md**: W2-005 Multi-Controller Ecosystem
- **VAPI_CONTEXT.md**: Controller registry status, State flags
- **VAPI_INVARIANTS.md**: Tier invariants, Controller-agnostic PoAC
- **VAPI_MEMORY.md**: Phase 136 session outcomes
- **VAPI_CORPUS.md**: Controller diversity metrics

### Bridge Code Files

- `bridge/vapi_bridge/device_registry.py` - DeviceProfileRegistry
- `bridge/vapi_bridge/agent_supervisor.py` - Agent health monitoring
- `bridge/vapi_bridge/session_adjudicator.py` - PITL weight adjustment
- `bridge/vapi_bridge/calibration_intelligence_agent.py` - Threshold tracks
- `bridge/vapi_bridge/transports/bluetooth.py` - BT 250Hz transport
- `bridge/vapi_bridge/gsr_registry_agent.py` - GSR grip addon

---

**Document Version**: 1.1 (Phase 149)  
**Last Updated**: 2026-04-03  
**Controller Profiles**: 7 defined (Edge, Xbox, Switch, DS4, DualSense Standard, Scuf, Razer) — all DESIGN ONLY  
**Agent**: #17 ControllerHardwareIntelligenceAgent — **DESIGN ONLY, no code written as of Phase 149**  
**Target**: Phase 150+ implementation (deferred; touchpad_corners separation breakthrough achieved without multi-controller support)  
**Key Phase 143 Finding**: Touchpad spatial entropy (touchpad_spatial_entropy) is the #1 inter-player discriminator → PHCI certification MUST require touchpad-capable hardware (DualShock Edge class or equivalent with 1000 Hz touchpad). Controllers without touchpad (Xbox Series X, Switch Pro) are LIMITED to Standard tier and cannot achieve Attested certification.  
**Separation Breakthrough Note**: touchpad_corners N=11, 3-player → ratio=1.261 (Phase 143). PHCI certification gate should require N≥30 touchpad_corners sessions for Attested tier controllers.  
