# NOV-3 — Ledger-native dispute escrow · implementation plan

**Status: BUILT (CANDIDATE) 2026-07-25** under operator GO (sole-agent sequence:
L0 hold → NOV-3 implement → post-check diversity). Companion to `nov-3-scope.md`
and L0 live-verify gate `l0-live-verify-2026-07-24.md`. Ladder index: `README.md`.

**Shipped surface:** `bridge/vapi_bridge/rwm_dispute_escrow.py` ·
`scripts/rwm_dispute_escrow.py` · `bridge/tests/test_rwm_dispute_escrow.py`.
Still offline-only; no stop-path hook; no FROZEN/PV-CI pin.

This was the D1 plan deliverable named in `nov-3-scope.md`. Same discipline as L0’s
`docs/a2a/retina-witness-mark/l0-implementation-plan.md`.

---

## 0. Honest claim (restated)

**Ship:** offline tools that take a verified L0 RWM session archive, commit to
the full set of per-frame leaf hashes, and produce a **dispute escrow package**
that reveals only a chosen subset of frames — verifiable by a third party from
the package + archive bytes alone.

**Ceiling:** membership + binding in an immutable committed set of L0 leaves.
**Not** ZK value-hiding of hashes (SD-1 still exposes leaf hashes of the full
set; SD-2 Merkle upgrade is optional later). **Not** proof under re-encode.
**Not** live anti-cheat. **Not** Path B device-signed marks.

---

## 1. Decisions locked by this plan (scope open Qs → answers)

| # | Question | Decision | Why |
|---|----------|----------|-----|
| **Q1 Leaf identity** | Raw `frame_hash_hex` vs VDC wrap | **RWM-native leaves + parallel SD-1-shaped commitment** — do **not** force `vapi-wmp-derived-claim-v1` / WMP `DERIVATIONS` registry | VDC claims require a WMP provenance *bundle* parent; L0 frames are RWM-domain. Coupling invents a fake parent bundle. Reuse the *math shape* of SD-1 (`count + sorted leaves + inventory + root`), not the VDC schema. |
| **Q2 Reveal media** | What files ship in the package | **Hash + paths default; optional `--include-media marked`** | Default package stays small and git-safe. Media copy is opt-in for steward handoff; originals remain the forensic baseline (never overwrite). |
| **Q3 Who opens escrow** | Gamer vs operator | **v0: local operator/gamer offline CLI** — no wallet gate | No on-chain identity required for CANDIDATE desk tool. Wallet / dual-key is NOV-2+ or a later NOV-3.1. |
| **Q4 PoAC / GIC bind** | Cross-link now? | **Strict L0-only in v0** — optional free-text `external_ref` field only | Do not invent a PoAC binding that is not verified. NOV-2 can promote a real cross-primitive link. |
| **Q5 Consent / erasure** | BP-007 | **Doc + CLI warning; no auto-publish** | Escrow never uploads. README/CLI states dispute media may be biometric-adjacent; operator must hold consent before any share. Code does not call Pinata/chain. |

---

## 2. Architecture (three pure layers + one CLI)

```text
  L0 archive (gitignored)
    rwm_manifest_chain.json
    panel_*.png          (originals)
    marked/panel_*.png   (sidecar)
           │
           ▼
  ┌─────────────────────────────────────┐
  │  bridge/vapi_bridge/rwm_dispute_escrow.py   NEW pure module
  │    load_l0_chain(path) -> dict
  │    verify_l0_or_raise(...)          # reuses verify_session_chain
  │    build_escrow(l0, reveal_indices, reason, ...) -> dict
  │    verify_escrow(escrow, archive_dir?) -> {ok, checks}
  └─────────────────────────────────────┘
           │
           ▼
  scripts/rwm_dispute_escrow.py         NEW CLI (offline, post-stop only)
           │
           ▼
  audits/rwm_escrow_<label>_<case>.json  (or path under archive/; never crops)
```

**Hard rule:** nothing in this plan hooks `cmd_stop` or the capture hot path.
NOV-3 is **post-session, fail-open-from-L0’s perspective** (L0 already finished).

---

## 3. Schema (CANDIDATE)

