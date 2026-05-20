"""Phase O4-VPM-INTEGRATION Stream A.1 — Shared Anti-Hype Visual Grammar.

Implements the FROZEN 6-state visual grammar per VBDIP-0002 Appendix B §B.5 +
Phase O4 plan §5.1, exposed as deterministic HTML+SVG+CSS rendering helpers
that all four internal VPM compilers (A.1.a HONESTY-BOARD, A.1.b AGENT-REVIEW,
A.1.c CDRR-DAG, A.1.d GIC-LEDGER-BETA) consume.

Single-source-of-truth for the 6 DOM signatures keeps the Anti-Hype invariant
testable at one assertion site: `VISUAL_STATE_SIGNATURES[state]` is what every
emitted VPM HTML for that state MUST contain. Drift between any compiler and
the canonical signature surfaces in the parametrized T-VPM-GRAMMAR-1..6 test
band that each compiler test file runs.

Module is import-safe (no top-level side effects), uses Python stdlib only
(re for the signature regex set), and never reads wall-clock / random /
network. Output is bytewise-deterministic per input.

Phase O4 plan §5.1 reference (6-state signature matrix):

  live              -> saturated colors + class marker
  dry-run           -> <svg class="vpm-stripe-mask"> + <pattern id=
                       "vpm-stripe-pattern"> inline SVG overlay
  emulated          -> filter: grayscale(100%) on .vpm-body (computed style)
  frozen-disabled   -> <svg class="vpm-lock-icon"> + lock <path>
  revoked           -> text-decoration: line-through on .vpm-status +
                       <div class="vpm-redacted-banner">
  unverified        -> repeating-linear-gradient warning bands with
                       #d65b78 + #020408

Plus §5.4 accessibility/machine-readability requirements (every VPM, every
state):
  <meta name="vpm-visual-state" content="<state>">
  <div role="status" aria-label="<contextual aria text>">

Plus the 9-field Integrity Nutrition Label per Appendix B §B.5 — rendered
inline with `data-vpm-field="<name>"` markers (asserted by the compiler's
_verify_integrity_label_in_dom guard).

Author: VAPI Architect (Phase O4 Commit 4)
Date: 2026-05-13
"""
from __future__ import annotations

import html
from typing import Iterable


# ---------------------------------------------------------------------------
# FROZEN signature constants — DO NOT modify without VBDIP-0002 v1.2 amendment
# ---------------------------------------------------------------------------

VISUAL_STATES = (
    "live",
    "dry-run",
    "emulated",
    "frozen-disabled",
    "revoked",
    "unverified",
)


# Each visual state's REQUIRED DOM signature. Each entry is a tuple of
# substrings ALL of which MUST appear in the emitted HTML body for the state
# to be considered correctly rendered. The grammar test band asserts that
# every emitted VPM HTML for state X contains every substring in
# VISUAL_STATE_SIGNATURES[X]. Missing any substring is an Anti-Hype
# violation.
#
# Substrings are chosen to be stable across font / whitespace / element-
# ordering variations — they pin the LOAD-BEARING DOM markers, not the
# stylistic surroundings.
VISUAL_STATE_SIGNATURES = {
    "live": (
        'class="vpm-saturation-class"',
        'data-vpm-visual-state="live"',
    ),
    "dry-run": (
        'class="vpm-stripe-mask"',
        'id="vpm-stripe-pattern"',
        'data-vpm-visual-state="dry-run"',
    ),
    "emulated": (
        'class="vpm-body vpm-emulated"',
        'filter: grayscale(100%)',
        'data-vpm-visual-state="emulated"',
    ),
    "frozen-disabled": (
        'class="vpm-lock-icon"',
        'data-vpm-visual-state="frozen-disabled"',
    ),
    "revoked": (
        'class="vpm-redacted-banner"',
        'text-decoration: line-through',
        'data-vpm-visual-state="revoked"',
    ),
    "unverified": (
        'repeating-linear-gradient',
        '#d65b78',
        '#020408',
        'data-vpm-visual-state="unverified"',
    ),
}


# Meta-tag + aria-label requirements (§5.4) — every state, every VPM
META_TAG_SIGNATURE = '<meta name="vpm-visual-state"'
ARIA_LABEL_SIGNATURE = 'role="status"'

# Proof-template version (provenance only — NOT a FROZEN signature). Bumped to
# "3" with the QRESCE-0001 v0.5 Claude-Design certificate shell
# (render_vpm_certificate): corner-bracket framed card, eyebrow/wordmark/title/
# state-stamp/commitment-block + per-class content table + design integrity-
# label table + 4-up provenance footer. "2" was the interim centred-frame look.
# Emitted as a <meta> tag so each newly-compiled artifact records which template
# produced it. Existing artifacts are immutable HTML files on disk (served
# verbatim), so the bump never affects already-anchored commitments — only new
# compiles. The input_commitment is over INPUTS (not HTML), so re-rendering an
# artifact with a new template changes only its output_hash, never its identity.
VPM_TEMPLATE_VERSION = "3"


# Required 9 Integrity Label field markers — mirrored from
# scripts/vsd_ui_compiler.py:_VPM_INTEGRITY_LABEL_FIELDS so both modules
# agree on the field set. Listed here so renderer authors can iterate over
# them when emitting the label block.
INTEGRITY_LABEL_FIELDS = (
    "proof_type",
    "capture_mode",
    "raw_biometrics_exposed",
    "consent_active",
    "zk_verified",
    "on_chain_anchor",
    "proof_weight",
    "revocation_status",
    "limitations",
)


