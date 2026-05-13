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

    No @font-face, no @import, no external URLs. system-monospace per
    Phase O4 plan §3 Stream A.0 compiler-discipline item 2.
    """
    return (
        "body { font-family: 'Courier New', monospace; "
        "background: #020408; color: #cfe8ff; margin: 0; padding: 1.5em; "
        "line-height: 1.5; }\n"
        "h1 { color: #5a8fb8; border-bottom: 1px solid #1a2a40; "
        "padding-bottom: 0.3em; }\n"
        "h2 { color: #5a8fb8; font-size: 1.0em; margin-top: 1.4em; "
        "border-bottom: 1px dotted #1a2a40; padding-bottom: 0.2em; }\n"
        ".vpm-body { padding: 1em; }\n"
        ".vpm-integrity-label { border: 1px solid #1a2a40; "
        "padding: 1em; margin-top: 1.2em; background: #0a0e14; }\n"
        ".vpm-integrity-label dt { color: #5a8fb8; font-weight: bold; "
        "display: inline-block; min-width: 14em; }\n"
        ".vpm-integrity-label dd { display: inline; margin: 0 0 0.4em 0; "
        "color: #cfe8ff; }\n"
        ".vpm-integrity-label dd::after { content: ''; display: block; }\n"
        "code { color: #d4f0ff; background: #0a0e14; padding: 1px 4px; "
        "border-radius: 2px; word-break: break-all; }\n"
        ".vpm-footer { margin-top: 2em; color: #607a93; font-size: 0.8em; "
        "border-top: 1px solid #1a2a40; padding-top: 0.5em; }\n"
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
        f'  {meta_state}\n'
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
