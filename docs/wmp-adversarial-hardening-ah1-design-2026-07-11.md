# WMP Adversarial Hardening Loop (AH-1) — Attack Taxonomy + Acceptance Bars

**Status:** DESIGN / DECISION-FIRST (2026-07-11). **No build in this commit.**  
**Why now:** WMP UC-1 LIVE + PUBLIC — `wmp_corpus_real/wmp_corpus.jsonl`, first real certified-human bundle VERIFIED under `scripts/wmp_full_verify.py --allow-deferred recency` (5/5 zero-stub with recency explicitly allowed; report `audits/wmp-phase2-first-real-bundle-2026-07-11.md`, merge trail includes `7129eee9`). Value claim is **zero-trust verification**: a stranger confirms real-human + on-chain consent + matrix↔root without trusting QorTroller.  
**Loop goal:** attack that claim **ourselves**, publicly, before others do. Credibility payload: *we tried to forge our own certified-human data N ways; the verifier caught them; gaps we found are documented or fixed.*  
**Precedent:** `l9_presence/adversarial/presence_forgery.py` + `scripts/run_forgery_matrix.py` (holds=True only if every attack hits a named rail).  
**Rails:** design + code/test/harness only · **no** wallet spend · **no** deploys · **no** chain writes · **no** FROZEN-v1 / 228B PoAC / Solidity edits · verifier never imports bridge · post-φ action-only · TGE frozen · claim ⊆ reality before bank · staged, operator commits.

---

## 0. Loop shape (process — frozen for AH-1)

```text
while not saturated and not operator_interrupt:
  1. Pick one un-attempted forgery vector from §2 (or newly discovered)
  2. Construct attack bundle FROM OUTSIDE (mutate/clone public UC-1 or synthetic JSON;
     never call BundleAssembler as the "attacker" unless the attack is specifically
     "malicious producer using our assembler" — default threat is external JSON forger)
  3. Run consumer path:
       - pure: sdk.wmp_verify.verify_bundle(..., injected callables mocked)
       - bar:  scripts/wmp_full_verify.py when crypto/RPC legs are load-bearing
  4. Outcome:
       REJECT at expected check  → bank CAUGHT (+ pinning test)
       PASS unexpectedly         → FINDING (GAP) → fix verifier → re-prove → GAP-FOUND-AND-FIXED
       Outside logic-level scope → OUT-OF-SCOPE-DOCUMENTED (assumption row)
  5. Append one public matrix row + one pinning test
```

**Saturation:** a full pass over the taxonomy adds **no new vector** and **no new gap**.  
**Never-a-silent-pass:** uncaught logic-level attack is a **FINDING**, never a skip or soft warn.

### Loop claim ceiling (carry with every external mention)

> AH-1 hardens the WMP consumer verifier against an **enumerated** set of **logic-level** forgeries. It does **not** claim field-security, complete attack coverage, or that no attack exists. Honest statement: *these vectors are caught; these gaps are documented; these assumptions are relied upon.*

---

## 1. Threat model

### 1.1 Forger goal (single sentence)

**Pass off bot, synthetic, replayed, spliced, or non-consented gameplay data as a zero-trust–VERIFIED “certified-human” WMP provenance bundle** so a world-model consumer (or journalist / buyer) treats it as real human action demonstration with real consent.

### 1.2 What “success” looks like for the attacker

The consumer runs:

```bash
python scripts/wmp_full_verify.py --bundle <forged.json|jsonl>
# attacker wins if: exit 0 AND overall VERIFIED AND zero stubs AND no unallowed deferred
```

or the pure path:

```python
verify_bundle(forged, allow_synthetic=False, groth16_verify=..., poseidon_root=...,
              beacon_lookup=..., consent_lookup=...)
# attacker wins if overall == VERIFIED with all required checks unstubbed
```

(Reference: `sdk/wmp_verify.py` `verify_bundle` ~L380–440; runner bar ~`scripts/wmp_full_verify.py` L18–21, L201–219.)

### 1.3 What the forger controls vs does not