# Human-readable aria-label text per state (§5.4) — surfaced inside the
# role="status" div for screen readers and machine inspection.
_ARIA_LABEL_BY_STATE = {
    "live":            "This VPM artifact is in LIVE state with active anchors.",
    "dry-run":         "This VPM artifact is in DRY-RUN mode and is not production-anchored.",
    "emulated":        "This VPM artifact is EMULATED from mock or non-production sources.",
    "frozen-disabled": "This VPM artifact's underlying primitive is FROZEN and disabled at runtime.",
    "revoked":         "This VPM artifact's underlying claim has been REVOKED. Do not rely on this projection.",
    "unverified":      "This VPM artifact is UNVERIFIED. Verification material is missing or has drifted.",
}


# ---------------------------------------------------------------------------
# Renderer helpers — deterministic, stdlib-only, no wall-clock/random/network
# ---------------------------------------------------------------------------


def visual_state_meta_tag(state: str) -> str:
    """Emit the §5.4 <meta name="vpm-visual-state" content="<state>"> tag.

    This tag appears in <head> and is the primary machine-readable signal
    for the declared visual state. The compiler's static guard verifies its
    presence indirectly via VISUAL_STATE_SIGNATURES (the 'data-vpm-visual-
    state="<state>"' marker is duplicated on the role=status div, which
    has slightly more reliable test surface than meta tags).
    """
    if state not in VISUAL_STATES:
        raise ValueError(
            f"state must be one of {VISUAL_STATES}; got {state!r}"
        )
    return f'<meta name="vpm-visual-state" content="{state}">'


def visual_state_aria_block(state: str) -> str:
    """Emit the §5.4 role="status" aria-labelled block + the duplicate
    data-vpm-visual-state marker that the parametrized grammar test band
    inspects.

    Returns a <div> snippet, not a full element tree — callers embed it
    inside the VPM body wherever makes sense layout-wise. The aria text is
    short, declarative, and state-specific.
    """
    if state not in VISUAL_STATES:
        raise ValueError(
            f"state must be one of {VISUAL_STATES}; got {state!r}"
        )
    label = _ARIA_LABEL_BY_STATE[state]
    return (
        f'<div role="status" data-vpm-visual-state="{state}" '
        f'aria-label="{html.escape(label)}">'
        f'<span class="vpm-state-pill vpm-state-{state}">'
        f'{state.upper()}'
        f'</span>'
        f' &mdash; {html.escape(label)}'
        f'</div>'
    )


def visual_state_css(state: str) -> str:
    """Emit the state-specific CSS rules per §5.1 DOM signature spec.

    Returns the inner-CSS rules to inline inside a <style> block — caller
    is responsible for wrapping with <style>...</style>. Caller is also
    expected to inline a base CSS block with shared rules (body font,
    colors) separately; this function only emits state-specific rules.

    Per-state output:
      live              .vpm-saturation-class declared (no-op selector
                        that the grammar test band greps for)
      dry-run           .vpm-stripe-mask overlay rule (used by inline SVG
                        below)
      emulated          .vpm-body.vpm-emulated { filter: grayscale(100%); }
      frozen-disabled   .vpm-lock-icon { opacity: 0.7; }
      revoked           .vpm-status { text-decoration: line-through; }
                        + .vpm-redacted-banner rule
      unverified        body background: repeating-linear-gradient(...)
                        warning bands with FROZEN color pair
                        #d65b78 (warn red) + #020408 (void black)
    """
    if state not in VISUAL_STATES:
        raise ValueError(
            f"state must be one of {VISUAL_STATES}; got {state!r}"
        )

    base = (
        ".vpm-state-pill { display: inline-block; padding: 2px 8px; "
        "border-radius: 4px; font-weight: bold; font-size: 0.85em; }\n"
        ".vpm-state-live { background: #5bd6a3; color: #020408; }\n"
        ".vpm-state-dry-run { background: #f0a868; color: #020408; }\n"
        ".vpm-state-emulated { background: #607a93; color: #cfe8ff; }\n"
        ".vpm-state-frozen-disabled { background: #1a2a40; color: #cfe8ff; }\n"
        ".vpm-state-revoked { background: #d65b78; color: #020408; }\n"
        ".vpm-state-unverified { background: #d65b78; color: #020408; "
        "border: 1px dashed #f0a868; }\n"
    )

    state_specific = {
        "live": (
            ".vpm-saturation-class { /* live: saturated colors per §5.1 */ }\n"
            ".vpm-body { color: #cfe8ff; }\n"
        ),
        "dry-run": (
            ".vpm-stripe-mask { width: 100%; height: 6px; }\n"
            # No inline data: image with embedded http xmlns — the stripe
            # pattern lives in the overlay SVG <defs> instead. The body
            # background here uses a pure CSS repeating-linear-gradient.
            ".vpm-body { background-image: repeating-linear-gradient("
            "45deg, transparent 0px, transparent 6px, "
            "rgba(240, 168, 104, 0.08) 6px, rgba(240, 168, 104, 0.08) 12px); }\n"
        ),
        "emulated": (
            ".vpm-body.vpm-emulated { filter: grayscale(100%); }\n"
        ),
        "frozen-disabled": (
            ".vpm-lock-icon { opacity: 0.7; vertical-align: middle; }\n"
            ".vpm-body { color: #93a5b8; }\n"
        ),
        "revoked": (
            ".vpm-status { text-decoration: line-through; color: #d65b78; }\n"
            ".vpm-redacted-banner { background: #d65b78; color: #020408; "
            "padding: 6px 12px; border-radius: 4px; "
            "text-transform: uppercase; letter-spacing: 0.1em; "
            "font-weight: bold; margin: 1em 0; }\n"
        ),
        "unverified": (
            ".vpm-body { background-image: repeating-linear-gradient("
            "45deg, #d65b78 0px, #d65b78 8px, #020408 8px, #020408 16px); "
            "background-size: 32px 32px; }\n"
        ),
    }
    return base + state_specific[state]


