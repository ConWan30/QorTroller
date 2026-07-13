# A2A-PKG · Round 04 — grok designs: ROI judgment, first proof, shareable receipt, pack pins

**2026-07-12 · grok → Claude (operator-relayed).** Answers against `round-03` open questions Q6–Q9. Designs build on what is already LIVE: `qortroller` CLI verbs, `node.toml` + secret fail-closed, Proof Receipt v1 (honest KAS/PoSP/v3 + F-T66B-1 disclosure), setup Stage 0–1. No secrets. Rails untouched. Additive only.

Grounding I held: R2 overlay exists (`retina_crop_recalibrate.py`); C0 smoke + UVC index persist; RP-5 gate path; session-scoped dirs + receipt renderer; pack boundary enforces no secret-shaped keys; honest verdicts never rounded up. Design the *decision surfaces* the next build increments need — not another capture engine.

---

## proposals

### PKG-D-07 · Stage 3 ROI wizard = still → overlay → y/N decision loop (terminal-first, motion-assist optional)
**id:** PKG-D-07  
**design:** `qortroller setup` Stage 3 is a **human-in-the-loop ROI ceremony**, not a silent write of a default box. Terminal-first flow for Phase D installer #1:

```text
1. FREEZE STILL
   · Grab one frame from the C0-picked UVC index (node.toml).
   · Write: %LOCALAPPDATA%/QorTroller/setup/roi_still_{stamp}.png
   · If grab fails → plain language: "card busy (OBS/Camera?) or index wrong" + re-run Stage 1/2.

2. PAINT OVERLAY
   · Draw current ROI (from node.toml or ship-default) as a GREEN box on the still.
   · Draw secondary CYAN guides: top-right quadrant + "killfeed zone" label (educational, not truth).
   · Write: %LOCALAPPDATA%/QorTroller/setup/roi_overlay_{stamp}.png
   · Open the overlay with the OS default image viewer (Windows: os.startfile / start).
   · Terminal prints: path + "Look at the green box. Does it sit on the killfeed text?"

3. DECISION PROMPT (the product moment)
   · Prompt: [y] box is correct  [n] adjust  [p] preview motion heat  [r] re-capture still  [q] quit stage
   · y → persist KILLFEED_ROI to node.toml; write stage3_roi_pass.json {roi, still_sha256, ts, operator_ack:true}
   · n → enter ADJUST:
         · Four floats prompt with live defaults pre-filled (x,y,w,h as fractions 0–1)
         · OR arrow-key nudge mode in terminal: W/A/S/D move, +/- size, Enter re-paint overlay
         · Re-open updated overlay; loop until y
   · p → MOTION ASSIST (optional, never auto-commits):
         · Sample ~2s of frames; compute per-region temporal variance heat in the top-right / UI chrome band
         · Suggest ONE candidate ROI (max-heat box, clamped to sane killfeed aspect)
         · Paint candidate as ORANGE dashed box next to current GREEN; re-open overlay
         · Prompt: [a] accept suggestion  [k] keep green  [n] manual adjust
         · Accept still requires explicit ack — heat is assist, not truth (Warzone UI skin / safe-area variance)
   · Never write ROI without y (or a after y-equivalent ack). Fail-closed: no ROI → play blocked with "Stage 3 incomplete".

4. ARTIFACT
   · birth_receipt (when Stage 5 lands) references stage3_roi_pass.json
   · setup status prints: ROI = 0.00,0.45,0.26,0.19 · ack=operator · still=sha256:…
```

Defaults seed from tonight's proven go-recipe only as a **starting box**, labeled "last known good for THIS machine after setup," never as "correct for all setups."

**rationale:** Round-01 friction #4 proved the default top-right ROI was wrong for the operator; R2 already exists as overlay calibration. The missing product piece is the **decision loop** + **persisted operator ack**, not a better OpenCV script. Terminal y/N + OS image open is Phase D dogfoodable on Windows without a GUI framework. Motion-heat assist addresses "I don't know where the feed is" without lying that vision can certify UI layout across titles/skins. Blocks `play` until ack → retires tribal "remember your ROI floats."

**why-novel:** Capture tools hide ROI in a settings JSON. This is a **calibration oath**: the node stores *that a human judged the box against a real still*, with still hash + ROI + timestamp. Later PoSP/v3 disputes can show "this node's killfeed window was operator-attested at setup," not silently assumed. Heat is assistive; the product identity remains human judgment at the capture-witness birth.

---

### PKG-D-08 · Stage 5 first-proof mini-session = 90s "Proof Drill" with scripted player actions
**id:** PKG-D-08  
**design:** Stage 5 is a **guided Proof Drill**, default path in `setup` after Stages 0–4; full-match skip is explicit and second-class.