```text
schema: "qortroller-rwm-dispute-escrow-v0"
candidate: true
domain_tag_commitment: "VAPI-RWM-DISPUTE-ESCROW-v0"   # bytes in root preimage only

session_id:           str   # from L0
device_id_hex:        str   # from L0, never fabricated
l0_genesis_ts_ns:     int
l0_chain_tip_hex:     str   # last chain_hex entry (binding to L0 tip)
l0_frame_count:       int

# SD-1-shaped set commitment (RWM-native leaves — NOT VDC claims)
set_size:             int
inventory:            list[str]   # "frame_{i}" sorted, i = frame_index
leaf_hashes:          list[str]   # sorted hex of leaf preimages (see §4)
commitment_root:      str         # hex SHA-256 over domain||session||tip||count||leaves||inventory

revealed_frame_indices: list[int]  # subset of frame_index
revealed: list[{
  frame_index: int
  frame_hash_hex: str            # L0 marked-file hash (must match L0 chain)
  source: str                    # original panel_*.png basename
  marked_relpath: str            # "marked/panel_....png"
  leaf_hash: str                 # must be in leaf_hashes
}]

reason:               str        # ≥10 chars
case_id:              str        # optional short id
external_ref:         str        # optional free text; not verified
include_media:        bool       # whether package was built with media copy
created_ts_ns:        int
```

**Domain tag is CANDIDATE** — not PV-CI-pinned, not FROZEN-v1. Any byte-order
change = v1 + new tag.

---

## 4. Commitment math (pin before code)

### 4.1 Leaf preimage (per L0 frame row)

```text
leaf_i = SHA-256(
  b"VAPI-RWM-DISPUTE-LEAF-v0"
  || session_id.encode("utf-8")
  || bytes.fromhex(device_id_hex)          # 32B
  || frame_index.to_bytes(4, "big")
  || bytes.fromhex(frame_hash_hex)         # 32B = L0 marked-file hash
)
leaf_hash_hex = leaf_i.hex()
inventory_id  = f"frame_{frame_index}"
```

Binding session + device + index + L0 hash into the leaf means a reveal cannot
re-label “frame 7 of session A” as “frame 7 of session B” without breaking the
root.

### 4.2 Commitment root

```text
commitment_root = SHA-256(
  b"VAPI-RWM-DISPUTE-ESCROW-v0"
  || session_id.encode("utf-8")
  || bytes.fromhex(l0_chain_tip_hex)
  || set_size.to_bytes(4, "big")
  || ",".join(sorted(leaf_hashes)).encode("utf-8")
  || ",".join(sorted(inventory)).encode("utf-8")
).hexdigest()
```

Mirrors SD-1’s “count + sorted leaves + inventory + parent binding” discipline
(`sdk/wmp_disclosure.py::_commitment_root`) with **L0 tip** as the parent
binding instead of a WMP bundle hash.

### 4.3 Prerequisites (fail-closed)

Before `build_escrow`:

1. Load `rwm_manifest_chain.json`.
2. Rebuild `(digest, ts_ns)` list from on-disk `marked/` files (same as
   `rwm_post_session_check` third-party path).
3. `verify_session_chain(session_id, device_id_hex, genesis_ts_ns, frames, chain)`
   must be **True**. Else raise / return error — **never invent leaves**.
4. Every `reveal_index` must exist in L0 `frames[]`.

---

## 5. API surface (pure module)

```python
# bridge/vapi_bridge/rwm_dispute_escrow.py  (NEW)

SCHEMA = "qortroller-rwm-dispute-escrow-v0"
DOMAIN_ROOT = b"VAPI-RWM-DISPUTE-ESCROW-v0"
DOMAIN_LEAF = b"VAPI-RWM-DISPUTE-LEAF-v0"

def load_l0_chain(archive_dir: Path) -> dict: ...
def verify_l0_archive(archive_dir: Path, l0: dict) -> bool: ...
def compute_leaf(session_id, device_id_hex, frame_index, frame_hash_hex) -> str: ...
def compute_commitment_root(session_id, l0_chain_tip_hex, leaf_hashes, inventory) -> str: ...

def build_escrow(
    archive_dir: Path,
    reveal_indices: list[int],
    reason: str,
    *,
    case_id: str = "",
    external_ref: str = "",
    include_media: bool = False,
) -> dict:
    """Fail-closed on bad L0 / empty reason / unknown indices.
    include_media: if True, caller/CLI may copy marked files beside the JSON;
    the JSON itself still only *references* paths (no base64 blobs in v0)."""

def verify_escrow(escrow: dict, archive_dir: Path | None = None) -> dict:
    """Recompute leaves + root. If archive_dir given, also re-hash revealed
    marked files and re-run L0 chain verify. Returns {ok, checks[]}."""
```

