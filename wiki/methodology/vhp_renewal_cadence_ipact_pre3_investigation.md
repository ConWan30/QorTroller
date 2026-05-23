# VHP Renewal Cadence as iPACT-DePIN Primitive — Pre-③ Investigation Note

**Status:** Pre-implementation investigation (Phase B item ③). **Read-only; no code; no scope
doc yet.** HEAD `94d36357` (feature) / `b24fcbdb` (main). Held for operator review of these
findings before a ③ scope doc is produced. Protocol: investigation → **hold** → scope doc →
hold → code + vectors → P-check → hold → atomic commit.

---

## (a) Current VHP-renewal state (what exists today)

**`VHPRenewalAgent`** (`bridge/vapi_bridge/vhp_renewal_agent.py`, 14th agent, Phase 102):
- Polls every **6 h** (`POLL_INTERVAL_S = 21_600`).
- Finds VHPs expiring within `cfg.vhp_renewal_warning_days` (**default 7**; `VHP_RENEWAL_WARNING_DAYS`).
- **Renewal extends TTL by a hardcoded `90 * 86_400` (90 days)** — `new_expires_at = expires_at + 90d`. This 90-day epoch is the *de-facto* current cadence, but it is **a hardcoded literal, not a named/frozen parameter.**
- `dry_run` → logs advisory; live → `chain.renew_vhp(token_id)` + `store.insert_vhp_renewal(device_id, token_id, old_expires_at, new_expires_at, tx_hash, dry_run)`.
- W2 liveness beacon `vhp_lifecycle_warning` when zero VHPs ever issued; emits `vhp_renewed` bus event.
- `vhp_renewal_enabled` default **True**; `ioswarm_renewal_enabled` default **False** (Phase 109B quorum guard, fail-open).