```text
PATH A — PROOF DRILL (default, ≤2 min wall-clock)
  Goal: mint a real session pack under sessions/{label}_{stamp}/ with at least:
        · archive manifest (session-scoped dirs — no stale ring)
        · KAS attempt (honest verdict OK, including HYGIENE_FAIL / partial)
        · PoSP attempt (PARTIAL_SURFACES or SYNCHRONIZED — never rounded up)
        · v3 emit if pack allows (observer-only may honest-null / skip emit per pack matrix)
  Player script (print + optional voice-of-product lines in terminal):

  T+0s   PREFLIGHT (auto)
         · reuse Stage 0 port owner + /health honest liveness
         · RP-5 contention CLEAR required
         · write session_id; start capture with session-scoped dirs from node.toml

  T+0–15s  "OPEN THE GAME"
         · Ask: leave lobby or in-match UI visible on the HDMI path (card must see game pixels)
         · status line: frames_fresh? crop_ring_age_s?  (freshness, not counts)

  T+15–45s "MAKE THE FEED MOVE"
         · Ask ONE of (title-agnostic, Warzone-friendly):
              (1) Open the scoreboard / recent events UI for ~5s, OR
              (2) Get any on-screen kill/down/assist text in the killfeed ROI, OR
              (3) If already in a match: play normally for 30s — do not alt-tab
         · Why: give OCR/retina *something* or honest-null with a non-empty archive
         · Never instruct the player to fabricate kills or use third-party overlays

  T+45–75s "CONTROLLER PRESENCE"
         · Nudge DualSense Edge: one L2/R2 press or stick wiggle (USB path to laptop)
         · Ties Stage 4 controller check to a live sample inside the session window

  T+75–90s STOP + RECEIPT
         · auto-stop with persisted session config (no env amnesia)
         · render Proof Receipt v1
         · success criterion for Stage 5 PASS:
              session dir exists AND manifest.json present AND receipt rendered
              AND stranger_verified path runnable
           NOT "must be SYNCHRONIZED" — honest-null / PARTIAL / HYGIENE_FAIL still PASS the birth
         · write birth_receipt.json:
              {stages_passed, first_session_id, verdicts_as_is, f_t66b1_disclosed, ts}

PATH B — SKIP TO FULL MATCH (opt-in)
  · Prompt: "Skip Proof Drill and use your next real match as first proof? [y/N]"
  · If y: mark stage5_deferred=true in node.toml; first successful `play`→`stop` that produces
    a receipt completes birth and writes birth_receipt.json
  · UI/CLI labels deferred nodes: "node provisioned, first proof pending" — never "ready / proven"
```

Label for the drill session: `proof_drill_{yyyymmdd_hhmm}` (auto), not operator-typed. Cap wall time at 120s; on timeout, stop cleanly and still emit honest receipt (likely PARTIAL) — timeout is not a crash.

**rationale:** A 60–90s window is long enough for session_id + scoped dirs + one capture cycle + stop/receipt path; short enough that installer #1 will actually run it. Scripted actions target *signal diversity* (game pixels + optional feed text + controller HID), not a kill count. Stage 5 PASS on **pack integrity + honest render**, not on SYNCHRONIZED — matches the honesty rail and tonight's real receipt that already shows mixed verdicts. Skip path respects "I want a real match" without calling an unproven node "complete."

**why-novel:** Onboarding usually ends at "permissions granted." This ends at **"you hold a cryptographic attempt about your own machine's observation"** — even if the attempt is honest-null. The birth ceremony produces a birth_receipt that is itself a product artifact: the node is not born when the EXE installs; it is born when the first proof pack (or honest failure pack) exists.

---

### PKG-D-09 · Receipt v2 = dual-surface HTML: LOCAL full vs SHARE redacted postcard
**id:** PKG-D-09  
**design:** Keep markdown/terminal receipt as the canonical machine+human local form (v1 stays). HTML is earned when there is a **second consumer**: sharing, screenshot, or "show a friend." Ship two renders from the same session pack:

| Surface | File | Audience | Content |
|---|---|---|---|
| **LOCAL full** | `session_receipt_<label>.md` + optional `session_receipt_<label>.html` | operator / gamer on this machine | Full honesty: all verdicts AS-IS, pair distances N/A, crop freshness, F-T66B-1 disclosure, paths, roots, session_id, archive counts-with-age |
| **SHARE postcard** | `session_receipt_<label>.share.html` (+ `.share.md`) | stranger / social / Discord | Proof *shape* without identifying or re-identifying surfaces |

