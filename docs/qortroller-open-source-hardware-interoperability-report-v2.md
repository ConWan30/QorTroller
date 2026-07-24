# QorTroller × Open-Source Gaming Hardware — Interoperability, Partnership & Scaling Report (v2)

**Date:** 2026-06-15 (finalized 2026-06-20)
**Version:** v2 (final) — all [CONFIRM] items resolved; QORTROLLER.md device_id fixed. Supersedes v1.
**Scope:** How QorTroller can interoperate with established open-source gaming hardware/firmware platforms (joypad-os and its peers) to unlock partnerships and scale through integrated open-source manufactured platforms — without building proprietary hardware from scratch, and without compromising gamer data sovereignty.

**Evidence grading (this version):**
- **VERIFIED** — confirmed in repo / canonical anchors.
- **BUILT** — code exists; not live in production.
- **GATED** — architecturally specified; blocked on hardware, ceremony, or a demand-side buyer.
- **[VERIFY]** — external claim (platform license, community size, current vendor product) needing independent confirmation before partner use.

**What changed from v1:** v1 conflated the two scaling tracks, overstated firmware integration as "proven," mis-stated the corpus as "N=3," overstated onboarding/corpus as "solved," and omitted the MFG CA fragility disclosure. v2 corrects all five. **All three `[CONFIRM against repo]` items from v2-draft are now resolved** (corpus figures confirmed from `CLAUDE.md`; `QORTROLLER.md` device_id drift fixed; BR/EDR-vs-BLE confirmed with MAX3421E nuance). The strategic thesis is unchanged and sound; the maturity grading and the dual-track reality are now honest.

---

## 0. The core strategic insight (unchanged — this is right)

QorTroller's scaling problem and its architecture point to the same answer: **don't manufacture a controller — become the attestation layer that any open-source controller can adopt.** A proprietary controller competes with every controller maker. An *attestation overlay* makes every open-source controller a potential V.A.P.I.-compliant device, inverting the dynamic from "beat the incumbents" to "be adopted by the ecosystem." This is the USB-IF / Matter / FIDO2 model: be the standard, don't build the devices.

**This is VERIFIED-aligned** with the on-chain surface, which is already designed for *multiple manufacturers* (`VAPIManufacturerDeviceRegistry`, `VAPIProtocolLensV2.isFullyEligible()` / `isFullyEligible_PathA()`, `TournamentGateV3`), with Sony/Edge as the v1 *reference* device — not the only possible device class.

---

## 0.5 THE DUAL-TRACK REALITY (new in v2 — read this before everything else)

The single most important correction to v1: **QorTroller runs two parallel scaling tracks, and open-source firmware integration accelerates only one of them.** Conflating these is the error a technical partner will catch fastest.

| Track | What scales | How it works TODAY | Role of OSS firmware | Status |
|---|---|---|---|---|
| **Track A — Production verification** | Tournament/anti-cheat verification via the bridge + on-chain `isFullyEligible_PathA()` | DualSense Edge + **Python bridge @ ~1002 Hz** | **None required** | **LIVE (testnet)** |
| **Track B — Reference dev-kit (Rung 2)** | Purpose-built controller manufacturing; Path A v2 per-PoAC on-device silicon signing; 1 kHz on-device corpus capture | joypad-os firmware overlay on ESP32-S3 | **The overlay IS this track** | **BUILT / GATED on hardware** |

**The load-bearing fact:** the AIT separation ratio of **1.199** — the project's headline biometric result — was produced via **Track A (the Python bridge at ~1002 Hz), not the firmware overlay.** Open-source firmware integration is how the *dev-kit roadmap* (Track B) scales; it is **not** how the protocol's verification works today (Track A). Any partner-facing statement must keep these distinct:

> "OSS integration accelerates the manufacturing/dev-kit track (B) and enables per-PoAC silicon rooting. The production verification track (A) — Edge + bridge — is live today and does not depend on the overlay. We maintain Edge+bridge as the live reference while the OSS dev-kit matures."

Everything below about overlays, GP2040-CE, and viral flashing is **Track B**. The §4 demand-side analysis applies to **Track A**.

---

## 1. The open-source gaming hardware landscape (Track B targets)

### Layer 1 — Controller firmware platforms (the entry point)

