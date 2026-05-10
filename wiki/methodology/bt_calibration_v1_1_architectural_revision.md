# BT Calibration v1.1: Architectural Revision

**Version:** 1.1
**Date:** 2026-05-10
**Supersedes:** v1.0 BT calibration architectural proposal (chat-session, marked [SUPERSEDED-BT-CALIB-LESSON-001])
**Canonical anchor:** `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`
**Companion lesson:** `lessons.md` entry `BT-CALIB-LESSON-001`
**Status:** Draft. Capture-session planning is gated on the empirical unknowns in §5 being resolved by pre-corpus measurement.

## Executive Summary

The v1.0 BT calibration architectural proposal was falsified during a methodology-research verification pass. Three of four proposed L4 features were derived against BLE primitives that do not exist on the actual transport the DualSense and DualSense Edge run, which is Bluetooth Classic BR/EDR with HIDP. The defensibility claim against three documented attack patterns was also overstated; under SDR-equipped attackers the published baseline (BlueShield, Wu et al., RAID 2020) inherits as a floor and the v1.0 composition does not improve on it. This v1.1 revision preserves the broader framing — BT-native attestation as structurally novel, LAN-witness as the only viable first witness, on-chain TWC commitment as the differentiator from BlueShield — and corrects four specific architectural choices that the verification pass falsified. The narrowing of the novelty claim is treated as a strengthening of the protocol's defensible position, not as a consolation property: the narrower claim has a smaller prior-art surface, a concrete documented attack class to point at, and a confirmed industry blind spot that the broader claim did not have.

The recommendation from the canonical anchor stands: 6 months minimum to first capture session, with the architectural revision (this document) plus pre-corpus empirical measurement (§5) plus original adversarial validation work (§6, Stage 3) sequenced before any production calibration data is collected.

## Section 1 — Transport Reframed to BR/EDR

The DualSense and DualSense Edge connect wirelessly using Bluetooth Classic BR/EDR with HID transported over L2CAP HID PSMs 0x11 (control) and 0x13 (interrupt). This is the legacy HIDP profile, not HID-over-GATT. The verification block establishing this transport is recorded in `lessons.md` entry `BT-CALIB-LESSON-001` and consists of the Linux mainline kernel `hid-playstation.c` driver (Roderick Colenbrander, Sony Interactive Entertainment, mainlined in Linux 5.12, April 2021), the Bluepad32 project FAQ, the BlueRetro reverse-engineering project at Hackaday.io, the PCGamingWiki Controller:DualSense Edge entry, and field confirmation on FreeBSD distinguishing BLE-only from BR/EDR-capable host adapters.

The architectural consequence is that the BLE primitive set on which the v1.0 proposal was built — advertising interval, advDelay (the 0–10 ms randomization characterized by Argenox), connection event anchors, the BLE PHY's GFSK CFO behavior characterized by Givehchian et al. (S&P 2022) — applies to a hypothetical BLE controller, not to the DualSense or DualSense Edge as currently shipped. The primitives that *do* exist on BR/EDR and that any v1.1 feature derivation must be built against are: Tpoll (the polling interval the master uses to query the slave for input data), Tsniff (the interval used in sniff mode for power-saving), page-scan repetition modes R0/R1/R2 on the host side during connection establishment, the AFH (Adaptive Frequency Hopping) channel map across 79 1-MHz channels, and the L2CAP/baseband ARQN/SEQN retransmission counters. RSSI per ACL link is exposed via the HCI `Read_RSSI` command and remains a valid primitive on this transport.

The feature mapping that any v1.1 derivation must respect is: `connection_interval_jitter` reframes to *poll-interval (Tpoll) variance* observed at the witness's HCI socket; `advertisement_period_drift` has no BR/EDR analog and is dropped from the v1 feature set entirely (BR/EDR has no advertising — only inquiry/page-scan procedures, and these are host-side, not controller-side); `retransmission_rate` survives but must be reframed as L2CAP/baseband retransmissions per N slots normalized against the AFH channel-map snapshot, because raw retransmission rate is dominated by 2.4 GHz coexistence interference (see §2 and §5); `rssi_variance_normalized` survives unchanged as an HCI Read_RSSI-derived signal.