| Controls (LOGIC-LEVEL — loop core) | Does **not** control (CRYPTO / CHAIN — assumed hard) |
|------------------------------------|------------------------------------------------------|
| Entire bundle JSON (any field) | Forging a **valid** Groth16 proof for an arbitrary matrix without the witness |
| Local corpus files / GitHub PRs / “leaked” exports | Forging **on-chain** `isWorldModelConsentGranted(gamer)==true` without that gamer’s key |
| Public inputs **as written in the bundle** (must still verify against proof) | Breaking SNARK soundness / swapping published vkey undetected if consumer pins the official vkey |
| Choosing empty vs filled recency fields | Minting true Arc 6 beacons at chosen blocks without keeper/registry |
| Setting `scope_*`, `scope_synthetic`, schema strings | Changing IoTeX history |

**Threat model phrase (sacred):** *“QorTroller might lie.”* The verifier therefore **must not** call bridge assembly code (`sdk/wmp_verify.py` L44–47). Attack constructions are **outside-in** on bundle bytes.

### 1.4 Map every attack class → goal

| Goal subtype | Example vectors (§2 IDs) |
|--------------|---------------------------|
| **Bot / non-human as human** | A1 matrix-swap, A2 stale-proof, A5 session-splice, A9 synthetic-unflagged, A10 humanity_deferred_lie |
| **Synthetic as real** | A9, A11 scope overclaim |
| **Replay / wrong session data** | A2 stale-proof, A5 splice, A1 matrix-swap |
| **Non-consented as consented** | A3 gamer-address swap, A4 consent-dim-without-chain, A12 consent_lookup stub misuse |
| **Recency theater** | A6 recency-downgrade / fake beacons |
| **Label / marketing fraud on top of weak data** | A7 strata inflation, A8 schema/circuit downgrade |
| **Integrity theater** | A13 bundle-hash / manifest games |

---

## 2. Attack taxonomy (seed set)

**Notation**

- **Target check** = one of: `schema` (early), `synthetic_gate`, `scope_honesty`, `matrix_root_rehash`, `humanity`, `recency`, `consent` (`sdk/wmp_verify.py` L88–92, L410–428).  
- **Expected** under **full consumer path** = injected callables as in `wmp_full_verify.py` (unless noted).  
- **UC-1 base** = first line of `wmp_corpus_real/wmp_corpus.jsonl` (schema `vapi-wmp-provenance-bundle-v1`, `world_model_consent_dimension=GRANTED`, `scope_synthetic=false`, recency fields empty / registry `""` per live artifact).

### 2.1 Already-proven defenses (seed bank — re-pin, do not re-derive science)

| ID | Vector | Status | Cite |
|----|--------|--------|------|
| **A1** | **Matrix-swap** — flip matrix hex / one byte; keep proof + public inputs | **CAUGHT** → `matrix_root_rehash` (POSEIDON_BN254) | Audit: “one flipped matrix byte → REJECTED” (`audits/wmp-phase2-first-real-bundle-2026-07-11.md` L25); code: `check_matrix_root_rehash` L215–236 |
| **P-UC2** | **Strata re-derivation FAIL** (skill-strata, not WMP verify_bundle) | **CAUGHT** at strata verifier | `l9_presence/skill_strata.py` `verify_strata_report` L131+ |
| **P-RES** | **Résumé totals-drift FAIL** | **CAUGHT** at play-resume / strata re-derive | UC-2/UC-4 chain — pin separately if loop touches strata |

AH-1 **re-banks A1 as WMP matrix row #1** with a pure pinning test (mock `poseidon_root` to return honest root for original matrix only).

### 2.2 Seed vectors (enumerate for the loop)

#### A1 — Matrix-swap *(seed CAUGHT)*

