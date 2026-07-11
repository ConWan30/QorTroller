# QorTroller — Pilot One-Pager for Tournament Organizers

**Audience:** small-event organizers running cloud- or Remote-Play-reachable matches who want an **advisory** integrity signal.  
**What this is:** one page you can read without us re-deriving state.  
**What this is not:** a ban handbook, identity product, token sale, or field-FAR certificate.  
**Banked sources (cite, do not re-derive):** [P0-B wedge](p0b-cloud-rp-wedge-thesis-2026-07-10.md) · [golden offline pack](golden-offline-authored-pack.md) · [consent/legitimacy](depin-consent-legitimacy-lane-2026-07-10.md) · [F2.x / D-F2X-1](f2x-residual-capture-contention-2026-07-10.md) · PoSP / PORT-CERT / VHR stack (paths in §Audit).

---

## Four ceilings (verbatim — never drop)

1. **Advisory soft-signal only, never a ban input.**  
2. **Offline deferred authored = the reliability path; live capture health = best-effort; self-starving criterion OPEN.**  
3. **`developer_self` scope — NO field-FAR, NO identity claims, NO population certification** (presence OP is **SEPARATED vs modeled auto only**; P1 was **MARGINAL_AIM**).  
4. **Testnet, no token, nothing purchasable.**

*(Same four bars as the operator brief / D-F2X-1 + P0-B §5 / DePIN §5.1 — restated here so the first outside reader cannot miss them.)*

---

## 1. The gap (why a wedge, not “replace kernel AC”)

When a match is played through **cloud streaming or Remote Play**, the game process often runs on a **remote host** the organizer and local kernel anti-cheat do not control. Kernel-class AC and host-root instrumentation need a trusted local game client; that path is **structurally unavailable** for pure remote-host play. Server-side systems still see a **streamed input stream**, not the controller as a physical source on the player’s desk.

**Source map:** structural gap framing only — [P0-B §2](p0b-cloud-rp-wedge-thesis-2026-07-10.md). Named vendor competitive claims (cloud platform docs, kernel product behavior, third-party cheat tools) are **cut** here unless re-sourced in-session; P0-B §5.3 flags those as the non-repo-verifiable class.

**QorTroller’s beachhead:** advisory **presence + kill-authorship** evidence at the **physical input ↔ rendered output** boundary on a capture path the player/operator can run — attestation that kernel AC cannot supply on cloud/RP-shaped clients. **Not** a claim that we replace host AC everywhere, catch all field cheats, or own prize enforcement.

---

## 2. What QorTroller attests (advisory only)

| Layer | What you can say today | Grade | Artifact / bank |
|-------|------------------------|-------|-----------------|
| **Session presence (PoSP)** | Multi-surface synchronized presence for a `session_id` (join across authorship / co-capture / archive) | Advisory · `developer_self` | `l9_presence/posp.py`; M14/M17 stack in P0-B §3.3 |
| **Kill authorship (KAS / deferred)** | Kill crops bound to controller fire on a **sealed archive** (post-match deferred path) | Reliability path = **offline deferred** + window pad | `l9_presence/kas_deferred.py`; [golden pack](golden-offline-authored-pack.md) |
| **Causal presence OP (P0-A v2)** | Pre-registered OP: aim-active **human** vs **modeled** full camera-injection automation → **SEPARATED** | Oracle **viability**, not field FAR | `audits/p0a-presence-op-v2-2026-07-09.json`: `verdict=SEPARATED`, `schema=p0a-presence-op-v2`, medians human **0.3738** / auto **0.0666**, `gap=0.3072` (P0-B rounds to 0.374 / 0.067 / 0.307) |
| **Below-threshold player (P1)** | Sole labeled player under the human floor on that aim-active set is **MARGINAL_AIM**, not automation | Honesty, not “every aimer passes” | `audits/p1-anomaly-diagnostic-2026-07-10.json`: `primary=MARGINAL_AIM`, `p0a_v2_separated_unchanged=true` |
| **Consent** | Gamer-sovereign category consent; bridge **read-only** on on-chain consent | Legitimacy axis — not a detection claim | [DePIN §4.1 / §5.2](depin-consent-legitimacy-lane-2026-07-10.md) |

