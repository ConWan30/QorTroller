# D-CERT-5 — Unified Presence-Gameplay Proof: Design Document (2026-07-04)

**Status: DESIGN ONLY — awaiting operator resolution of D-CERT-5.1 … 5.4. No code changed, no flags
flipped, no tests written by this arc. Produced autonomously in parallel with (and without touching) the
D-PKG-1 v6 parity recheck.**

## 1. Executive summary

QorTroller today has two working, validated proof surfaces that do not know about each other:

- **`FusedGamerPresenceProof`** (`bridge/vapi_bridge/novel_presence_fusion.py`) — the SESSION-level
  presence fusion: PoEP, retina/PoCP, CCO, L4L5L6 folded by `fuse()` into one verdict + `presence_score`,
  with the D-CERT-1 `active_oracles` manifest (per-oracle contributed/abstained/absent), the D-CERT-7
  `verifier_independence` rail, the D-CERT-8 evidence base, and `cert_scope` (advisory/developer_self).
- **The KAS certificate** (`l9_presence/kill_authorship_session.py` + `scripts/issue_kas_records.py`) —
  the PER-KILL-EVENT authorship record: dual-lobe `events_root` binding device-clocked HID R2-onsets to
  screen-side kill outcomes, live-validated (15/15 kills COHERENT 1.0), G4-adversarially-paired (five
  attack runs, zero adversarial certificates), issued at daemon stop via `--kas`.

This arc is **unification, not a new capability**. The controller-physics-to-gameplay binding already
exists and is proven; what is missing is that the certificate and the session fusion live in mutually
ignorant objects — **they share not one identifier** (§2.6), so a third-party verifier holding both cannot
even correlate them for the same session. D-CERT-5's original question ("does per-action AUTHORED presence
bind to the cert") has narrowed since cycle 57: KAS now exists, G4 pairing is green, and the D-CERT-1
manifest already solved the comparability problem that made binding risky. What remains is choosing the
unification shape (§3), deciding its ceremony/naming posture (§7), and sequencing any startup work
separately from schema work (§7, D-CERT-5.4).

**Out of scope, by name:** PoAC (FROZEN-v1 228-byte wire — untouched under every option below),
ZK-SEPPROOF (biometric separation pillar), VHP soulbound tokens, ioID/DID infrastructure. Adjacent, not in
this unification.

## 2. Current-state map (Phase 0 findings, verified against current code)

### 2.1 `FusedGamerPresenceProof` (verified at `novel_presence_fusion.py`, cycle-59 state)

Frozen dataclass; verdict enum `NQPVVerdict` (8 values); fields: `device_id`, `record_hash`, per-oracle
inputs (`cco_tier`/`retina_verdict`/`poep_present`/`l4_l5_l6_consistent`), `presence_score` +
`disagreement_index` (cycle-29 split-output model, provisional weights `retina .35 / poep .30 / l4l5l6 .20
/ cco .15`, threshold 0.60), `binding_ok`, `commitments` dict (retina/cco), PoVCA advisory fields
(non-scoring until RETINA-EXCL-2), `cert_scope` + `population_certified` + `verifier_independence`
(D-CERT-7: derived from scope, never caller-set), D-CERT-8 evidence base (`governing_model`,
`calibration_band_commitment`, `calibration_n`, `calibration_player_scope`), and `active_oracles`
(D-CERT-1: derived inside `fuse()` from the same inputs it scores — cannot disagree with the verdict).
Hard gates: CCO tier FAIL, `consent_ok is False`. Anti-GCAP rule: missing oracle ABSTAINS (omitted from
the weighted sum), never scores 0.

**D-CERT-1 invariant carried in-code:** `cert_scope` = who vouches; `verifier_independence` = is the
voucher independent; `active_oracles` = what evidence backed it. New oracles join by MANIFEST DECLARATION,
not by minting scope strings. The comment at the invariant block names retina/authorship joining the
fusion as "a D-CERT-5 question" — this document is that question's design table.

### 2.2 KAS object shape (verified at `kill_authorship_session.py` + `issue_kas_records.py`)