| | |
|--|--|
| **Construction** | Clone UC-1; mutate `action_trace_matrix_hex[ch]` by one nibble; leave `humanity_proof_*` and `sanitizedTraceRoot` public input unchanged. |
| **Goal** | Different action data under a still-valid-looking proof package. |
| **Target** | `matrix_root_rehash` |
| **Expected** | `REJECTED`; reason mentions Poseidon root mismatch (`wmp_verify.py` L233–235). |
| **Class** | LOGIC · **CAUGHT** (already) |
| **Test** | Pure: inject `poseidon_root` → fixed root for golden matrix, different for mutated; no snarkjs required if humanity mocked to pass only when proof hex unchanged *and* rehash runs first — prefer full path once for external credibility. |

#### A2 — Stale-proof replay (old proof + new data)

| | |
|--|--|
| **Construction** | Keep UC-1 proof bytes + public inputs; replace matrix with **another session’s** post-φ matrix (or regenerated ticks≠1730); optionally update `action_trace_ticks`. |
| **Goal** | Attach a real human proof to the wrong demonstration trace. |
| **Target** | Primary `matrix_root_rehash`; secondary `humanity` if public inputs also rewritten inconsistently. |
| **Expected** | `REJECTED` at rehash when Poseidon injected. If forger also sets public `sanitizedTraceRoot` to match new matrix **without** new proof → `humanity` FAIL (proof no longer verifies). |
| **Class** | LOGIC · expected **CAUGHT** |
| **Honest note** | Without `poseidon_root` injection, v1 structural path may **pass rehash when `structural_rehash_v1` unpaired** (`wmp_verify.py` L198–205 — surfaces digest only). Full-verify bar is the consumer path; pure tests **must inject** poseidon for A1/A2. |

#### A3 — Gamer-address swap

| | |
|--|--|
| **Construction** | Clone UC-1; set `consent_gamer_address` to a **different** EOA that has **not** granted world-model consent (or random `0x`+64 hex). Keep proof. |
| **Goal** | Steal a real proof’s credibility under another identity / non-consenter. |
| **Target** | `consent` (`check_consent` L338–375) |
| **Expected** | With `consent_lookup` injected: `passed=False` if chain says false (`L374–375`). |
| **Class** | LOGIC (bundle field) + **view-call oracle** · expected **CAUGHT** under full path |
| **Gap watch** | If `consent_lookup is None` and dimension is `GRANTED`, check returns **passed=True, stubbed=True** (`L356–362`). Runner without `--consent-registry` is **not** at 5/5 zero-stub bar — document as **misconfiguration**, not CAUGHT. Pinning tests **must inject** `consent_lookup`. |

#### A4 — Consent-dimension GRANTED but gamer never signed

| | |
|--|--|
| **Construction** | Fresh or cloned bundle: `world_model_consent_dimension="GRANTED"`, `consent_gamer_address` = address with on-chain `false` (or never registered). Optionally empty `world_model_consent_registry`. |
| **Goal** | Local claim of consent without on-chain grant. |
| **Target** | `consent` |
| **Expected** | Injected lookup → REJECTED. |
| **Class** | LOGIC · expected **CAUGHT** under full path |
| **Related** | Cannot forge the true grant without gamer key → that half is **CRYPTO/CHAIN OUT-OF-SCOPE** (§3). |

#### A5 — Session-splice

| | |
|--|--|
| **Construction** | Mix fields from two real sessions: e.g. M17 proof + matrix from another match; or keep matrix+proof consistent but splice contradictory metadata (ticks, roots, poacChainRoot from another public.json). |
| **Goal** | Composite franken-bundle that still looks “certified.” |
| **Target** | `matrix_root_rehash` and/or `humanity` depending on which roots stay. |
| **Expected** | At least one REJECTED if any continuous leg inconsistent with proof public inputs. |
| **Class** | LOGIC · expected **CAUGHT** when Poseidon + Groth16 injected |
| **Gap watch** | Metadata-only splice that **does not** break public inputs or matrix root (e.g. only `extra_metadata` lies) may **PASS** WMP-5 checks — then either **GAP** (if we claim strata integrity inside WMP) or **OUT-OF-SCOPE** (strata is separate re-derive tool). See A7. |

#### A6 — Recency-downgrade / fake recency