This is a structural problem, not a relabeling problem. The published BLE-fingerprinting literature that the v1.0 proposal implicitly leaned on (BlueShield, BLESA, SweynTooth, Givehchian) overwhelmingly targets BLE; its empirical anchors do not transfer cleanly to BR/EDR. The v1.1 architecture must produce its own empirical anchors for the BR/EDR primitives, which is what §5's pre-corpus measurement campaign exists to deliver.

## Section 2 — Feature Set Reduced to RSSI-Variance-Primary Plus BR/EDR-Native Co-Signals

Of the four features in the v1.0 proposal, only `rssi_variance_normalized` carries weight in the v1.1 architecture. The literature anchors that support it are: Faragher and Harle (IEEE JSAC 33(11), November 2015) reporting "30 dB drops in power across just 10 cm" with deep fades occurring at different positions on each of the three BLE advertising channels, which means even sub-centimeter hand tremor will produce RSSI excursions when the device traverses a deep fade; Cotton et al.'s 2.45 GHz off-body channel study (IEEE 2011) showing stationary line-of-sight RSSI variation typically within 0.5 dB of a log-distance path-loss model and substantial widening under body-NLOS; Sulaiman et al. (Sensors 2021, MDPI 21/16/5405) reporting approximately 5 dBm RSSI distortion under body shadowing with positioning-error degradation around 67%; and Wei et al. (arXiv 1904.03968) reporting that on-body signals exhibit larger RSS variance than off-body signals in the walking state. These anchors are directionally promising for the held-versus-placed discrimination that L8 needs but they do not directly answer the specific empirical question — what is σ_RSSI for a held-by-hand DualSense Edge versus a placed-on-table DualSense Edge at identical position, distance, orientation, and RF environment — which §5 lists as the primary empirical unknown.

The BR/EDR-native co-signals that v1.1 admits but downgrades to co-signal status (never primary discriminator) are: `tpoll_variance` (the BR/EDR analog of the dropped `connection_interval_jitter`), with no published anchor establishing that BR/EDR poll-interval jitter is per-device or per-session stable, marked as empirical unknown in §5; `afh_normalized_retransmission_rate` (the AFH-aware reframing of `retransmission_rate`), where the dominant variance source is environmental rather than human-presence — multiple INL and academic studies (INL/RPT-23-74719 2023, Raza et al. MDPI Sensors 2021, eAFH arXiv 2112.03046) report 97–99.5% link-layer reliability typical and WiFi co-channel interference as the dominant modulator. The v1.0 phrasing that captures the structural problem — "a WiFi router being moved 1 m would produce more retransmission-rate change than a controller transitioning from held-in-hand to placed-on-table" — explains why this feature is at best a co-signal.

The dropped feature is `advertisement_period_drift`, removed entirely from the v1 feature set because BR/EDR has no advertising. Reintroduction would require either pivoting calibration to a BLE-HOGP controller (Xbox Wireless v5+ per Bluepad32 documentation, or a BLE keyboard) — a strategic choice with downstream implications for the controller-grade hardware story — or scoping v1 to BR/EDR controllers exclusively. The v1.1 architecture chooses the latter.

The physical-layer features used by Givehchian et al. (CFO, IQ-offset, IQ-imbalance) are not part of the v1 feature set because they require SDR-grade capture hardware (the wcsng.ucsd.edu/files/sp22_paper.pdf measurement methodology uses USRP-class equipment, not commodity USB BT dongles), which is incompatible with the LAN-tower witness scope described in §4. They are flagged as a candidate for v2 if SDR witness hardware is justified by the v1 detection performance.

