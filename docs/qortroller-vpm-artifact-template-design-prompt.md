# QorTroller — VPM Proof **Artifact** Template · Claude-Design Master Prompt

This prompt is for designing **the served proof artifact itself** — the
self-contained HTML certificate the protocol compiles, hashes, and serves (what
renders inside the VPM Proof page's iframe). It is **not** a React view; it's the
document. A coding agent will translate the resulting HTML/CSS into the Python
compiler templates (`scripts/vpm_visual_grammar.py` + the per-class compilers),
so every generated artifact looks like this certificate.

> Why this prompt exists: the VPM Proof page (`VpmProofView`) already fetches +
> renders the real served artifact via `srcDoc` + `no-store`. The page is done.
> What's left is making the *served artifact* look like the design certificate
> (today it uses an interim template). Design the artifact here; it gets wired
> into the compilers verbatim.

---

## PART A — THE MASTER PROMPT

### 1. What to design

A **self-contained HTML proof certificate** — one document, openable standalone
in any browser, that re-derives its own SHA-256. Design **one shared certificate
shell** plus **per-class content blocks** for these six classes (each serves a
different reader — design the content for that reader):

| Class | Reader | Content block to design |
|---|---|---|
| `MLGA-SESSION-v1` | gamer / tournament operator | session aggregates: duration, n_poac_records, R2/L2 trigger pulls, GIC advances, BT observability, APOP state counts |
| `GIC-LEDGER-BETA-v1` | operator / auditor | chain continuity: grind_session_id, chain length (milestone), head hash, genesis hash + ts, on-chain anchor (block + tx), underlying ZKBA manifest hash |
| `HONESTY-BOARD-v1` | grant evaluator | protocol state: fleet phase, ZKBA coverage, chain-submission gate, Cedar bundles, PV-CI count, wallet, last anchor |
| `CDRR-DAG-v1` | auditor | contradiction-resolution DAG summary |
| `CONSENT-COMMIT-v1` | buyer / gamer | per-category consent state + GDPR note |
| `VHP-ZKBA-v1` | buyer / tournament | VHP token validity, cert level, expiry |

### 2. Brand + aesthetic (locked — QRESCE-0001 v0.5)

Void-black `#04060a` + forensic graticule background; amber `#f0a868`
(medial-T accent); chain-green `#5bd6a3` for verified/anchored values; red
`#d65b78` for risk values (raw biometrics exposed, consent withdrawn, revoked).
**Syne** for display/title, **JetBrains Mono** for data/hashes. The look is a
**framed cryptographic certificate** — instrument-grade, not a marketing card.

### 3. The shared certificate shell (every class)

Match the existing `synthesizeProofHtml` certificate, top to bottom:
- **Corner-bracket framed card** on the graticule matte (`.frame` with
  `::before`/`::after` corner brackets in the state accent color).
- **Eyebrow**: `VERIFIED · PROJECTION · MEDIA · {template_version}`.
- **Wordmark**: `Qor` + amber `T` + `roller` (Syne).
- **Big title** (Syne, ~38px): the `{vpm_id}`.
- **State stamp** (top-right): a dot + label in the state accent
  (e.g. `LIVE · CRYPTOGRAPHICALLY ANCHORED`).
- **Commitment block**: `COMMITMENT_HEX` label + the full hash, space-grouped,
  chain-green.
- **→ PER-CLASS CONTENT BLOCK** (§1) — the new part. Section headers in Syne
  uppercase; data in clean tables (key column dim, value column with semantic
  color: chain-green for anchored/valid, amber for weights, red for risk).
- **Integrity Nutrition Label** — the 9 FROZEN fields (§5), as a bordered table.
- **Provenance footer** (4-up grid): `schema`, `manifest_uri`, `output_hash`,
  `ts_ns`.

### 4. FROZEN visual-state signatures — MANDATORY (do not omit)

The live grammar verifier checks these exact markers; the certificate MUST carry
them for its declared state (they can be visually subtle — most are part of the
state styling). For each of the 6 states the document MUST include:
- `<meta name="vpm-visual-state" content="{state}">` in `<head>`.
- A `<div role="status" data-vpm-visual-state="{state}" aria-label="…">` block.
- The state's signature element/CSS:
  - **live**: `class="vpm-saturation-class"` marker div.
  - **dry-run**: inline `<svg class="vpm-stripe-mask">` with `<pattern id="vpm-stripe-pattern">`.
  - **emulated**: body wrapper `class="vpm-body vpm-emulated"` + CSS `filter: grayscale(100%)`.
  - **frozen-disabled**: inline `<svg class="vpm-lock-icon">`.
  - **revoked**: `class="vpm-redacted-banner"` + CSS `text-decoration: line-through`.
  - **unverified**: body `repeating-linear-gradient` using `#d65b78` + `#020408`.

Keep these alongside the design chrome — they coexist (markers + state styling).

### 5. The 9 FROZEN Integrity Label fields (display order, exact keys)

`proof_type` · `capture_mode` · `raw_biometrics_exposed` · `consent_active` ·
`zk_verified` · `on_chain_anchor` · `proof_weight` · `revocation_status` ·
`limitations`. Render each with a `data-vpm-field="{key}"` marker on the value.

### 6. The 6 FROZEN visual states

`live` · `dry-run` · `emulated` · `frozen-disabled` · `revoked` · `unverified`
— each with its accent color + a one-line meaning in the stamp.

### 7. Hard constraints (the artifact is self-contained + deterministic)

- **No external resources in the REAL artifact**: no `https://`, no `@import`, no
  `@font-face`, no `<link rel>`, no CDN, no network JS, no `Date.now()` /
  `Math.random()`. (The mockup MAY use a Google-Fonts `@import` for fidelity —
  the coding agent will swap it for a system stack:
  `ui-monospace, 'JetBrains Mono', …, monospace` and
  `'Syne', system-ui, sans-serif` — so name those fonts but don't rely on the load.)
- **Bytewise-deterministic** per input (same data → same bytes; the SHA-256 is
  the artifact's identity).
- Every status color pairs with a text label (no color-only meaning).

### 8. Output format

Six self-contained `.html` files (one per class in §1), each a complete
certificate for a representative `live`-state example, plus — if convenient — one
file cycling a single class through all 6 visual states so the state treatments
are reviewable.

---

## PART B — WIRING (coding agent, after export)

1. Translate the certificate shell → `scripts/vpm_visual_grammar.py`
   (`base_style_block` CSS + a shared `assemble_certificate(...)` that emits the
   frame/eyebrow/wordmark/title/stamp/commitment + integrity label + provenance
   footer + the FROZEN overlay/meta/aria), keeping `visual_state_css` /
   `visual_state_overlay` / `integrity_label_html` intact.
2. Translate each per-class content block → the matching compiler
   (`vpm_compile_*` / `zkba_compile_*` / `mlga_compile_session_artifact`), which
   fills the content slot with its real data.
3. Swap the mockup's webfont `@import` for the system stack; verify no forbidden
   patterns (the compiler discipline guard rejects `https://` / `@font-face`).
4. Regenerate all artifacts (preserving determinism + FROZEN grammar tests) so
   the served proofs become the new certificate. `VpmProofView` already renders
   them via `fetch + srcDoc + no-store` with the live SHA-256 + grammar verdict —
   no React change needed.