`build_session_record(session_label, handle, composites, event_trail, hygiene, coupling, events_root,
events_root_scheme, events_root_lobes, cross_lobe, min_kills)` → record with closed verdict enum
(`AUTHORED_SESSION / INSUFFICIENT_KILLS / HYGIENE_FAIL / UNVERIFIABLE`; hygiene beats kill-count),
window-dedup on `window_gate_ms`, `QORTROLLER-KAS-v0` CANDIDATE domain tag, SHA-256 commitment over the
record body. **`events_root` IS in the commitment; `cross_lobe_coherence` is advisory (rides `to_dict()`
only, never moves the commitment).** Issuance is post-hoc: `issue_record_for_label` parses the newest
daemon log for the label (span + anchor event trail incl. C3 engine provenance), selects that span's rows
from `retina_kf_composite.jsonl` (screen lobe) and `retina_hid_events.jsonl` (HID lobe), unifies both
lobes via `unify_session_events_root` (existing `compute_events_root_for_scheme`, sha256_v1 — NO new
frozen tag was minted), computes the advisory cross-lobe readout, writes `audits/kas_record_<label>_<date>.json`.
Trigger: `retina_capture_daemon.py stop --kas` (explicit opt-in) or retro-issuance.

### 2.3 REQUIRED FINDING — Trio-Retina "HID sidecar (Phase 3c)" vs `killfeed_hid_event.py`

**They are NOT the same mechanism, and "Phase 3c" is not an HID path at all.** Verified:

- **Phase 3c is the DA WITNESS bundle** (`retina_da_witness.py`): the full witness JSON stored off-chain
  on `da_router`, keyed by the 32-byte `events_root`. A storage/witness sidecar — consumes an events_root,
  captures no HID.
- **Trio-Retina's HID-consuming path is Phase A** (`retina_controller_embedder.py`): pure encoder mapping
  DualSense HID **windows** into trio-retina `WorldState`/`Event` perception schema (latent tag
  `qortroller-controller-v1`), feeding `retina_perception` → `retina_state_commitment` →
  `retina_events_root` (sha256_v1 + optional Poseidon scheme).
- **KAS's HID path** (`l9_presence/killfeed_hid_event.py`): `HidOnsetDetector` wraps
  `DeviceClockL2Source` (raw-hidapi offset-28 @3 MHz device timestamp), detects R2 rising **edges** →
  `r2_onset` timed events → `retina_hid_events.jsonl`.

**The load-bearing consequence:** there are TWO parallel HID→events_root pipelines with different event
vocabularies (perception WorldState windows vs r2_onset edges), different clock treatments (resampled
windows vs raw device clock), and therefore **potentially TWO DIFFERENT events_roots for the same
session** — the retina perception root (which Phase 2c PDA attestation and Phase 3c DA witness key on) and
the KAS dual-lobe session root. They deliberately share the root COMPUTATION (`compute_events_root_for_scheme`)
but nothing reconciles the two root INSTANCES. Any unified proof must state explicitly which root(s) it
references; silently saying "the events_root" is ambiguous today. This is not duplicate code to delete —
it is two purposes (perception embedding vs input-edge authorship witness) that a unified proof must NAME
separately or explicitly join.

### 2.4 Bridge-startup call graph (actual, not idealized)

There is **no canonical startup hook and no fusion singleton**. `NovelPresenceFusionOrchestrator` is
stateless and constructed at point of use, six sites:

1. `operator_api/_app.py:1263` — per HTTP request (public presence-proof endpoint).
2. `oracle_panel.py:174` — lazy, per panel render.
3. `live_presence_signaling_agent.py:313` — lazy, per signal emission.
4. `scripts/record_devcert_session.py` — offline CLI.
5. `nqpv_study_harness.py` — offline study.
6. `nqpv_corpus_loader.py` — offline corpus→fuse bridge.

Live capture (`dualshock_integration.py:2344`) does NOT construct the orchestrator; it writes co-capture
ORACLE FIELDS into per-record PITL meta via `cocapture_fields_from_pitl_meta` (fail-open None = abstain).
KAS issuance happens entirely at daemon STOP, parsing sinks retroactively. **Both surfaces are post-hoc
assemblies over sinks/meta — nothing is "constructed at bridge start" today.** The daemon
(`retina_capture_daemon.py`) spawns the whole bridge (`bridge.vapi_bridge.main`) with env-mapped flags;
FastAPI (`operator_api`) and the capture loop live in that one process.

### 2.5 Flag inventory (defaults verified in `config.py` / daemon)

