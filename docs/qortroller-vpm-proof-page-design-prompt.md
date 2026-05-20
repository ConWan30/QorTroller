# QorTroller — VPM Proof Page · Claude-Design Master Prompt

Paste **Part A** into Claude's design feature (artifacts) to generate the new VPM
Proof page. Iterate the look there. **Part B** is the integration checklist for
the Claude Code porting step. This supersedes the current two-pane
`VpmRegistryView` layout — the goal is a fresh, synergistic "proof gallery +
forensic inspector" page that makes the autonomously-generated HTML proofs the
hero, with the cryptographic-honesty surfaces front and center.

> **Carry-over from the main remodel:** brand, palette, typography, and the
> `.qt-design-root` scoping rules are identical to
> `docs/qortroller-claude-design-master-prompt.md`. Read that first; this doc
> only adds the VPM-page specifics.

---

## PART A — THE MASTER PROMPT

### 1. What this page is

The **VPM Proof page** browses **Verified Projection Media** — HTML proof
artifacts the protocol compiles **autonomously** (one per ZKBA artifact / MLGA
gameplay session / VPM-family record). Each artifact is a **self-contained,
independently-verifiable** HTML document: open it in any browser, re-run its
SHA-256 in dev tools, and the protocol's claims hold. This page is where a grant
evaluator sees that the protocol's outputs are real, audited, and tamper-evident.

There are ~14 artifact classes today, e.g. `MLGA-SESSION-v1`, `CDRR-DAG-v1`,
`GIC-LEDGER-BETA-v1`, `HONESTY-BOARD-v1`, plus the ZKBA cards (VHP / AIT /
tournament / marketplace / consent / hardware / GIC-ledger).

### 2. Brand + aesthetic (locked — QRESCE-0001 v0.5)

- Void-black `#04060a` + forensic graticule matte; amber `#f0a868` accents
  (medial-T discipline); chain-green `#5bd6a3` for "verified / re-derived OK";
  red `#d65b78` for MISMATCH/blocked.
- **Syne** for display/headings, **JetBrains Mono** for all data/hashes.
- Aesthetic: "forensic instrument panel meets living cryptographic specimen."
  The artifact itself is a framed certificate; the page is the instrument bench
  around it.
- Everything scoped under `.qt-design-root` (zero collision with other views).

### 3. Layout direction (the synergistic part — design freely here)

Move away from the cramped left-list / right-stacked-panels. Proposed shape
(refine in the tool):

- **Top: a filterable proof gallery / rail** — compact cards, one per artifact,
  showing `vpm_id`, a visual-state chip, short `commitment_hex`, capture mode,
  proof weight. Filter by `vpm_id` + visual state. This replaces the narrow
  360px left list.
- **Center (hero): the selected proof, full-bleed** — the actual rendered HTML
  artifact in a large framed stage (the framed-certificate look). This is the
  star. It must render the **fresh** proof (see §4 render rule).
- **Right / side: the forensic inspector** — collapsible:
  - **Integrity verdict** — the live in-browser HASH check: `HASH OK` (chain
    green) / `MISMATCH` (red) / `UNAVAILABLE`. Big, unmissable.
  - **Visual-grammar verdict** — the DOM-signature check (`VpmGrammarVerifier`)
    confirming the rendered proof matches its declared visual state.
  - **Provenance line** — `commitment_hex`, `output_hash`, `schema`,
    `template_version`, `ts`.
- The plain 9-row "Integrity Nutrition Label" table is **redundant** with the
  label already inside the proof — fold it into the inspector as a compact
  verdict + "view full label" affordance, don't duplicate the whole table above
  the proof.

### 4. The proof RENDER RULE (non-negotiable — this is the bug fix)

The proof MUST render via **`srcDoc`**, fed by a **`fetch(..., {cache:
'no-store'})`** of the artifact HTML. **Never** point an iframe `src=` directly
at the artifact URL — that path lets the browser serve a cached old proof
(VPM-family URLs are keyed on the *input* commitment, which is stable across
re-renders, so `src=` caches indefinitely). The fetch+srcDoc path is what makes
regenerated v2 proofs actually appear.