| | |
|--|--|
| **Construction A6a** | Set `recency_registry_address` to LIVE registry, invent `open/close` blocks+hashes that never anchored (or wrong hash). |
| **Construction A6b** | Claim “beacon-recency verified” in prose while bundle keeps empty registry (UC-1 shape) — **documentation attack**, not JSON. |
| **Construction A6c** | Empty registry + zero blocks (UC-1 honest deferral) but consumer runs **without** `--allow-deferred recency` and treats exit 1 as success — **operator misuse**. |
| **Target** | `recency` (`check_recency` L281–335) |
| **Expected A6a** | Injected `beacon_lookup` → mismatch / no beacon → REJECTED (`L327–333`). Structural: `close <= open` or bad hex → REJECTED (`L301–310`). |
| **Expected A6b** | Not a verifier issue — **claim ceiling** on announcements (UC-1 report already: never claim beacon-bound recency). |
| **Class** | A6a LOGIC · expected **CAUGHT**; A6b OUT-OF-SCOPE-DOCUMENTED (comms); A6c process |
| **Honest UC-1 fact** | Live bundle has `recency_registry_address=""` and zero blocks — full verify uses **`--allow-deferred recency`**. AH-1 must not “prove recency” on UC-1; next-match upgrade is separate. |

#### A7 — Strata-band inflation

| | |
|--|--|
| **Construction** | Set `extra_metadata.skill_strata_band` to a higher band than re-derive allows (e.g. force `AUTHORED_HIGH_DENSITY` on a thin session). |
| **Target** | **Not** in `verify_bundle` five checks today — only rides in `extra_metadata` (`bundle_assembler.py` L154–159). |
| **Expected (WMP-only)** | Bundle may still VERIFIED 5/5 — **WMP does not re-derive strata**. |
| **Expected (combined)** | `skill_strata.verify_strata_report` → FAIL on re-derive. |
| **Class** | **Split:** pure WMP path → **OUT-OF-SCOPE-DOCUMENTED** (or future GAP if product claims “strata verified by wmp_full_verify”). Combined corpus bar → CAUGHT at strata tool. |
| **Design ruling (proposed)** | AH-1 matrix includes A7 as **OUT-OF-SCOPE for WMP-3** with pointer to UC-2 re-derive; do **not** pretend check #5 catches it. Optional later: WMP check #6 soft-warn — **not** this design’s build. |

#### A8 — Schema / circuit downgrade

| | |
|--|--|
| **Construction A8a** | `schema` ≠ `vapi-wmp-provenance-bundle-v1` |
| **Construction A8b** | `humanity_proof_type` altered / v2 proof bytes under v1 type |
| **Construction A8c** | Truncated proof hex (≠256 bytes wire) |
| **Target** | A8a early schema (`L411–414`); A8c `humanity` structural (`L259–270`); A8b may pass structural then fail Groth16 |
| **Expected** | REJECTED (schema / humanity) |
| **Class** | LOGIC · expected **CAUGHT** |

#### A9 — Synthetic bundle without flag

| | |
|--|--|
| **Construction** | Fixture/synthetic matrix + stub proof markers but `scope_synthetic=false` (or omit true). Inverse: real fields with `scope_synthetic=true` hoping consumer uses `--allow-synthetic` in production. |
| **Target** | `synthetic_gate` (`L416–420`); plus humanity/rehash if synthetic data is nonsense |
| **Expected** | True synthetic with flag → REJECTED without `allow_synthetic`. Lying `scope_synthetic=false` on fixture data → should fail humanity/rehash under full inject. |
| **Class** | LOGIC · expected **CAUGHT** |
| **Gap watch** | Structural-only path without inject can “pass” garbage with stubbed humanity — **not** the public bar. |

#### A10 — Humanity deferred lie

| | |
|--|--|
| **Construction** | `humanity_deferred=true`, empty/invalid proof, claim certified-human. |
| **Target** | `humanity` (`L250–257` returns passed=True, deferred=True) |
| **Expected full bar** | `wmp_full_verify` treats deferred as **not at bar** unless `--allow-deferred humanity` (`L205–206`). |
| **Class** | LOGIC / process · **CAUGHT** at full-verify bar; pure `verify_bundle` alone can overall VERIFIED with deferred — document: **consumer must use full-verify bar for UC-1-class claims**. |