| Flag | Default | Gates |
|---|---|---|
| `RETINA_GAME_CAPTURE_ENABLED` | False | WGC capture (daemon sets true) |
| `RETINA_KILLFEED_ENABLED` / `_CAPTURE_ENABLED` | False | OCR sink / dense crop ring |
| `RETINA_KILLFEED_INLINE_ENABLED` | False | R2-gated inline classify (base for the producer) |
| `RETINA_SESSION_ANCHOR_ENABLED` | False | per-session feed-cut generator |
| `RETINA_OCR_BOOTSTRAP_ENABLED` | False | OCR catch (within session-anchor; D-CG-1 witness reuses it) |
| `RETINA_DENSE_CLASSIFY_ENABLED` | False | in-window dense tail (still R2-gated) |
| `RETINA_DEATH_WINDOW_ENABLED` | False | loop-2 corpus |
| `RETINA_HID_EVENTS_ENABLED` | False | HID lobe (KAS dual-lobe input) |
| `RETINA_ADS_COUPLING_ENABLED` | False | l2_ads raw capture (verdicts abstain uncalibrated) |
| `--kas` (daemon stop arg, not config) | off | KAS issuance at stop |
| `POEP_LIVENESS_ENABLED` / `poep_enabled` | False | PoEP (L6B N≥50 gate) |
| `NQPV_COCAPTURE_ENABLED` | False | co-capture oracle fields into PITL meta |
| `DEVELOPER_SELF_CERT_ENABLED` | False | `cert_scope=developer_self` |
| `PRESENCE_LEAN_MODE` | False | lean capture (GOTCHA: needs NQPV_COCAPTURE or coupling=None) |
| `RETINA_PERCEPTION_ENABLED`, `RETINA_DA_UPLOAD/WITNESS`, `RETINA_PDA_ATTESTATION`, `RETINA_EVENTS_ROOT_POSEIDON`, `RETINA_W3BSTREAM_*` | False | trio-retina perception/DA/attestation family |
| `RETINA_OCR_ENGINE` | unset (=tesseract) | engine chain (D-PKG-1 in flight) |

Known interaction: KAS's HID lobe requires `--hid-events` AND `--killfeed-inline` (the flush lives on the
inline tick). `PRESENCE_LEAN_MODE` without `NQPV_COCAPTURE_ENABLED` silently yields coupling=None. The
corpus-growth session (2026-07-04) ran killfeed-inline + session-anchor + ocr-bootstrap + dense-classify +
death-window + hid-events + ads simultaneously with no observed flag conflict.

### 2.6 Shared-identifier check — the sharpest concrete gap

**They share NOTHING.** KAS records key on `session_label` (operator-chosen daemon label) + `handle` +
`span_ms`. `FusedGamerPresenceProof` keys on `device_id` + `record_hash` + `timestamp_ns`. No field
overlaps; the only possible correlation is fuzzy wall-clock overlap between `span_ms` and `timestamp_ns` —
inference, not identification. A verifier handed both objects for the same session cannot prove they
describe the same session, same device, or same player. **This is the concrete interoperability failure
that makes unification more than elegance.** (Related: D-CERT-9 established label-as-sole-scope is already
a guarded hazard on the PoEP side; KAS inherits the same label-scoping without the guard.)

### 2.7 Proof/acronym inventory

| Surface | What | Scope call |
|---|---|---|
| `FusedGamerPresenceProof`/NQPV (incl. PoEP, PoCP/retina, CCO, L4L5L6, PoVCA field) | session presence fusion | **IN-SCOPE (primary)** |
| KAS (`QORTROLLER-KAS-v0`) | per-kill-event authorship certificate | **IN-SCOPE (primary)** |
| Retina perception root + PDA attestation + DA witness (Phases 2b/2c/3c) | trio-retina commitment family | **IN-SCOPE as a NAMED root** (must be disambiguated per §2.3), not merged |
| PoAC (228B wire) | FROZEN-v1 cognition record | OUT (untouched under every option) |
| PoSR / TemporalBeacon | session recency | ADJACENT (future outer-wrapper field candidate) |
| ZK-SEPPROOF / BIOMETRIC-SNAPSHOT | separation pillar | OUT |
| VHP soulbound / ioID / DID | credential/identity | OUT |
| GIC / WEC / VAME / CORPUS-SNAPSHOT / CONSENT | provenance chains | ADJACENT (consent hard-gate already in `fuse()`) |
| l2_ads | second anti-splice channel | ADJACENT — future oracle candidate for the SAME manifest (not a blocker) |

### 2.8 D-CERT-5's exact recorded state

