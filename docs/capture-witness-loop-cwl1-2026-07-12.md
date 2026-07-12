# Capture Witness Loop (CWL-1) — bring OBSERVATION live, freeze its commitment, and the DePIN device it points to

**Drafted 2026-07-12. RIG-GATED — nothing in this loop builds until the capture card is physically
connected.** An orchestrated loop for card-arrival: take the OBSERVATION plane from "a committed root,
advisory, default-OFF" to **live real-fidelity capture**, **promote its commitment from candidate to a
novel FROZEN-v1 primitive** (interpretation stays advisory), close TPF-1 F3's live join, and name the
DePIN device this all points to — **the QorTroller Capture Witness**.

> **The law, unchanged (why this is safe): the screen is spoofable; the thumb is not.** OBSERVATION may
> suggest; only ASSERTION (the 1 kHz controller signal) may claim humanity. A hardware-rooted capture
> card makes the *observation's provenance* strong — it never makes video the humanity gate. Freezing
> the *commitment* (the hash of what was captured) is not the same as making the *interpretation* (what
> it means) load-bearing. Both stay true at once.

---

## North star — the QorTroller Capture Witness (the DePIN device thesis)

**Today, "trusted gameplay capture" does not exist.** A tournament trusts a laptop running OBS — a
stream that is spoofable, unattributable, and un-anchored. QorTroller has already built every piece of
the alternative; CWL-1's north star is to name and shape the device that embodies them:

> **A purpose-built, IoTeX-native HDMI capture appliance that is itself a DePIN node** — it ingests
> pixel/HDMI data, computes the retina observation commitment at a hardware root, emits only a 32-byte
> commitment + a DA pointer, and carries its own on-chain identity. The raw pixels never leave
> un-committed. The card is a **trusted observation *oracle* for gameplay.**

### What QorTroller has already built → the device's components

| Device component | Already built in QorTroller | Maturity |
|---|---|---|
| HDMI/pixel ingest → perception stage | trio-retina embedder / perception (`retina_state_commitment`, `retina_events_root`) | **BUILT**, advisory |
| On-device commitment *validation* | W3bstream Rust/Wasm sandbox (`wasm32-unknown-unknown`, `frame_grabbing:false` — validates, never grabs) | **BUILT** (INV-W3S-001/002) |
| Hardware identity + trust root | Path-A silicon-root device birth cert + VMDR registry + secure element (ATECC608B/C per HWFL-1 BOM) + **ioID DID** | **LIVE (protocol) / GATED (silicon)** |
| Bulky payload off-chain, pointer on-chain | Arc-7 **Decoupled Sidecar Pointer** (32B commitment crosses the wire; video/perception on the DA node) | **BUILT** |
| Federation with the play itself | `session_id` join to the controller's ASSERTION plane (TPF-1) | **BUILT + merged** |
| Economic agency | observation commitments feed the MEANING plane (consent + marketplace), gamer-owned | **BUILT** |

### The two-piece trusted-capture system

The device is not one box — it is a **pair**, and that pairing is the novelty:

```text
  CERTIFIED CONTROLLER  ---(ASSERTION: "a live human authored this", PoAC/PoSP, 1 kHz thumb)--\
                                                                                                >-- one session_id (TPF-1)
  CERTIFIED CAPTURE WITNESS ---(OBSERVATION: "and here is the committed record of the screen")--/
                                                                                                |
                                            gamer wallet owns the MEANING plane (consent/market)-/
```

Two IoTeX-native, hardware-rooted devices — one proving *humanity at the source*, one proving *capture
provenance* — federated under one join key, with the gamer owning what it all means. **No screen-only,
input-only, or data-only system can produce this object.**

### Why it is genuine DePIN (and where it is honest)

- **Verifiable physical data** — a certified card emits *provenance-bearing* observation: "this pixel
  stream was captured by device `0x…` at session S, committed at root R" — verifiable months later by a
  party outside the trust chain. That is the DePIN definition.
- **Economic agency** — each card is an ioID node; its observation commitments are a gamer-owned data
  product. A *network* of cards (venues, players) is a decentralized physical observation infrastructure.
- **Composability** — `isFullyEligible()` (humanity) + a capture-witness attestation (provenance), one
  call each, federated.
- **The honest ceiling that never moves:** a certified card proves **capture provenance** (who/when/what
  device captured this stream), **not content truth** — you can still point a certified card at a
  replay. It *raises the cost of video spoofing and gives attribution*; it does **not** turn video into
  a humanity proof. The humanity anchor stays with the thumb. A capture witness is a **provenance
  oracle, not a truth oracle.**

### Lineage in QorTroller's own architecture

This is not a new idea bolted on — it is the natural evolution of witness devices the repo already
reasoned about: the **L8 BT LAN-tower witness** (BlueZ + USB dongle) and the **Sensor-Stack v2.1
Surface-4 optical witness** (tournament camera observes the lightbar). The **capture witness** is the
screen-observation member of that same family — and the one the data economy most wants.

