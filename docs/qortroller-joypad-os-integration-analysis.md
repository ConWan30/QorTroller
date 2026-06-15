# QorTroller × joypad-os — Integration Analysis

**Date:** 2026-06-15  
**Scope:** Meticulous analysis of `bridge/firmware/joypad-os` (Apache-2.0 fork, commit `8fa2e144`)
as the ESP32-S3 firmware chassis for the QorTroller reference dev-kit.  
**Status discipline:** Claims graded VERIFIED / ASPIRATIONAL / UNRESOLVED — nothing promoted
to LIVE without measurement.

---

## §0 Honesty stamp

joypad-os is a real, working firmware platform. The fork adds it as a git submodule at
`bridge/firmware/joypad-os`. This document grades what it actually provides versus what
would need to be built on top. Every "ASPIRATIONAL" below is buildable, not fictional —
but it is **not inherited from the upstream codebase.**

---

## §1 What joypad-os actually is (VERIFIED)

From the upstream repo and the forked tree at `8fa2e144`:

| Verified fact | Evidence |
|---|---|
| Apache-2.0 license | `LICENSE` file; fully permissive, commercial-friendly |
| Multi-target MCU platform | `src/` trees compile for RP2040, ESP32-S3, nRF52840 |
| Real ESP32-S3 / ESP-IDF tree | `esp/main/` with IDF `CMakeLists.txt`, `idf_component.yml`, `main.c` |
| ESP32-S3 peripheral drivers verified | `battery_esp32.c`, `btstack_hal_esp32.c`, `button_esp32.c`, `display_i2c_esp32.c`, `flash_esp32.c`, `ws2812_esp32.c`, `max3421_host_esp32.c`, `platform_gpio_esp32.c` |
| Board configs present | `feather_esp32s3`, `xiao_esp32s3` (both QorTroller-compatible form factors) |
| BTstack + TinyUSB integration | `src/bt/` + `src/usb/` (Bluetooth Classic + BLE + USB HID/XInput) |
| I2C peer transport | `src/i2c_peer/` — direct hook for ATECC608B (I2C, BOM C2) |
| UART peer transport | `src/uart_peer/` — direct hook for QM35825 presence flag (UART interface) |
| WiFi OTA path | `src/wifi/` — OTA firmware updates without USB |
| Input normalization layer | `src/pad/pad_input.c` + `src/core/input_event.h` (see §3) |
| MAX3421E USB host | `esp/main/max3421_host_esp32.c` — USB host for reading external controllers |

**E1: ESP32-S3 firmware baseline** → **VERIFIED.** The ESP-IDF tree compiles for the exact
MCU target in BOM C1 (Espressif ESP32-S3). This is the board QorTroller needs and it works
upstream.

---

## §2 What is ASPIRATIONAL (not inherited)

The commit notes accompanying the fork reference three capabilities that need to be built:

**E2: Thread-C / core-locked 1 kHz biometric partition → ASPIRATIONAL**

joypad-os processes inputs at whatever cadence the USB/BT poll or GPIO scan dictates.
It does **not** have a dedicated core-pinned 1 kHz loop for the biometric sense path.
The QorTroller requirement:
- ESP32-S3 has two cores (PRO_CPU / APP_CPU)
- Core 1 runs the FreeRTOS event loop (BT + WiFi + app logic)
- **QorTroller needs Core 0 pinned exclusively to the 1 kHz ADC/IMU sense loop** (the
  current bridge captures at 1002 Hz via hidapi on Windows; the native dev-kit must
  match this cadence for PoAC cycle integrity)
- joypad-os uses a single-core FreeRTOS model for ESP32-S3; adding a core-pinned
  high-rate task requires a **new FreeRTOS task** with `xTaskCreatePinnedToCore(..., 0)`
  and its own timer ISR or `vTaskDelayUntil` at 1 ms cadence

**Build cost:** ~200–400 lines of new C in a `qortroller_sense_task.c`. Medium complexity.
No upstream change needed — joypad-os's FreeRTOS abstraction doesn't conflict.