## Section 3 — Threat Anchor Narrowed to Cloud-Gaming-Bot Stealth Pattern

The v1.0 threat-model framing was "spatial co-presence attestation" — broad enough to intersect substantial prior art across IoT proximity attestation, co-presence pairing protocols, and TPM-anchored witness schemes. The v1.1 architecture narrows the threat anchor to a specific, concretely documented attack class: the cloud-gaming-bot stealth pattern. A real DualSense Edge sits on the player's desk, paired to and emitting plausible BR/EDR traffic to a local host. Simultaneously, a remote operator drives the input pipeline upstream — through Parsec, a custom RPC, a modified game client, or a cloud-gaming-side userscript injected into the WebRTC data channel — producing inputs at the game layer that arrive without any corresponding RF event at the witness's BR/EDR scan.

The concrete documented instances supporting this attack class are: the Greasy Fork userscript "WormVision Lite MAX – Full ESP + Aimbot UI (CloudSafe/Chromebook)", published 2024-12-26, self-described as running on Xbox Cloud Gaming; NVIDIA's own published "Guide: Making Your Anti-cheat Compatible with GeForce NOW" at developer.geforcenow.com, which explicitly concedes cloud-gaming clients are a distinct attestation surface from kernel anti-cheat that runs server-side on the rendering host; and the Activision Team RICOCHET Season 02 update (callofduty.com/blog/2026/02/call-of-duty-black-ops-7-ricochet-anti-cheat-season-02), which describes moving toward behavioral input-pattern detection on the input-stream side because hardware detection of devices designed to "hide, adapt, and change configurations" has been defeated.

The confirmed industry blind spot is established by the 2024 ARES paper "If It Looks Like a Rootkit and Deceives Like a Rootkit" (DOI 10.1145/3664476.3670433), which audits BattlEye, Easy Anti-Cheat, FACEIT AC, Vanguard, and Tencent ACE and confirms that none performs BT-native attestation, none collects radio-layer evidence, none runs a witness scan from a separate machine, and none anchors a co-presence proof to a public ledger. The L8 v1.1 layer is positioned in this confirmed gap.

The differentiator from BlueShield (Wu et al., RAID 2020) is on three axes: BlueShield is a static-IoT spoof detector while L8 is a dynamic-gaming-session presence prover; BlueShield produces local detection events while L8 produces portable on-chain commitments; BlueShield's two-collector architecture is positioned against single-source SDR replay while L8's three-witness composition (controller emission, host reception, independent witness scan) is positioned against the cloud-gaming-bot stealth pattern where the controller's own emission is plausible but the upstream input timing is not.

## Section 4 — Novelty Claim Split: Detection Floor Versus Forensic Layer

The v1.0 proposal equivocated on whether on-chain TWC commitment improved detection. The v1.1 architecture splits the novelty claim into two clean components and treats them separately.

The detection-capability component inherits the BlueShield published baseline as a floor: 5.84% FN on CFO inspection, 8.72% FN on RSSI inspection, 2.37% combined FP across the three-inspection composition. On-chain anchoring does not improve these floors. Any reviewer who collapses the L8 argument by pointing at BlueShield's numbers is correct on the detection axis; the v1.1 architecture concedes this rather than equivocates around it. The v1 detection performance must demonstrate measurable improvement *or parity* against this floor on the BR/EDR transport — which BlueShield does not directly cover — but it should not claim improvement on the inspection axes BlueShield already characterizes.

The forensic and governance component is where the v1.1 architecture locates the genuine novelty. The on-chain TWC commitment provides three properties that BlueShield's local-detector model structurally does not: cross-tournament portability of witness signatures (a witness attestation is verifiable by parties not in the original trust chain, including parties who arrive months later); non-repudiable temporal ordering (a forensic anchor for adjudication disputes that can be checked against the public ledger long after the session ends); and governance hooks that local detectors cannot produce (tournament organizers, league bodies, and arbitration panels can each operate against the same canonical attestation record without a custodial trust assumption). The novelty claim in v1.1 explicitly lives on this axis, not on the detection axis. Whitepaper, prototype documentation, and external-review framing must respect this split. The mistake the v1.0 proposal made — implying that on-chain anchoring improves detection — is the equivocation v1.1 exists to prevent.