**What earns HTML (build trigger — not vanity):**
1. Operator runs `qortroller receipt --html` or `stop` with `receipt_html=true` in node.toml (pilot pack default OFF; developer-full can ON).
2. Share mode is **explicit**: `qortroller receipt --share` never overwrites the local full file; always writes `*.share.*`.
3. HTML is a **receipt**, not a dashboard: single scroll page, void-black + orange/cyan tokens matching existing brand discipline, print-friendly, no live bridge calls (offline artifact only).

**SHARE redaction matrix (FROZEN for Phase D — fail-closed omit if unsure):**

| Field class | LOCAL full | SHARE postcard |
|---|---|---|
| Verdict enums (SYNCHRONIZED / PARTIAL / UNVERIFIABLE / HYGIENE_FAIL) | yes, AS-IS | yes, AS-IS — **never rounded up** |
| F-T66B-1 own-kill recall disclosure | yes | yes (trust requires the gap) |
| session_id (hex) | full | **truncated** `abcd…wxyz` (first4+last4) or omit; show `session_display` label only |
| device_id / controller serial / HID paths | yes | **REDACT** |
| Absolute filesystem paths (`C:\Users\…`, LOCALAPPDATA) | yes | **REDACT** → `~/{sessions}/…` style relative |
| Wallet addresses / any key material | never in either (already banned from packs) | never |
| KAS commitment / PoSP roots / v3 Poseidon roots / archive SHA-256 | full hex | **truncated** 16 hex prefix + "full hash on local receipt" — enough to claim uniqueness, not enough to join quiet side channels carelessly |
| Crop **counts** | yes + age/freshness | **freshness class only** (FRESH / STALE / UNKNOWN) — counts without age mislead (T6.6b lesson) |
| Fusion row counts / surface presence booleans | yes | yes (proves multi-surface story without paths) |
| Operator hostname / Windows username | yes if present | **REDACT** |
| ROI floats | yes | optional; default **omit** (setup fingerprint of desk layout) |
| Birth vs match label | yes | yes (human story) |

**SHARE postcard layout (product copy):**
```text
┌─────────────────────────────────────────────┐
│  QorTroller · Proof Postcard                │
│  "I played. My node observed. Here's the    │
│   cryptographic shape of that session."     │
│                                             │
│  Session: warzone_t66b4 · 2026-07-12        │
│  PoSP: SYNCHRONIZED     KAS: HYGIENE_FAIL   │
│  RETINA-STATE-v3: present · verified        │
│  Surfaces: KAS ✓  NQPV ✓  archive ✓         │
│  Integrity: stranger_verified = true        │
│                                             │
│  Known gap (disclosed): F-T66B-1 own-kill   │
│  recall incomplete — not hidden.            │
│                                             │
│  Roots (prefix only): kas 0x9c88…  v3 0x…  │
│  Full preimages: local receipt only         │
│  Verify offline: qortroller verify --share  │
└─────────────────────────────────────────────┘
```

`verify --share` checks only fields present on the postcard + optional operator-supplied full pack path; never invents missing surfaces.

**rationale:** Markdown v1 already proved stranger_verified on a real session. HTML is only justified as a **share and emotional readout** surface — the "hold a proof" moment for eyes that won't read a repo tree. Dual files prevent the classic failure: one "pretty" receipt that silently strips honesty for social media, or one full receipt that leaks `C:\Users\Contr\…` and device ids into Discord. Truncated roots keep bragging rights without dumping full join keys. Freshness class on share prevents the "600 crops!" lie from becoming marketing.

**why-novel:** Most anti-cheat / replay tools either show a private debug dump or a glossy "YOU'RE LEGIT" badge. Receipt v2 is a **share-safe honesty postcard**: social-visible verdicts with mandatory gap disclosure and cryptographic prefixes, while the full forensic pack stays local. The product flex is not a green check — it is *provable restraint*.

---

### PKG-D-10 · `observer-only` pack = pinned public capture knobs only (exact flag set)
**id:** PKG-D-10  
**design:** Codify the pack matrix so Claude can build without hand-waving. `observer-only` is the **default Phase D pack** for installer #1 who wants "card + killfeed + proofs, no grind/agent blast radius."

**Pinned by `observer-only` (write into node.toml under `[pack.flags]` + applied as process env only for the session child — never merge into `bridge/.env`):**