**E3: PV-CI firmware instrumentation → ASPIRATIONAL**

joypad-os has no concept of QorTroller's invariant gate (`vapi_invariant_gate.py`),
the 228-byte PoAC wire format, or the FROZEN-v1 family. Adding CI instrumentation means:
- A Python test runner (`scripts/test_firmware_invariants.py`) that compiles the ESP-IDF
  tree with `idf.py build`, inspects the `.elf` for symbol presence (e.g.,
  `qortroller_sense_task`, `poac_build_record`), and asserts the PoAC struct size == 228
- Integration into `.github/workflows/ci.yml` alongside the existing bridge + SDK gates
- New PV-CI entries for the firmware build target

**Build cost:** 100–200 lines of Python + CI YAML. Low-medium complexity.

---

## §3 The critical architectural tension: raw vs. normalized input

**This is the most important finding in this document.**

joypad-os's job is to normalize controller inputs. Its `src/core/input_event.h` defines:

```c
typedef struct input_event_t {
    input_device_type_t device_type;
    input_transport_t   transport;
    uint32_t            buttons;        // bitmask — already debounced
    int16_t             analog[INPUT_AXIS_COUNT]; // normalized to [-32767, 32767]
    // ...
} input_event_t;
```

`src/pad/pad_input.c` reads raw ADC values and **normalizes them** before emitting
`input_event_t` structs. Debounce (`pad_prev_buttons`), D-pad mode mapping, and stick
centering all happen here.

**QorTroller's biometric fidelity depends on PRE-normalization raw values:**

| Signal | joypad-os normalized | QorTroller needs RAW | Why |
|---|---|---|---|
| Trigger analog (L2/R2) | 0–255 or –32767–32767 | Raw ADC count + onset timing | `trigger_onset_velocity` + force-curve L4 feature |
| Stick axes | Normalized to ±32767 | Raw ADC + tremor variance | `micro_tremor_accel_variance`, `stick_autocorr_lag1/5` |
| IMU | Via driver abstraction | Raw LSB values | `accel_magnitude_spectral_entropy`, tremor peak Hz |
| Button timestamps | Debounced bitmask | Raw edge time (ns precision) | `press_timing_jitter_variance` |

**If QorTroller only consumes the normalized `input_event_t`, it loses the biometric
signal that makes the protocol's L4 separation ratio (1.199) meaningful.**

### The tap-point solution

joypad-os's architecture naturally accommodates a raw-capture tap *before* the
normalization layer. The pattern:

```
GPIO / ADC read  →  [RAW HOOK]  →  normalization  →  input_event_t  →  USB/BT output
                         ↓
                   qortroller_raw_capture_t
                         ↓
                   PoAC record builder (228 bytes)
                         ↓
                   ATECC608B sign (I2C)  →  BLE/WiFi  →  bridge
```

Concrete location: `src/pad/pad_input.c`, in the ADC sample loop (before the
`analog[axis] = normalized_value` write). A single callback function pointer
(`void (*qortroller_raw_hook)(qortroller_raw_sample_t*)`) registered at startup
captures the raw ADC count + timestamp without touching the normalization path.

**This is additive — it does not change joypad-os's output behavior at all.**
joypad-os continues to present a normal HID device to the PS5/host. QorTroller
taps the data stream in parallel.

---

## §4 Layer mapping: joypad-os → QorTroller BOM