**No** bridge process, **no** SQLite, **no** network.

---

## 6. CLI (operator-facing)

```text
python scripts/rwm_dispute_escrow.py build \
  --archive retina_kf_archive/<label>_<stamp> \
  --reveal 10,11,12,13 \
  --reason "tournament dispute: clip 00:12-00:18" \
  --case-id CASE-001 \
  [--include-media] \
  [--out audits/rwm_escrow_CASE-001.json]

python scripts/rwm_dispute_escrow.py verify \
  --escrow audits/rwm_escrow_CASE-001.json \
  [--archive retina_kf_archive/<label>_<stamp>]
```

Exit codes: `0` ok · `1` verify/build fail · `2` usage / missing archive.

Print a one-line **consent reminder** on `build` (no network check).

---

## 7. Tests (target ~10–12, pure, no hardware)

| ID | Case |
|----|------|
| T1 | Happy path: synthetic L0 archive (reuse D6 crop seed pattern) → build → verify ok |
| T2 | Bit-flip a revealed marked file → verify fails |
| T3 | Wrong `session_id` in escrow JSON → root fails |
| T4 | Reveal index not in L0 → build raises |
| T5 | L0 chain broken (bit-flip before build) → build refuses |
| T6 | Empty reason / reason &lt; 10 chars → build raises |
| T7 | Full reveal (all indices) still verifies |
| T8 | Empty reveal list → build raises (escrow with zero reveal is useless noise) |
| T9 | `include_media=False` package has no media dir requirement for hash-only verify |
| T10 | Leaf preimage golden vector (fixed inputs → fixed hex) for independent reimplement |

cv2-guarded only if tests seed real PNGs the same way `test_rwm_daemon_wiring.py` does.

---

## 8. Ranked build order (after operator GO)

| Rank | Item | Notes |
|------|------|-------|
| 1 | Pure module + commitment helpers + golden T10 | No CLI yet |
| 2 | `build_escrow` / `verify_escrow` + T1–T8 | |
| 3 | CLI `build` / `verify` | Offline only |
| 4 | Optional `--include-media` path | Still no upload |
| 5 | Run against real `cfb_rwm_live_01` archive (local only) | Document result; no crop commit |
| 6 | Short ship note in ladder README | Honest ceiling restated |
| — | **Not this ship:** stop hook, chain anchor, wallet gate, SD-2 Merkle, FROZEN pin | |

---

## 9. Explicit non-goals (plan-level)

- No edits to `retina_capture_daemon.py` stop path for NOV-3
- No FROZEN-v1 / PV-CI allowlist ceremony
- No 228B PoAC wire change
- No `poep_enabled` / `L6B_ENABLED` / campaign flags
- No automatic Pinata / IoTeX write
- No claim that YouTube/Twitch re-encodes verify against exact-pixel leaves
- No multi-checkpoint (`checkpoint_index` stays 0 until a later ladder layer)

---

## 10. Rails

228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` · single-committer=operator ·
no secrets · archives gitignored · CANDIDATE schemas only

---

## 11. Operator GO checklist (before any NOV-3 code)

- [ ] Read this plan + `nov-3-scope.md`
- [ ] Accept Q1–Q5 decisions (or annotate changes)
- [ ] Explicit “GO build NOV-3” (or HOLD / amend plan)
- [ ] Confirm no stop-path coupling

**Until GO: plan only.**

---

## 12. Relationship to next capture (L0 ops — independent of NOV-3 code)

NOV-3 plan does **not** block L0 capture. Next capture readiness is L0-only:

1. `RWM_L0_DAEMON_ENABLED=true` and `RWM_DEVICE_ID_HEX=<edge>` in `bridge/.env` (already set)
2. Code on machine includes `_env_or_bridge_dotenv` (`d504ba58`+) so **stop auto-arms RWM**
3. Eye-check game feed before start; stop → expect `[daemon] RWM: N frames marked + chained`
4. `python scripts/rwm_post_session_check.py --label <label>` → EXIT 0

---

*Plan authored 2026-07-24. Ready for operator review. Not a build authorization.*