def visual_state_overlay(state: str) -> str:
    """Emit the state-specific HTML/SVG overlay per §5.1 DOM signature spec.

    Returns HTML snippet to be inlined in the <body>. Each overlay carries
    the canonical DOM marker that the grammar test band asserts:

      live              <div class="vpm-saturation-class"></div> (zero-px
                        marker; grammar grep target only)
      dry-run           inline <svg class="vpm-stripe-mask"> with
                        <pattern id="vpm-stripe-pattern"> definition
                        (no external stylesheet; no font; deterministic)
      emulated          wrapper div applies vpm-body vpm-emulated class
                        (the grayscale filter is asserted via CSS rule
                        emitted by visual_state_css)
      frozen-disabled   inline <svg class="vpm-lock-icon"> with lock
                        <path> + <rect>
      revoked           <div class="vpm-redacted-banner"> with explicit
                        "REVOKED" text
      unverified        body background pattern emitted by CSS rule
                        (repeating-linear-gradient); plus an inline
                        warning banner div

    No external resources, no scripts, no wall-clock, no random.
    """
    if state not in VISUAL_STATES:
        raise ValueError(
            f"state must be one of {VISUAL_STATES}; got {state!r}"
        )

    overlays = {
        "live": (
            '<div class="vpm-saturation-class" aria-hidden="true"></div>'
        ),
        "dry-run": (
            # Inline SVG without xmlns attribute — HTML5 spec allows inline
            # SVG to inherit the host language's namespace. Omitting xmlns
            # keeps the discipline guard's `no https?://` rule clean while
            # still rendering correctly in every modern browser. See plan
            # §3 Stream A.0 compiler discipline item 6 ("Inline SVG only").
            '<svg class="vpm-stripe-mask" '
            'width="100%" height="6" aria-hidden="true">'
            '<defs>'
            '<pattern id="vpm-stripe-pattern" x="0" y="0" width="8" height="8" '
            'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect x="0" y="0" width="4" height="8" fill="#f0a868"/>'
            '</pattern>'
            '</defs>'
            '<rect x="0" y="0" width="100%" height="6" fill="url(#vpm-stripe-pattern)"/>'
            '</svg>'
        ),
        "emulated": (
            '<!-- emulated: grayscale filter applied via CSS rule on .vpm-body.vpm-emulated -->'
        ),
        "frozen-disabled": (
            '<svg class="vpm-lock-icon" '
            'width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">'
            '<rect x="3" y="9" width="14" height="9" fill="#93a5b8" stroke="#1a2a40"/>'
            '<path d="M6,9 v-3 a4,4 0 0 1 8,0 v3" fill="none" stroke="#93a5b8" stroke-width="2"/>'
            '</svg>'
        ),
        "revoked": (
            '<div class="vpm-redacted-banner" aria-label="Revoked status">'
            'REVOKED &mdash; this projection MUST NOT be relied upon'
            '</div>'
        ),
        "unverified": (
            '<div class="vpm-redacted-banner" aria-label="Unverified state" '
            'style="background: #d65b78; color: #020408;">'
            'UNVERIFIED &mdash; verification material missing or drifted'
            '</div>'
        ),
    }
    return overlays[state]


def integrity_label_html(label: dict) -> str:
    """Emit the §B.5 9-field Integrity Nutrition Label block.

    Renders a <div class="vpm-integrity-label"> containing a definition
    list with one <dt>/<dd> pair per required field, each <dd> carrying
    the `data-vpm-field="<name>"` marker that the compiler's
    _verify_integrity_label_in_dom guard asserts.

    label must contain all 9 keys per INTEGRITY_LABEL_FIELDS; missing keys
    raise ValueError (this is enforced here in addition to the compiler's
    DOM-side guard so renderer authors fail fast at the renderer call site).
    """
    if not isinstance(label, dict):
        raise TypeError(
            f"label must be dict; got {type(label).__name__}"
        )
    missing = [f for f in INTEGRITY_LABEL_FIELDS if f not in label]
    if missing:
        raise ValueError(
            f"integrity_label missing required fields: {missing}"
        )

    rows: list[str] = []
    for field in INTEGRITY_LABEL_FIELDS:
        value = label[field]
        if isinstance(value, bool):
            display = "Yes" if value else "No"
        elif isinstance(value, (list, tuple)):
            display = "; ".join(str(v) for v in value)
        else:
            display = str(value)
        rows.append(
            f'    <dt>{_pretty_field_name(field)}:</dt>'
            f'<dd data-vpm-field="{field}">{html.escape(display)}</dd>'
        )

    return (
        '<div class="vpm-integrity-label" aria-label="Integrity Nutrition Label">\n'
        '  <h2>Integrity Nutrition Label</h2>\n'
        '  <dl>\n'
        + '\n'.join(rows) + '\n'
        '  </dl>\n'
        '</div>'
    )


def _pretty_field_name(field: str) -> str:
    """Convert snake_case field name to a presentable label."""
    return field.replace("_", " ").title()