| joypad-os component | Maps to QorTroller role | Status |
|---|---|---|
| ESP32-S3 ESP-IDF chassis | BOM C1 (MCU) | **VERIFIED — direct target** |
| `esp/main/display_i2c_esp32.c` | I2C bus (shared with ATECC608B) | VERIFIED — I2C bus exists |
| `src/i2c_peer/` | BOM C2 ATECC608B path | **ASPIRATIONAL** — needs PoAC signing integration |
| `src/uart_peer/` | QM35825 UWB presence (UART, BOM A6) | **ASPIRATIONAL** — needs presence-flag protocol |
| `src/wifi/` | BLE/WiFi OTA for bridge telemetry | VERIFIED — WiFi stack present |
| `esp/main/btstack_hal_esp32.c` | BT Classic for PS5 passthrough | VERIFIED — BTstack present |
| `esp/main/max3421_host_esp32.c` | USB host (read DualSense Edge raw HID) | VERIFIED — USB host for full HID access |
| `src/pad/pad_input.c` ADC loop | **RAW HOOK TAP POINT** for biometric capture | **BUILD REQUIRED** (§3) |
| `src/core/input_event.h` | Normalized output — passthrough to host | VERIFIED (but QorTroller bypasses this for biometrics) |

---

## §5 Synergy assessment: where joypad-os genuinely helps QorTroller

**High-value contributions (saves weeks of work):**

1. **ESP-IDF build system already configured.** CMakeLists, component.yml, IDF version
   pins, and board configs exist. Starting from scratch on ESP-IDF for ESP32-S3 is
   non-trivial; joypad-os eliminates that.

2. **MAX3421E USB host driver (`max3421_host_esp32.c`).** Reading raw USB HID from a
   DualSense Edge on ESP32-S3 requires a USB host IC (the ESP32-S3 has USB OTG *device*
   mode, not host). The MAX3421E is a standard external USB host IC. joypad-os already
   has the SPI driver for it — **this saves the highest-complexity firmware driver** in
   the stack.

3. **I2C bus infrastructure (`display_i2c_esp32.c`, `src/i2c_peer/`).** The ATECC608B
   (BOM C2) is an I2C device. The bus is wired and working in joypad-os for displays
   and I2C peers. QorTroller can add the ATECC608B as an I2C peer on the same bus.

4. **UART peer (`src/uart_peer/`).** The QM35825 (BOM A6) exposes SPI + UART. The
   UART peer infrastructure maps directly to reading the QM35825 presence flag —
   presence output over UART → ESP32 UART peripheral → presence field in PoAC.

5. **BTstack + WiFi for bridge telemetry.** The BLE/WiFi stack is production-grade and
   already targets ESP32-S3. QorTroller's bridge communication (PoAC record shipment
   to the Python asyncio bridge) can ride this channel without building a BT stack.

**Medium-value contributions:**

6. **WS2812 RGB LED driver.** Useful for protocol status feedback (green = NOMINAL,
   red = DISCONNECTED, amber = DEGRADED) — maps cleanly to CaptureHealthMonitor states.

7. **Flash config storage (`pad_config_flash.c`).** Per-player calibration persistence
   (L4 thresholds, player enrollment state) on the device itself.

8. **Button + ADC debounce patterns.** While QorTroller needs the raw pre-debounce
   values for biometrics, the debounce logic is a reference for the host-passthrough
   path (the PS5 still gets a clean HID device).

---

## §6 Build-forward plan (ordered by unlock-leverage)

### Step 1 — Raw hook tap (highest priority, unblocks all biometric capture)

**File:** `src/pad/pad_input.c` (new ~50 lines)  
**What:** Insert a `qortroller_raw_hook` callback at the ADC read site, called with
`{adc_raw, axis_id, timestamp_us}` before any normalization. A null pointer = no-op
(zero cost when QorTroller capture is disabled).  
**Why first:** Without this, the entire biometric pipeline is blind on the native device.

### Step 2 — PoAC builder task (Core 0 pinned, 1 kHz)

**File:** new `src/qortroller/poac_task.c` (~300 lines)  
**What:** `xTaskCreatePinnedToCore` on Core 0 at 1 ms cadence. Receives raw samples
from Step 1 via a ring buffer, builds the 228-byte PoAC record, accumulates L4 features
per cognition cycle, and queues records for ATECC signing.  
**Depends on:** Step 1.

### Step 3 — ATECC608B I2C integration (Path A Arc 2)

