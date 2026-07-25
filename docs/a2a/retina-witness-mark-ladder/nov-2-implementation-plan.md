# NOV-2 — Cross-primitive session bind + multi-checkpoint locator · implementation plan

**Status: BUILT (CANDIDATE) 2026-07-25** under operator GO.  
Companion: `nov-2-scope.md`. Ladder: `README.md`. Prior: NOV-3 BUILT (`073819da`).

**Shipped surface:** `bridge/vapi_bridge/rwm_session_bind.py` ·
`rwm_checkpoint_inventory.py` · `rwm_share_postcard.py` ·
`scripts/rwm_nov2_cli.py` · `bridge/tests/test_rwm_nov2.py` (T1–T10).
Still offline-only; no stop-path hook; no FROZEN/PV-CI pin.

---

## 0. Honest claim (restated)

**Ship (after GO):** offline pure modules + CLI that (1) attach a **re-checkable**
cross-primitive bind (PoAC segment tip and/or GIC tip) to an L0/NOV-3 package when
local artifacts exist, (2) emit a **multi-checkpoint inventory** over an existing
L0 archive without breaking single-checkpoint L0 decode, and (3) produce a
**SHARE-redacted dispute postcard** from a LOCAL escrow package.

**Ceiling:** verified *local* tip equality + optional checkpoint addressing.
**Not** re-encode proof, not FROZEN, not on-chain, not stop-path mandatory work,
not Path B device signatures.

---

## 1. Decisions locked by this plan (scope open Qs → answers)

| # | Question | Decision | Why |
|---|----------|----------|-----|
| **Q1 Bind priority** | PoAC / GIC / dual? | **dual-optional** — `bind_kind ∈ {none, poac_segment, gic_tip, dual}` | Grind sessions may have GIC; non-grind captures may only have PoAC export. Missing either never fails L0; `bind_ok` only true when cited tips re-check. |
| **Q2 Checkpoint cadence** | wall / N frames / operator? | **v0 inventory over frame indices** — default checkpoints at indices `{0, n//4, n//2, 3n//4, n-1}` (unique, n≥1); CLI `--checkpoint-indices` override | Avoids stop-path multi-window compositing in v0 (FROZEN_RING live ops already fragile). Locator payload already carries `checkpoint_index` uint24; L0 stop still writes `RWM_CHECKPOINT_INDEX=0` for all frames. v0 **inventory** maps logical cp → frame_index + L0 leaf hash; does **not** re-paint marks. |
| **Q3 SHARE redaction** | strip device_id? | **yes by default** — SHARE omits `device_id_hex`, full `leaf_hashes`, full `inventory`; keeps `session_id`, `commitment_root`, `revealed_frame_indices`, `bind_ok` summary | Matches `qortroller receipt` dual-surface discipline; LOCAL remains full steward package. |
| **Q4 Escrow schema** | v0 additive vs v1? | **additive optional fields on escrow v0** + **separate bind/postcard schemas** | Existing dogfood packages keep verifying. New keys ignored by old `verify_escrow` if we only add optional top-level objects and keep SCHEMA string. New schemas: `qortroller-rwm-session-bind-v0`, `qortroller-rwm-share-postcard-v0`, `qortroller-rwm-checkpoint-inventory-v0`. |

**Q5 (implicit) Stop-path coupling:** **none in v0.** All tools offline post-stop. Multi-checkpoint *live re-encode* is NOV-2.1 (explicit GO, touches `_issue_rwm_l0`).

---

## 2. Architecture (three pure modules + one CLI)

```text
  L0 archive (gitignored)
    rwm_manifest_chain.json
    panel_*.png / marked/
  optional local tips
    audits/*  / grind chain export / PoAC segment file
           │
           ▼
  ┌─────────────────────────────────────────────────────┐
  │  bridge/vapi_bridge/rwm_session_bind.py      NEW     │
  │    load_tip_hex(path|str) -> bytes                   │
  │    verify_bind(l0_tip, kind, refs) -> BindResult     │
  │    attach_bind(escrow_dict, bind) -> escrow_dict     │
  └─────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────┐
  │  bridge/vapi_bridge/rwm_checkpoint_inventory.py NEW  │
  │    build_inventory(l0, indices|default) -> dict      │
  │    verify_inventory(inv, archive) -> {ok, checks}    │
  └─────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────┐
  │  bridge/vapi_bridge/rwm_share_postcard.py    NEW     │
  │    to_share(local_escrow, bind_summary?) -> postcard │
  │    verify_share(postcard) -> structural only         │
  └─────────────────────────────────────────────────────┘
           │
           ▼
  scripts/rwm_nov2_cli.py   NEW (subcommands: bind / checkpoints / share)
           │
           ▼
  audits/rwm_bind_*.json · rwm_cp_inv_*.json · rwm_share_*.json
```

**Hard rules:**
- Never import bridge hot path / never call from `cmd_stop` in v0
- Never mutate 228B PoAC wire or FROZEN domain tags
- Never fabricate tips — missing artifact ⇒ `bind_ok=false` or refuse attach if `--require-bind`
- Never commit crops or device secrets; SHARE already strips device_id

---

## 3. Schemas (CANDIDATE)

### 3.1 Session bind — `qortroller-rwm-session-bind-v0`

```text
schema: "qortroller-rwm-session-bind-v0"
candidate: true
session_id:           str     # must match L0
l0_chain_tip_hex:     str     # must match re-verify
bind_kind:            none | poac_segment | gic_tip | dual
poac_tip_hex:         str     # "" if unused; 64 hex when set
gic_tip_hex:          str     # "" if unused
bind_proof: {
  poac_source:        str     # path or "inline"
  gic_source:         str
  algorithm:          "sha256-hex-eq-v0"   # exact tip equality only in v0
}
bind_ok:              bool    # true only if all cited tips present + equal
created_ts_ns:        int
```