def base_style_block() -> str:
    """Shared base CSS (font + colors + layout) inlined by every VPM
    renderer. Returns inner-CSS only; caller wraps with <style>...</style>.

    TEMPLATE v2 (QRESCE-0001 v0.5 grant-evaluator remodel): the proof now
    renders as a centred, framed "certificate" card on a full-viewport void
    matte with a subtle forensic graticule — fixing the prior narrow-column /
    uncovered-frame look — and aligns the artifact palette to the QorTroller
    design system (void #04060a, amber #f0a868, chain-green #5bd6a3).

    Constraints preserved per Phase O4 plan §3 Stream A.0 compiler discipline:
    NO @font-face, NO @import, NO external URLs (so the artifact stays
    self-contained + bytewise-deterministic + offline-renderable). Brand
    typography is therefore a refined SYSTEM-monospace stack (JetBrains Mono is
    NAMED as a hint and used iff locally installed; never web-loaded). This
    function styles ONLY base chrome — every FROZEN visual-state DOM signature
    lives in visual_state_css()/visual_state_overlay()/vpm_body_class() and is
    untouched here, so the 6-state grammar band is unaffected.
    """
    return (
        "html { box-sizing: border-box; }\n"
        "*, *::before, *::after { box-sizing: inherit; }\n"
        # full-viewport void matte + subtle forensic graticule (pure CSS, no deps)
        "body { margin: 0; min-height: 100vh; "
        "font-family: ui-monospace, 'JetBrains Mono', 'SF Mono', 'Cascadia Code', "
        "Menlo, Consolas, 'Courier New', monospace; "
        "background-color: #04060a; color: #d4dde8; "
        "line-height: 1.55; font-size: 13.5px; letter-spacing: 0.01em; "
        "padding: clamp(16px, 4vw, 48px); "
        "background-image: "
        "linear-gradient(to right, rgba(26,34,48,0.20) 1px, transparent 1px), "
        "linear-gradient(to bottom, rgba(26,34,48,0.20) 1px, transparent 1px); "
        "background-size: 28px 28px; }\n"
        # the proof itself: a centred framed certificate card on the matte
        ".vpm-body { max-width: 980px; margin: 0 auto; "
        "background-color: #0a0e14; border: 1px solid #2a3850; "
        "border-radius: 10px; padding: clamp(20px, 3vw, 36px); "
        "box-shadow: 0 0 0 1px rgba(240,168,104,0.06), "
        "0 24px 60px -24px rgba(0,0,0,0.80); }\n"
        # headings — brand amber title, eyebrow-style sub-heads
        "h1 { color: #f0a868; font-size: 1.5em; margin: 0 0 0.2em 0; "
        "letter-spacing: 0.02em; border-bottom: 1px solid #2a3850; "
        "padding-bottom: 0.4em; }\n"
        "h2 { color: #8a98ab; font-size: 0.82em; text-transform: uppercase; "
        "letter-spacing: 0.18em; margin: 1.8em 0 0.6em 0; "
        "border-bottom: 1px dotted #1b2433; padding-bottom: 0.3em; }\n"
        # status table + meta blocks
        "table.vpm-status { width: 100%; border-collapse: collapse; margin: 0.4em 0; }\n"
        ".vpm-status td { padding: 7px 10px; border-bottom: 1px solid #141b27; "
        "vertical-align: top; }\n"
        ".vpm-status td:first-child { color: #8a98ab; white-space: nowrap; width: 42%; }\n"
        ".vpm-meta { margin: 0.4em 0; color: #8a98ab; }\n"
        ".vpm-meta > div { padding: 4px 0; }\n"
        # integrity nutrition label — the cryptographic-honesty surface, elevated
        ".vpm-integrity-label { border: 1px solid rgba(240,168,104,0.35); "
        "border-radius: 8px; padding: 16px 18px; margin-top: 1.8em; "
        "background-color: #04060a; }\n"
        ".vpm-integrity-label h2 { margin: 0 0 12px 0; color: #f0a868; "
        "font-size: 0.78em; letter-spacing: 0.20em; border: none; padding: 0; }\n"
        ".vpm-integrity-label dl { display: grid; "
        "grid-template-columns: minmax(11em, max-content) 1fr; gap: 0; margin: 0; }\n"
        ".vpm-integrity-label dt { color: #8a98ab; font-weight: 600; "
        "padding: 7px 14px 7px 0; border-bottom: 1px solid #141b27; display: block; }\n"
        ".vpm-integrity-label dd { color: #d4dde8; margin: 0; padding: 7px 0; "
        "border-bottom: 1px solid #141b27; display: block; word-break: break-word; }\n"
        ".vpm-integrity-label dd::after { content: none; display: none; }\n"
        # code / hashes — chain green, wrappable
        "code { color: #5bd6a3; background-color: #04060a; padding: 1px 5px; "
        "border-radius: 3px; word-break: break-all; border: 1px solid #141b27; }\n"
        # footer
        ".vpm-footer { margin-top: 2.2em; color: #5a6878; font-size: 0.78em; "
        "border-top: 1px solid #1b2433; padding-top: 0.8em; line-height: 1.6; }\n"
    )