| Platform | License | MCU targets | Maturity / community | QorTroller fit |
|---|---|---|---|---|
| **joypad-os** (current fork) | Apache-2.0 **VERIFIED** | RP2040, ESP32-S3, nRF52840 | Working; community size **[VERIFY]** | **Reference integration BUILT** — raw-ADC tap + `CONFIG_QORTROLLER` Kconfig opt-in |
| **GP2040-CE** | **[VERIFY exact license]** | RP2040-family | Large PC fight-stick community, very active **[VERIFY]** | **Community/adoption lever, NOT Edge parity** (see correction below) |
| **QMK / VIA controller forks** | GPL-family **[VERIFY]** | Various | Huge keyboard heritage **[VERIFY]** | Medium — GPL changes the open-core math |
| **Open fight-stick firmware** | Mixed | RP2040 / ATmega | Niche, passionate | Cultural fit (these communities care about input fidelity) |

**Correction to v1 on GP2040-CE:** it is a **community/adoption lever for the PC fight-stick scene, not a shortcut to Edge-equivalent L4 signal.** GP2040 excels at fight-stick USB *device output*; it does **not** give you adaptive triggers, a touchpad, the 1002 Hz Sony HID report shape, or native WiFi/DePIN telemetry (RP2040 has no native WiFi). I2C for the ATECC608 is feasible there, but a raw biometric tap on custom GPIO pads is **not** the same signal surface as a commercial DualSense's input stream. **GP2040 buys you reach into the fight-stick community; it does not buy you the L4 biometric discriminators.** Target it for adoption breadth, not for signal parity.

### Layer 2 — Sensor/module ecosystems (VERIFIED-aligned with BOM/Sensor B)

- **GuliKit** — dominant commercial TMR vendor **[VERIFY current line]**.
- **K-Silver** — Hall (JH16) + TMR (JS16) in one form factor (A/B testing without PCB respin) — a real, repo-confirmed engineering advantage.
- **Microchip ATECC608B/608C-TFLXTLS** with **TrustFLEX factory provisioning** — keys injected at Microchip's facility; the Rung 3 convergence target.
- Same-family L/R stick discipline (no mixing Hall+TMR across L/R) is a canonical BOM rule.

Reference-design relationships (spec recommends their modules; they get design-win volume) are low-friction and realistic.

### Layer 3 — Board & manufacturing ecosystems

ESP32-S3 / RP2040 commodity boards (Feather/XIAO form factors joypad-os already supports) as the dev-kit substrate; small controller ODMs / mod houses (Battle Beaver-class) as the realistic first manufacturing partners.

---

## 2. The interoperability model — additive, non-invasive, opt-in (VERIFIED architecture)

The overlay pattern, **VERIFIED** in repo (`bridge/firmware/joypad-os/QORTROLLER.md`, `docs/qortroller-joypad-os-integration-analysis.md`, `src/qortroller/CMakeLists.txt`):

```
Open controller firmware (unchanged HID-to-host behavior)
        │
        ├─ [RAW ADC HOOK]  ← null-default callback, zero cost when CONFIG_QORTROLLER off
        │        ↓
        │   qortroller sense_task (Core 0 pinned, ~1 kHz)   ← sense_task.c (BUILT)
        │        ↓
        │   PoAC record builder (228 bytes)                 ← poac_builder.c (BUILT)
        │        ↓
        │   ATECC608B sign (I2C peer)                       ← atca_signer.c (BUILT, hardware-GATED)
        │        ↓
        │   bridge transport                                ← bridge_transport.c (BUILT)
        │
        └─ normal HID/XInput output to PS5/PC (untouched)
```

Three properties make this adoptable by any compliant firmware: it's a **parallel tap, not a data-path fork** (device still presents normal HID); it's a **compile-time opt-in** (`CONFIG_QORTROLLER` — firmware that doesn't enable it carries zero QorTroller code); and the **license boundary is clean** for Apache-2.0 hosts (`src/qortroller/` namespace). **[VERIFY this holds for GPL-family platforms — GPL's derivative-work rules change the math.]**

