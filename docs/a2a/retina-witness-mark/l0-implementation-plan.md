# Retina Witness Mark — L0 (Path A) implementation plan

**Status: PLAN ONLY. No code written. Not authorized to build.** Per the A2A
protocol's own pre-committed sequence ("r05 is your implementation plan for
review before any code"), this is that deliverable. Companion to
`scope.md` (D-RWM-1 resolution) — read that first for the fork history and
why Path A was chosen over Path B.

## What changed from the original (superseded) design

The original scope's `compute_witness_mark_commitment` conflated two
different jobs: (1) a human/tool-usable *locator* pointing at which session
this footage claims to be from, and (2) *proof* the footage is genuine.
F-RWM-1 showed the same public, unkeyed function can't do both — a locator
built from public metadata is trivially reproducible onto any footage.

**Path A's fix: split the two jobs into two separate mechanisms that don't
pretend to be the other:**

1. **The manifest** (new) — a signed, hash-chained record of what the
   archive daemon actually captured, checkpointed and eventually anchored
   into PoAC. This is where real tamper-evidence lives, and only for
   pristine (non-transcoded) archives — exactly the honest boundary F-RWM-2
   named.
2. **The locator mark** (revised) — the same visual color-block channel as
   before, but its payload is now explicitly *just* a pointer ("this footage
   claims session X, checkpoint Y") — small, cheap to encode, and never
   described as proof by itself. Useful even on a transcoded copy (a
   streamer's VOD, say) precisely because it doesn't need cryptographic
   protection to be a useful breadcrumb — see it, look up session X,
   checkpoint Y, and go check the manifest/chain if you need proof.

This also resolves F-RWM-4 (the freshness-floor-vs-depicts-gameplay
conflation): the manifest proves "this frame was captured during session X",
the locator proves nothing by itself, and the plan states that plainly
instead of overclaiming.

## Component 1: the manifest (`retina_capture_manifest.py`, new)

**F-RWM-7 disposition: fixed, not disputed.** The prior draft claimed "the
exact FROZEN-v1 PATTERN-017 hash-chain convention already used by WEC and
GIC — same shape." Checked against the real code, that claim was imprecise.
Cited, verified layouts:

- **WEC** (`bridge/vapi_bridge/watchdog_chain.py:50-64` genesis,
  `:67-98` entry): genesis = `SHA-256(TAG || grind_session_id.encode() ||
  ts_ns_be(8))` — **raw variable-length session-id string, no pre-hash, no
  device field**. Entry = `SHA-256(prev(32) || event_code(1) || pid(4) ||
  sid_hash(16) || ts_ns_be(8))` = 61B.
- **GIC** (`bridge/vapi_bridge/grind_chain.py:40-54` genesis, `:57-86`
  entry): genesis — **identical shape to WEC's**, raw session-id string, no
  device field. Entry = `SHA-256(prev(32) || commitment_hash(32) ||
  verdict_byte(1) || host_byte(1) || ts_ns_be(8))` = 74B.

**What actually matches vs. what's a deliberate divergence:** the
*discipline* matches exactly — prev-hash chaining, a tagged genesis,
fixed-width big-endian integer fields, no per-entry domain tag (separation
inherits from the tagged genesis, which the reviewer's own finding already
validated as cryptographically sound). The *field layout* does not match
either precedent byte-for-byte, and was never going to — each PATTERN-017
family's fields are domain-specific (WEC needs `pid`+`sid_hash` for
process-supervision; GIC needs `verdict`+`host_state` for session
adjudication; a frame manifest needs `frame_hash`+`frame_index`, which
neither precedent carries). Entry shape is structurally closest to GIC's
(prev + 32B content-hash + small metadata + timestamp), not WEC's.

**One real fix taken from this comparison, not just a wording correction:**
the original genesis draft added an unjustified `session_id_hash(32)`
pre-hash step neither WEC nor GIC does, and reused it. Simplified to match
their proven, simpler approach — raw `session_id.encode()`, no pre-hash.
`device_id` is **kept**, as a genuine, stated divergence: unlike a grind
session (implicitly single-device), a footage manifest is specifically
meant to be checked by third parties matching footage to a *specific
certified device*, so binding `device_id` directly into genesis makes the
manifest self-describing without requiring an external session→device
lookup. That's a deliberate design choice, stated as one, not an
unexamined copy of a pattern that doesn't quite fit:

```python
DOMAIN_TAG_GENESIS = b"VAPI-RWM-MANIFEST-GENESIS-v1"  # CANDIDATE, not PV-CI-pinned

def genesis_manifest_hash(session_id: str, device_id_hex: str, ts_ns: int) -> bytes:
    """SHA-256(DOMAIN_TAG_GENESIS || session_id.encode() || device_id(32) || ts_ns_be(8)).
    session_id raw (not pre-hashed) -- matches WEC/GIC's genesis convention.
    device_id(32) is a deliberate addition beyond WEC/GIC's shape (see above)."""

def compute_manifest_entry(prev_hash: bytes, frame_hash: bytes, frame_index: int, ts_ns: int) -> bytes:
    """SHA-256(prev_hash(32) || frame_hash(32) || frame_index_be(4) || ts_ns_be(8)) = 76B.
    Structurally closest to GIC's entry shape (prev + 32B content-hash + metadata + ts);
    frame_hash/frame_index are new fields specific to frame-manifest semantics."""
```

**F-RWM-5 disposition: fixed.** The draft never pinned write-order between
compositing the locator mark and computing `frame_hash` — a real,
verification-killing ambiguity if implemented wrong (hashing pre-composite
bytes means no verifier can ever recompute a matching hash from the
archived file, since the archived file itself has the mark burned in).
**Pinned order: composite mark onto frame → hash the composited bytes →
append manifest entry → write to disk.** `frame_hash` is computed over
*exactly* what ends up on disk, mark included.

- `frame_hash` = SHA-256 of the composited archived frame's raw pixel bytes
  at the moment it's written to disk (pristine, pre-any-recompression). This
  is the F-RWM-2-anticipated "exact-pixel hash dies under re-compression"
  limitation stated as a design boundary, not hidden: **the manifest proves
  the pristine archive; it says nothing about a re-encoded copy someone
  downloads later.** That's Path A's honest scope, not a bug.
- **NOV-3 forward-compatibility (per reviewer's r04 sizing note):** entries
  are individually addressable (frame_index-keyed), not a monolithic blob —
  matching `sdk/wmp_disclosure.py`'s "sorted leaf hashes" shape, so NOV-3 can
  wire SD-1's `build_disclosure`/`verify_disclosure` directly over manifest
  entries later without a manifest redesign. Confirmed compatible by reading
  `sdk/wmp_disclosure.py`'s commitment shape (bundle + count + sorted leaf
  hashes + claim-type inventory) — a manifest entry is structurally a leaf.
- Checkpointing cadence: proposed to match whatever cadence the session
  archive daemon (`retina_capture_daemon.py`) already uses for its own
  session boundaries — **not yet confirmed**, this is open question #3 from
  `scope.md`, needs a real read of that file before finalizing, not guessed
  here.

## Component 2: the locator mark (`retina_witness_mark.py`, revised)

**F-RWM-6 disposition: fixed.** The prior draft's bit-budget math ("96 bits
×3 = 288 symbol-slots") silently assumed 1 bit per symbol and never defined
`DEFAULT_PALETTE` or stated that assumption — a real gap, since "symbol" and
"bit" aren't interchangeable once a palette has more than two colors.
Fixed by defining a concrete palette first and deriving every downstream
number from it explicitly:

```python
# 2 reserved sentinel colors (sync preamble only, never carry payload bits) +
# 4 payload colors (2 bits/symbol) -- 6 total, chosen for maximum pairwise
# visual separation under compression/noise (exact swatch TBD at live-rig
# testing, open question #4; these are placeholders for the encoding scheme,
# not a finalized color spec):
PREAMBLE_COLORS = [(255, 255, 255), (0, 0, 0)]        # pure white, pure black
DEFAULT_PALETTE = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # R,G,B,Y -> 00,01,10,11

DOMAIN_TAG = b"VAPI-RETINA-WITNESS-MARK-v1"  # CANDIDATE — not PV-CI-pinned

def compute_locator_payload(session_id_hash_8b: bytes, checkpoint_index: int) -> bytes:
    """8-byte session_id hash-prefix + 3-byte checkpoint index + 1-byte CRC-8
    checksum (error DETECTION, not correction) = 12 bytes / 96 bits total.

    Deliberately NOT the full commitment from the superseded design -- under
    Path A this is a LOCATOR, not a proof, so it only needs to be
    practically-unique for lookup, not cryptographically complete. Full
    verification happens by using this to find the session, then checking
    the manifest/chain -- not from the mark alone.
    """

def encode_mark_symbols(payload: bytes, *, palette: list[tuple[int,int,int]] = DEFAULT_PALETTE) -> list[tuple[int,int,int]]:
    """DEFAULT_PALETTE is 4 colors -> 2 bits/symbol (see module-level
    PREAMBLE_COLORS/DEFAULT_PALETTE above). Prepends the fixed 2-symbol sync
    preamble (drawn from PREAMBLE_COLORS, never reused for payload bits, so a
    decoder can't mistake genuine payload data for a sync marker or vice
    versa) so a decoder scanning an arbitrary frame sequence can locate mark
    boundaries even with dropped/reordered frames -- addresses F-RWM-3's
    missing sync. Each payload symbol repeated 3x (majority-vote decode) as
    the baseline error-correction proposal -- simplest viable scheme, not
    full Reed-Solomon, because the payload is now ~96 bits (not the original
    design's 256+), and repetition is enough to evaluate empirically before
    reaching for something more complex. If live testing (open question #4)
    shows repetition-3 insufficient, Reed-Solomon is the documented
    fallback, not a redesign."""

def composite_mark_onto_frame(frame, symbol, *, corner="bottom-right", block_px=32):
    """Unchanged from the superseded design -- pure, returns a new frame,
    never mutates input, operates only on the archival copy."""

def decode_mark_from_frames(frames: list) -> Optional[bytes]:
    """Scans for the sync preamble first, then majority-vote decodes the
    payload run following it. Returns None (not a wrong answer) if no valid
    preamble is found -- fail-closed, matching this session's established
    discipline for every oracle touched this arc."""
```

**Bit budget, concretely derived from the palette above (resolves open
questions #1-2):** 96-bit payload / 2 bits-per-symbol (4-color
`DEFAULT_PALETTE`) = 48 symbols per payload pass. ×3 repetition = 144
symbol-slots, plus the fixed 2-symbol preamble once per cycle = **146
symbol-slots per full mark cycle** — corrected from the prior draft's
unexplained "288 symbol-slots" (that number silently assumed 1 bit/symbol;
at the actual 2 bits/symbol the real payload count is half, plus the
2-symbol preamble this draft accounts for explicitly). At the lightbar
precedent's "5-15 symbols/sec" density, that's ~10-29 seconds per full
cycle. **Proposed starting point for review, not finalized:** 8
symbols/sec, **~18s per cycle** (146/8), refreshed at the manifest's own
checkpoint cadence once that's confirmed (open question #3) so the locator
and the manifest never drift out of sync with each other.

## Corrected verification story

Anyone with (a) footage bearing a decodable mark and (b) access to the
bridge/chain can look up session `session_id_hash_prefix`, checkpoint
`checkpoint_index` — **this identifies which session the footage claims to
be from; it does not, by itself, prove the footage is genuine or unmodified.**
Proof requires the separate manifest: if the archive is the pristine,
unmodified original, its hash-chained entries can be independently
recomputed and checked against the chained/anchored root. A transcoded copy
(re-encoded, re-compressed) breaks the manifest check but not the locator
decode — which is the honestly-scoped, two-tier claim Path A actually
supports, replacing the superseded single-claim design F-RWM-1 broke.

## Test plan

1. Manifest: chain-continuity tests (tamper detection breaks the chain from
   the tampered entry forward, mirroring WEC/GIC's existing test pattern),
   determinism, domain separation from `VAPI-RETINA-STATE-v1/v2/v3` /
   `VAPI-VAME-v1` / WEC / GIC.
2. Locator: `compute_locator_payload` determinism; `encode_mark_symbols` /
   `decode_mark_from_frames` round-trip; preamble-detection under simulated
   dropped frames (decode must still find sync after removing frames from
   the middle of a sequence); majority-vote correction under simulated
   single-symbol corruption; CRC catching a corrupted decode (must return
   `None`, never a wrong-but-plausible payload); **`PREAMBLE_COLORS ∩
   DEFAULT_PALETTE == ∅` asserted directly (the two sets must never share a
   color), plus a decode-time case feeding a payload run that happens to
   contain a preamble-colored symbol run mid-stream — decoder must not
   mistake it for a second sync marker, and must not decode genuine
   preamble symbols as if they were payload data.**
3. Standalone repro script proving the full pipeline end to end on synthetic
   frame arrays, matching this session's established pattern.
4. **Explicitly deferred to a live rig pass** (not part of this plan, needs
   its own go-ahead when it comes up): decode robustness against *real*
   capture-card noise and *real* re-compression, to replace the "proposed
   starting point" bit-rate/cadence numbers above with measured ones.

## Ceiling

This plan only. No code written, no production file touched. Building
requires a further, separate, explicit go-ahead after this plan is
reviewed — the same two-step discipline (scope → explicit "build it") used
for every other primitive shipped this session.