```
fetch(artifactUrl, { headers: { 'x-api-key': KEY }, cache: 'no-store' })
  .then(r => r.text())
  .then(html => /* feed to <iframe sandbox="allow-scripts allow-same-origin" srcDoc={html}> */)
```

Sandbox is FROZEN: `sandbox="allow-scripts allow-same-origin"` (allows the
proof's inline JS + lets the grammar verifier read the DOM). No `allow-forms`,
`allow-popups`, `allow-top-navigation`.

### 5. FROZEN data contract (real hooks — consume verbatim, no invented shapes)

- `useVpmList({ vpmId, visualState, limit })` → `{ data: { rows: [...] } }`.
  Each row: `commitment_hex`, `vpm_id`, `visual_state`, `capture_mode`,
  `zkba_class`, `proof_weight`, `integrity_label_hash_hex`,
  `compiler_output_hash_hex`, `manifest_uri`, `ts_ns`. **`noMock:true`** — never
  fabricate rows; on offline show an honest "bridge offline / no recorded
  artifacts" empty state.
- `useVpmManifest(commitmentHex)` → `{ data: { found, manifest, db_row,
  file_missing } }`; `manifest` carries `input_commitment_hex`, `output_hash_hex`,
  `integrity_label_hash_hex`, `vpm_id`, `capture_mode`, `proof_weight`, `schema`.
- Proof HTML: `GET /operator/operator/vpm-artifact/{commit}?api_key=…&v={compiler_output_hash_hex}`
  — fetch with `no-store` (see §4). The `&v=` content-hash also busts cache.
- `VpmGrammarVerifier({ iframeRef, declaredState })` — reads the rendered DOM,
  returns OK/violation against the 6 FROZEN visual-state signatures.
- The 9 FROZEN Integrity Label fields (display order): `proof_type`,
  `capture_mode`, `raw_biometrics_exposed`, `consent_active`, `zk_verified`,
  `on_chain_anchor`, `proof_weight`, `revocation_status`, `limitations`.
- 6 FROZEN visual states: `live`, `dry-run`, `emulated`, `frozen-disabled`,
  `revoked`, `unverified` (each has a color + meaning).

### 6. Hard constraints (non-negotiable)

- **Named export** `export function VpmProofView()` (App.jsx lazy adapter:
  `.then(m => ({ default: m.VpmProofView }))`).
- **Proof renders via `srcDoc` + `no-store` fetch** (§4) — the defining fix.
- **`noMock:true`** on the registry hooks; honest empty/offline states; no
  fabricated artifacts or hashes.
- **Real HASH check preserved** — the OK/MISMATCH verdict must be a genuine
  in-browser SHA-256, not a static badge.
- FROZEN sandbox attribute; FROZEN 9 label fields; FROZEN 6 visual states.
- Brand-display discipline: `V.A.P.I.` (with periods) in display copy; `VPM`,
  `vpm_id`, byte literals stay verbatim (Layer C).

### 7. Output format

A single named-export React component (plus small sub-components) consuming the
hook signatures in §5 verbatim. Use the `.qt-design-root` token classes from the
kit. The artifact stage uses the fetch+srcDoc pattern from §4.

---

## PART B — INTEGRATION CHECKLIST (Claude Code porting)

- [ ] Named export + App.jsx lazy adapter; routed as `04 VPM · Proofs`
- [ ] `useVpmList` / `useVpmManifest` wired (real shapes, `noMock` preserved)
- [ ] Proof renders via **`srcDoc`** from a **`no-store` fetch** — verified that
      a regenerated artifact shows fresh (no cached old proof)
- [ ] Live HASH OK/MISMATCH is a real `crypto.subtle` check
- [ ] `VpmGrammarVerifier` wired against the rendered DOM
- [ ] FROZEN sandbox attr + 9 label fields + 6 visual states intact
- [ ] honest empty/offline state; no fabricated rows
- [ ] Vitest green (VpmIframe / VpmManifestPanel / VpmGrammarVerifier / FilterChips)
- [ ] live-bridge visual check: gallery + proof render v2; `mythos_frontend_brand_drift` = 0
