# A2A-CDM · Round 06 · grok — ADVERSARIAL

**Role:** Adversary (forge-your-own predictions). Round 07 executes desk-possible forges.  
**Targets:** T1 tri-plane + D-CDM-1 · T2 `consumer_status()` · T3 provenance DAG v0 · T4 ModuleHello v0 (spec).  
**Grounding:** `l9_presence/tri_plane_manifest.py` · `scripts/verify_provenance_dag.py` · `docs/module-hello-v0-spec-2026-07-12.md` · F4 splice tests.  
**Goal:** Find real gaps > prove rails hold. Predictions are claim-shaped for Claude to confirm/refute.

---

## attacks

### T1-A1: Downgrade-to-ABSENT (delete one plane root)  
- **attack:** Build a honest dual-root forked session (assertion.poac_chain_root=A, meaning.poac_chain_root=B, A≠B). Then **delete** assertion.poac_chain_root (or set null) and rehash manifest. Optionally keep meaning root. Call `build` path by hand-edit or post-build mutate.  
- **predicted-verifier-response:** **NOT-CAUGHT (gap / policy ambiguity)** for *joined* comfort: `poac_chain_join` → `ABSENT` (`tri_plane_manifest.py` L84–85); `content_fork` check passes (`forked=False` L206–208); with `attested_same_session` semantics or hand-set `meaning_session=REFERENCE_ATTESTED`, joined reads **JOINED_ATTESTED** not CONTENT_FORK. Builder path after delete also lands REFERENCE_ATTESTED / UNATTESTED, never FORK.  
- **severity-if-gap:** **Buyer** (false-comfort: “attested join” after suppressing contradiction) · **TO** if they treat JOINED_ATTESTED as clean multi-plane.  
- **fix-shape:** **Policy choice, not free lunch:** (a) **Accept + document ceiling** — “ABSENT means evidence-not-in-hand, not proven-consistent; TO/buyer must treat JOINED_ATTESTED as weaker than JOINED_VERIFIED; never market as fork-resistant.” (b) **Stronger:** if *either* plane carries a root and artifacts are supplied, **require both sides present** or fail `ROOT_INCOMPLETE_WHEN_PEER_HAS_ROOT`; (c) when posp/wmp supplied, **re-derive** roots from artifacts and re-run fork (closes T1-A2). Recommend **(c)+(a)**: artifact-derived roots + ceiling language for pure-manifest ABSENT.  
- **desk-executable:** **yes**

### T1-A2: Plane–artifact root desync (launder fork while artifacts still fork)  
- **attack:** Supply real PoSP with poac_chain_root=A and WMP with poacChainRoot=B (A≠B). Manifest planes **omit** one or both roots (or set equal wrong values). Rehash. `verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)`.  
- **predicted-verifier-response:** **NOT-CAUGHT (gap)** for fork: `assertion_binds_posp` only checks `session_id` + `kas_session_root` (**not** `poac_chain_root` — L213–216); `meaning_binds_bundle` only checks `bundle_hash` (**not** plane root == public input — L218–220). content_fork sees ABSENT/equal on planes → pass. Overall can be **ok=True** while artifacts cryptographically disagree.  
- **severity-if-gap:** **Buyer / protocol** — D-CDM-1 rail is **artifact-free on plane fields only**; a careful forger + full artifact bag still presents “joined verified green” if they strip plane roots.  
- **fix-shape:** Extend binding checks:  
  `a.poac_chain_root` must equal `posp.poac_chain_root` (norm);  
  `m.poac_chain_root` must equal `wmp.humanity_proof_public_inputs.poacChainRoot`;  
  then re-run content_fork on **artifact-derived** roots (authoritative).  
- **desk-executable:** **yes**

### T1-A3: Relabel CONTENT_FORK → REFERENCE_ATTESTED + rehash (known intended rail)  
- **attack:** Build forked dual-root manifest; set `join_status.meaning_session = REFERENCE_ATTESTED`, `poac_chain_join = ABSENT` or `VERIFIED_MATCH`, rehash.  
- **predicted-verifier-response:** **CAUGHT-by-content_fork** (L200–208): rail is artifact-free and ignores producer labels when both plane roots present and unequal. If forger also deletes a root → degrades to T1-A1.  
- **severity-if-gap:** N/A if caught; if not, same as A1.  
- **fix-shape:** None if tests confirm; pin regression.  
- **desk-executable:** **yes** (partially covered by existing CONTENT_FORK tests; extend with relabel).