**File:** new `src/qortroller/atca_signer.c` (~150 lines using CryptoAuthLib component)  
**What:** Register ATECC608B on the existing I2C bus. Receive completed PoAC records
from Step 2, call `atcab_sign()` to produce the 64-byte ECDSA-P256 sig, emit the full
228-byte signed record over BLE/WiFi to the bridge.  
**Depends on:** Steps 1–2. **Gated on:** physical ATECC608B breakout (hardware-gated).

### Step 4 — Bridge telemetry channel

**File:** new `src/qortroller/bridge_transport.c` (~200 lines)  
**What:** BLE characteristic or WiFi UDP packet carrying the 228-byte PoAC record to
the Python bridge. The bridge already parses the 228-byte format; this just delivers it
wirelessly instead of via hidapi/USB.  
**Depends on:** Step 3. Existing `src/wifi/` provides the transport.

### Step 5 — QM35825 presence flag reader (UART)

**File:** new `src/qortroller/uwb_presence.c` (~100 lines)  
**What:** Read the QM35825 presence/absent binary decision over UART into a flag polled
by Step 2's PoAC task. If present=false → PoAC cycle skipped (no human detected).  
**Depends on:** Step 2. **Gated on:** QM35825DK-05 eval kit (hardware-gated, Qorvo
partner reg submitted 2026-06-14).

### Step 6 — PV-CI firmware gate

**File:** new `scripts/test_firmware_build.py` + CI YAML update  
**What:** `idf.py build` on CI, symbol assertions on the `.elf`, PoAC struct size check
(must == 228), new PV-CI entries for INV-FIRMWARE-001/002.  
**Depends on:** Steps 1–2. Can be parallelized with Steps 3–5.

---

## §7 What does NOT change

- **228-byte PoAC FROZEN wire format** — untouched. joypad-os knows nothing about it
  and the new QorTroller layer adds it on top.
- **PV-CI 174/174 invariant baseline** — no firmware invariants added until Step 6 lands.
- **Bridge Python codebase** — the bridge already consumes 228-byte PoAC records; the
  transport changes from USB/hidapi to BLE/WiFi but the record format is identical.
- **ATECC608B → Microchip, not Qorvo** — the secure element is Path A Arc 2; joypad-os's
  I2C bus merely *enables* the wiring without dictating the part.
- **License** — joypad-os is Apache-2.0; QorTroller additions in `src/qortroller/` can
  be any compatible license including proprietary.

---

## §8 Summary grades

| Claim | Grade | Detail |
|---|---|---|
| joypad-os gives us an ESP32-S3 firmware baseline | **VERIFIED** | Real IDF tree, real board configs, real drivers |
| joypad-os gives us a 1 kHz biometric loop | **ASPIRATIONAL** | New FreeRTOS task needed (§6 Step 2) |
| joypad-os gives us PV-CI firmware gates | **ASPIRATIONAL** | New CI scripts needed (§6 Step 6) |
| joypad-os is compatible with the PoAC tap | **VERIFIED** | Additive hook pattern in pad_input.c (§3) |
| joypad-os's I2C bus works for ATECC608B | **VERIFIED** (bus) / **ASPIRATIONAL** (integration) | Bus present; CryptoAuthLib integration is new work |
| joypad-os's UART peer works for QM35825 | **VERIFIED** (transport) / **ASPIRATIONAL** (protocol) | UART peer exists; presence-flag protocol is new |
| MAX3421E USB host saves weeks of work | **VERIFIED** | Driver already implemented for ESP32-S3 |

---

## §9 Provenance

Born 2026-06-15. Grounded in direct inspection of `bridge/firmware/joypad-os` at
commit `8fa2e144` (ConWan30/joypad-os fork). Anchors: `docs/path-a-manufacturing-spec.md`
(ATECC608B integration), `wiki/methodology/sensor_stack_v2_3_uwb_presence_design_note.md`
(QM35825/UART), `docs/qortroller-devkit-bom-v0_1.md` (BOM v0.2), `CROSS-LESSON-001`
(separability constraint). PV-CI 174/174 unchanged; 0 IOTX; no FROZEN edits.