The constraint envelope on what L8 v1 *claims* is, accordingly: L8 v1 produces session-bound presence attestation with detection performance that inherits BlueShield-class floors and a forensic layer that BlueShield does not provide. L8 v1 does not claim cross-session controller identity, does not claim improvement over BlueShield on detection axes BlueShield characterizes, and does not claim defense against attackers who have full controller-firmware compromise plus three-position-coordinated SDRs with channel-aware pre-distortion (attack pattern (i) in the canonical anchor's three-attack evaluation, which is at most partially closed by any composition inheriting BlueShield's floors).

## Section 5 — Empirical Unknowns: Pre-Corpus Measurement Required

The literature does not answer the following questions for the specific deployment, and each must be resolved by pre-corpus measurement before the first calibration capture session.

The σ_RSSI gap between held-by-hand and placed-on-table for a stationary DualSense Edge at 1 m, 3 m, and 5 m, sampled at the maximum rate the BlueZ-attached USB BT dongle exposes via HCI Read_RSSI, in a controlled low-WiFi-interference environment. The literature gives σ ≈ 2–4 dB stationary indoors at <3 m line-of-sight, climbing to 4–8 dB at >10 m, but does not give the held-versus-placed delta that L8's primary discrimination axis depends on. Required: ≥30-second windows, ≥5 sessions per condition per player, with explicit logging of orientation and the AFH channel map snapshot at each session.

The Tpoll variance distribution for the DualSense Edge over BR/EDR across host BT stack versions and adapter chipsets — Linux BlueZ on the witness tower, Windows BTHPORT on the host, Intel AX210/AX211 versus Realtek versus CSR dongles — including the temperature-drift sensitivity that Givehchian et al. document for CFO (a +10 °C internal rise during GPU-intensive gameplay produced a 7 kHz CFO shift, larger than the 9.12 kHz cross-population σ). An analog characterization for poll-interval drift is required.

The retransmission-rate baseline as a function of WiFi co-channel load with controlled WiFi neighbors on Channels 1, 6, and 11. This establishes whether `afh_normalized_retransmission_rate` retains any human-presence SNR after subtracting the WiFi-coexistence component.

The same-model separability for N≥3 identical DualSense Edges in the same RF environment. Givehchian et al.'s intra-Apple FPR (1.91% Apple-vs-Apple versus 0.62% across all devices) is the published anchor; N≥3 identical controllers in a tournament-realistic RF environment is materially harder than the 162-device heterogeneous study. The v1.1 architecture's explicit claim that L8 v1 attests session-bound presence only — and defers cross-session controller identity until a same-model separability study is completed — depends on this measurement establishing the bound.

The cross-correlation lag between USB-HID-side (host, Tier-A clock) and BT-air-side (witness, Tier-B clock) timestamps for the same input event, and its session-stationarity. The cloud-gaming-bot stealth detection in §3 depends on the witness's RF-observed input timing being correlatable to the host's claimed input timing; the cross-correlation lag is the structural parameter that determines detection sensitivity for the network-mediated remote-operator attack pattern.

Whether the on-chain TWC commitment leaks side-channel timing or metadata in a way that reduces effective spoof cost. This is a privacy-and-security question the canonical anchor flagged but did not resolve; v1.1 explicitly defers it to a privacy review before mainnet anchoring.

## Section 6 — Stage Gates and Timeline (6 Months Minimum)

The canonical anchor establishes a three-stage progression of approximately 24 weeks before first calibration capture.