**verify_bind algorithm (v0):**
1. Re-verify L0 chain from archive (reuse NOV-3 `verify_l0_archive`).
2. For each non-empty tip field: load 32B hex from file or inline; compare to expected field.
3. `bind_ok = all required tips for bind_kind present and equal`.
4. No cryptographic cross-domain hash invented in v0 — **equality of published tips only**.
   (A future v1 may bind `SHA-256(DOMAIN || l0_tip || poac_tip || gic_tip)` as a single commitment; defer.)

### 3.2 Checkpoint inventory — `qortroller-rwm-checkpoint-inventory-v0`

```text
schema: "qortroller-rwm-checkpoint-inventory-v0"
candidate: true
session_id: str
l0_chain_tip_hex: str
n_frames: int
n_checkpoints: int
checkpoints: list[{
  checkpoint_index: int      # logical 0..n_cp-1
  frame_index: int           # into L0 frames[]
  frame_hash_hex: str        # L0 marked hash at that frame
  chain_hex_at_frame: str    # L0 chain_hex[frame_index]
}]
note: "L0 stop-path still paints locator checkpoint_index=0 on all frames; this inventory is steward addressing, not re-encoded marks."
```

### 3.3 SHARE postcard — `qortroller-rwm-share-postcard-v0`

```text
schema: "qortroller-rwm-share-postcard-v0"
candidate: true
session_id: str
commitment_root: str         # from LOCAL escrow
l0_frame_count: int
revealed_frame_indices: list[int]
bind_ok: bool | null
bind_kind: str | null
case_id: str
reason: str                  # may truncate to 200 chars
redaction: ["device_id_hex", "leaf_hashes", "inventory", "revealed.media"]
created_ts_ns: int
```

**Structural verify only** — SHARE is indicative (same class as receipt postcard). Full proof stays LOCAL + archive.

### 3.4 Escrow additive (optional)

When CLI attaches bind:

```text
# existing qortroller-rwm-dispute-escrow-v0 fields unchanged
session_bind: { ... qortroller-rwm-session-bind-v0 fields ... } | absent
```

`verify_escrow` v0.1: if `session_bind` present, run `verify_bind` and require `bind_ok` match field; if absent, behavior identical to today.

---

## 4. CLI surface

```text
python scripts/rwm_nov2_cli.py bind \
  --archive retina_kf_archive/cfb_rwm_live_01_... \
  --escrow audits/rwm_escrow_....json \
  --kind dual \
  --poac-tip path/or/hex \
  --gic-tip path/or/hex \
  --out audits/rwm_bind_....json

python scripts/rwm_nov2_cli.py checkpoints \
  --archive retina_kf_archive/... \
  --out audits/rwm_cp_inv_....json

python scripts/rwm_nov2_cli.py share \
  --escrow audits/rwm_escrow_....json \
  --out audits/rwm_share_....json
```

Consent banner on `share` (reuse NOV-3 text). No upload.

---

## 5. Tests (minimum suite after GO)

| ID | Assert |
|----|--------|
| T1 | `verify_bind` none → bind_ok true, empty tips |
| T2 | poac tip match → bind_ok true |
| T3 | poac tip mismatch → bind_ok false |
| T4 | missing tip file for required kind → bind_ok false (no throw if soft) / EscrowError if `--require-bind` |
| T5 | checkpoint inventory default indices unique + hashes match L0 |
| T6 | checkpoint inventory wrong frame hash fails verify |
| T7 | SHARE omits device_id_hex and leaf_hashes |
| T8 | SHARE keeps commitment_root + revealed indices |
| T9 | escrow without session_bind still verifies (backward compat) |
| T10 | escrow with session_bind bind_ok=false fails extended verify |

Target: ~10–12 bridge tests. No Hardhat. No PV-CI pin.

---

## 6. Definition of Done (build round)

| Step | Criterion |
|------|-----------|
| D1 | This plan reviewed — **operator GO** |
| D2 | Three pure modules land under `bridge/vapi_bridge/` |
| D3 | CLI `scripts/rwm_nov2_cli.py` |
| D4 | Tests T1–T10 green |
| D5 | Dogfood on local `live_01` archive (bind may be `none` if no tips; checkpoints + share still run) |
| D6 | Ladder README + scope status → BUILT (CANDIDATE) |
| D7 | No PoAC wire / FROZEN / stop-path / CHAIN_SUBMISSION change |

---

## 7. Explicit non-goals (v0)

- Live multi-checkpoint **re-encode** into `marked/` at stop (`RWM_CHECKPOINT_INDEX` loop) — **NOV-2.1**
- Cross-domain single hash commitment over (l0‖poac‖gic) — **v1** if needed
- On-chain bind registry / spend
- Path B SE perceptual marks
- Flipping `poep_enabled` / L6B / kill-switch
- Treating SHARE postcard as full third-party forensic proof

---

## 8. Live ops note (does not block plan GO)

`cfb_rwm_live_06` re-confirmed stop-fire integrity + FROZEN_RING diversity failure.
Multi-checkpoint **live-verify** still wants a diverse archive; v0 inventory dogfood
works on frozen rings (hashes stable) but should not be marketed as multi-moment play proof.

---

## 9. Operator GO checklist

Reply **GO NOV-2 plan** (or equivalent) to authorize code. Optionally override:

- [ ] Q2: prefer wall-clock cadence in 2.1 instead of frame-index inventory
- [ ] Q1: PoAC-only (drop GIC) for smaller surface
- [ ] Q3: keep device_id_hex on SHARE (default is strip)

*Plan drafted 2026-07-25 · sole agent (grok) · design-only until GO.*