**Maturity grading (corrected from v1's "proven"):**
- **VERIFIED:** overlay architecture, Apache-2.0 fork, `CONFIG_QORTROLLER` conditional build, raw-tap-before-normalization design, the 228-byte compile-time assert intent.
- **BUILT (code exists, per the June-15 firmware assessment):** `sense_task.c`, `poac_builder.c`, `bridge_transport.c`, `atca_signer.c`.
- **NOT LIVE IN PRODUCTION:** Arc 2 ATECC608 hardware gate is open; the registered reference Edge is **`signing_path = B` (host-key)**, not silicon-rooted Path A per device; Path A registry/lens infrastructure is live on testnet, but not every device is silicon-rooted yet; the firmware path is dev-kit/CI, **not player-facing deployment**.

**"Proven on joypad-os" is fair for the *architecture*; it is overstated for *operational anti-cheat at scale*.** Use: "reference integration built; production gated on Arc 2 hardware + manufacturing ceremony."

**device_id canon (RESOLVED 2026-06-20):** `QORTROLLER.md` line 51 now cites `keccak256(65-byte SEC1 P-256 pubkey)` per `wiki/methodology/DEVICE_ID_CANON_v1.md` (supersedes the older `SHA-256(pubkey ‖ serial)` formula). The F-FW-2-DRIFT probe (`bridge/vapi_bridge/daemon_health_monitor.py`) scans `atca_signer.c` and `docs/path-a-arc2-prompt.md` only — partner-facing markdown is out of probe scope; doc hygiene for integration docs remains manual.

---

## 3. Certification model — becoming a compliance standard (strong, with one required disclosure)

The goal: QorTroller is to attested gaming input what **USB-IF is to USB, Matter to smart home, FIDO2 to authentication** — a certification any OEM implements, gated by a verifiable standard rather than owned by one vendor.

### The model: open-core + compliance certification
- **Open the verifiable layer** (attestation spec, PoAC format, verification rail, reference overlay) — logically required by the protocol's own thesis (a verification system that can't be verified undermines its value).
- **The certification is the product.** A controller is "V.A.P.I.-compliant" when its silicon-rooted device identity chains into QorTroller's CA hierarchy and its PoAC records verify.
- **The CA hierarchy is the gate** — manufacturers chain their provisioning CA into QorTroller's root.

### Precedents that transfer (the strongest partner argument — QorTroller is NOT novel in category)
- **Matter device attestation** — every Matter device proves authenticity via a Device Attestation Certificate chaining to a CSA-managed root. **Almost exactly QorTroller's birth-cert + manufacturer-CA + on-chain-registry model.** [VERIFY current Matter specifics before citing precisely.] **Lesson: a consortium-managed CA root + per-device attestation certs is a proven, shipping model for attesting millions of consumer devices.**
- **FIDO2 / WebAuthn** — multi-vendor hardware authenticators against an open standard, alliance-certified. **Lesson: open standard + multi-vendor hardware + certification scales an attestation primitive across an ecosystem without one vendor owning the hardware.**
- **DePIN onboarding (Helium/DIMO/Hivemapper)** — on-chain device identity earning participation. **Lesson (and caution): the on-chain-identity *mechanism* transfers; the data-economy *model* must NOT — they reward data contribution; QorTroller rewards proof/verification contribution to preserve sovereignty.**
- **Hardware wallets (Ledger/Trezor)** — secure-element-rooted consumer devices, key never leaves silicon. **Lesson: consumers adopt secure-element-rooted hardware when the integrity value is clear.**

**Throughline:** attested consumer hardware via a certification standard is *proven and shipping* (Matter, FIDO2). QorTroller is novel in *application* (gaming + biometric presence) and *substrate* (IoTeX-native ioID + sovereignty-as-a-feature), **not in category** — a far stronger pitch than "we invented something new."

