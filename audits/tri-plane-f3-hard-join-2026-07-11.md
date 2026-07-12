# Tri-Plane F3 — meaning-plane HARD cryptographic join (grounding + mechanism)

**2026-07-11.** F3 closes the tri-plane fusion's last open lane: upgrading the MEANING↔session join
from *reference + attestation* (S4's ceiling) to a **cryptographic** join — **earned by a verified
root match, never asserted**. Grounding-first refuted the easy path; the honest mechanism is built and
tested; the real-M17 join is honestly gated (DeferredProver shape). No fake join ships.

Reproduce: `python -m pytest l9_presence/tests/test_tri_plane_f3_hard_join.py -q`

## The grounding finding (why the easy path was wrong)

F1 claimed the hard join would be cheap because "the PoSP's KAS is committed over the SAME M17 PoAC
records" as the WMP bundle's `poacChainRoot`. **Grounding the two artifacts refuted this:**

| plane | artifact field | value shape | domain |
|---|---|---|---|
| MEANING (WMP bundle) | `humanity_proof_public_inputs.poacChainRoot` | `2883…5222` — **BN254 field element** (decimal) | Arc-5 **Poseidon** over the PoAC chain |
| ASSERTION (M17 PoSP) | `kas.commitment` / `events_roots.kas_session_root` | `4b453dd8…` / `441585a6…` — **SHA-256 hex** | **KAS domain** (authored_kills, kas_domain_tag, verdict) |

The KAS commitment is a **SHA-256 over KAS-domain data**, not the Poseidon PoAC-chain root. The two
roots are in **different domains with different hash functions — they cannot byte-match.** A naive F3
that byte-compared `kas_session_root` against `poacChainRoot` would have manufactured a **fake**
cryptographic join. The M17 PoSP contains **no poac-shaped field at all** (`poac`, `poac_chain_root`,
`chain_root` all absent).

## The honest mechanism (built + tested)

The hard join requires the PoSP to **carry the SAME Arc-5 `poac_chain_root`** the WMP replay pipeline
computes. `poac_chain_join(assertion_root, meaning_root)` byte-compares them as BN254 field elements
(representation-robust across int / decimal-str / `0x`-hex):

- **`VERIFIED_MATCH`** → the meaning join **earns** `CRYPTOGRAPHIC`. `verify_tri_plane_manifest` permits
  the `CRYPTOGRAPHIC` label **only** with this verified match; an unearned claim is **REJECTED**.
- **`MISMATCH`** → a caught cross-plane splice; the join stays attested, never rounded up.
- **`ABSENT`** (either side has no root) → today's committed **M17** — the join stays honestly
  `REFERENCE_ATTESTED` (`assertion.poac_chain_root: null`, `join_status.poac_chain_join: ABSENT`).

**This defeats the S4 meaning splice** for any field-bearing session: a spliced (different-session)
bundle has a different `poacChainRoot`, so the roots disagree → the builder refuses `CRYPTOGRAPHIC`,
and a forger who forces the label + rehashes is rejected by verify.

## What is gated (and it is genuinely gated, not hand-waved)

The **mechanism** is live now. The **real M17 cryptographic join** is deferred because:

1. M17's committed PoSP (2026-07-08) **predates** the `poac_chain_root` field.
2. Surfacing M17's actual Arc-5 root means **re-deriving it from `bridge_match17.db`** through the
   replay pipeline + Poseidon helper — a DB/rig-gated offline step (the INC-0 kill-check path).

**Activation, either path:**
- **Live:** the daemon carries `poac_chain_root` on the PoSP at mint (the same Arc-5 Poseidon root the
  WMP pipeline already computes). Every new field-bearing session then earns the cryptographic join.
- **M17 backfill:** re-derive M17's root offline from `bridge_match17.db`, add it to an M17 PoSP, and
  the join verifies against the bundle's existing `poacChainRoot`.

## Ceiling

N=1, developer_self, IoTeX testnet. The mechanism touches **no** PoAC / 228B wire / FROZEN-v1 / chain —
it reads an optional field and byte-compares two published roots. `poac_chain_root` on the PoSP is an
**additive, optional** field: absent → byte-identical to prior behavior (M17 unchanged). Federation, not
conflation. PV-CI 182.
