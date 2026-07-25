# Retina Witness Mark — scope (D-RWM-1 RESOLVED: Path A. Implementation plan pending, no code yet.)

**Status: D-RWM-1 RESOLVED — Path A (2026-07-23, operator decision via the
claude-ai⇄claude-code A2A loop).** Operator: *"I agree with the logical
recommendations provided"* — adopting the reviewer's full recommendation
set: **Path A as L0 of the NOV ladder → NOV-3 → NOV-2 → NOV-1**, each layer
opened only after the prior layer's live verification passes. Path B
(device-signed, SE-dependent) is banked behind the Path-A-Arc-2 hardware
gate, not abandoned — see § D-RWM-1 below for the still-valid fork writeup.

RWM Path A now becomes "L0" in a larger sequence (see
`docs/a2a/retina-witness-mark-ladder/` for NOV-3/NOV-2/NOV-1, opened only
once L0 ships and live-verifies).

**L0 STATUS UPDATE 2026-07-24:** L0 **shipped and live-verified** on rig
session `cfb_rwm_live_01` (1076 frames; post-session check EXIT 0; locator
decoded through OBS path). Gate record:
`docs/a2a/retina-witness-mark-ladder/l0-live-verify-2026-07-24.md`.
**NOV-3 is BUILT (CANDIDATE)** — see ladder `nov-3-scope.md` + implementation
plan. **NOV-2 is BUILT (CANDIDATE)** — bind + checkpoint inventory + SHARE
postcard; offline CLI `scripts/rwm_nov2_cli.py`. **NOV-1 scope + plan DRAFTED**
(`nov-1-scope.md` / `nov-1-implementation-plan.md`) — code needs GO.

~~**Still no code written, no production file touched.** Per the A2A protocol's own explicit next step ("r05 is your
implementation plan for review before any code"), the next deliverable is an
implementation plan for Path A specifically — not code, and not yet
authorized to become code without a further explicit go-ahead.~~
*(original hold line — superseded by L0 ship + live-verify above; kept for the record.)*

The design as originally written below had a confirmed BLOCK-severity flaw
(F-RWM-1) — the "cryptographically ties the footage to that session" claim
was false as specified. The scoping *discipline* (ground on real
infrastructure, propose CANDIDATE not FROZEN, no code without authorization)
was validated as correct throughout; the specific design needed the fork
decision now resolved above. See **§ Review findings** and **§ D-RWM-1**
below — added findings-forward, original text preserved (not rewritten),
matching this project's established `[SUPERSEDED-...]` convention for
corrected claims.

~~**Status:** scoping only. No code written, no production file touched. This
is a new-primitive proposal, not a bug fix — a different risk/effort class
than anything else built this session, and explicitly framed as CANDIDATE
(not FROZEN-v1) per the project's own convention for new commitment families.~~
*(original status line, superseded by the HOLD above — kept for the record.)*

## What this is, precisely

**Not** an overlay rendered into the game itself — the PS5/console rendering
pipeline cannot be hooked by a third party, so nothing about what the player
sees on their TV changes, ever. This is a small, cryptographically-derived
visual marker that QorTroller's **own capture pipeline** composites onto **its
own archived copy** of captured frames — turning recorded gameplay footage
into independently-verifiable evidence that it came from a specific,
signed PoAC session at a specific point in that session's hash chain.

**Category:** forensic/evidentiary primitive, not a real-time anti-cheat
signal (this distinction was made explicit in the prior exploratory turn and
carries through the whole design — it does not detect cheating during play;
it makes footage tamper-evident after the fact, e.g. for adjudication
disputes or stream-authenticity claims).

## Why this is buildable on existing infrastructure, not from scratch

Every piece this needs already exists in some form:

- **The capture pipeline already exists.** `bridge/vapi_bridge/
  qortroller_retina_capture.py` (`WgcFrameSource`/`UvcFrameSource`) already
  turns the game's video (screen-grab or physical HDMI capture card) into
  frames the bridge processes. This proposal adds a compositing step to the
  *archival* path only — never the buffer that feeds killfeed/down-distance
  OCR (confirmed those ROIs are per-game configurable fractions, not fixed
  coordinates, so there is no safe fixed corner to avoid on the *live* buffer
  — the only structurally safe answer is to never touch it at all).
- **The commitment-scheme convention already exists**, exactly reusable:
  `bridge/vapi_bridge/retina_state_commitment.py`'s v1/v2/v3 all follow
  `SHA-256(DOMAIN_TAG || device_id(32) || ts_ns_be(8) || ...)`, shipped as
  **CANDIDATE** (not PV-CI-pinned) with promotion to FROZEN-v1 as an explicit,
  separate **operator governance seal** — never autonomous. This proposal
  follows that identical pattern, down to the domain-tag naming convention
  (`VAPI-RETINA-STATE-v1/v2/v3` → propose `VAPI-RETINA-WITNESS-MARK-v1`).
- **The bit-encoding scheme already exists, designed and reasoned through**:
  Sensor Stack v2.1's Surface 4 (lightbar optical emission) already spec'd a
  "3-color symbol stream at 5-15 symbols/second producing 25-75 bits over a
  5-second window" as a challenge-response witness channel via the
  controller's LED. This proposal reuses that exact bit-encoding concept —
  coarse, high-contrast, temporally-spread color blocks — rendered as a small
  on-frame region across a *sequence* of archived frames instead of via the
  physical lightbar. This is a deliberate choice over a QR-code-style dense
  spatial encoding: coarse solid color blocks survive lossy video
  re-compression (which archived/streamed footage routinely gets) far better
  than fine QR modules would.
- **The chain-head-binding convention already exists**: VAME
  (`commitment = SHA-256(VAPI-VAME-v1 || chain_head_16b || ts_ns_be(8) ||
  endpoint || body_bytes)`) already does exactly this pattern — bind an
  observable artifact to a specific point in the session's hash chain — just
  for HTTP response headers instead of video frames.

Nothing here is a new cryptographic idea for this project; it's recombining
four already-shipped, already-vetted pieces into a new artifact.

## Proposed design