### REQUIRED DISCLOSURE (v2; **updated 2026-07-17**) — CA hierarchy maturity
The Matter/FIDO2 analogy holds **structurally**, and a partner doing diligence will now find **F-DECON-3.2
closed at root**: as of **2026-07-16/17** the **Foundation reference MFG Root CA is HSM-rooted** — a
non-exportable **AWS KMS P-256** key (the bridge can request a signature, never read the key); the live
reference device was re-issued + re-anchored and verifies **VALID** under it; **Sensor C gate G1.6 is
`LIVE`** (was `LIVE-FRAGILE`); OA-4 is **done**. The prior software-backed, single-copy, LIVE-FRAGILE root
is retired (cold-forensic only). **What still needs honest disclosure to partners** (state this): (a) this
is the **reference-implementation Foundation root** — a production partner **replaces it with their own
HSM-rooted CA** (the swap is one line of config; the ceremony is documented in
`docs/path-a-mfg-ca-hsm-migration.md`); (b) it is **testnet**; (c) **silicon-rooted-every-PoAC** (Path A v2)
remains **Arc-2-hardware-gated** — v1 delivers silicon-rooted VHP/renewal authenticity today. The honest
framing: *"The CA hierarchy and attestation model are Matter/FIDO2-grade; the reference root is now
HSM-backed (F-DECON-3.2 closed at root) and a production partner runs their own HSM ceremony per the
migration spec. We disclose the reference-vs-partner-production distinction rather than imply a partner
inherits production key custody."* Disclosing the maturity honestly — done, and what a partner still owns —
is the trust move.

---

## 4. Partner archetypes (sequencing insight is correct — applies to Track A demand + Track B supply)

| Archetype | Ask | What they get | Friction |
|---|---|---|---|
| **OSS firmware maintainers** (joypad-os, GP2040-CE) | Permit an optional secure-element overlay; no behavior change | Attestation-capable platform; differentiation | Low — opt-in; **[VERIFY GPL compat]** |
| **Hall/TMR vendors** (GuliKit, K-Silver) | Reference-design recommendation | Design-win volume; credibility | Very low |
| **Secure-element vendor** (Microchip) | TrustFLEX provisioning relationship | Volume sales; flagship gaming use-case | Low |
| **Small ODMs / mod houses** | Build small runs; chain CA into root | First-mover in attested controllers | Medium — real cost; realistic first hardware partner |
| **IoTeX ecosystem** | Halo grant; native ioID/W3bstream | Flagship DePIN gaming use-case | Low — natural first funder |
| **Tournament organizers / studios (DEMAND)** | Adopt V.A.P.I. verification | Provable-human gating, no kernel anti-cheat | **HIGH — the real bottleneck** |

**Sequencing insight (correct):** supply-side asks (firmware, modules, secure element, ODM, IoTeX) are all low-friction and parallelizable. The demand-side ask (studios/tournaments) is the hard one and gates monetization — and the repo confirms it: enormous supply-side engineering (174 invariants, 66 contracts, Path A deployed) but **no live tournament operator currently requiring `isFullyEligible()` as a gate.** Build the supply-side ecosystem first; find the demand-side pilot deliberately.

---

## 5. The scaling mechanism (corrected — viral flash is bootstrap, not certification)

Why open-source platforms enable fast Track-B scaling: no firmware NRE (rides commodity boards); the community does distribution; the certification scales without QorTroller manufacturing anything; IoTeX-native identity is inherited substrate.

**Corrections to v1's overstatements:**

**The "flash the overlay" path is an ENTHUSIAST/DEV-KIT bootstrap, NOT a certification path.** Flashing firmware does not make a device V.A.P.I.-compliant/FULL-tier. Certification requires the **Path A manufacturing ceremony**: ATECC608B provisioned (`atcab_genkey`, locked slots) + device birth cert + MFG CA chain (`provision_device_mfg.py`, `VAPIManufacturerDeviceRegistry`) + the canonical `device_id = keccak256(65-byte SEC1 pubkey)`. **Community flash bootstraps enthusiast/dev-kit nodes; certified manufacturer rows require ceremony + CA hierarchy.** That distinction is load-bearing for "USB-IF of provable presence" — USB-IF certification isn't "flash some firmware," and neither is this.