#### A11 — Scope overclaim

| | |
|--|--|
| **Construction** | Flip `scope_observation_channel` away from `ABSENT_BY_DESIGN_DATA_FLOOR`, or `scope_is_full_pomdp_tuple=true`, or wrong channel string. |
| **Target** | `scope_honesty` (`L127–141`) |
| **Expected** | REJECTED |
| **Class** | LOGIC · expected **CAUGHT** |

#### A12 — Consent stub / DEFERRED theater

| | |
|--|--|
| **Construction** | `world_model_consent_dimension="DEFERRED"` on a bundle marketed as Phase-2 consented; or omit injection so GRANTED stubs pass. |
| **Target** | `consent` + full-verify deferred policy |
| **Expected** | DEFERRED → not at 5/5 zero-stub bar without allow; stubbed GRANTED → not at bar if runner detects stub (`L204`). |
| **Class** | LOGIC / process · **CAUGHT** at full bar |

#### A13 — Bundle-hash / manifest games

| | |
|--|--|
| **Construction** | Mutate bundle but keep an external `corpus_manifest.json` entry claiming old hash; or publish two JSON lines where one is forged. |
| **Target** | `_bundle_hash` is **recomputed** each verify (`L120–123`, L401) — **not** compared to a signed field inside the bundle. Manifest is **not** checked by `verify_bundle`. |
| **Expected** | Forged content still runs checks on **current** bytes — A1–A11 apply. Manifest drift is **tooling gap**. |
| **Class** | Mostly **OUT-OF-SCOPE-DOCUMENTED** for WMP-3 (manifest integrity = exporter/CI concern); optional AH-1 row: “manifest hash ≠ recompute → process FAIL” if we add a tiny corpus linter later. |

#### A14 — Public-input swap without proof (subset of A2)

| | |
|--|--|
| **Construction** | Change `humanity_proof_public_inputs.sanitizedTraceRoot` to match a new matrix while keeping old proof bytes. |
| **Target** | `humanity` (Groth16 must fail) |
| **Expected** | REJECTED at humanity under inject |
| **Class** | LOGIC · expected **CAUGHT** |

#### A15 — Observation / biometric smuggle (data-floor)

| | |
|--|--|
| **Construction** | Inject forbidden keys into `extra_metadata` or new fields (e.g. raw L4 vector). |
| **Target** | Assembler rejects at **produce** time (`DataFloorViolationError`); **consumer verify_bundle does not scan FORBIDDEN_COLUMNS** today. |
| **Expected** | Malicious external JSON can carry extra keys and still pass five checks if core legs valid. |
| **Class** | **Candidate GAP** — if confirmed, either document OUT-OF-SCOPE (“consumer must ignore unknown keys; floor is producer-side”) or add check #5b unknown-key / forbidden-key reject. **Finding-first:** first AH cycle should **probe** A15 and bank GAP or DOCUMENTED. |

---

## 3. Load-bearing scope split: LOGIC vs CRYPTO

```text
                    ┌─────────────────────────────────────┐
                    │     Forger goal: VERIFIED @ bar     │
                    └─────────────────────────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
   LOGIC-LEVEL (AH-1 core)                         CRYPTO / CHAIN (assumptions)
   Forger edits bundle JSON                        Forger would need:
   and/or abuses stubbed path                      • Valid Groth16 for false statement
   ─────────────────────────────────               • On-chain consent without gamer key
   MUST catch under full consumer path             • False beacon without registry control
   + pinning tests with injected mocks             • Break published vkey pin
   ─────────────────────────────────               ─────────────────────────────────
   Matrix rows: CAUGHT / GAP-FIXED                 Matrix rows: OUT-OF-SCOPE-
   / OUT-OF-SCOPE only if not WMP-3 job              DOCUMENTED (relied-upon)
```

### 3.1 Relied-upon assumptions (document, do not “prove” in AH-1)