`audits/dcert-board-clearance-2026-07-02.md`: *"D-CERT-5 (does per-action AUTHORED presence bind to the
developer-self cert) is the sole remaining cert-path decision"* — gated on (1) l2_ads calibration
(RP-session-gated), (2) adversarial pairing debt, (3) range→match transfer. **State update since that
record (2026-07-03/04):** gate (2) is substantially discharged — G4 ran five attack classes with ZERO
adversarial certificates (spectate-spam, splice OCR-on/off, boundary, structural), and KAS is now
live-validated dual-lobe. Gate (1)'s blocker (RP-reliable L2 source) was resolved (offset 5 confirmed);
the 8×→3×→1× calibration itself remains open. Gate (3) remains open. The cycle-57 vault notes for
D-CERT-1/8 exist signed in `vsd-vault/notes/decision/`; the 2026-07-02 drafts remain unsigned pending a
VSD ceremony (correctly so).

### 2.9 v6 parity recheck non-interference

The D-PKG-1 processes are `python3.13.exe` instances running `scripts/killfeed_audit_lane.py` over
`retina_kf_archive/*` writing only `audits/dpkg1_v6_*`. This investigation performed greps and file reads
only; it wrote exactly one file (this document), never read or wrote any `dpkg1_v6_*` artifact
mid-run, and executed no CPU-significant work.

## 3. Unification architecture options (costed at the actual call sites of §2.4)

### Option (a) — KAS becomes an oracle inside `FusedGamerPresenceProof`

`active_oracles` gains a `"kas"` entry (contributed/abstained/absent); `fuse()` gains optional KAS inputs
(verdict, commitment, events_root, authored_kills); the KAS commitment joins the `commitments` dict.