**Organizer one-liner (four ceilings ride along):**  
> Advisory presence + authorship attestation for cloud/RP play — soft post-match signal, never a ban input, not a kernel-AC replacement.

---

## 3. What you get (package + re-run + re-check)

### 3.1 Per-session / per-match advisory package

- **Session certificate path:** PoSP + kill-authorship (live and/or **deferred**) + optional **PORT-CERT** portable match certificate schema `qortroller-match-certificate-v0` for off-rig re-verify.  
  - Demo artifact: `audits/match_certificate_m17.json` (`schema=qortroller-match-certificate-v0`).  
  - Builder: `l9_presence/port_cert.py`.
- **Optional chain digests (testnet only):** one demonstrated real **Groth16 VHR** replay proof accepted on IoTeX testnet — event class `ReplayProofVerified`, block **45479067**.  
  - Proof of record: `audits/vhr_proof2_m17/vhr_onchain_submission.json` (`block=45479067`, `method=… -> ReplayProofVerified`, `status=1`).  
  - Submit path: `scripts/submit_vhr_proof.py`.  
  - **Not** mainnet production AC.

### 3.2 Proof you can re-run without another match

```bash
python scripts/golden_offline_authored.py
```

**Only accept a green line equivalent to** ([bar F](golden-offline-authored-pack.md); runner prints these semantic fields — `scripts/golden_offline_authored.py`):

```text
GOLDEN OFFLINE AUTHORED PACK: PASS
  goldens=2 present=2 missing=0
  each: verdict=DEFERRED_AUTHORED_SESSION authored>=2 verify=OK session_id=joined pad_ms=4000
  scope=developer_self bounded_lag=true m18_excluded=true
  exit=0
```

**What is banked (exactly two goldens — do not inflate):**

| Golden label | Live KAS (as banked) | Deferred @ pad=4000 | Cite |
|--------------|----------------------|---------------------|------|
| `densecand_validate` | `INSUFFICIENT_KILLS` | `DEFERRED_AUTHORED_SESSION` authored=3 | [golden pack table](golden-offline-authored-pack.md) · script `GOLDEN[0]` |
| `match14_rp_option_b` | `INSUFFICIENT_KILLS` | `DEFERRED_AUTHORED_SESSION` authored=3 | same · `GOLDEN[1]` |

Live thinned crops → offline deferred recovery is the reliability story. **Missing golden ≠ pass** (exit 2). **M18-class >4 s lag is excluded** from the golden set (honest limit under pad=4000 — not papered over; pinned in pack + script docstring).

### 3.3 Third-party re-check story (honest composition)

| Surface | Third party can… | Cannot claim… | Path |
|---------|------------------|---------------|------|
| **PoSP** | Re-check session join / surface presence verdict | Host compromise resistance | `l9_presence/posp.py` |
| **PORT-CERT** | Re-verify portable cert off-rig (snarkjs/RPC checks are **injected** callables) | Capture independence / trustless host | `l9_presence/port_cert.py` · M17 cert above |
| **VHR (testnet)** | Confirm a real Groth16 replay proof was accepted on-chain once (demo path) | Population enforcement or mainnet product | `audits/vhr_proof2_m17/vhr_onchain_submission.json` |

---

## 4. What it does **NOT** claim (expanded non-claims)

Copy the **four ceilings** (§top) plus these inherited limits from P0-B §5 / golden pack / DePIN:

5. **Presence OP = SEPARATED vs modeled automation only** (synth full camera injection) — **not** field cheat-hardware rates (P2 not done).  
6. **P1 = MARGINAL_AIM** — not proof every aimer clears the human floor.  
7. **Aim-active only** on the OP — low-aim excluded by pre-registered gate; raw v1 pool was **INCONCLUSIVE** (kept in P0-B citation graph).  
8. **Bounded-lag authorship** — pad 4000 ms; M18 excluded from golden set.  
9. **Host not trustless** — portable proofs ≠ independent capture; EVENT-BIND (mechanism-proven) closes splice classes, **not** compromised host / **not** live-validated on all RP kill paths (P0-B §5.3).  
10. **Consent ≠ full legal erasure** of every offline copy; bridge never grants/revokes on-chain consent for the gamer (DePIN §5.2–5.3).  
11. **No “live path healthy” language** — live capture remains best-effort; self-starving criterion **OPEN** ([F2.x](f2x-residual-capture-contention-2026-07-10.md)). Do not sell live fps as solved.

---

## 5. Pilot ask (one game · N matches · soft-signal only)

| Knob | Pilot default | Bank |
|------|---------------|------|
| **Games** | **One** title (your competitive context) | P0-B §4.3 |
| **Mode** | Remote Play / cloud-adjacent client path | P0-B §4.3 |
| **Matches** | Small **N** (weekend cup / single bracket night) — not a league-wide hard gate | P0-B §4.3 |
| **Grade** | **Advisory only** — soft signal + post-match review packet; **never** sole prize / ban authority | Ceiling 1 |
| **Players** | Opt-in; gamer holds consent categories | DePIN |
| **Success** | Golden pack **exit 0** before citing; ≥1 portable cert re-check; **0 silent false “VERIFIED”**; honest PARTIAL / fail-closed when tools missing | Golden bar G + P0-B §4.3 |
| **Failure** | Any marketing that drops the four ceilings | Operator brief |

**What we need from you:** schedule + title + opt-in players + agreement that the signal is **review-only** for the pilot window.  
**What we bring:** session stack, deferred authorship reliability path, certificate + re-check path, claim ceilings in writing.

---

## Ops footnote (run before any organizer-facing claim)

| When | Do |
|------|-----|
| Before external demo / pilot handoff | `python scripts/golden_offline_authored.py` → **exit 0** only ([bars A–G](golden-offline-authored-pack.md)) |
| Reliability narrative | **Offline deferred authored** on sealed archives = reliability path; do **not** claim live path healthy / fixed |
| Live lag | Best-effort; self-starving criterion **OPEN** (D-F2X-1) — no 30 fps promise under all RP load |
| Consent language | “Gamer-sovereign; bridge reads only” — never “we manage consent for you” |
| Distribution | **Operator decides** who sees this page; Claude audits claim ⊆ repo before send |

---

## Audit map (Claude claim ⊆ reality)

| Claim in this page | Must resolve to |
|--------------------|-----------------|
| Four ceilings | Operator brief + §top (verbatim) |
| Structural cloud/RP gap | P0-B §2 (no named-vendor competitive claims) |
| SEPARATED OP numbers | `audits/p0a-presence-op-v2-2026-07-09.json` (exact medians/gap/schema/verdict) |
| P1 MARGINAL_AIM | `audits/p1-anomaly-diagnostic-2026-07-10.json` |
| Golden PASS line + goldens=2 | `scripts/golden_offline_authored.py` + `docs/golden-offline-authored-pack.md` bar F |
| Two goldens live→deferred recovery | Golden pack table (not “three consecutive” — **only two are in `GOLDEN`**) |
| PORT-CERT schema + M17 demo | `audits/match_certificate_m17.json` |
| VHR block 45479067 | `audits/vhr_proof2_m17/vhr_onchain_submission.json` |
| Consent bridge read-only | DePIN §5.2 + CLAUDE.md hard rules |
| Live self-starve OPEN | `docs/f2x-residual-capture-contention-2026-07-10.md` D-F2X-1 / §6 |
| No live-path-healthy language | §4 item 11 + ops footnote |

**Pre-empt fixes applied in this revision:** cut uncited “Ricochet” one-liner; cut “three consecutive” recovery claim (banked goldens = **2**); pin exact OP floats + audit JSON paths; add verbatim four-ceilings block; forbid “live path healthy.”

---

*Pilot organizer one-pager v0.1 (audit-preempt) — 2026-07-10. Loop: Grok design → Claude claim⊆reality audit → operator distribution decision.*
