# NOV-1 — Portable stranger-verify dispute pack · implementation plan

**Status: BUILT (CANDIDATE) 2026-07-25** under operator GO.  
Companion: `nov-1-scope.md`. Ladder: `README.md`. Prior: NOV-2 BUILT (`78c0b1c8`).

**Shipped:** `bridge/vapi_bridge/rwm_stranger_pack.py` · `scripts/rwm_nov1_cli.py` ·
`bridge/tests/test_rwm_nov1.py` (T1–T5). Offline only; archive-free verify.

---

## 0. Honest claim

**Ship (after GO):** offline tools that build a **portable pack** from a verified
L0 archive + NOV-3 escrow (or reveal indices), such that a third party can
`verify_stranger_pack(pack)` **without** access to the full ring archive.

**Ceiling:** membership of revealed L0 marked-frame hashes under a committed set,
with pack-local media for those frames. **Not** re-encode proof. **Not** FROZEN.

---

## 1. Decisions locked

| # | Question | Decision | Why |
|---|----------|----------|-----|
| **Q1 Mode** | Merkle now? | **v0.a first: pack-local media + existing SD-1 root + full leaf_hashes optional** | Unblocks archive-free verify of media integrity + root recompute when leaves present; Merkle (v0.b) is same PR if small else NOV-1.1 |
| **Q2 Media** | paths vs inline | **default inline base64 of marked PNG for revealed only** | Stranger has no archive path; LOCAL escrow may keep paths |
| **Q3 Privacy** | device_id | **omit device_id from stranger pack** (leaf still binds it internally via leaf preimage — stranger needs device_id_hex to recompute leaf!) | **Revised:** include `device_id_hex` in pack (required for leaf preimage) OR change leaf to not need device for stranger path. **Lock: include device_id_hex** — same as LOCAL escrow; SHARE remains the redacted surface |
| **Q4 Stop-path** | couple? | **none** | Offline only |
| **Q5 Schema** | | `qortroller-rwm-stranger-pack-v0` CANDIDATE | Separate from SHARE postcard |

**Leaf recompute note:** NOV-3 `compute_leaf(session, device, index, frame_hash)` needs
`device_id_hex`. Stranger pack **must** carry it (or leaf_hash only + trust package
leaf without recompute from media). **Lock: recompute from media** → carry
session_id + device_id_hex + frame_index + media bytes → hash media → leaf → root.

---

## 2. Architecture

```text
  L0 archive + reveal indices
        │
        ▼
  bridge/vapi_bridge/rwm_stranger_pack.py   NEW
    build_stranger_pack(archive, reveal_indices, reason, ...) -> dict
    verify_stranger_pack(pack) -> {ok, checks}   # NO archive_dir required
        │
        ▼
  scripts/rwm_nov1_cli.py   OR extend rwm_nov2_cli with `stranger` subcommand
```

**Hard rules:** offline; no stop-path; no PoAC wire; no auto-upload; consent banner.

---

## 3. Schema (CANDIDATE) — v0.a

```text
schema: "qortroller-rwm-stranger-pack-v0"
candidate: true
mode: "sd1_inline_media_v0"
session_id: str
device_id_hex: str
l0_chain_tip_hex: str
set_size: int
inventory: list[str]
leaf_hashes: list[str]
commitment_root: str
revealed: [{
  frame_index: int
  frame_hash_hex: str      # SHA-256 of marked media
  leaf_hash: str
  marked_png_b64: str      # pack-local media
}]
reason: str
case_id: str
created_ts_ns: int
```

**verify_stranger_pack:**
1. For each revealed: decode b64 → sha256 == frame_hash_hex
2. recompute leaf == leaf_hash ∈ leaf_hashes
3. recompute commitment_root == package root
4. set_size consistency

---

## 4. Tests (minimum)

| ID | Assert |
|----|--------|
| T1 | build+verify happy without archive on verify |
| T2 | bit-flip media fails |
| T3 | wrong leaf fails root |
| T4 | empty reveal refused |
| T5 | consent: no network calls |

---

## 5. DoD

D1 GO · D2 module · D3 archive-free verify · D4 tests · D5 dogfood live_01 · D6 docs.

---

## 6. Non-goals

Merkle compression (NOV-1.1) · on-chain · Path B · FROZEN · stop-path.

*Plan drafted 2026-07-25 · sole agent · design-only until GO.*