**New module:** `l9_presence/retina_witness_mark.py` (matches the `l9_presence/`
convention for novel candidate primitives), pure functions, no bridge
dependency at import time (matches this session's established discipline):

```python
DOMAIN_TAG = b"VAPI-RETINA-WITNESS-MARK-v1"  # CANDIDATE — not PV-CI-pinned

def compute_witness_mark_commitment(device_id_hex: str, ts_ns: int, chain_head_32: bytes) -> bytes:
    """SHA-256(DOMAIN_TAG || device_id(32) || ts_ns_be(8) || chain_head(32))."""

def encode_mark_symbols(commitment: bytes, n_symbols: int = 25) -> list[tuple[int, int, int]]:
    """Deterministically maps commitment bits to a sequence of high-contrast
    RGB colors from a small fixed palette (mirrors the lightbar's 3-symbol
    scheme, extended since a screen region has more expressive range than
    one LED)."""

def composite_mark_onto_frame(frame, symbol, *, corner="bottom-right", block_px=32):
    """Pure: returns a NEW frame array with one solid-color block drawn in a
    corner region. Never mutates the input. One symbol per archived frame in
    sequence -- the mark is temporal (spread across N consecutive archived
    frames), not spatial-in-one-frame."""

def decode_mark_from_frames(frames: list) -> bytes:
    """Verifier side: reads the color-block sequence back from N frames,
    reconstructs the bit sequence. Used independently of the bridge, by
    anyone reviewing archived footage."""
```

**Bridge integration point:** wherever archived frames/crops currently get
written to disk (the `retina_kf_archive`/session-manifest path referenced in
CLAUDE.md's U1 session-archive work) — composite the mark onto the archived
copy right before it's saved, using the CURRENT PoAC chain-head (already
tracked in `chain.py`) at that moment. **Not** the live OCR-feeding buffer.

**[SUPERSEDED-F-RWM-1] Verification story (ORIGINAL, FALSE AS SPECIFIED —
kept verbatim for the record, see § Review findings):** anyone with (a) the
archived footage and (b) the claimed session's on-chain/signed chain-head
values can independently run `decode_mark_from_frames` and compare against
`compute_witness_mark_commitment` recomputed from the claimed metadata. A
match cryptographically ties the footage to that exact session at that exact
chain position; a mismatch or absence means the provenance claim is
unverified — a genuinely new capability, distinct from VAME (HTTP headers,
not video) and from PoSP (session_id metadata join, not a pixel-level
tamper-evident binding).

**Why this is false:** `compute_witness_mark_commitment`'s three inputs
(`device_id`, `ts_ns`, `chain_head`) contain zero frame content and are all
public/derivable from session metadata alone — none require possession of
the actual video. `encode_mark_symbols` is a pure, public, unkeyed function.
So anyone who knows a session's metadata can compute the identical
commitment, encode the identical symbols, and composite a valid mark onto
*any* footage — doctored, unrelated, or fabricated — and it will decode
correctly. The mark is freely reproducible independent of what it's marking.
Contrast with VAME, the cited precedent: VAME's commitment includes
`body_bytes` — the actual response content — which is exactly the term this
design dropped when adapting VAME's pattern. Without a content or signature
term, "the mark verifies" and "the footage is genuine" are unrelated claims.
See F-RWM-1 below.

## Scope boundaries — what this does NOT do

- Does not touch the 228-byte PoAC wire, or any FROZEN-v1 primitive.
- Does not render anything into what the player sees on their TV/monitor —
  the console output is completely untouched.
- Does not touch the live buffer feeding killfeed/down-distance OCR — operates
  only on a separate archival copy, so it cannot regress existing detection
  by construction, not by care taken to avoid overlapping a specific ROI.
- Is not a real-time anti-cheat signal — evidentiary/forensic only, verified
  after the fact.
- Does not become FROZEN-v1 in this scope — ships CANDIDATE, matching
  `VAPI-RETINA-STATE-v1/v2/v3`'s own precedent; promotion is a later,
  separate, explicit operator governance seal.

## Test plan

1. Unit tests for `compute_witness_mark_commitment` (determinism, domain
   separation from `VAPI-RETINA-STATE-v1/v2/v3` and `VAPI-VAME-v1`).
2. Unit tests for `encode_mark_symbols` / `decode_mark_from_frames` round-trip
   on synthetic frame arrays — including a robustness check with simulated
   compression artifacts (Gaussian blur / JPEG-style block noise added to the
   color region before decode) to establish an actual measured margin, not
   an assumed one.
3. A standalone repro script (matching this session's established pattern)
   proving round-trip correctness end to end: commitment → symbols →
   composited frames → decoded symbols → recovered commitment.

## Review findings (Claude.ai external review, 2026-07-23) — HOLD

Verdict: **HOLD on the design as written; the scoping discipline itself is
right.** Four findings, then a decision. Added findings-forward per the
project's own convention — the original design and its false claim are
preserved above with a `[SUPERSEDED-F-RWM-1]` marker, not deleted.

**F-RWM-1 (BLOCK).** The commitment
`SHA-256(TAG || device_id || ts_ns || chain_head)` contains no frame
content, and every input is public/derivable. Anyone with session metadata
can compute the commitment, encode the symbols, and composite a valid mark
onto arbitrary or doctored footage — the frame pixels never enter the hash.
VAME (the cited precedent) commits over `body_bytes`; this design dropped
the content term and with it the tamper-evidence claim. "A match
cryptographically ties the footage to that session" is false as specified —
it ties the *mark* to the session, and the mark is freely reproducible.
Middle-of-footage edits also pass decode unchanged. Independently verified
against the design above before accepting this finding — confirmed correct.

**F-RWM-2 (WARN).** The fix isn't just "add a frame hash" — exact-pixel
hashes die under the re-compression the doc itself anticipates (the entire
reason coarse color blocks were chosen over QR encoding), and a signed
per-frame-hash manifest chained into PoAC achieves tamper-evidence with no
visual mark at all. This forces a fork — see D-RWM-1.

**F-RWM-3 (WARN).** No channel coding. Decoding from transcoded/frame-dropped
archived footage needs a sync preamble + error correction (e.g., Reed–Solomon
over the symbol stream), and the original design never sized the truncation:
25-75 bits at the proposed density vs. a 256-bit commitment. Sizing deferred
until D-RWM-1 resolves — Path B changes the bit budget entirely.

**F-RWM-4 (INFO).** The temporal claim was one-sided in the original design:
archive-time stamping with the current chain-head proves "no earlier than"
(a freshness floor), not "depicts gameplay at" that chain position. State
this explicitly in any future revision.

## Decision D-RWM-1 — RESOLVED: Path A

**Path A — demote the claim (CHOSEN).** The mark becomes a locator tag
("footage claims session X, chain position Y"), paired with a signed
per-frame-hash manifest for pristine-archive tamper-evidence; the mark alone
is an honest breadcrumb on transcoded copies, not a tamper-evidence proof by
itself. Cheap, buildable on current infrastructure. The verification story
in § Proposed design above is corrected accordingly in the implementation
plan (`docs/a2a/retina-witness-mark/l0-implementation-plan.md`, sibling to
this doc) rather
than rewritten in place here, per the findings-forward convention.

Per the reviewer's r02 stacking analysis (independently checked and
confirmed, see LANE RWM r05 disposition): NOV-3 (ledger-native dispute
escrow) consumes L0's manifest almost whole — its "new surface" may reduce
to wiring the already-shipped `sdk/wmp_disclosure.py` selective-disclosure
primitive to PoAC-segment claims, not building a new reveal protocol. That
sizing belongs in the L0 plan, not resolved here.

**Path B — earn the original claim (BANKED, not abandoned).** The mark
would encode a device-signed value over
`chain_head || window_index || perceptual_hash(window)` — unforgeable
(requires the device's private key), transcoding-tolerant (perceptual, not
exact-pixel, hash). The secure element is the natural signer, which ties
this to the Path A Arc 2 hardware gate — it stays banked there, not
abandoned; the encode/decode/composite channel built for Path A carries
forward unchanged if/when Path B is revisited (confirmed via file:line
check in LANE RWM r05: `encode_mark_symbols`/`decode_mark_from_frames`/
`composite_mark_onto_frame` are payload-agnostic by construction).

**Status: RESOLVED 2026-07-23.** Operator: *"I agree with the logical
recommendations provided"* (adopting Path A + the L0→NOV-3→NOV-2→NOV-1
ladder + true-merge posture for `main`, via the claude-ai⇄claude-code A2A
loop). Open questions 1-2 below are no longer premature — they're now live
inputs to the L0 implementation plan.

## Open questions for the operator

1. **Palette size / symbol count** — now live for Path A specifically (no
   longer needs to accommodate Path B's larger signature payload). Addressed
   in the L0 implementation plan, not finally decided here.
2. **Refresh cadence** — same status, addressed in the L0 implementation
   plan.
3. **Where exactly in the archive path this hooks in** — needs a closer read
   of the U1 session-archive manifest code (`retina_capture_daemon.py`) than
   this scoping pass did. Addressed in the L0 implementation plan.
4. **Live verification plan** — like every prior primitive built this
   session, this would need a real rig pass once built (real capture card,
   real archived footage, independent decode) before being trusted — still a
   later step, still needs the standing "ask before rig sessions" go-ahead
   when it comes up.

## Ceiling

This document only (plus the companion L0 implementation plan, also
doc-only). No code written. No production file touched. Not authorized to
build without a further, explicit, separate go-ahead after the
implementation plan is reviewed. **Current state: D-RWM-1 RESOLVED (Path A);
implementation plan next; still no code.**