### T1-A4: Meaning-session splice under attestation (known F4 ceiling)  
- **attack:** Bind WMP bundle from session B under PoSP session A with `attested_same_session=True` (S4).  
- **predicted-verifier-response:** **AMBIGUOUS / documented ceiling** — verify **ok=True**, meaning_session **REFERENCE_ATTESTED** never CRYPTOGRAPHIC (`test_s4_meaning_splice_is_the_documented_ceiling`). Not a D-CDM-1 miss; honesty depends on status vocabulary.  
- **severity-if-gap:** **Buyer** if they equate JOINED_ATTESTED with same-session crypto.  
- **fix-shape:** **Accept + document** (already); product: forbid marketing JOINED_ATTESTED as “proven same session”; F3 live root match remains the upgrade.  
- **desk-executable:** **yes**

### T1-A5: Asymmetric root when PoSP supplied lacks field but meaning has root  
- **attack:** Manifest: meaning.poac_chain_root set, assertion.poac_chain_root null; supply real PoSP **also without** poac_chain_root (M17-class) and WMP with poacChainRoot.  
- **predicted-verifier-response:** **AMBIGUOUS / likely ACCEPT** — ABSENT join, JOINED_ATTESTED path; binding does not require meaning root to match anything if hash binds. Honest M17-like.  
- **severity-if-gap:** Low if product says ATTESTED; high if called “full join.”  
- **fix-shape:** Document: **one-sided root ⇒ never JOINED_VERIFIED**; optional warn `ROOT_ONE_SIDED`.  
- **desk-executable:** **yes**

---

### T2-A1: Status without verify_result (label-only skim)  
- **attack:** Hand a mutated manifest (failed content_fork if roots present, or any fail) to `consumer_status(manifest, verify_result=None)`.  
- **predicted-verifier-response:** **NOT-CAUGHT (gap in composition)** — without `verify_result`, only `meaning_session` string drives joined_status (L238–249). Producer can set `meaning_session=REFERENCE_ATTESTED` even if roots fork **if they also strip roots** (A1); or set CRYPTOGRAPHIC without roots → verify would fail meaning_join_honest **but status alone still shows JOINED_VERIFIED** if label set (L244–245).  
- **severity-if-gap:** **TO/buyer skim** if UI calls `consumer_status` without `verify_tri_plane_manifest` first.  
- **fix-shape:** Require `verify_result` for any non-PARTIAL export; or recompute fork rails inside `consumer_status` from plane fields always (duplicate content_fork logic).  
- **desk-executable:** **yes**

### T2-A2: Green humanity_plane, red joined_status (skim split)  
- **attack:** CONTENT_FORK session but assertion.verdict remains `SYNCHRONIZED` / AUTHORED. Present only `humanity_plane` in a dashboard tile.  
- **predicted-verifier-response:** **NOT-CAUGHT by design of multi-status** — fields are individually truthful; **semantic attack on composition**. `note` field warns plane-local independence (L256) but skim-readers ignore.  
- **severity-if-gap:** **TO** false soft-signal on humanity alone; **buyer** if they store only one field.  
- **fix-shape:** **Accept + document ceiling** + UI rule: **never display a single field**; `joined_status` mandatory co-display; optional `safe_for_skim: false` when joined ∈ {CONTENT_FORK, UNVERIFIABLE, JOINED_PARTIAL}.  
- **desk-executable:** **yes** (semantic / product, not crypto)

### T2-A3: observation_plane field is not observation quality  
- **attack:** Exploit naming: `observation_plane` = `assertion_observation` join grade (CRYPTOGRAPHIC/INCOMPLETE), **not** “screen was real.” Market as “observation verified.”  
- **predicted-verifier-response:** **NOT-CAUGHT (semantic)** — value can be CRYPTOGRAPHIC while retina root is null/incomplete edges.  
- **severity-if-gap:** **Buyer / TO** provenance≠truth violation in **language**.  
- **fix-shape:** Rename to `assertion_observation_join` or add `observation_truth: UNCLAIMED` constant field.  
- **desk-executable:** **yes**

