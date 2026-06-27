---
type: synthesis
id: s-sidecar-capture-process-vs-device
title: Sidecar capture — a sidecar PROCESS can't give the capture its own GPU (one laptop GPU, shared with Remote Play's decoder; MEASURED ~13fps standalone-under-load = cross-process contention, refutes process-isolation a 2nd time). Lean mode already gives the CPU isolation. The VALID evolution is a sidecar DEVICE (own GPU: mini-PC / HDMI capture card / 2nd machine / L8 witness tower). Lean+on-demand is the best single-laptop software answer.
created: 2026-06-27T13:05:00Z
modified: 2026-06-27T13:05:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 40
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

OPERATOR IDEA (worth assessing carefully — the instinct is sound, the pattern is already in QorTroller via the
Arc 7 Decoupled Cryptographic Sidecar Pointer): run a SECOND "sidecar" bridge in parallel, collocated/sharing
lifecycle but logically separate, dedicated ONLY to WGC/retina/screen-proof capture, so the capture gets "a
unique amount of GPU" to hit its true FPS without the primary bridge + Remote Play crowding it.

THE HONEST REFUTATION (of the GPU premise specifically — measured this session, not assumed): a sidecar
PROCESS does NOT get its own GPU. The laptop has ONE physical GPU; Remote Play's VideoDecode engine and ANY
capturer's Copy/3D engines are time-sliced by the WDDM scheduler on that same GPU — cross-process, shared
memory bandwidth. We MEASURED it: a standalone subprocess capturing monitor-1 WHILE the bridge ran got ~13fps
(not the ~32 it gets alone), and capturing-while-Remote-Play-decodes lags the game REGARDLESS of which process
captures. That is exactly the cycle-46 process-isolation premise ([[s-retina-remote-play-process-isolation]]),
already refuted by live data. A 2nd GPU wouldn't trivially help either: WGC captures the DWM-composed desktop,
rendered by whichever GPU drives the display, so you can't easily pin capture to a different GPU than the
display. So a software sidecar cannot unlock the FPS or "source" dedicated GPU on this hardware.

WHAT THE SIDECAR WOULD HAVE GIVEN — ALREADY ACHIEVED BY LEAN MODE: the real win the sidecar promises is CPU /
fault isolation (keep the capture off the heavy primary). But the measured lag driver was the bridge's ~38%
CPU (agent fleet + 5.4GB DB + grind + provenance), NOT the capture — and PRESENCE_LEAN_MODE
([[s-presence-lean-mode-build-plan]]) already strips that to ~8-15% (system CPU 73%->43-50%, operator-confirmed
"much better"). With on-demand capture (no bursts during play) normal play is SMOOTH. So a sidecar process adds
little over lean+on-demand on this laptop, and nothing on the GPU axis.

THE VALID EVOLUTION (this is where the instinct is RIGHT): a sidecar DEVICE, not a sidecar process. To truly
give the capture its own GPU/resources, the capturer must live on SEPARATE silicon: (a) a mini-PC / SBC with
an HDMI capture card tapping the laptop's display output; (b) a second machine that itself runs Remote Play and
captures locally; (c) a capture on the PS5-side HDMI (full-rate frames, never touches the laptop's decode);
(d) generalizes the L8 BT-witness "LAN tower" — a dedicated, collocated witness DEVICE on the LAN. That is a
genuine sidecar (own GPU, own lifecycle, localhost/LAN networking to the primary) and it mitigates GPU sourcing
for real, at the cost of one piece of hardware. It also aligns the cycle-44 "native-PC for the lag pillar"
re-scope with the operator's Remote-Play commitment: the GAME stays on Remote Play; only the WITNESS moves to
dedicated silicon.

RECOMMENDATION: (1) ship lean + on-demand as the single-laptop answer NOW (smooth play + a deliberate proof
burst on request — the captcha model). (2) Do NOT build a sidecar PROCESS (it re-treads the refuted
process-isolation; one GPU). (3) Hold the sidecar DEVICE as the real headroom path when continuous full-rate
coupling is needed (tournament/cert tier): a small dedicated capture/witness box on the LAN, which also folds
in the L8 BT witness. The 4 controller-side pillars (USB, lean) run lag-free regardless. No FROZEN-v1 / 228B
PoAC / chain / IOTX. Related: [[s-retina-remote-play-process-isolation]], [[s-presence-lean-mode-build-plan]],
[[project_retina_phase0_live_starvation_finding]], [[recursive_verification_first_pattern]].
