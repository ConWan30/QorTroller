# EVENT-BIND — Cryptographic Per-Event Authorship Binding

**Status:** DESIGN + increment 1 BUILT (2026-07-09). Offline; no rig, no chain, no FROZEN-v1.
**Novelty:** upgrade per-event kill authorship from a **temporal ∩** to a **shared-anchor
cryptographic join** — so authorship is proven by a common commitment, not by clock proximity.
**Related:** `l9_presence/adversarial/cocapture_binding.py` (the template — presence↔retina),
`l9_presence/kill_authorship_session.py` (KAS), `l9_presence/killfeed_screen_event.py`,
`l9_presence/killfeed_hid_event.py`, `l9_presence/posp.py`, `audits/rp-close-1-ledger-2026-07-07.md`.

---

## 0. The gap (named by the code itself)

`cocapture_binding.py` says it out loud: a presence proof carries **only a timestamp**, so it is
paired to its gameplay record by a **±window temporal join — "a PROTOTYPE correlation, NOT a
cryptographic proof."** The same pattern governs *kill authorship*:

- **KAS today:** a kill is AUTHORED because its screen composite `resolves only inside an R2
  window` (`kill_authorship_session.py`) — the on-screen outcome timestamp falls inside a live
  trigger window. That is a **temporal ∩** of two independently-clocked lobes (WGC frame-capture
  vs device clock).
- The two lobes already exist as canonical events — `authored_screen_event` (outcome) and
  `hid_onset_event` (`r2_onset`, the "LIVE controller cause a replay-splice cannot produce on
  demand") — feeding one `events_root`. **Neither carries a PoAC `record_hash`.**

**Presence binds by identifier (session_id, U1); authorship binds by clock.** A clock join is the
seam. EVENT-BIND closes it by giving the outcome event and its causing input event a **shared
cryptographic anchor** — mirroring the `RECORD_HASH_PRODUCTION` mode `cocapture_binding` already
names but never built for the KAS lobe.

## 1. The anchor

The PoAC record hash — `record_hash = SHA-256(raw[:164])` — already exists per gameplay record and
is already stamped into `retina_event_log.record_hash_hex`. It is the natural shared anchor:

- At capture time the host knows the **live** `record_hash` (the PoAC record active at that frame).
- Stamp it into BOTH the authored screen event and the co-detected HID onset.
- A verifier then checks **"these two lobes reference the same `record_hash`,"** independent of
  either clock — the production bind. Absent stamping, the binder falls back to the temporal join
  with an explicit `TEMPORAL_PROTOTYPE` downgrade label (never silently conflated).

No new primitive, no domain tag, no FROZEN-v1: EVENT-BIND *references* the existing PoAC anchor.

## 2. Honest scope — what it closes, composes with, and does NOT close

| Adversary | Temporal ∩ (today) | EVENT-BIND (record_hash join) |
|---|---|---|
| **Cross-source SPLICE** — kill-outcome from capture A + input-onset from capture B, timestamps aligned | **FOOLED** (aligned clocks pass the window) | **CAUGHT** — the two lobes carry *different* `record_hash`es; the crypto join fails, the pair degrades to TEMPORAL_PROTOTYPE (honest, not AUTHORED-crypto) |
| **Full-session REPLAY** — replay both lobes with their original anchors | fooled | **not closed by EVENT-BIND alone** — a faithful replay reproduces self-consistent *old* anchors. **Composes with PoSR recency** (Arc 6 `temporal_beacon`): require the anchor to chain from a fresh beacon → stale replay fails recency |
| **Compromised capture HOST** — host stamps both lobes with a fabricated shared anchor | fooled | **not closed** — this is the witness-independence long arc (RP-7 residue); EVENT-BIND is host-trusting like every current surface |

**The novel, demonstrable claim:** EVENT-BIND makes per-event authorship **splice-proof** — a class
the temporal ∩ provably cannot resist — and it *composes* with the already-built PoSR beacon to add
replay resistance. It does not claim to close a compromised host; that stays honestly open.

## 3. Design — generalize `cocapture_binding` to the KAS lobe

`l9_presence/event_bind.py` (pure stdlib, mirrors `cocapture_binding`):

- `EventBindMode` = {`RECORD_HASH_PRODUCTION`, `TEMPORAL_PROTOTYPE`, `UNBOUND`} (same enum shape).
- `ScreenOutcome` / `HidOnset` frozen rows (the join-relevant fields incl. optional `record_hash`).
- `bind_events(outcomes, onsets, *, window_ns) -> EventBindReport`: per outcome, **crypto-preferred**
  — a shared-`record_hash` onset (time-independent) beats a nearest-in-window onset (temporal),
  else UNBOUND. Fail-open. Every outcome reports its `binding_mode` + `cryptographically_bound`.
- `EventBindReport`: per-kill modes + `n_crypto_bound` / `n_temporal` / coverage + an honest banner
  ("CRYPTOGRAPHIC BINDING" only when *every* authored kill is crypto-bound; else the TEMPORAL-prototype
  caveat verbatim from `cocapture_binding`).

**Anti-splice rail (the demonstration):** a `bind_events` over a *spliced* corpus (outcome anchor A ≠
onset anchor B, timestamps aligned) yields `TEMPORAL_PROTOTYPE`, never `RECORD_HASH_PRODUCTION` —
whereas a genuine co-capture (shared anchor) yields `RECORD_HASH_PRODUCTION`. Pinned by test.

## 4. Increments

1. **BUILT (2026-07-09) — offline core:** `event_bind.py` (binder + modes + report) + the adversarial
   splice demonstration + tests. Consumes optionally-present `record_hash`; works today (fails open to
   temporal when stamping isn't live). **No capture-path change, no KAS record change.**
2. **Capture-path stamping (flagged, default-OFF; buildable offline, field-validated at rig):** stamp
   the live PoAC `record_hash` into `hid_onset_event` + `authored_screen_event`; surface each authored
   kill's `binding_mode` on the KAS record. Live validation is a rig session (pairs with RP-6).
3. **PoSR compose (later):** require the anchor to chain from a fresh `temporal_beacon` → replay
   resistance. Design-only until 2 lands.

## 5. Rails

Advisory, `developer_self`, `verifier_independence=False` inherited (EVENT-BIND closes splice, not
host trust). No 228B PoAC contact (it *references* `record_hash`, never alters the wire). No FROZEN-v1,
no domain tag, no chain write, 0 IOTX, PV-CI 182 untouched. Pure stdlib, no bridge import. Single-committer.