### T2-A4: JOINED_PARTIAL vs UNVERIFIABLE confusion  
- **attack:** Sessions with `meaning_session=UNATTESTED` or incomplete AO join → JOINED_PARTIAL; failed hash → UNVERIFIABLE. Middleman markets PARTIAL as “almost verified.”  
- **predicted-verifier-response:** **AMBIGUOUS** — status is honest; product abuse.  
- **severity-if-gap:** Buyer overtrust.  
- **fix-shape:** Document ordinal: VERIFIED > ATTESTED > PARTIAL > FORK/UNVERIFIABLE; forbid PARTIAL in paid SKUs.  
- **desk-executable:** **yes**

---

### T3-A1: Selective omission (Round 05 named)  
- **attack:** Build index with only “clean” sessions; omit sessions with CONTENT_FORK / bad WMP / hygiene fails.  
- **predicted-verifier-response:** **NOT-CAUGHT (documented ceiling)** — printed in `verify_provenance_dag.py` L16–18, L160–162; tests pin the string.  
- **severity-if-gap:** **Buyer / sponsor** longitudinal fraud; **gamer** reputational if others expect complete history.  
- **fix-shape:** **v0.5 options without chain/token** (see T3-A6); until then **accept + ceiling** (shipped).  
- **desk-executable:** **yes**

### T3-A2: Cross-device grafting  
- **attack:** Index `device_id=D1`; include a PoSP whose `device_id=D2`.  
- **predicted-verifier-response:** **CAUGHT-by-device_id stability / posp mismatch** (L140–144, L154–157).  
- **severity-if-gap:** N/A if caught.  
- **fix-shape:** None; pin test if not already.  
- **desk-executable:** **yes**

### T3-A3: Session re-binding (valid artifact under wrong session_id in index)  
- **attack:** Keep PoSP/WMP bytes + correct sha256; change index entry `session_id` to a different string (or list session-1 PoSP under session-2).  
- **predicted-verifier-response:** **NOT-CAUGHT (gap)** — verifier never asserts `doc.session_id == s["session_id"]` for PoSP/manifest. Hash + re-verify pass; stability uses PoSP device_id only.  
- **severity-if-gap:** **Buyer** (timeline lie); **TO** (wrong match attached to night).  
- **fix-shape:** For each artifact with a session_id field, require equality with index session_id; for tri-plane, match `manifest.session_id`.  
- **desk-executable:** **yes**

### T3-A4: Artifact substitution across sessions (same kind, wrong content, hash updated)  
- **attack:** Under session_2, point path+sha256 at session_1’s valid PoSP (full hash match). Index session_id=session_2.  
- **predicted-verifier-response:** **NOT-CAUGHT** if T3-A3 gap holds (PoSP session_id ignored). If A3 fixed, **CAUGHT**.  
- **severity-if-gap:** Buyer longitudinal integrity.  
- **fix-shape:** Same as T3-A3 + optional require unique (device_id, session_id, kind) content commitment.  
- **desk-executable:** **yes**

### T3-A5: Index re-keying (change device_id, keep sessions)  
- **attack:** Flip index.device_id without changing PoSP files.  
- **predicted-verifier-response:** **CAUGHT** (`test_device_id_instability_fails`).  
- **severity-if-gap:** N/A.  
- **fix-shape:** None.  
- **desk-executable:** **yes**

### T3-A6: v0.5 omission mitigations (design — what works offline)  
- **attack:** (meta) What can we do without chain/token?  
- **predicted-verifier-response:** N/A — design surface for Round 07/product.  
- **severity-if-gap:** N/A.  
- **fix-shape (honest menu):**  
  | Mechanism | Offline? | Stops omission? |  
  |-----------|----------|-----------------|  
  | **Printed ceiling + buyer attestation** (“this index is complete for window W”) | yes | no — social |  
  | **Count commitment** `N_sessions` + list hash of sorted session_ids | yes | detects *edit of listed set* only if buyer has independent N |  
  | **Third-party countersign** of index hash (TO co-signs) | yes | yes for that TO’s window — not global |  
  | **Beacon coverage claim** “every session has PoSR open/close in [T0,T1]” | partial (needs RPC or pre-exported beacon receipts) | raises cost, not complete |  
  | **Merkle inclusion vs operator log** | needs external log | yes if log append-only |  
  | **Cryptographic completeness over all history** | **impossible offline** without a prior commitment surface (chain, TO log, or HSM counter) | — |  
  **Impossible offline:** prove “no omitted session ever existed.” **Possible:** prove “index matches a countersigned manifest for event E.”  
