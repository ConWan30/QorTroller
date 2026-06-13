# QorTroller — Manufacturer Outreach One-Pager

**What this is:** a single-page brief to open a conversation with a hardware partner
(Qorvo, Boréas, Battle Beaver / X-manufacturer) about building the V.A.P.I.-native
reference controller. Pair it with the architecture diagram
(`cad/out/qortroller_architecture.png`) and, when ready, the CAD model
(`cad/out/qortroller_layout.step`).

**Tone discipline:** every claim here is graded, not marketed. We say "raises spoof
cost / measurement pending," never "unbeatable." A hardware EE will trust the whole
pitch more for it.

---

## The one-sentence pitch

**QorTroller is a purpose-built game controller where the physical input device is
also the cryptographic owner of the data it produces — proving a live human at the
input layer so cheating can't be asserted, and giving the player sovereign ownership
of their gameplay data.**

It is the reference hardware for **V.A.P.I.** (Verifiable Autonomous Physical
Intelligence), a Decentralized Physical Infrastructure (DePIN) category, anchored on
IoTeX L1.

---

## Why now / why a partner

The protocol software is built and running (testnet): ~5,766 automated tests, a frozen
228-byte cryptographic record per cognition cycle, 66 deployed contracts, a 173-check
fail-closed CI gate. What it does **not** yet have is purpose-built silicon. Today it
runs on a certified third-party device (DualSense Edge). The next step is a reference
controller where the protocol's strongest signals are native hardware — and that needs
a manufacturing partner.

We are not asking for a finished product. We are opening a **design-partner
conversation** around a defined Bill of Materials and a staged measurement plan.

---

## The trust chain (see the architecture diagram)

```
human input → sensors → MCU builds the 228-byte record → secure element signs it
            → tamper-proof, gamer-owned data on-chain
```

| Stage | Components | What it does |
|---|---|---|
| Physical input | C7 adaptive triggers, C3/C4 sticks, C5 IMU, C8 touchpad, A1 lightbar | Capture human biomechanical signal at 1 kHz |
| Cognition | C1 ESP32-S3-class MCU | Builds the Proof-of-Autonomous-Cognition record |
| Root of trust | C2 ATECC608B/608C-class secure element | Signs every record with an on-chip, non-extractable P-256 key |

---

## What we need from a partner (by partner type)

| Partner | Best-fit role | Specific asks |
|---|---|---|
| **Qorvo** | RF / connectivity / power-management ICs; possibly MEMS | Component alignment for the wireless + power path; design-partner intro. *(Note: Qorvo's acoustic-wave strength is BAW/SAW RF filters — we are NOT asking them for haptic piezo.)* |
| **Boréas Technologies** | Piezo haptic actuation (CapDrive) | The L6 challenge-response channel — microsecond-accurate, silent, localized trigger-cap haptics. This is the strongest piezo fit (see Sensor Stack v2.2 design note). |
| **Battle Beaver / mod-house / X-manufacturer** | Assembly, Hall/TMR stick integration, small-run build | Reference dev-kit assembly; stick-module sourcing + integration expertise |

---

## The honest status (what's measured vs. proposed)

This is the part that earns trust — we are explicit about it:

- **PRIMARY discriminator (C7 adaptive trigger):** the strongest anti-cheat signal;
  translator hardware (Cronus/XIM) physically cannot synthesize a biomechanical 1 kHz
  force curve. **Status: candidate — Stage A separability measurement pending.**
- **Sticks / IMU (C3/C4/C5):** drift-free contactless sensing as L4 fingerprint
  surfaces. **Status: measurement-pending.**
- **Secure element (C2):** silicon root of trust; we already run the full cert/registry
  chain in software on a software-backed CA. **Status: spec locked, family selected
  (608B/608C-class, polling-based timing required).**
- **Piezo surfaces (acoustic liveness + L6 haptics):** proposed, with named Stage A
  gates. **Status: design-note proposal, not yet measured.**

We do not claim any of these is "unbeatable." Each is a signal that raises spoof cost,
and each has a defined measurement that must pass before it earns a production claim.

---

## What we bring to the table

- A complete, tested protocol stack (not vaporware) — software runs today on testnet.
- A defined dev-kit BOM (C1–C8 + advisory) with a two-supplier discipline rail.
- A staged measurement plan (Stage A empirical unknowns) — we know exactly what has to
  be proven and how.
- A digital prototype (CAD model + exploded architecture) for design alignment.
- Native fit to IoTeX's Internet of Trusted Things / DePIN ecosystem (relevant for
  grant co-funding, e.g. IoTeX Halo Grants).

---

## The ask

A 30-minute design-partner conversation: does the BOM align with your portfolio, and
what would a reference dev-kit build look like? We bring the protocol, the BOM, and the
measurement plan; you bring the silicon and manufacturing reality.

---

## Attachments to send with this page

1. `cad/out/qortroller_architecture.png` — the trust-chain diagram (the visual)
2. `docs/qortroller-devkit-bom-v0_1.md` — the Bill of Materials
3. `docs/path-a-manufacturing-spec.md` — the silicon/cert spec (608B/608C family)
4. `wiki/methodology/sensor_stack_v2_2_piezo_surfaces_design_note.md` — piezo proposal (for Boréas)
5. `cad/out/qortroller_layout.step` — the CAD model (when the recipient is technical)

---

## Provenance

Born 2026-06-13. Honest-status language inherited from the protocol's verification-first
discipline. Vendor roles reflect the Sensor Stack v2.2 sourcing correction (Qorvo =
RF/power, Boréas = haptic piezo). All vendor portfolios to be independently verified
before any named commitment (BT-CALIB-LESSON-001).