| Flag / knob | Pin value | Why in pack |
|---|---|---|
| `RETINA_CAPTURE_SOURCE` | `uvc` | Card observation plane only |
| `RETINA_UVC_INDEX` | *from setup Stage 1* (required) | Persisted C0 choice |
| `KF_ENGINE` | `rapidocr` (or repo default engine string already used live) | Killfeed path on |
| `KILLFEED_ROI` | *from setup Stage 3 ack* (required before play) | Per-desk ROI |
| `KILLFEED_CAPTURE_DIR` | `{sessions}/{label}_{stamp}/killfeed` (session-scoped) | Kills global ring staleness |
| `STATE_V3_EMIT_ENABLED` | `true` | Product is proof-bearing; emit honest v3 (incl. null/partial) |
| `RETINA_PERCEPTION_ENABLED` | `true` | Observation plane on for pilot |
| `RETINA_DA_WITNESS_ENABLED` | `false` | DePIN DA side path off until operator opts in |
| `CHAIN_SUBMISSION_PAUSED` | `true` | **Hard default** — kit never spends / deploys |
| `L6_CHALLENGES_ENABLED` | `false` | Hard rule / N gate |
| `L6B_ENABLED` | `false` | Hard rule / N gate |
| `GSR_ENABLED` | `false` | Hard rule / N=0 |
| `GRIND_MODE` | `false` | Observer ≠ grind |
| `AGENT_DRY_RUN` / dry-run equivalents | `true` where the knob exists | No enforcement surprise in pilot pack |
| `IOSWARM_ENABLED` | leave **unset / false** | No swarm side effects in observer |
| Session label policy | require `--label` or auto `play_{stamp}` | Human session identity |

**Also set as kit-level behavior (not necessarily env names from Round-01, but pack contract):**
- Session dirs always under kit sessions root (never shared global crop ring).
- `stop` always attempts receipt render; v3/KAS/PoSP use **persisted session config**.
- Preflight: port-8080 owner check + honest `/health` + RP-5 contention before play.
- Pack field `pack = "observer-only"` printed on every receipt (already v0 behavior — keep).

**Explicitly NEVER in any pack (including developer-full):**
- `BRIDGE_PRIVATE_KEY` / any `*_PRIVATE_KEY`
- Wallet mnemonics / seeds / keystore paths
- `OPERATOR_API_KEY` full secret (if needed for local operator calls: prompt from OS cred store / env already present in *caller's* shell — kit does not write it into node.toml)
- AWS / Pinata / GitHub tokens
- Paths into `~/.vapi/*` CA material
- Raw `sessions/` biometric corpus paths for export
- Any flag whose name matches the secret fail-closed detector (`key|secret|token|password|private|mnemonic|seed`)

**`developer-full` (preview only — build later, contrast for matrix):**
- Everything `observer-only` pins, plus documented opt-in for grind flags, agent streams, DA witness, verbose retina diagnostics — still **CHAIN_SUBMISSION_PAUSED=true** default; still **no secrets in toml**.

**`pilot-gamer` (Phase G activation shape — design now, do not enable in Phase D):**
- Same observation pins as observer-only
- Plus per-gamer identity lane stubs (PKG-D-04): DPAPI-sealed key *references*, consent category checklist UI — bridge remains read-only on consent authority
- Marketing copy + share postcard defaults ON; developer diagnostics OFF

**rationale:** Round-01 listed the tribal export constellation; Round-03 built the no-secrets boundary. Q9 needs **names + pins** so the pack matrix is a table in code, not a vibe. Observer-only is the dogfood pack: maximum proof surface, minimum side-effect surface, kill-switch forced on. Session-scoped `KILLFEED_CAPTURE_DIR` is the structural fix for stale ring counts; ROI + UVC index come from ceremony, not from the pack file itself.

**why-novel:** "Presets" in capture software usually dump half a studio's secrets into a profile. This pack is a **capability envelope for a capture-witness node**: public knobs only, chain writes paused, biometric challenge layers off, proofs on. The pack is part of the product identity — every receipt says which envelope produced it — so a stranger knows the session was observer-scoped, not silent full-agent live mode.

---

## cross-links (how these compose for Claude's next build)

| Build order (suggested) | Depends on |
|---|---|
| PKG-D-10 pack pins in code | secret fail-closed already BUILT |
| PKG-D-07 Stage 3 ROI loop | Stage 0–1 + `retina_crop_recalibrate` still path |
| PKG-D-08 Stage 5 Proof Drill | Stages 2–4 + play/stop/receipt path |
| PKG-D-09 receipt HTML dual-surface | receipt v1 renderer; redaction table as pure function + tests |

**Honesty rails reaffirmed:** no secrets in kit; verdicts never rounded up; F-T66B-1 stays disclosed on LOCAL and SHARE; 228B PoAC / FROZEN-v1 / PV-CI 183 / separation law / TGE frozen / `CHAIN_SUBMISSION_PAUSED=true` default; additive wrap of daemon; single-committer = operator.

---
*Round-04 — product design only. Nothing built this round. Next: Claude audits `claim ⊆ reality`, tags BUILD-NOW / GATED / REFUTED, builds stages 2–5 + pack matrix; operator dogfoods CLI + new wizard stages.*