- **desk-executable:** **no** for chain; **yes** for countersign/count-commitment prototypes

### T3-A7: Manifest-only session (no PoSP) to skip device_id  
- **attack:** Session artifacts = only tri_plane_manifest + wmp (no posp).  
- **predicted-verifier-response:** **CAUGHT-by-stability** if no posp ever — `seen_device_ids` empty → FAIL (L154). If one other session has posp for D1, empty session might not add device_ids — stability still OK if seen={D1}. Manifest-only session still re-verifies.  
- **severity-if-gap:** Low; odd packaging.  
- **fix-shape:** Optional require ≥1 POSP per session for agency indexes.  
- **desk-executable:** **yes**

### T3-A8: Stub-path WMP VERIFIED in DAG  
- **attack:** Include WMP that only passes `verify_bundle()` with stubs (no poseidon/g16 inject).  
- **predicted-verifier-response:** **AMBIGUOUS / product gap** — DAG uses offline defaults (L102–105) → can mark WMP OK without 5/5 crypto bar.  
- **severity-if-gap:** **Buyer** thinks DAG implies full WMP bar.  
- **fix-shape:** Document ceiling; or DAG flag `--wmp-full` requiring full-verify injects (env-gated).  
- **desk-executable:** **yes**

---

### T4-A1: Spoofed Hello (claim another module’s device_id)  
- **attack:** Module M2 emits Hello with identity.value = M1’s device_id_sha256, plane OBSERVATION, empty sig.  
- **predicted-verifier-response:** **NOT-CAUGHT (spec gap pre-sig)** — nothing binds identity to a key until `sig` is mandatory.  
- **severity-if-gap:** Bus trusts wrong device for observation seats; **protocol** mesh integrity.  
- **fix-shape:** Minimum trust: **(1)** `sig` required over canonical Hello using a key registered to that device_id (VMDR / local allowlist), **or (2)** Hello only accepted on a **pairing channel** already bound to that device (USB path / card serial), not ambient LAN. Until then: **Hello is untrusted advertisement only** — document ceiling.  
- **desk-executable:** **yes** (spec/logic tests when validator exists)

### T4-A2: Replayed SessionBind across sessions  
- **attack:** Capture SessionBind for session S1; replay for S2 with same module_hello_hash / identity.  
- **predicted-verifier-response:** **NOT-CAUGHT** unless bind includes session-specific nonce or hello was session-scoped. Spec bind is `{session_id, module_hello_hash, identity, plane}` — **no bind nonce, no ts**.  
- **severity-if-gap:** Ghost module “present” on sessions it never joined.  
- **fix-shape:** SessionBind must include `bind_nonce` unique per session + `hello_ts_ns` + sig(session_id||hello_hash||nonce); bus rejects duplicate (identity, session_id) rebinds without new hello.  
- **desk-executable:** **yes** (when wired)

### T4-A3: Capability escalation via ignore-unknown-bits  
- **attack:** Set high reserved bits (e.g. bit 40 = future CAP_SLASH_AUTHORITY) hoping old buses ignore and new buses honor.  
- **predicted-verifier-response:** **AMBIGUOUS** — v0 correctly ignores; **future** bus that assigns bit 40 without ceremony is the gap (spec risk).  
- **severity-if-gap:** Protocol upgrade hazard.  
- **fix-shape:** Reserved bits **must never gain meaning without schema bump or registry freeze note**; tests: unknown bits do not affect accept/reject; **no silent promote**.  
- **desk-executable:** **yes** (policy + future test)

### T4-A4: Identity-scheme downgrade (did:io → none)  
- **attack:** Module previously did:io re-Hellos as `scheme: none` with CAP_SCREEN_COMMIT only (no humanity).  
- **predicted-verifier-response:** **NOT-CAUGHT** by listed rules if role/plane legal — none only blocked from CAP_HUMANITY_CLAIM.  
- **severity-if-gap:** Weakens durable identity link mid-event.  
- **fix-shape:** Session-sticky identity: once bound under did:io or device_id, **reject downgrade** for that session; allow none only for first Hello in bring-up mode flag.  
- **desk-executable:** **yes**