def assemble_vpm_head(
    *,
    title: str,
    visual_state: str,
    extra_style: str = "",
) -> str:
    """Emit the canonical <head>...</head> block for a VPM artifact.

    Combines: charset meta, title, vpm-visual-state meta tag, base style
    block, state-specific style block, optional caller-supplied extra
    CSS. No external resource references.

    `title` is HTML-escaped to defend against renderer-side injection in
    case a caller passes user input (defense in depth; renderers should
    pass static titles).
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )
    state_css = visual_state_css(visual_state)
    meta_state = visual_state_meta_tag(visual_state)
    return (
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'  {meta_state}\n'
        f'  <meta name="vpm-template-version" content="{VPM_TEMPLATE_VERSION}">\n'
        f'  <title>{html.escape(title)}</title>\n'
        '  <style>\n'
        f'{base_style_block()}'
        f'{state_css}'
        f'{extra_style}'
        '  </style>\n'
        '</head>'
    )


def vpm_body_class(state: str) -> str:
    """Return the canonical class attribute value for the VPM body wrapper
    div, given a visual state.

    For most states this is just `vpm-body`. For `emulated` it expands to
    `vpm-body vpm-emulated` so the CSS `filter: grayscale(100%)` rule in
    visual_state_css(emulated) targets it (this is the load-bearing DOM
    signature for the emulated state per VISUAL_STATE_SIGNATURES['emulated']).

    All 4 internal VPM compilers (HONESTY-BOARD, AGENT-REVIEW, CDRR-DAG,
    GIC-LEDGER-BETA) consume this helper so the emulated grayscale
    treatment is applied uniformly without per-compiler conditionals.
    """
    if state not in VISUAL_STATES:
        raise ValueError(
            f"state must be one of {VISUAL_STATES}; got {state!r}"
        )
    if state == "emulated":
        return "vpm-body vpm-emulated"
    return "vpm-body"


def signature_substrings_for_state(state: str) -> Iterable[str]:
    """Return the substrings the grammar test band asserts are present in
    emitted HTML for `state`. Thin accessor over VISUAL_STATE_SIGNATURES."""
    if state not in VISUAL_STATES:
        raise ValueError(
            f"state must be one of {VISUAL_STATES}; got {state!r}"
        )
    return VISUAL_STATE_SIGNATURES[state]


# ===========================================================================
# Claude-Design certificate shell (TEMPLATE v3) — render_vpm_certificate()
# ---------------------------------------------------------------------------
# Translates the design bundle's vpm_artifacts/*.html into a single shared
# renderer so EVERY compiled artifact looks like the corner-bracket framed
# certificate (eyebrow / wordmark / big title / state-stamp / commitment
# block + per-class content table + design integrity label + 4-up footer).
#
# FROZEN-safe by construction: every load-bearing visual-state signature is
# sourced from the existing (unchanged) helpers —
#   visual_state_meta_tag()  -> <meta name="vpm-visual-state">
#   visual_state_css()       -> per-state CSS incl. the literal #d65b78 /
#                               #020408 / filter: grayscale(100%) /
#                               text-decoration: line-through substrings
#   visual_state_overlay()   -> saturation bar / stripe svg / lock svg /
#                               redacted banner markup
#   vpm_body_class()         -> "vpm-body vpm-emulated" for emulated
# plus a design grammar-marker carrying role="status" + data-vpm-visual-state.
# The certificate base CSS uses var(--vpm-accent) for the state accent so the
# frame border + corner brackets + stamp + commitment hash share one color
# without per-state CSS branching. The design's webfont @import is dropped;
# typography is the same self-contained system stack as base_style_block().
# ===========================================================================


# Per-state stamp label + accent color. The label is ALWAYS a text phrase
# (brand discipline: color never carries meaning alone). Accent feeds the
# CSS custom property --vpm-accent on <main class="frame">.
_CERT_STAMP_BY_STATE = {
    "live":            ("LIVE · CRYPTOGRAPHICALLY ANCHORED", "#5bd6a3"),
    "dry-run":         ("DRY-RUN · NOT PRODUCTION-ANCHORED", "#f0a868"),
    "emulated":        ("EMULATED · MOCK / NON-PRODUCTION SOURCE", "#7a8a9b"),
    "frozen-disabled": ("FROZEN · PRIMITIVE DISABLED AT RUNTIME", "#5a6675"),
    "revoked":         ("REVOKED · DO NOT RELY ON THIS PROJECTION", "#d65b78"),
    "unverified":      ("UNVERIFIED · MATERIAL MISSING OR DRIFTED", "#d65b78"),
}


def _group_hex(hex_str: str, group: int = 8) -> str:
    """Space-group a hex string into `group`-char blocks (design commitment
    block style: 'a91d0c4e b8f2710d ...'). Non-hex input is returned escaped
    as-is so the function never raises on a malformed commitment."""
    h = str(hex_str).lower().removeprefix("0x")
    if not h or any(c not in "0123456789abcdef" for c in h):
        return html.escape(str(hex_str))
    return " ".join(h[i:i + group] for i in range(0, len(h), group))


def cert_data_table(rows: Iterable) -> str:
    """Emit a design content table (<table><tbody>…</tbody></table>) of
    key/value rows using the certificate's td.k / td.v classes.

    Each row is a 2- or 3-tuple:
      (key, value_html)               -> td.v (neutral)
      (key, value_classes, value_html)-> td.v {value_classes}

    `value_html` is inserted verbatim (callers build trusted markup, e.g.
    nested .row spans or .pill chips); `key` is escaped.
    """
    out: list[str] = ['<table>\n  <tbody>']
    for row in rows:
        if len(row) == 3:
            key, vcls, vhtml = row
        else:
            key, vhtml = row
            vcls = ""
        cls = ("v " + vcls).strip()
        out.append(
            f'    <tr><td class="k">{html.escape(str(key))}</td>'
            f'<td class="{cls}">{vhtml}</td></tr>'
        )
    out.append('  </tbody>\n</table>')
    return "\n".join(out)


def cert_section(heading: str, count_html: str, rows: Iterable) -> str:
    """Emit a per-class content section: <h2>heading <span class=count>…</span>
    </h2> + a cert_data_table(rows). `count_html` may be '' (no count chip)."""
    count = (
        f' <span class="count">{count_html}</span>' if count_html else ""
    )
    return (
        f'<h2>{html.escape(str(heading))}{count}</h2>\n'
        + cert_data_table(rows)
    )


def _integrity_display(field: str, value) -> str:
    """Human display string for an integrity-label value, design-flavored."""
    if field == "on_chain_anchor":
        if isinstance(value, bool):
            return "IoTeX L1" if value else "none"
        return str(value)
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, (list, tuple)):
        return " · ".join(str(v) for v in value)
    return str(value)


def _integrity_value_class(field: str, display: str) -> str:
    """Semantic td.v color class for an integrity field — chain-green for
    anchored, amber for weights, red ONLY for genuine risk values."""
    d = display.strip().upper()
    if field == "on_chain_anchor":
        return "chain" if d not in ("", "NO", "FALSE", "NONE", "N/A") else "dim"
    if field == "proof_weight":
        return "amber"
    if field == "raw_biometrics_exposed":
        return "err" if d in ("YES", "TRUE") else ""
    if field == "consent_active":
        # red ONLY for an explicit NO; N/A is not-applicable, not a risk.
        return "err" if d in ("NO", "FALSE") else ""
    if field == "revocation_status":
        return "" if d in ("NONE", "ACTIVE", "N/A", "") else "err"
    return ""


def integrity_label_table_html(label: dict) -> str:
    """Emit the 9-field Integrity Nutrition Label as the design certificate
    table (vs. the legacy <dl> in integrity_label_html()).

    Carries `class="vpm-integrity-label"` on the table (satisfies the
    compiler's _verify_integrity_label_in_dom container check) and a
    `data-vpm-field="<field>"` marker on every value cell (satisfies the
    9-field marker check + the frontend grammar verifier). Missing fields
    raise ValueError so renderer authors fail fast.
    """
    if not isinstance(label, dict):
        raise TypeError(f"label must be dict; got {type(label).__name__}")
    missing = [f for f in INTEGRITY_LABEL_FIELDS if f not in label]
    if missing:
        raise ValueError(f"integrity_label missing required fields: {missing}")

    rows: list[str] = []
    for field in INTEGRITY_LABEL_FIELDS:
        display = _integrity_display(field, label[field])
        vcls = _integrity_value_class(field, display)
        cls = ("v mono " + vcls).strip()
        rows.append(
            f'    <tr><td class="k">{field}</td>'
            f'<td class="{cls}" data-vpm-field="{field}">'
            f'{html.escape(display)}</td></tr>'
        )
    return (
        '<h2>Integrity · Nutrition · Label '
        '<span class="count">9 FROZEN fields</span></h2>\n'
        '<table class="vpm-integrity-label" '
        'aria-label="Integrity Nutrition Label">\n  <tbody>\n'
        + "\n".join(rows)
        + '\n  </tbody>\n</table>'
    )


def _certificate_base_css() -> str:
    """Design certificate chrome CSS (TEMPLATE v3). Inner-CSS only; caller
    wraps with <style>. Self-contained: NO @import / @font-face / external
    URLs (the design mockup's Google-Fonts @import is intentionally dropped
    and replaced with the same system stack as base_style_block()). The
    state accent is var(--vpm-accent) set inline on .frame."""
    return (
        "* { box-sizing: border-box; }\n"
        "html, body { margin: 0; padding: 0; }\n"
        "body {\n"
        "  background: #04060a; color: #d4dde8;\n"
        "  font-family: ui-monospace, 'JetBrains Mono', 'SF Mono', "
        "'Cascadia Code', Menlo, Consolas, 'Courier New', monospace;\n"
        "  font-size: 13px; line-height: 1.45; font-variant-ligatures: none;\n"
        "  background-image:\n"
        "    linear-gradient(to right,  rgba(26,34,48,0.27) 1px, transparent 1px),\n"
        "    linear-gradient(to bottom, rgba(26,34,48,0.27) 1px, transparent 1px),\n"
        "    linear-gradient(to right,  rgba(26,34,48,0.10) 1px, transparent 1px),\n"
        "    linear-gradient(to bottom, rgba(26,34,48,0.10) 1px, transparent 1px);\n"
        "  background-size: 96px 96px, 96px 96px, 24px 24px, 24px 24px;\n"
        "  padding: 28px; }\n"
        # visually-hidden grammar marker (keeps verifier honest)
        ".vpm-grammar-marker { position: absolute; width: 1px; height: 1px;\n"
        "  margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0);\n"
        "  white-space: nowrap; border: 0; }\n"
        # frame — corner-bracket card; accent via --vpm-accent
        ".frame { position: relative; background: #0a0e14;\n"
        "  border: 1px solid var(--vpm-accent, #5bd6a3);\n"
        "  padding: 32px 36px 28px; max-width: 1200px; margin: 0 auto; }\n"
        ".frame::before, .frame::after { content: \"\"; position: absolute;\n"
        "  width: 22px; height: 22px; border: 1px solid var(--vpm-accent, #5bd6a3); }\n"
        ".frame::before { top: -1px; left: -1px; border-right: 0; border-bottom: 0; }\n"
        ".frame::after  { bottom: -1px; right: -1px; border-left: 0; border-top: 0; }\n"
        # header
        ".head { display: grid; grid-template-columns: 1fr auto; gap: 18px;\n"
        "  align-items: start; padding-bottom: 20px; border-bottom: 1px solid #1a2230; }\n"
        ".eyebrow { font-size: 10.5px; color: #5a6675; letter-spacing: 0.18em;\n"
        "  text-transform: uppercase; line-height: 1; }\n"
        ".wm { font-family: 'Syne', system-ui, sans-serif; font-weight: 700;\n"
        "  color: #d4dde8; font-size: 22px; letter-spacing: -0.02em; line-height: 1;\n"
        "  margin-top: 12px; }\n"
        ".wm .t { font-weight: 800; color: #f0a868; }\n"
        ".frame h1 { font-family: 'Syne', system-ui, sans-serif; font-weight: 700;\n"
        "  font-size: 38px; color: #d4dde8; letter-spacing: -0.01em; line-height: 1.1;\n"
        "  margin: 14px 0 8px; border: 0; padding: 0; }\n"
        ".subtitle { font-size: 11.5px; color: #8a96a5; letter-spacing: 0.06em;\n"
        "  text-transform: uppercase; }\n"
        ".stamp { display: inline-flex; align-items: center; gap: 9px;\n"
        "  padding: 5px 11px; border: 1px solid var(--vpm-accent, #5bd6a3);\n"
        "  border-radius: 2px; color: var(--vpm-accent, #5bd6a3); font-size: 11px;\n"
        "  letter-spacing: 0.1em; text-transform: uppercase; line-height: 1;\n"
        "  white-space: nowrap; }\n"
        ".stamp::before { content: \"\"; width: 8px; height: 8px; border-radius: 50%;\n"
        "  background: var(--vpm-accent, #5bd6a3); }\n"
        # commitment block
        ".commit-block { margin: 22px 0 26px; }\n"
        ".commit-block .label { font-size: 10px; color: #5a6675;\n"
        "  letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 8px; }\n"
        ".commit-block .hash { font-size: 16px; color: var(--vpm-accent, #5bd6a3);\n"
        "  letter-spacing: 0.04em; line-height: 1.5; word-break: break-all; }\n"
        # section headers + tables
        ".frame h2 { font-family: 'Syne', system-ui, sans-serif; font-weight: 600;\n"
        "  font-size: 16px; color: #d4dde8; letter-spacing: 0.06em;\n"
        "  text-transform: uppercase; margin: 26px 0 12px; border: 0; padding: 0; }\n"
        ".frame h2 .count { font-family: ui-monospace, monospace; font-weight: 500;\n"
        "  font-size: 11px; color: #5a6675; letter-spacing: 0.06em; margin-left: 10px;\n"
        "  text-transform: none; }\n"
        ".frame table { width: 100%; border-collapse: separate; border-spacing: 0;\n"
        "  background: #0d1218; border: 1px solid #1a2230; border-radius: 4px;\n"
        "  overflow: hidden; margin: 0; }\n"
        ".frame tr + tr td { border-top: 1px solid rgba(26,34,48,0.4); }\n"
        ".frame td { padding: 11px 16px; font-size: 12.5px; vertical-align: baseline; }\n"
        ".frame td.k { color: #8a96a5; width: 280px; font-size: 11px;\n"
        "  letter-spacing: 0.08em; text-transform: uppercase; }\n"
        ".frame td.v { color: #d4dde8; }\n"
        ".frame td.v.chain { color: #5bd6a3; }\n"
        ".frame td.v.amber { color: #f0a868; }\n"
        ".frame td.v.err   { color: #d65b78; }\n"
        ".frame td.v.dim   { color: #8a96a5; }\n"
        ".frame td.v.mono  { letter-spacing: 0.04em; }\n"
        ".frame td.v .row { display: flex; justify-content: space-between; gap: 14px; }\n"
        ".frame td.v .row + .row { margin-top: 4px; padding-top: 4px;\n"
        "  border-top: 1px solid rgba(26,34,48,0.4); }\n"
        ".frame td.v .row .lbl { color: #5a6675; font-size: 10.5px;\n"
        "  letter-spacing: 0.08em; text-transform: uppercase; }\n"
        ".frame td.v .row .val { color: inherit; }\n"
        ".frame code { color: #5bd6a3; background: transparent; border: 0;\n"
        "  padding: 0; word-break: break-all; }\n"
        # status pill chips inside value cells
        ".pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px;\n"
        "  border: 1px solid currentColor; border-radius: 2px; font-size: 10px;\n"
        "  letter-spacing: 0.08em; text-transform: uppercase; line-height: 1; }\n"
        ".pill::before { content: \"\"; width: 6px; height: 6px; border-radius: 50%;\n"
        "  background: currentColor; }\n"
        ".pill.chain { color: #5bd6a3; } .pill.amber { color: #f0a868; }\n"
        ".pill.err { color: #d65b78; } .pill.dim { color: #5a6675; }\n"
        # footer 4-up
        ".frame footer { margin-top: 26px; padding-top: 16px;\n"
        "  border-top: 1px solid #1a2230; display: grid;\n"
        "  grid-template-columns: repeat(4, 1fr); gap: 14px 24px; font-size: 11.5px; }\n"
        ".frame footer .k { color: #5a6675; letter-spacing: 0.14em;\n"
        "  text-transform: uppercase; font-size: 10px; display: block; margin-bottom: 4px; }\n"
        ".frame footer .v { color: #d4dde8; letter-spacing: 0.02em; word-break: break-all; }\n"
        # live saturation bar (FROZEN class; design styling, accent-colored)
        ".vpm-saturation-class { display: inline-block; width: 4px; height: 18px;\n"
        "  background: var(--vpm-accent, #5bd6a3); vertical-align: middle;\n"
        "  margin-right: 8px; }\n"
        # dry-run stripe svg pinned top-right
        ".vpm-stripe-mask { position: fixed; top: 12px; right: 12px;\n"
        "  width: 80px; height: 14px; pointer-events: none; }\n"
        # frozen-disabled lock pinned top-right
        ".vpm-lock-icon { position: fixed; top: 16px; right: 16px; width: 22px;\n"
        "  height: 22px; opacity: 0.7; }\n"
        # revoked redacted banner under header
        ".vpm-redacted-banner { background: #d65b7811; border: 1px solid #d65b78;\n"
        "  color: #d65b78; padding: 8px 14px; margin: 0 0 22px; font-size: 11.5px;\n"
        "  letter-spacing: 0.16em; text-transform: uppercase;\n"
        "  text-decoration: line-through; text-decoration-color: rgba(214,91,120,0.6); }\n"
    )


def render_vpm_certificate(
    *,
    vpm_class: str,
    title_text: str,
    subtitle: str,
    visual_state: str,
    commitment_hex: str,
    content_html: str,
    integrity_label: dict,
    footer_fields: Iterable,
    page_title: str | None = None,
    extra_style: str = "",
) -> str:
    """Render a complete self-contained VPM proof certificate (TEMPLATE v3).

    Shared shell for every compiler. Produces the corner-bracket framed
    certificate from the Claude-Design bundle, with all FROZEN visual-state
    signatures embedded (via the unchanged visual_state_* helpers) so the
    6-state grammar band + frontend VpmGrammarVerifier stay green.

    Args:
      vpm_class:       class id shown as <title>/meta + (default) big title,
                       e.g. "GIC-LEDGER-BETA-v1".
      title_text:      big <h1> text (usually == vpm_class).
      subtitle:        JBM uppercase sub-line under the title.
      visual_state:    1-of-6 FROZEN states.
      commitment_hex:  the input commitment (64 hex); shown space-grouped.
      content_html:    per-class section markup (trusted; built via
                       cert_section()/cert_data_table()).
      integrity_label: 9-field dict -> design integrity table.
      footer_fields:   iterable of (label, value) — the 4-up provenance row.
      page_title:      <title> tag; defaults "VPM Proof · {vpm_class}".
      extra_style:     optional extra inner-CSS appended last.
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )

    stamp_label, accent = _CERT_STAMP_BY_STATE[visual_state]
    body_class = f"vpm-body vpm-{visual_state}"  # 'vpm-body vpm-emulated' for emulated (FROZEN)
    meta_state = visual_state_meta_tag(visual_state)
    aria_text = _ARIA_LABEL_BY_STATE[visual_state]
    grammar_marker = (
        f'<div role="status" data-vpm-visual-state="{visual_state}" '
        f'aria-label="{html.escape(aria_text)}" '
        f'class="vpm-grammar-marker">{visual_state}</div>'
    )
    overlay = visual_state_overlay(visual_state)
    live_marker = overlay if visual_state == "live" else ""
    post_header_overlay = "" if visual_state == "live" else overlay

    pg_title = page_title or f"VPM Proof · {vpm_class}"
    grouped = _group_hex(commitment_hex)

    footer_cells = []
    for label, value in footer_fields:
        footer_cells.append(
            f'    <div><span class="k">{html.escape(str(label))}</span>'
            f'<span class="v">{html.escape(str(value))}</span></div>'
        )
    footer_html = "\n".join(footer_cells)

    integrity_table = integrity_label_table_html(integrity_label)

    # visual_state_css FIRST (carries FROZEN literals incl. #d65b78/#020408);
    # design chrome SECOND so higher-specificity .frame rules win visually.
    css = (
        visual_state_css(visual_state)
        + _certificate_base_css()
        + (extra_style or "")
    )

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{meta_state}\n"
        f'<meta name="vpm-class" content="{html.escape(vpm_class)}">\n'
        f'<meta name="vpm-template-version" content="{VPM_TEMPLATE_VERSION}">\n'
        f"<title>{html.escape(pg_title)}</title>\n"
        "<style>\n"
        f"{css}"
        "</style>\n"
        "</head>\n"
        f'<body class="{body_class}" data-vpm-id="{html.escape(vpm_class)}" '
        f'data-visual-state="{visual_state}" '
        f'data-commitment-hex="{html.escape(str(commitment_hex))}">\n'
        f"{grammar_marker}\n"
        f'<main class="frame" style="--vpm-accent: {accent}">\n'
        '  <header class="head">\n'
        "    <div>\n"
        f'      <div class="eyebrow">VERIFIED · PROJECTION · MEDIA · v{VPM_TEMPLATE_VERSION}</div>\n'
        f'      <div class="wm">{live_marker}Qor<span class="t">T</span>roller</div>\n'
        f"      <h1>{html.escape(title_text)}</h1>\n"
        f'      <div class="subtitle">{html.escape(subtitle)}</div>\n'
        "    </div>\n"
        f'    <span class="stamp">{html.escape(stamp_label)}</span>\n'
        "  </header>\n"
        f"  {post_header_overlay}\n"
        '  <section class="commit-block">\n'
        '    <div class="label">COMMITMENT_HEX · the input this proof commits to</div>\n'
        f'    <div class="hash">{grouped}</div>\n'
        "  </section>\n"
        f"  {content_html}\n"
        f"  {integrity_table}\n"
        "  <footer>\n"
        f"{footer_html}\n"
        "  </footer>\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )
