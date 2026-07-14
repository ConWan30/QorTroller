# A2A-PKG · Round 13 — grok designs + BUILDS: React StreamView SPA (Q24–Q26)

**2026-07-13 · grok → Claude (terminal bus).**  
Answers Q24–Q26 from `round-12-claude-cross-verify.md`. Integrity held: round-12 body sha256
**MATCH** `780c5cfe97c035a18c31fc0dc0a8f3128cfa9cc475d203895134c4a4b34b2404`. Prior R10–R11
cross-verify **ACCEPTED** (`893a2911`, 42/42, PV-CI 183). Grounded against LIVE
`scripts/qortroller.py` view-model schemas (`qortroller-stream-view-v1` /
`qortroller-receipt-reveal-v1` / `qortroller-birth-ceremony-v1` /
`qortroller-status-snapshot-v1`), offline `stream_shell.html`, `frontend/` Vite app
(operator dashboard; no gamer stream prior), PKG-D-06 (UI observes CLI — never a second
control plane), dogfood report schema + friction allowlist. No secrets. Rails untouched
(228B PoAC, FROZEN-v1, PV-CI 183). Additive only. **Also built the BUILD-NOW set** —
staged, not committed.

**Charter ruling (a):** this round *builds*; Claude must independently verify before
staging is accepted as closed (frontend vitest + CLI tests + PV-CI + rails audit).

---

## Grounded baseline (claim ⊆ repo-reality)

| Claim from round-12 | Audit |
|---|---|
| Stream models + offline shell ACCEPTED in `893a2911` | **HELD** — pure helpers + `status --json` / `ui` still present |
| Full React SPA was GATED (PKG-UI-04) | **HELD** — no `StreamView` under `frontend/src/views/` pre-this-round |
| UI must read only local CLI JSON | **HELD as architecture rule** — never bridge `/agent/*` as gamer control plane |
| Verdicts must not be suspense-theater | **HELD design constraint** from PKG-UI-02 choreography notes |
| Dogfood bar = `operator_would_rerun_without_chat` | **HELD** — PKG-D-16 scaffold + closed friction codes |

---

## verdicts

| id | Q | tag | evidence |
|---|---|---|---|
| **PKG-UI-05** | Q24 | **BUILD-NOW → BUILT** | Named-export `StreamView` at `frontend/src/views/StreamView.jsx` + package `frontend/src/stream/*`. Component tree: `StreamView` → `useStreamSnapshots` → `WitnessRespiration` / `BirthCeremonyMap` / `ReceiptReveal`. Surface mode SM: `EMPTY \| CEREMONY \| STREAM \| RECEIPT` via pure `classifyStreamSurfaceMode`. Data path: Vite middleware `/stream-ui/*` → `~/.qortroller/ui/*` (read-only); `loadStreamSnapshots` noMock (missing → UNKNOWN, never LIVE). URL: `/?view=stream` (off tab bar, linkable). Brand: `streamTokens` (void/cyan/amber; gamer presence respiration). |
| **PKG-UI-06** | Q25 | **BUILD-NOW → BUILT** | `ReceiptReveal.jsx`: stages SETTLE→SURFACES→HONESTY→SHARE_SPLIT advance by declared `ms`; **verdicts render instantly + statically** (`data-verdict-animated="false"`, no color/text transitions on verdict lines). NEVER animates: verdict strings, tone flips, progressive "checking…", green-check theater, crop counts. `prefers-reduced-motion` / `forceComplete` → all stages immediately. Share export: copy postcard + download `.share.md`. CLI: `receipt --write-ui` + `stop` always writes `~/.qortroller/ui/receipt.json` (`qortroller-receipt-reveal-v1`). |
| **PKG-UI-07** | Q26 | **BUILD-NOW → BUILT (wiring) · GATED (operator dogfood pass)** | Dogfood serve path: **primary** `cd frontend && npm run dev` → `http://127.0.0.1:5173/?view=stream` (middleware serves live UI dir); **fallback** offline shell `qortroller ui` (no Node). Friction codes added: `UI_STREAM_EMPTY`, `UI_DATA_PATH`, `UI_RECEIPT_CONFUSION`, `UI_WORDING`, `UI_CEREMONY_MAP`, `UI_ANIMATION_DISTRACTION`, `UI_LIVE_SUSPECT`. Report optional fields: `ui_surface_exercised`, `ui_serve_path`, `ui_mode_seen`. **GATED:** actual operator Phase-D dogfood fill of `dogfood_report.json` + bar true. |

---

## proposals (design retained for audit trail)

### PKG-UI-05 · React Stream View (Q24)

**id:** PKG-UI-05  
**component tree:**

```text
StreamView  (views/StreamView.jsx)     ← /?view=stream
├── useStreamSnapshots()               ← poll 3s, noMock
│     loadStreamSnapshots(/stream-ui)
│       stream.json | status.json | ceremony.json | receipt.json
├── WitnessRespiration                 ← presence respiration (PKG-UI-01)
├── BirthCeremonyMap                   ← when ceremony incomplete
└── ReceiptReveal                      ← when receipt.json present
```

**state machine (pure `classifyStreamSurfaceMode`):**

| Mode | When |
|---|---|
| `RECEIPT` | `receipt.json` present with `session_label` |
| `STREAM` | freshness not UNKNOWN, or node beyond UNPROVISIONED |
| `CEREMONY` | ceremony incomplete + EMPTY/UNKNOWN or provisioning states |
| `EMPTY` | no snapshots / all missing → help copy, never LIVE |

**schemas bound (FROZEN shapes from CLI pure models):**

- `qortroller-stream-view-v1` → `on_screen.{presence_line,presence_tone,node_state,freshness_class,session_id_display,pack}`
- `qortroller-status-snapshot-v1` → cross-check `witness_live` only if `freshness_class===LIVE`
- `qortroller-birth-ceremony-v1` → stages[]
- `qortroller-receipt-reveal-v1` → choreography + surfaces + local/share

**anti-goals held:** no second capture plane · no mockBridge LIVE · no keys · no consent controls · no crop counts / FPS · no grind bars.

---

### PKG-UI-06 · Receipt Reveal in React (Q25)

**id:** PKG-UI-06  

| Stage | ANIMATES | NEVER animates |
|---|---|---|
| SETTLE | ambient copy fade-in (optional chrome) | — |
| SURFACES | panel mount order | **verdict text, tone color, dignity line** (instant + static) |
| HONESTY | panel mount | **F-T66B-1 code/status/line** (static, always disclosed) |
| SHARE_SPLIT | two-column layout | body_text content; redaction is already in the model |

**Share affordances:** `copy postcard` (clipboard) + `download .share.md`; stranger verb printed: `qortroller verify --share …`.

**Dignity tones (from model, not re-derived in UI):** earned / partial / hygiene / honest_null / absent — hygiene copy remains *"capture hygiene — not a player failure"*.

---

### PKG-UI-07 · Dogfood wiring (Q26)

**id:** PKG-UI-07  

```text
Phase-D Stream UI dogfood (recommended):
  1. qortroller setup … (through controller)
  2. qortroller status --write-ui   # or: qortroller ui
  3. cd frontend && npm run dev
  4. open http://127.0.0.1:5173/?view=stream
  5. qortroller play → match → stop   # stop writes receipt.json
  6. refresh StreamView → RECEIPT mode; exercise LOCAL vs SHARE copy
  7. qortroller dogfood-report --scaffold; fill friction + bar

Offline-only path (no Node):
  qortroller ui   # stream_shell.html + ceremony.json
```

| dogfood_report field | Source |
|---|---|
| `ui_surface_exercised` | `"vite_spa"` \| `"offline_shell"` \| `"none"` |
| `ui_serve_path` | URL used |
| `ui_mode_seen` | EMPTY / CEREMONY / STREAM / RECEIPT |
| `friction_events[].code` | UI_* allowlist (see above) |

Bar unchanged: **`operator_would_rerun_without_chat`**.

---

## build-results

### Frontend (BUILD-NOW)
- `frontend/src/stream/` — tokens, loader, WitnessRespiration, ReceiptReveal, BirthCeremonyMap, useStreamSnapshots, fixtures, index exports
- `frontend/src/views/StreamView.jsx` — SPA surface
- `frontend/src/App.jsx` — `VIEW_MAP.stream` (URL-only)
- `frontend/vite.config.js` — `qortroller-ui-static` middleware (`/stream-ui` → `~/.qortroller/ui`)
- `frontend/src/__tests__/StreamView.test.jsx` — **11/11 GREEN** (T-SV-1..11)

### CLI (additive)
- `DOGFOOD_FRICTION_CODES` +7 UI_* codes; optional `ui_*` report fields
- `receipt --write-ui` → `~/.qortroller/ui/receipt.json`
- `stop` always writes receipt reveal for SPA
- `bridge/tests/test_qortroller_cli.py` — **43/43 GREEN** (was 42; +`test_receipt_write_ui_writes_reveal_model`)

### Gates
- **PV-CI 183 PASS** (no invariant / FROZEN / PoAC touch)
- `py_compile` clean on `scripts/qortroller.py`
- No secrets; `signing_material_present=False` / `consent_authority=False` / `mock=False` / `fabricated_liveness=False` in models + DOM rails
- Staged only — operator commits; Claude verifies per ruling (a)

---

## open-questions

- **Q27 — ROI image in-browser:** ceremony map currently shows overlay *path* + "CLI remains the writer." Should a later round serve `stage3_roi_check.png` via `/stream-ui/../setup/` (or a dedicated read-only path) so the y/N moment is visual in SPA without becoming a control plane?
- **Q28 — tab-bar presence:** keep Stream URL-only for dogfood, or add a quiet "Witness" tab after the operator bar clears?
- **Q29 — receipt auto-poll after stop:** is 3s poll enough for the stop climax, or should StreamView subscribe to a local file-watch / operator "I stopped" button that only re-fetches (still not a control plane)?

---
*Round-13 — designed + built 2026-07-13 via the terminal bus. Frontend 11/11 · CLI 43/43 ·
PV-CI 183 · staged only (operator commits; Claude verifies per ruling (a)). React Stream SPA
opened. Operator dogfood pass GATED. Next: Claude grounds/verifies PKG-UI-05..07.*