- **Fits the D-CERT-1 invariant exactly** (declare in manifest, don't mint scope strings) — the in-code
  comment already reserves this move for D-CERT-5.
- **Cost:** `fuse()` signature + manifest builder + the SIX call sites (only the ones with KAS access need
  to pass it; the rest abstain by default = zero forced churn); SDK `VAPIPresenceProof` gains the fields
  (additive, null-safe — same pattern as D-CERT-7/8); tests mirror `test_dcert1_active_oracles.py`.
- **Timing mismatch to design around:** KAS exists only AFTER daemon stop; `fuse()` runs per-request
  mid-session. Mid-session fusions would honestly report `kas: absent` — correct but means the strongest
  evidence only appears on post-session proofs. That asymmetry is inherent to (a) alone.
- **Does NOT solve §2.6 by itself** — an identifier still has to be added somewhere (see 5.3 rider).

### Option (b) — outer wrapper referencing both objects (loosest coupling)

A new small record (e.g. `UnifiedSessionProof`, operational, no frozen tag) holding: shared session
identifier + device_id + the KAS commitment + the FusedGamerPresenceProof (or its hash) + both
events_roots NAMED (kas_session_root, retina_perception_root when present) + spans. Neither existing
object changes at all.

- **Zero schema-migration risk**; both validated objects stay byte-stable; issuance naturally lives where
  KAS already issues (daemon stop / `issue_kas_records`), where the session's fusion proofs can be
  collected by span.
- **Cost:** one new module + issuance hook at the KAS call site (`retina_capture_daemon.py:233` /
  `issue_record_for_label`) + an SDK reader; no `fuse()` change; no call-site churn.
- **Weakness:** correlation is by the wrapper's say-so unless the wrapper carries an identifier that both
  inner objects ALSO carry — otherwise it merely asserts the join it was created to prove. To be
  verifier-grade it needs at minimum the session identifier added to both inner objects eventually, which
  re-opens (a)-style edits later. As a FIRST increment it is still the cheapest carrier of the join.

### Option (c) — KAS `events_root` becomes the canonical per-session root; fusion folds in as events

Invert primacy: every oracle contribution becomes an event on the KAS session root; the session fusion is
re-derived from the root's event set.

- **Architecturally elegant; practically the most expensive and the most collision-prone**: it collides
  head-on with the §2.3 finding (the retina perception root already exists with DA-witness/PDA/W3bstream
  consumers keying on it — INV-W3S-006/INV-RETINA-001/002 pin parts of that family), would re-plumb six
  fusion call sites AND the issuance path, and converts fusion from a pure function over inputs into a
  root-accumulation protocol (startup/ordering-sensitive — exactly the risk class D-CERT-5.4 says to keep
  out of schema work).
- Not recommendable today on cost; recorded as the direction a future v-freeze COULD take once the two
  roots of §2.3 are deliberately reconciled.

### Recommended hybrid (b→a): wrapper NOW, manifest entry NEXT

Increment 1 ships (b) as the join carrier (and mints the shared session identifier both surfaces lack);
Increment 2 adds the (a) manifest entry so mid-session and post-session proofs both declare KAS honestly
(`absent` mid-session, `contributed` on post-stop re-issue). (c) is explicitly deferred.

## 4. What "synchronized at bridge start" requires under each option

Today NOTHING synchronizes at bridge start (§2.4) — and for (a) and (b) that remains true and correct:
both are post-hoc joins over sinks; the only "synchronization" needed is a SHARED SESSION IDENTIFIER
minted once per session and visible to both surfaces. The daemon already mints exactly one candidate at
start: the label+stamp (`corpus_growth_20260704_1783188334`). Threading that (or a UUID derived from it)
into (i) the PITL meta co-capture fields and (ii) KAS issuance is internal wiring — **no default-behavior
change required for (a) or (b)**. Construction order is unconstrained; no oracle consumes another's output
at startup.

Option (c) alone would require true startup sequencing (a live root accumulator constructed before
capture begins, ordered ahead of the WGC/HID feeds) — a restructuring of `dualshock_integration` startup.
That cost belongs to (c) and is a reason it is deferred.

**Default-flip candidates flagged as their own decisions, NOT folded into the architecture choice:**
making `--kas` implied at stop when the session-anchor stack ran; making `NQPV_COCAPTURE_ENABLED` implied
by `DEVELOPER_SELF_CERT_ENABLED`. Both would change what a default session emits. Neither is assumed
wanted; see D-CERT-5.4.

## 5. Interoperability surface

- **SDK:** `VAPIPresenceProof` (sdk/vapi_sdk.py:119) already carries `active_oracles` +
  `verifier_independence` + the evidence base (D-CERT board, `deed6dee`). (a) adds `kas` manifest entry +
  optional kas_commitment/root fields (additive, null-safe, same discipline). (b) adds one new SDK reader
  for the wrapper.
- **API:** the per-request endpoint (`operator_api/_app.py:1263`) keeps returning fusion proofs; a wrapper
  (b) would surface via a session-scoped read (natural home: alongside the KAS artifact path).
- **Provenance continuity:** KAS event_trail already carries C3 engine identity; the wrapper should carry
  the manifest.json/session-archive linkage from the tier-1 archive work (2026-07-04) so the proof, the
  raw sinks, and the archive checksums form one chain.
- **`verifier_independence` semantics extend unchanged**: KAS is self-witnessed by the same rig
  (verifier == subject), so under `developer_self` it inherits `False` exactly like every other leg;
  nothing about the KAS leg reaches `True` today. No semantic extension needed — only the statement that
  the rail covers the new leg too.

## 6. Prerequisites and gates (stated honestly)

1. **Cross-lobe latency stays UNCALIBRATED until the one USB-direct controlled press-to-kill calibration
   session runs.** It gates the MEANING of any latency field in a unified proof — not the design, not the
   wrapper, not the manifest entry. Until then the field rides advisory with its `UNCALIBRATED` marker,
   exactly as it does in KAS today.
2. **The v6 parity recheck INFORMS, does not BLOCK**: the unification sits above the OCR layer; C3
   provenance carries whichever engine was live. (Parity evidence affects D-PKG-1's default-flip decision,
   a separate table.)
3. **l2_ads F2/F4 out-of-sample confirmation is orthogonal** — a future oracle candidate for the SAME
   `active_oracles` manifest; explicitly not a blocker for the wrapper or the manifest entry.
4. **Board-gate state update (per §2.8):** gate (2) substantially discharged by G4; gate (1) reduced to
   the calibration protocol (source resolved); gate (3) open. Under the D-CERT-1 manifest discipline, the
   KAS leg can join the fusion NOW as a declared oracle without waiting for (1)/(3) — because
   `active_oracles` + `cert_scope` + `verifier_independence` make exactly-what-backed-this visible, which
   is what the original D-CERT-5 gating was protecting. Whether Con agrees is D-CERT-5.1's call.

## 7. Decision blocks (each self-contained; resolve cold)

### D-CERT-5.1 — unification shape
**Options:** (a) KAS as manifest oracle · (b) outer wrapper · (c) KAS root canonical · hybrid (b→a).
**Evidence:** §3 costs at real call sites; §2.6 zero-shared-identifier gap; §2.3 two-roots finding; the
D-CERT-1 in-code invariant explicitly reserving manifest-declaration for this case.
**Recommendation:** hybrid (b→a). (b) alone can't be verifier-grade without eventually touching the inner
objects; (a) alone leaves mid-session/post-session asymmetry and doesn't mint the join key. (c) deferred
on cost + the §2.3 collision.

### D-CERT-5.2 — ceremony or operational?
**Question:** does the unified artifact need a FROZEN-v1 ceremony/new domain tag?
**Evidence:** the `events_root` precedent — Increment B deliberately reused `compute_events_root_for_scheme`
with NO new tag, recorded as "operational infrastructure; v-freeze is an explicit later decision." KAS
itself is `QORTROLLER-KAS-v0` CANDIDATE (v1 freeze already queued as its own ceremony). A wrapper that
REFERENCES two existing commitments creates no new cryptographic primitive.
**Recommendation:** operational now; the eventual KAS v0→v1 freeze ceremony is the natural moment to also
freeze the wrapper schema if it has earned it. Cost of deciding "ceremony now": a governance seal
(operator-fired per `[[process_autonomous_governance_seal_boundary]]`) + PV-CI allowlist change — not
justified by a candidate-stage artifact.

### D-CERT-5.3 — naming/versioning
**Options:** extend `QORTROLLER-KAS-v0` scope · extend fusion scope strings · new operational schema name.
**Evidence:** D-CERT-1 forbids minting scope strings for what a manifest entry expresses; KAS's tag is a
commitment domain tag, not a scope string — overloading it to also cover fusion data would change what
existing KAS commitments MEAN (a silent semantic break).
**Recommendation:** for (a): NO new name anywhere — `"kas"` manifest key + fields. For (b): one new
operational schema string (suggest `qortroller-unified-session-proof-v0`, explicitly CANDIDATE, carrying
the session identifier + both named roots per §2.3). `cert_scope` strings unchanged in every case.
**Rider (from §2.6):** whichever shape wins, the minted SESSION IDENTIFIER is the real naming decision —
recommend daemon label+stamp as the human-readable id plus a derived hash as the join key, so KAS files,
session archives (tier-1 manifest), and fusion proofs all carry the same pair.

### D-CERT-5.4 — bridge-startup restructuring?
**Question:** is startup work needed, and is it sequenced separately?
**Evidence:** §2.4/§4 — no startup singleton exists; (a)/(b) need only an identifier threaded through
existing construction points (internal wiring, no default change, no ordering constraint); only (c)
requires real startup restructuring.
**Recommendation:** NO startup restructuring in this arc. If (c) is ever chosen, its startup work is its
own phase with its own replay gate — never bundled with schema changes (different risk classes). The two
flagged default-flips (§4) are separate mini-decisions if ever wanted; neither is required.

## 8. Phased implementation roadmap (NOT implementation — build prompt derives from this)

Each increment in the established shape: pre-implementation verify → build → replay/validate → HOLD →
commit.

- **Increment U1 — session identifier (the join key).** Verify: identifier absent everywhere (§2.6).
  Build: daemon mints `session_id` (label+stamp + derived hash) → PITL meta co-capture fields → KAS
  issuance kwargs → tier-1 archive manifest. Validate: one replayed session shows the same id in all
  three artifacts. HOLD → commit. (Smallest honest step; unblocks everything.)
- **Increment U2 — wrapper (option b).** Verify: KAS + fusion artifacts for one session collectable by
  span. Build: `UnifiedSessionProof` (operational schema per 5.3) + issuance at the `--kas` stop hook +
  SDK reader. Validate: wrapper for the corpus-growth session references the real KAS commitment + real
  fusion proofs + BOTH named roots (or honestly one, when perception was off). HOLD → commit.
- **Increment U3 — manifest entry (option a).** Verify: D-CERT-1 tests as the template. Build: `fuse()`
  optional KAS inputs + `"kas"` manifest outcome + SDK fields (additive/null-safe). Validate: mid-session
  proof shows `kas: absent`; post-stop re-issue shows `contributed`; manifest never disagrees with inputs.
  HOLD → commit.
- **Increment U4 — two-roots reconciliation note (from §2.3).** Not code: a short design addendum deciding
  whether the wrapper permanently carries both roots as named fields (recommended) or a future ceremony
  merges them. Feeds the eventual KAS v1 freeze.
- **Gated later:** cross-lobe latency semantics (after the calibration capture); l2_ads as a new manifest
  oracle (after F2/F4); (c) evaluation only if root-accumulation is ever actually wanted.

---

*Written 2026-07-04 by the autonomous scoping arc. Zero files outside this document were touched; the
D-PKG-1 v6 parity recheck processes were never interacted with (§2.9).*
