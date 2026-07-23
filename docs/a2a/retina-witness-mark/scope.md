# Retina Witness Mark — scope (NOT built, NOT authorized to build)

**Status:** scoping only. No code written, no production file touched. This
is a new-primitive proposal, not a bug fix — a different risk/effort class
than anything else built this session, and explicitly framed as CANDIDATE
(not FROZEN-v1) per the project's own convention for new commitment families.

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

**Verification story:** anyone with (a) the archived footage and (b) the
claimed session's on-chain/signed chain-head values can independently run
`decode_mark_from_frames` and compare against
`compute_witness_mark_commitment` recomputed from the claimed metadata. A
match cryptographically ties the footage to that exact session at that exact
chain position; a mismatch or absence means the provenance claim is
unverified — a genuinely new capability, distinct from VAME (HTTP headers,
not video) and from PoSP (session_id metadata join, not a pixel-level
tamper-evident binding).

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

## Open questions for the operator

1. **Palette size / symbol count** — more colors per symbol and more symbols
   per mark trade off information density against decode robustness under
   real capture-card noise/compression; the lightbar precedent used 3 colors,
   25-75 bits over 5 seconds — worth deciding whether to match that exactly
   or widen it now that a screen region has more usable contrast range than
   one LED.
2. **Refresh cadence** — how often does the mark's underlying chain-head
   update (every frame? every N seconds, mirroring PoSR's 64-block anchor
   cadence)? Too frequent burns more archived-frame corner space; too
   infrequent weakens the temporal-binding claim.
3. **Where exactly in the archive path this hooks in** — needs a closer read
   of the U1 session-archive manifest code (`retina_capture_daemon.py`) than
   this scoping pass did, to pick the precise integration point without
   assuming its current shape.
4. **Live verification plan** — like every prior primitive built this
   session, this would need a real rig pass once built (real capture card,
   real archived footage, independent decode) before being trusted — not
   scoped here, a later step, and would need the standing "ask before rig
   sessions" go-ahead when it comes up.

## Ceiling

This document only. No code written. No production file touched. Not
authorized to build without further operator direction.