| Assumption | Meaning |
|------------|---------|
| **ZK soundness** | Attacker cannot produce accepting proof for false public inputs under the published circuit/vkey |
| **vkey authenticity** | Consumer uses the repo/official vkey path (`wmp_full_verify.py` DEFAULT_VKEY) |
| **Chain integrity** | IoTeX testnet view-calls reflect real `isWorldModelConsentGranted` / beacon storage |
| **Gamer key secrecy** | Only gamer can flip consent true |
| **No malicious RPC MITM** | Optional: pin RPC + compare; out of AH-1 v0 unless operator expands |

### 3.2 Explicit non-goals

- Do not re-prove Groth16 by attempting proof forgery.  
- Do not spend IOTX or deploy.  
- Do not claim capture-host honesty (self-witnessed matrix still producer-trust for *recording*; WMP proves *consistency* of export with proof+consent).  
- Do not absorb presence-forgery KAS/OCR vectors into WMP matrix (different stack; cross-link only).

---

## 4. Acceptance bars

### 4.1 “Caught”

A vector is **CAUGHT** iff:

1. Attack bundle is constructed as specified; **and**
2. Consumer path returns `overall=REJECTED` **or** full-verify `exit=1` / not at bar for deferred-stub abuse; **and**
3. The **expected check name** appears in `reasons` / deferred/stub list as designed; **and**
4. A pinning test encodes the construction and asserts the same outcome.

### 4.2 “Gap”

A vector is a **GAP** iff it is **LOGIC-LEVEL in-scope** and:

- `verify_bundle` / full-verify returns **VERIFIED at bar** for the forged bundle; **or**
- Failure mode is silent pass / wrong check / stubbed pass presented as crypto.

**Required response:** open finding → fix verifier (or runner policy) → re-prove attack → matrix row **GAP-FOUND-AND-FIXED** (cite fix commit).

### 4.3 “Out of scope”

**OUT-OF-SCOPE-DOCUMENTED** iff:

- Requires breaking ZK/chain assumptions (§3.1); **or**
- Belongs to another verifier (strata, KAS, manifest linter) and WMP product does not claim that property; **or**
- Pure social/comms attack (A6b).

Never use OUT-OF-SCOPE to hide a logic-level pass.

### 4.4 Matrix row schema (public doc)

| Column | Content |
|--------|---------|
| `id` | A1, A2, … |
| `vector` | short name |
| `construction` | one paragraph |
| `target_check` | check key(s) |
| `expected` | REJECT + check |
| `result` | **CAUGHT** / **GAP-FOUND-AND-FIXED** / **OUT-OF-SCOPE-DOCUMENTED** |
| `evidence` | test name + optional audit hash |
| `notes` | stub/defer caveats |

File pattern: `docs/wmp-adversarial-matrix-YYYY-MM-DD.md` (rolling) + optional `audits/wmp_adversarial_matrix.json` machine mirror (presence_forgery pattern).

### 4.5 Full-verify vs pure path (both required in design)

| Path | Use |
|------|-----|
| **Pure** `verify_bundle` + mocks | CI-fast pinning; offline; inject failures for lookup callables |
| **Full** `wmp_full_verify.py` | External credibility on A1/A3/A4/A14 when env complete; exit 2 = incomplete (never silent pass) |

Bar for public “caught with crypto legs”: full path when tools present; pure path always in CI.

---

## 5. Per-cycle artifact shape

### 5.1 Code layout (when operator greenlights build)

```text
sdk/wmp_adversarial/                 # or l9-style package; prefer next to sdk/wmp_verify
  __init__.py
  attacks.py                         # pure constructors: clone UC-1 path or fixture → dict
  matrix.py                          # run_all / run_one → MatrixResult (holds bool)
scripts/run_wmp_adversarial_matrix.py
sdk/tests/test_wmp_adversarial_ah1.py   # pinning tests per banked row
docs/wmp-adversarial-matrix-2026-07-11.md
audits/wmp_adversarial_matrix.json      # optional machine mirror
```