---

## The loop (cycle shape)

```text
while card_connected and not saturated and not operator_interrupt:
  1. Pick the next cycle (below)
  2. GROUND on the real card first (fps / resolution / HDMI path) - never assume fidelity
  3. Respect the law: OBSERVATION augments, never asserts; the 228B PoAC wire + assertion plane
     stay BYTE-UNTOUCHED (kill-check every cycle that retina running does not perturb PoAC/PoSP)
  4. Verify (pytest + PV-CI) + bank + STAGE for operator commit
  5. Freeze / deploy / ceremony steps are OPERATOR-FIRED (governance seal boundary), never autonomous
```

## Backlog

| id | cycle | what it does | gate |
|----|-------|--------------|------|
| **C0** | **Ground the live card path** | confirm real fps/resolution + clean HDMI; observation plane populates at fidelity; **kill-check** that retina running leaves PoAC/PoSP bytes identical | **RIG** (card) |
| **R1** | **Capture smoke** | reuse `scripts/retina_card_smoke.py` (TRL-1) against the real card — fps, no WGC-style collapse, clean frames | RIG |
| **R2** | **Crop/ROI recalibrate** | reuse `scripts/retina_crop_recalibrate.py`; TRL-1 found ROIs are *fractional* (resolution-independent) so this should be light — validate at the card's real resolution | RIG |
| **R3** | **Observation-fidelity gate** | `retina_perception_root` populates at real fps (not thin/placeholder); a small **N>1 calibration** so the plane earns an evidence bar before any freeze | RIG + calibration |
| **F1** | **Freeze the observation commitment** *(the novel frozen use case)* | promote candidate `VAPI-RETINA-STATE-v1` / `VAPI-RETINA-EVENT-LINE-v1` → **FROZEN-v1** (byte-stable observation-commitment formula); add the PV-CI invariant + allowlist digest (183+); **interpretation stays advisory**. The SEAL is **operator-fired** | **DRAFT autonomous · SEAL operator** |
| **J1** | **Close TPF-1 F3 live** | daemon threads the Arc-5 `poac_chain_root` onto the live PoSP at mint → the tri-plane manifest's meaning↔session join **earns CRYPTOGRAPHIC** (no more ABSENT) | RIG + daemon wiring |
| **A1** | **Adversarial: replay-into-card** | feed a replay / OBS virtual stream into the certified card; LUMEN causal-coupling directionality must flag it **NON-CAUSAL** (input does not lead the observed effect) → observation flagged, humanity unaffected. Honest: a coupling signal that *raises spoof cost*, not a guarantee | RIG |
| **P1** | **Capture Witness device design** | the DePIN-device spec (north star above) as a partner-facing artifact — BOM tie-in (HWFL-1), Path-A Arc-2 silicon lineage, ioID provisioning, the provenance-not-truth ceiling stated up front | **DESK** (design) → **hardware/partner-gated** to build |

---

## Honest ceilings (carry with every cycle)

- **RIG-GATED** — the software cycles need the card; nothing builds blind. The *device* (P1) is a
  hardware/manufacturing effort in the Path-A Arc-2 / HWFL-1 / Qorvo-outreach lineage, not a thing that
  ships from this repo.
- **Federation, not conflation** — observation augments the humanity proof; it never becomes it. The
  freeze is on the *commitment*, the advisory status is on the *interpretation*.
- **Provenance, not truth** — a certified capture card proves *who/when/what-device captured a stream*,
  not that the stream is genuine gameplay. It raises spoof cost + gives attribution; the humanity anchor
  stays at 1 kHz on the thumb.
- **N=1 today** — the freeze (F1) is gated on R3's calibration earning an evidence bar; a candidate tag
  is not promoted to FROZEN-v1 on one session.
- **228B PoAC wire + assertion plane BYTE-UNTOUCHED** every cycle (kill-checked). W3bstream sandbox stays
  validation-only (`frame_grabbing:false`). TGE frozen; `CHAIN_SUBMISSION_PAUSED=true` held; the F1 seal
  and any deploy are operator-fired.

---

## Why this is the right shape

CWL-1 does three honest things at once and nothing more: it (1) makes the OBSERVATION plane *real* when
the card gives it fidelity, (2) gives you the **novel FROZEN retina use case** you asked for — by
freezing the commitment while keeping interpretation advisory, so the moat is never weakened — and (3)
names the **DePIN device** the whole architecture has been quietly describing: a trusted capture witness
that pairs with the certified controller so that *one match is a complete, hardware-rooted,
IoTeX-anchored object across all three planes*. Build phase already done in software; CWL-1 is where the
hardware and the freeze earn their live status — gated, tested, and honest about the one line it will
never cross.

---

*CWL-1 orchestrator — drafted 2026-07-12. Operator-paced; every cycle RIG-gated on the card; F1 freeze
and any deploy are operator-sealed. The screen is spoofable; the thumb is not. Federation, never
conflation.*