**Stage 1 (Weeks 1–6): Architecture revision, not data capture.** This document is the Stage 1 deliverable. It re-derives the four L4 features against BR/EDR primitives, drops `advertisement_period_drift`, decides DualSense BR/EDR as the calibration target rather than pivoting to a BLE controller, and establishes the witness-host trust chain (TPM-backed witness signing key on the LAN tower for v1; Play Integrity / App Attest deferred to v2 with mobile witness).

**Stage 2 (Weeks 7–14): Pre-corpus empirical measurement.** The seven empirical unknowns in §5 are resolved by measurement campaigns in a controlled RF environment. No production calibration data is collected during this stage. The output of Stage 2 is an empirical-anchor document that supplements the canonical anchor and provides the missing literature-tier numbers for the BR/EDR transport.

**Stage 3 (Weeks 15–24): Adversarial validation as original red-team work.** This stage is the order-of-magnitude budget correction the v1.0 proposal got wrong. Stage 3 is not a sanity check measured in weeks; it is original red-team protocol research measured in months. The work consists of: a KNOB-class encryption-entropy-downgrade attempt against the test DualSense pairing (the Antonioli et al. 2019 PoC works on standard chips); a single-SDR RSSI replay against a single witness, then against three witnesses geometrically separated, to measure whether the triple-witness geometry yields the multiplicative FN improvement the architecture claims; and a Parsec-mediated input-replay reproduction of the cloud-gaming-bot stealth pattern, with the controller paired locally and the operator remote, to test attack pattern (iii) closure with both USB-side and BT-side traces. The Parsec-mediated reproduction has no published methodology — Activision RICOCHET Season 02 is doing behavioral input-pattern detection against this attack class on the input-stream side, but no public work does the radio-witness side. The methodology has to be invented, documented, and replicated before Stage 3 counts as adversarial validation. The first N≥3 production calibration capture happens only after Stage 3 completes.

The condition under which the timeline compresses to approximately 6 weeks — explicitly enumerated in the canonical anchor — requires four concessions: that the σ_held vs σ_placed gap is answerable from existing internal data without a new measurement campaign; that the DualSense BR/EDR vs BLE-controller decision is already made (this v1.1 document makes it: BR/EDR with the renamed feature set); that mobile witness is dropped from v1 scope (this v1.1 document makes it: deferred to v2); and that the TWC commitment is accepted to inherit BlueShield-class FN floors rather than improving on them (this v1.1 document makes it: detection inherits, novelty lives in the forensic layer). Of the four required concessions, this v1.1 document makes three; the fourth — that σ_held vs σ_placed is answerable from existing data — is unlikely to hold because the existing USB calibration corpus did not capture wireless RSSI under controlled held-versus-placed conditions. The 6-month timeline therefore stands as the operative recommendation.

## Section 7 — Constraint Envelope

L8 v1 claims session-bound presence attestation only. L8 v1 does not claim cross-session controller identity; that claim is deferred until a same-model separability study for N≥3 identical DualSense Edges is completed and the bound from §5 is known. L8 v1 detection performance is measured against the BlueShield published baseline (5.84% FN CFO inspection, 8.72% FN RSSI inspection, 2.37% combined FP across the three-inspection composition) on the BR/EDR transport, with parity as the success criterion rather than improvement on detection axes BlueShield characterizes. L8 v1 novelty lives in the forensic and governance layer (cross-tournament portability of witness signatures, non-repudiable temporal ordering for adjudication, on-chain TWC commitment as portable attestation record); the detection-axis novelty claim is explicitly *not* made. The witness device for v1 is LAN-tower-only (BlueZ + USB BT dongle + Python wrapper); mobile witness is structurally degraded by iOS Core Bluetooth API constraints and Android raw-HCI inaccessibility, and is deferred to v2. Capture-session planning is gated on Stage 2 (pre-corpus measurement) being complete and the empirical unknowns in §5 resolved.

