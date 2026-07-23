# Retina Witness Mark — scope (NOT built, NOT authorized to build)

**Status: HOLD (2026-07-23, external review via Claude.ai).** The design as
originally written below has a confirmed BLOCK-severity flaw (F-RWM-1) — the
"cryptographically ties the footage to that session" claim is false as
specified. The scoping *discipline* (ground on real infrastructure, propose
CANDIDATE not FROZEN, no code without authorization) is validated as
correct; the specific design needs a fork decision before any build
authorization is possible. See **§ Review findings** and **§ D-RWM-1** below
— added findings-forward, original text preserved (not rewritten), matching
this project's established `[SUPERSEDED-...]` convention for corrected
claims. No code written, no production file touched, do not build.

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

## Decision D-RWM-1 (operator's to resolve — both paths presented, neither built)

**Path A — demote the claim.** The mark becomes a locator tag ("footage
claims session X, chain position Y"), paired with a signed per-frame-hash
manifest for pristine-archive tamper-evidence; the mark alone is an honest
breadcrumb on transcoded copies, not a tamper-evidence proof. Cheap,
buildable on current infrastructure, requires rewriting the verification
story to match what it actually proves.

**Path B — earn the original claim.** The mark encodes a device-signed value
over `chain_head || window_index || perceptual_hash(window)` — unforgeable
(requires the device's private key), transcoding-tolerant (perceptual, not
exact-pixel, hash). A ~512-bit signature implies a rolling ~17s stamp
cadence at lightbar-precedent symbol density. The secure element is the
natural signer, which makes this Path-A-Arc-2-adjacent — it banks next to
the ATECC hardware arc rather than shipping standalone.

**Status: unresolved, operator's decision.** Open questions 1-2 below
(palette size, refresh cadence) are premature until D-RWM-1 resolves — Path
B changes both the bit budget and the cadence math entirely, so sizing them
against the original (now-superseded) design would be wasted work.

## Open questions for the operator

1. ~~**Palette size / symbol count**~~ — **PREMATURE, deferred to post-D-RWM-1.**
2. ~~**Refresh cadence**~~ — **PREMATURE, deferred to post-D-RWM-1.**
3. **Where exactly in the archive path this hooks in** — needs a closer read
   of the U1 session-archive manifest code (`retina_capture_daemon.py`) than
   this scoping pass did, to pick the precise integration point without
   assuming its current shape. Still relevant under either path.
4. **Live verification plan** — like every prior primitive built this
   session, this would need a real rig pass once built (real capture card,
   real archived footage, independent decode) before being trusted — not
   scoped here, a later step, and would need the standing "ask before rig
   sessions" go-ahead when it comes up. Still relevant under either path.

## Ceiling

This document only. No code written. No production file touched. Not
authorized to build without further operator direction. **Current state:
HOLD pending D-RWM-1.**