**Attestation layer** (Phases 185–187, separate from VHP TTL):
- `ReEnrollmentAttestationAgent` (#29, Phase 185): on persona-break, issues a time-bound token
  `HMAC-SHA256(secret, "{player_id}:{ts_ns}:{loo_trend}:{tdi}:{ttl_days}")` (or `SHA-256(...)` in test mode), default TTL **7 days**. Secret = `REAUTH_ATTESTATION_SECRET`.
- `AttestationBoundRenewalAgent` (#30, Phase 186): can require a valid/active/non-expired attestation for `POST /agent/renew-separation-ratio-commitment`; **default off**, fail-open.
- `VHPReenrollmentBadge` contract (Phase 187, LIVE `0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C`).
- Related: biometric TTL (Phase 178), biometric_renewal (180), renewal_provenance (181).

**Renewal trigger today = pure time (TTL expiry window).** The agent renews any VHP inside the
7-day window. The HMAC attestation gate (Phase 186) is **off by default** and scoped to the
*biometric* re-enrollment path, **not** the VHP TTL renewal path.

## (b) IIP-64 §4.8.5 (iPACT-DePIN) alignment — and the load-bearing constraint

From the recorded engagement (`docs/qortroller-iip64-pr72-engagement.md`, PR #72 head `2c9b098`):
- §4.8.5 (iPACT-DePIN) is **sketched in a single paragraph**; it says manufacturers generate
  iPACTs *"during firmware updates or during provisioning."*
- **The refresh semantics are UNRESOLVED.** QorTroller's own open question #2 on PR #72 asks
  exactly this — *(a)* does §4.8.5 imply a **refreshable cadence vs one-time**, with what
  replay/timestamp semantics; *(b)* how does iPACT-DePIN interact with **verified-hardware-proof
  renewal cadences**. **Awaiting @cryptoxfan's reply.**
- Branch outcomes already recorded: **refreshable** → bind VHP renewal cadence = iPACT-DePIN
  cadence (offer a §4.8.5 contribution); **one-time** → design VHP renewal as a **layer above**
  iPACT (the periodic re-attestation the manufacturer's one-time iPACT does not provide).

→ **Constraint: ③ must be regime-agnostic.** It cannot hard-couple to a §4.8.5 cadence that
does not yet exist. It must be defensible whether §4.8.5 lands refreshable or one-time — which
matches the operator's stated ordering rationale ("defensible … regardless of which regime
§4.8.5 lands on").

## (c) Prior constraints / pre-commitments

- **No prior governance decision pins a renewal cadence.** Memory + docs sweep found only
  incidental VHP mentions; the 90-day TTL is an un-versioned hardcode, free to be formalized.
- **Gamer-sovereignty invariant applies** (cf. the CONSENT primitive: "bridge never grants/
  revokes on behalf of the gamer"). Today, however, `VHPRenewalAgent` **auto-renews via the
  bridge wallet** (`chain.renew_vhp`) — see the gap in (d).
- **Born-PQ discipline:** any new commitment must be SHA-256 domain-tagged (PATTERN-017 family
  shape) to stay PQ-safe and consistent with the 12 frozen families.
- **No existing "renewal"/"iPACT" commitment family** among the 12 frozen PATTERN-017 tags — ③
  would introduce a new primitive (family or capability — a scope-doc decision).
- **kill-switch:** `renew_vhp` is a gated chain-submission path (memory `feedback_kill_switch_coverage`); any live renewal stays behind `CHAIN_SUBMISSION_PAUSED`.

## (d) Proposed cadence choice + reasoning (for operator review)

**Sharpest finding — the current auto-renew is dormant-blind.** `VHPRenewalAgent` renews on TTL
proximity *alone*; in live mode the **bridge** keeps extending a token's life every cycle with no
requirement that the device still be present/attesting. A dormant device's credential would be
**auto-renewed forever** — the opposite of a defensible dormant-wallet answer. The architectural
leverage of ③ is to **bind renewal to a fresh re-attestation**, so a credential lapses unless the
device actively re-proves itself within the epoch.

**Proposed primitive (regime-agnostic iPACT-DePIN renewal cadence):**
1. **Name + freeze the epoch.** Promote the 90-day hardcode to a named cadence parameter
   `IPACT_RENEWAL_EPOCH_DAYS = 90` (keeps the battle-tested value; zero behavior change to the
   number; eliminates the silent literal). 90 d aligns with the device-identity tier's long-lived
   posture and is short enough that dormancy lapses within a quarter.
2. **Renewal-cadence commitment chain (the iPACT primitive).** A FROZEN SHA-256 domain-tagged
   commitment per renewal, chained to the prior — e.g.
   `SHA-256(b"QORTROLLER-IPACT-RENEWAL-v1" || device_id || token_id || prev_commitment || epoch_index || reattest_proof || ts_ns)`.
   The `prev_commitment` link + `ts_ns` give **monotonic, replay-resistant timestamp semantics**
   — a direct, concrete answer to §4.8.5 open-question (a).
3. **Bind renewal to re-attestation (close the dormant-blind gap).** A renewal is only valid if
   accompanied by a fresh device re-attestation proof (presence/VHP/PoEP-class), preserving
   **gamer-sovereignty** (the gamer's device produces the proof; the bridge observes, does not
   manufacture it).
4. **Regime-agnostic wrt §4.8.5.** If §4.8.5 lands **refreshable**, this chain *is* QorTroller's
   iPACT-DePIN refresh cadence (offer it as the §4.8.5 contribution). If **one-time**, this chain
   sits as the **re-attestation layer above** the manufacturer's one-time iPACT. Either way the
   on-wire artifact is identical → no rework on the author's reply.

**Open decisions for the ③ scope doc (operator calls):**
- **D-③-1 — new FROZEN-v1 family vs capability tag?** Is `QORTROLLER-IPACT-RENEWAL-v1` a 13th
  PATTERN-017 commitment family, or a capability tag (like MLGA)? (Family-vs-capability per the
  R3 criterion.) Freeze ceremony deferred regardless.
- **D-③-2 — epoch value:** keep 90 d, or split by device tier? Recommend **keep 90 d** v1.
- **D-③-3 — enforcement posture:** ship the re-attestation binding **default-OFF** (additive,
  no behavior change — matches every prior primitive) and flip later? Recommend **yes, default-OFF**.
- **D-③-4 — relationship to the existing HMAC attestation (Phase 185/186):** does ③ supersede
  the operator-secret HMAC with a gamer-sovereign commitment, or compose with it? (Lean: compose
  — ③ is the cadence/commitment, Phase 186 stays the optional enforcement gate.)
- **D-③-5 — wait for @cryptoxfan, or proceed regime-agnostic now?** Operator ordering already
  says proceed now; confirm.

---

**Cross-refs:** `bridge/vapi_bridge/vhp_renewal_agent.py`, `…/reenrollment_attestation_agent.py`,
`…/attestation_bound_renewal_agent.py`, `docs/qortroller-iip64-pr72-engagement.md`,
`l9_presence/composite_sig.py` (① — ③'s sibling primitive). Memory: `iip64-pr72-engagement`,
`composite-sig-v1-shipped`.