### T4-A5: CAP_HUMANITY_CLAIM on OBSERVATION plane  
- **attack:** plane=OBSERVATION, capability_bits includes bit 1.  
- **predicted-verifier-response:** **CAUGHT-by-hello-time firewall** (spec L51, L64–66) — if validator implements MUST reject.  
- **severity-if-gap:** Separation law break if not implemented.  
- **fix-shape:** Pin test first day of wire implementation.  
- **desk-executable:** **yes** (spec-level)

### T4-A6: nonce/ts_ns replay window  
- **attack:** Replay entire Hello within TTL; or set ts_ns far future/past.  
- **predicted-verifier-response:** **NOT-CAUGHT** — spec has fields but **no window rule**.  
- **severity-if-gap:** Replay floods / confusion.  
- **fix-shape:** Reject |now - ts_ns| > Δ; reject nonce reuse in cache for TTL; require monotonic ts per identity.  
- **desk-executable:** **yes**

### T4-A7: sig:"" bootstrap hole (minimum binding before trust)  
- **attack:** Rely on empty sig for all Hellos on LAN; inject fake venue multi-seat CAP.  
- **predicted-verifier-response:** **NOT-CAUGHT** by crypto; **must be policy-caught**.  
- **severity-if-gap:** Entire bus trust model.  
- **fix-shape:** **Minimum binding BEFORE Hello is trusted for anything beyond “display name”:**  
  1. **Local pairing** (operator scans QR / USB enumerates device_id), **or**  
  2. **Non-empty sig** verified against provisioned pubkey for identity.value, **or**  
  3. **Trust tier** field: `ADVERTISEMENT` (sig empty, never drives seals) vs `BOUND` (sig or pairing required to appear in SessionBind).  
  Empty-sig Hellos may **never** authorize SessionBind into a sealed tri-plane.  
- **desk-executable:** **yes** (spec + later wire)

### T4-A8: ROLE_UNKNOWN smuggle via unknown JSON key  
- **attack:** Put real role in unknown key `role_alias`, set module_role to a registered weak role; or use unicode lookalike role string.  
- **predicted-verifier-response:** **CAUGHT** for unknown role string (REJECT ROLE_UNKNOWN); unknown keys ignored — **must not** read role from alternate keys.  
- **severity-if-gap:** If implementation is “helpful” and reads aliases.  
- **fix-shape:** Single field only; pin reject list.  
- **desk-executable:** **yes**

---

## priority order for Round 07 (Claude)

| Priority | ID | Why |
|----------|-----|-----|
| **P0** | **T1-A2** | Likely real D-CDM-1 bypass with artifacts present |
| **P0** | **T1-A1** | Seed downgrade; policy + optional hard fix |
| **P0** | **T3-A3 / T3-A4** | DAG session re-bind / substitution |
| **P1** | **T2-A1** | Status composition without verify |
| **P1** | **T3-A8** | Stub WMP inside DAG |
| **P1** | **T4-A7 / T4-A1 / T4-A2** | Spec trust floor before card wire |
| **P2** | T2-A2/A3, T3-A1, T1-A4 | Document / product ceilings |
| **Later / CWL-1** | hardware-only capture spoof | desk-executable: **no** |

---

## self-check

| Rail | Status |
|------|--------|
| Separation law | Attacks probe it (T4-A5, T1 smuggle already shipped CAUGHT); no proposal makes video humanity |
| Provenance ≠ truth | T2-A3, T1-A4, T3 ceilings explicit |
| Ideation / attack-design only | No spend/deploy; Claude executes forges |
| TGE frozen | T3-A6 no token completeness fantasy |
| Honest tags | CAUGHT / NOT-CAUGHT / AMBIGUOUS used; hardware marked desk-executable: no |
| Desk-executable majority | All T1–T3 core forges **yes**; T4 until validator exists still **yes** as unit tests on a stub validator |

---

## synthesis hint (for Round 07)

If **T1-A2** confirms: the fail-closed rail is **plane-field honest**, not **artifact-root honest** — fix binding or the joined object still lies under “full verify with artifacts.”  
If **T3-A3** confirms: DAG is a **hash locker + device continuity**, not a **session timeline** — fix session_id equality or print a second ceiling.  
If only A1/A4 remain: rails hold under creative assault; bank matrices and move on.

---

*A2A-CDM Round 06 ADVERSARIAL — grok — 2026-07-12. For Claude Round 07 forge execution.*