**Onboarding/corpus is architecturally right, operationally not running (corrected from v1's "solved"):**
- **ioID** is integrated in the bridge (Phase 55) — a good substrate, **not** a finished OSS-controller onboarding product.
- **The BCC corpus harvester** (`l9_presence/`) is **dormant** (`bcc_enabled` false). The "open-source scaling also grows the corpus" story is **architecturally correct, operationally not yet running.** It's a real future mechanism, not a current one.

**Calibration authority is bridge-side, and a partner will ask who governs it.** Today the **Python bridge** holds enrollment centroids and Mahalanobis thresholds (7.009/5.367, numpy via `asyncio.to_thread`). Firmware `poac_builder.c` does incremental feature accumulation, but **corpus-validated separation claims remain bridge-calibrated.** OSS scaling helps *capture* at 1 kHz; it does **not** automatically solve **enrollment + threshold governance across vendors** — that's an open design question for a multi-vendor certification regime.

---

## 6. Honest strategic caveats (v1's strongest section — extended)

**1. The adaptive trigger is the IP and supply long-pole — breaks the "ride open-source hardware" story for ONE component.** Every other component is commodity/open-source-adoptable. The adaptive trigger is **not** — Sony actively patents the mechanism (worm-gear/motor/lever + a 2025 fluid-adaptive continuation), no merchant module exists, and reproducing Sony-class force-curve fidelity is a development program with FTO exposure. **Repo confirms: BOM C7 = "HARDEST PROBLEM," Sensor Stack v2.1 PRIMARY DISCRIMINATOR.** **Lead the pitch with the reflex-band challenge-response instead** (80–280 ms human reaction; repo's L6B infrastructure is built but `L6B_ENABLED=false`, thresholds pending hardware calibration) — it's the strong, buildable, novel liveness signal that does NOT require the patented trigger. Position the force-curve as aspirational-with-FTO-dependency.

**2. Demand side is the real bottleneck, not supply.** Attested hardware in hands is worthless without tournament organizers/studios who *require* V.A.P.I. verification. Chicken-and-egg: hardware adoption needs demand-side buyers; buyers need installed hardware. The OSS supply-side strategy de-risks *half* the problem cheaply; the demand side needs a separate flagship-pilot play. Don't let supply-side progress create the illusion adoption is solved.

**3. Console licensing is unsolved by any protocol elegance.** Works on PC and via licensed-adapter passthrough; native PS5/Xbox is a Sony/Microsoft business negotiation. **PC-first, console via passthrough, native console licensing is a separate commercial track.** Repo confirms Edge+PS5 dual-connection grind with no native Sony license path.

**4. A specific RF constraint — CONFIRMED:** the **DualSense uses BR/EDR (Bluetooth Classic), while the ESP32-S3 joypad-os port is BLE-only** (confirmed from `bridge/firmware/joypad-os/src/bt/btstack/btstack_config_esp32.h` — "ESP32-S3 has BLE only (no Classic BT)"). This means the ESP32-S3 overlay **cannot directly read a DualSense over its native Bluetooth**, which reinforces the PC-first/wired posture. Track B's documented path for using a commercial DualSense as input on ESP32-S3 is **USB host via MAX3421E** (`max3421_host_esp32.c` in the integration analysis) — wired, not wireless. RP2040 + Pico W has Classic BT via CYW43, but the canonical dev-kit BOM is ESP32-S3, so the wired-USB path is the Track B integration story. State this to partners rather than leaving the wireless question open.

**5. Biometric data carries regulatory weight even sanitized.** Micro-tremor, skin-conductance, force-curve attract BIPA/GDPR/CIPA scrutiny at *capture*, regardless of sanitization. The proof-not-data boundary (φ-sanitization, raw biometrics never cross the network) is the *right* architecture and a partnership **asset** ("the player's raw biometrics never leave their device") — repo confirms TRACK1-LESSON-003, BIPA/GDPR framing. It must be airtight and stated; privacy counsel will ask. Sovereignty is a regulatory feature, not just an ethical one.

**6. GPL licensing on some platforms changes the open-core math.** joypad-os is Apache-2.0 (clean). GP2040-CE/QMK-derived may be GPL-family, making the overlay's licensing interaction stricter — the "additions can be any license including proprietary" claim may not hold there. **[VERIFY every Layer-1 target's license.]** Affects which platform is the right second target.

**7. The corpus depth (corrected from v1's "N=3").** The honest caveat is **not** "we have almost no data." The repo shows: **AIT N=37 sessions across 3 players** (P1=13, P2=10, P3=14 — **CONFIRMED** from `CLAUDE.md` Phase 229/231 anchors), ratio 1.199, all inter-player pairs > 1.0; plus a **broader calibration corpus of 217 total session files** (153 terminal + ~64 hw, hw_005–hw_078 — **CONFIRMED**). Note: the 217 figure mixes session types; the tournament gate metric is AIT-specific (ratio 1.199), not the full 217-pooled corpus (ratio 0.060 for free-form gameplay — known/expected, not a failure). The accurate partner framing: **"a 3-player, ~37-session AIT breakthrough that is real and statistically clean for that set, but insufficient for production FAR/FRR and cross-population generalization."** The OSS scaling strategy is *also* the corpus-depth strategy (controllers in hands → provenance-clean corpus via the currently-dormant BCC harvester) — architecturally, not yet operationally.

---

## 7. Recommended sequencing (corrected)

1. **Solidify joypad-os as the reference integration — AND maintain Edge+bridge as the live reference.** Track A (Edge+bridge) stays the live production path; Track B (overlay) is the dev-kit demonstrator. Don't let the overlay narrative erase the live path.
2. **[VERIFY] GP2040-CE as a community/adoption lever** (PC fight-stick reach) — confirm license + architecture; do NOT pitch it as Edge biometric parity.
3. **Lock reference-design relationships** (GuliKit/K-Silver, Microchip TrustFLEX) — low-friction.
4. **Pursue the IoTeX Halo grant** — natural first funder, native ioID/W3bstream fit.
5. **Draft the compliance spec as a standard** — CA hierarchy + birth-cert + PoAC-verification — **with the honest CA maturity status included** (F-DECON-3.2 **closed at root** 2026-07-16/17: reference root now HSM-backed / G1.6 `LIVE`; a production partner runs their **own** HSM ceremony per `docs/path-a-mfg-ca-hsm-migration.md`).
6. **Find ONE demand-side pilot** (competitive title / tournament / AGaaS customer) — the hard, gating, Track-A play that converts ecosystem into revenue.
7. **Lead every pitch with reflex-band challenge-response + proof-not-data sovereignty; caveat the adaptive trigger, console licensing, the BR/EDR/wired constraint, and corpus depth honestly.**
8. **Path A v1 vs v2 (one sentence for architecture reviewers):** Path A v1 (live) delivers silicon-rooted VHP/renewal authenticity; Path A v2 (Arc 3+, Track B gated) delivers silicon-rooted every PoAC cycle — the overlay enables v2, it is not live today. See `docs/path-a-manufacturing-spec.md` §1.

---

## 8. The one-paragraph version (v2)

QorTroller scales by becoming the **attestation compliance layer any open-source controller can adopt** — an additive, opt-in, non-invasive secure-element + PoAC overlay (architecture VERIFIED, code BUILT, production GATED on Arc 2 hardware + manufacturing ceremony) that leaves existing HID behavior untouched. Critically, this is the **dev-kit track (B)**; the **live production verification track (A) — DualSense Edge + Python bridge at ~1002 Hz, which produced the 1.199 AIT ratio — does not depend on the overlay** and must be kept distinct in any partner conversation. The partnership model is **open-core + certification**, directly precedented by Matter device attestation and FIDO2 — proven, shipping patterns for attesting consumer hardware at scale via a consortium CA root — making QorTroller novel in *application* and *substrate*, not *category*; the Matter/FIDO2 analogy must be paired with the honest CA maturity status (**F-DECON-3.2 closed at root 2026-07-16/17** — the reference Foundation CA is now HSM-rooted, non-exportable AWS KMS, Sensor-C G1.6 `LIVE`; still testnet, and a production partner runs their **own** HSM ceremony per the migration spec). Supply-side asks (firmware maintainers, module vendors, secure-element provisioning, small ODMs, IoTeX grants) are low-friction and parallelizable; the demand side (studios/tournaments) is the real bottleneck needing a separate flagship pilot. The honest long-poles are the patent-encumbered adaptive trigger (lead with reflex-band challenge-response instead), console licensing (PC-first, console via passthrough), a **confirmed BR/EDR-vs-BLE wireless constraint** (ESP32-S3 is BLE-only; Track B DualSense capture is USB host via MAX3421E, wired), and corpus depth (**3-player / 37-session AIT breakthrough — real but insufficient for production FAR/FRR**, which the OSS scaling strategy also addresses by putting controllers in hands). Position QorTroller as **the verification standard for human-attested gaming input — the USB-IF of provable presence — not a proprietary hardware play**, and keep the dev-kit roadmap (Track B) clearly distinct from protocol deployment today (Track A).