**Hard rule:** attack modules **import only** `sdk.wmp_verify` (and stdlib/json). **No** `bridge.vapi_bridge.wmp` import in the attack runner (threat model). Loading UC-1 golden is **file read**, not assembler.

### 5.2 Pinning test pattern (logic-level)

```python
def test_A1_matrix_swap_rejected():
    base = load_uc1_bundle()  # from wmp_corpus_real or committed fixture clone
    forged = matrix_swap(base)
    # Inject poseidon that returns correct root only for unmodified matrix bytes
    res = verify_bundle(
        forged,
        allow_synthetic=False,
        poseidon_root=poseidon_mock_for(base),
        groth16_verify=lambda pi, hx: True,   # isolate rehash; A1 does not need fail humanity
        beacon_lookup=None,
        consent_lookup=lambda g: True,
    )
    assert res.overall == "REJECTED"
    assert any("matrix_root_rehash" in r or "Poseidon" in r for r in res.reasons)
```

For A3/A4, invert: `groth16_verify=True`, `poseidon_root` honest match, `consent_lookup=lambda g: g == REAL_GAMER`.

### 5.3 Cycle definition of done

- [ ] One new matrix row committed  
- [ ] One pinning test green  
- [ ] If GAP: verifier/runner fix in same or immediately following commit + re-prove  
- [ ] Claim audit: row construction matches code paths cited  
- [ ] No chain spend  

### 5.4 Suggested first three cycles (operator order)

| Cycle | Vector | Why first |
|-------|--------|-----------|
| **C1** | **A1** matrix-swap | Already proven; banks methodology + test harness |
| **C2** | **A3** gamer-address swap | Load-bearing consent story; pure mock of lookup |
| **C3** | **A15** forbidden-key smuggle **or** **A2** stale-proof | Probe producer-only floor vs consumer (possible first GAP) |

Then A4, A6a, A8, A9, A11, A14, A10/A12 (full-bar policy), A7 (document split), A13 (document).

---

## 6. Grounding index (file:line — read before each cycle)

| Surface | Path | Role |
|---------|------|------|
| Five checks + inject | `sdk/wmp_verify.py` L1–67, L127–375, `verify_bundle` L380–440 | Consumer truth |
| Structural rehash gap | `sdk/wmp_verify.py` L198–205 | Why inject poseidon in pure tests |
| Consent stub risk | `sdk/wmp_verify.py` L356–362 | Why inject consent_lookup |
| Deferred humanity | `sdk/wmp_verify.py` L250–257 | Full-bar vs pure |
| Full 5/5 runner | `scripts/wmp_full_verify.py` L1–26, L79–155, L157–219 | Public bar |
| Assembler fields | `bridge/vapi_bridge/wmp/bundle_assembler.py` L80–159 | Field names / extra_metadata |
| UC-1 corpus | `wmp_corpus_real/wmp_corpus.jsonl` | Attack base |
| UC-1 report | `audits/wmp-phase2-first-real-bundle-2026-07-11.md` | Recency deferred honesty |
| Presence matrix precedent | `l9_presence/adversarial/presence_forgery.py`, `scripts/run_forgery_matrix.py` | holds=True discipline |
| Strata re-derive | `l9_presence/skill_strata.py` L131+ | A7 home |

---

## 7. Operator decision table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-AH1-1** | Adopt threat model §1 + logic/crypto split §3 | Yes | ☐ accept ☐ amend |
| **D-AH1-2** | Seed taxonomy A1–A15 as loop backlog | Yes | ☐ accept ☐ amend |
| **D-AH1-3** | A7 strata = OUT-OF-SCOPE for WMP-3 (document + UC-2 pointer) | Yes | ☐ accept ☐ amend |
| **D-AH1-4** | A15 probe is first-class FINDING candidate | Yes | ☐ accept ☐ amend |
| **D-AH1-5** | Public matrix doc + pinning tests per cycle; operator commits | Yes | ☐ accept ☐ amend |
| **D-AH1-6** | Greenlight **build** of harness (attacks.py + first A1 test) | Hold until design accept | ☐ GO ☐ hold |
| **D-AH1-7** | Claim ceiling §0 in every external AH-1 mention | Yes | ☐ accept ☐ amend |