## Section 8 — References

Givehchian, H. et al. "Evaluating Physical-Layer BLE Location Tracking Attacks on Mobile Devices." IEEE Symposium on Security and Privacy, 2022. wcsng.ucsd.edu/files/sp22_paper.pdf.

Wu, J. et al. "BlueShield: Detecting Spoofing Attacks in Bluetooth Low Energy Networks." RAID 2020. usenix.org/system/files/raid20-wu.pdf.

Wu, J. et al. "BLESA: Spoofing Attacks against Reconnections in Bluetooth Low Energy." USENIX WOOT 2020 (Best Paper). usenix.org/conference/woot20/presentation/wu.

Antonioli, D., Tippenhauer, N. O., Rasmussen, K. "The KNOB is Broken: Exploiting Low Entropy in the Encryption Key Negotiation Of Bluetooth BR/EDR." USENIX Security 2019. knobattack.com.

Antonioli, D., Tippenhauer, N. O., Rasmussen, K. "BIAS: Bluetooth Impersonation AttackS." IEEE Symposium on Security and Privacy, 2020.

Garbelini, M. E. et al. "SweynTooth: Unleashing Mayhem over Bluetooth Low Energy." USENIX Security 2020. github.com/Matheus-Garbelini/sweyntooth_bluetooth_low_energy_attacks.

Faragher, R., Harle, R. "Location Fingerprinting With Bluetooth Low Energy Beacons." IEEE Journal on Selected Areas in Communications, 33(11), November 2015.

Cotton, S. L. et al. "An experimental study on the impact of human body shadowing in off-body communications channels at 2.45 GHz." IEEE 2011.

Sulaiman, B. et al. "Landmark-Assisted Compensation of User's Body Shadowing on RSSI for Improved Indoor Localisation with Chest-Mounted Wearable Device." Sensors 21(16):5405, MDPI 2021.

Wei, Y. et al. "Towards Motion Invariant Authentication for On-Body IoT Devices." arXiv 1904.03968.

Raza, M. et al. "Bluetooth Low Energy Interference Awareness Scheme and Improved Channel Selection Algorithm for Connection Robustness." Sensors 21(7):2257, MDPI 2021. PMC8037550.

"If It Looks Like a Rootkit and Deceives Like a Rootkit: A Critical Examination of Kernel-Level Anti-Cheat Systems." ARES 2024. DOI 10.1145/3664476.3670433.

Activision Team RICOCHET. "RICOCHET Anti-Cheat™ Update – Season 02." callofduty.com/blog/2026/02/call-of-duty-black-ops-7-ricochet-anti-cheat-season-02. February 2026.

Greasy Fork userscript "WormVision Lite MAX – Full ESP + Aimbot UI (CloudSafe/Chromebook)." Published 2024-12-26. greasyfork.org/en/scripts/517058.

NVIDIA. "Guide: Making Your Anti-cheat Compatible with GeForce NOW." developer.geforcenow.com/learn/guides/guide-make-anti-cheat-cloud-compatible.

Bossi, A., Mellia, M., Trevisan, M. "A Network Analysis on Cloud Gaming: Stadia, GeForce Now and PSNow." arXiv 2012.06774.

Linux mainline kernel `drivers/hid/hid-playstation.c`. Roderick Colenbrander, Sony Interactive Entertainment. Mainlined Linux 5.12, April 2021.

Bluepad32 project FAQ. bluepad32.readthedocs.io/en/latest/FAQ/.

BlueRetro reverse-engineering project. Hackaday.io project 170365 (darthcloud).

PCGamingWiki Controller:DualSense Edge. pcgamingwiki.com/wiki/Controller:DualSense_Edge.

FreeBSD Forums thread 80786 — "PlayStation 5 DualSense controller pairing."

Canonical anchor: `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`.

Companion lesson: `lessons.md` entry `BT-CALIB-LESSON-001`.