---

## 8. Success criterion for the design lane

AH-1 **design** is done when:

1. This doc is accepted (or amended) by the operator.  
2. Every seed vector has an expected check + classification path.  
3. Logic vs crypto line is explicit enough that engineers do not “prove” SNARK soundness in CI.  
4. Build (D-AH1-6) can start without re-deriving threat model.

AH-1 **loop** is done when matrix saturates (§0) or operator interrupts.

---

## 9. Auditor's addendum (Claude, 2026-07-11) — design ACCEPTED

Audited every grounded callout against the live code (`sdk/wmp_verify.py`, `scripts/wmp_full_verify.py`, grep of `FORBIDDEN_COLUMNS`). All cited line numbers land on the real mechanism — the design reads the code, not training data. **Verdict: accepted as written; build may start.**

### 9.1 Load-bearing confirmation — the full-verify bar fails closed

`scripts/wmp_full_verify.py` L205: `at_bar = (overall=="VERIFIED" and not stubbed and not bad_deferred)`. A `stubbed=True` check (e.g. `GRANTED` consent with no injected `consent_lookup`) or a deferral not named in `--allow-deferred` → **exit 1, not at bar**. This is what makes A3 / A10 / A12 "CAUGHT at full bar" true, and confirms A3's gap-watch: a runner without `--consent-registry` is honest misconfiguration (stub uncounted), never a silent pass.

### 9.2 A15 reframed — "scope-honesty asserted, not enforced" (confirmed REAL)

grep is decisive: `FORBIDDEN_COLUMNS` / `DataFloorViolationError` live in the **producer** (`bundle_assembler.py`, `wmp_export.py`, `pre_processor.py`) and are **absent from `sdk/wmp_verify.py`**. `check_scope_honesty` verifies the scope *strings* (`ABSENT_BY_DESIGN_DATA_FLOOR`, `MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL`) but never checks the *payload* honors them — a bundle can claim biometric-absent (pass check #5) while carrying a forbidden key (unpoliced). **A real gap that undercuts a headline promise (the biometric moat never exports).** Auditor lean: **fix, not document** — a payload-level forbidden-channel/key scan makes check #5 mean what it says. Decision unchanged (D-AH1-4: probe-first in an AH cycle); the fix bar is now framed.

### 9.3 A16 (new) — `sanitized_trace_root_ref` fallback (`wmp_verify.py` L229)

The Poseidon rehash compares against `pub.sanitizedTraceRoot` **or** the **producer-controlled** `sanitized_trace_root_ref` when the public input is omitted. Under the full runner this is caught: `make_groth16_verify` **raises** on any empty `_PUBLIC_ORDER` input (`wmp_full_verify.py` L81-83) → humanity FAIL. **Rail:** pure-path pinning tests **must** mock `groth16_verify` to enforce the same public-input completeness the real runner does — else the pure path can "pass" a self-consistent fake-root/ref pair. (Encoded in the C1 harness's `honest_kwargs`.) Class: LOGIC · CAUGHT-at-full-bar.

### 9.4 A17 (new) — corpus N-inflation (duplicate JSONL)

`verify_bundle` is per-bundle; replaying one valid bundle 50× passes every per-bundle check. Class: **OUT-OF-SCOPE-DOCUMENTED** — corpus count is a *statistics* claim, not a per-bundle property; points at the N=1 honesty ceiling (a future corpus linter's job, adjacent to A13).

### 9.5 Decisions

D-AH1-1 / 2 / 3 / 5 / 7 accepted · D-AH1-4 accepted (A15 confirmed real, fix-leaning) · D-AH1-6 **GO** (C1 = A1 matrix-swap). Refinements 9.2–9.4 fold into the matrix backlog (`docs/wmp-adversarial-matrix-2026-07-11.md`).

---

*WMP AH-1 design v0 + auditor addendum §9 — 2026-07-11. Design accepted; C1 build authorized. Verifier zero-trust posture sacred.*
