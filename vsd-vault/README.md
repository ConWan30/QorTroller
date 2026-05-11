# VSD Vault

This directory houses the **VAPI Architectural Discipline (VAD)** framework
as established by VBDIP-0001 on 2026-05-10 (commit landed in Phase
O1-VBDIP-0001-INTEGRATION Step 5).

VAD is the top-level framework name for VAPI's methodology surface, with
three sub-disciplines:

- **VSD** — Verified Synthesis Discipline (synthesis sub-discipline; this
  directory hosts the synthesis vault when Phase O1-VSD-BOOTSTRAP ships)
- **VED** — Verified Engineering Discipline (engineering sub-discipline;
  governs protocol-side engineering work retroactively named under VED)
- **VBD** — Verified Bridge Discipline (composition sub-discipline;
  governs cross-fleet skill-separation, the unified harness, CDRR
  primitive, and the proposal-numbering lineage)

## Current vault contents

| Path | Purpose | Trackable? |
|------|---------|------------|
| `README.md` | This file. | YES |
| `.gitignore` | SECURITY-CRITICAL: keeps private key material out of git. | YES |
| `architect_key.pem` | **PRIVATE KEY** — gitignored. NEVER committed. | NO |
| `architect_pubkey.pem` | Architect Ed25519 public key (convenience artifact). | NO (gitignored by root `*.pem`) |
| `eval/architect_key_attestation.json` | Bridge wallet attestation of architect Ed25519 pubkey. Phase O1-VBDIP-0001 Step 4. | YES |
| `manifests/proposals-VBDIP-0001/001.manifest.json` | Architect Ed25519 signature over VBDIP-0001 FROZEN content (Step 5 deliverable). | YES |
| `notes/` | Synthesis note directory tree (12 note types; populated at Phase O1-VSD-BOOTSTRAP Stream F). | YES (when present) |
| `corpus/` | NotebookLM corpus snapshots (populated at Phase O1-VSD-BOOTSTRAP Stream G). | YES (when present) |
| `proposals/` | VSDIP / VEDIP / VBDIP numbered proposals (eventual home; VBDIP-0001 currently in `wiki/methodology/` staging). | YES (when present) |
| `eval/INVARIANTS.md` | 23 VSD invariants normative form (populated at Phase O1-VSD-BOOTSTRAP Stream B). | YES (when present) |

## Framework rename and deferred directory migration

This directory retains the name `vsd-vault/` from the VSD-only era
because directory paths are operationally load-bearing in:

- The unified `scripts/vapi_invariant_gate.py` harness configuration
- The NotebookLM export script (post-bootstrap)
- The Synthesis Operator Fleet (SOF) Cedar bundle lane prefixes
  (post-bootstrap)

The rename to `vad-vault/` is **deferred** to a separate phase named
**Phase O1-VAD-MIGRATE** per VBDIP-0001 §6 / VBDIP-0002 reserved
numbering slot. Until Phase O1-VAD-MIGRATE ships, the directory name
does not match the framework name; this inconsistency is intentional,
named, and operationally bounded.

VBDIP-0002 (per the resolved Section 1.3 N1/N2'/N3 numbering decision)
must be resolved before Phase O1-VAD-MIGRATE proceeds. The Migration's
wallet impact is estimated at ~0.18 IOTX for Cedar bundle re-anchoring;
operator-authorized at the appropriate time.

## VAD sub-discipline mapping

| Sub-discipline | Invariant prefix | Methodology file | Harness `--proposal-type` mode |
|----------------|------------------|------------------|---------------------------------|
| VSD synthesis | `VSD-INV-N` (post-bootstrap) | `wiki/methodology/vsd_volume_2_final.md` | `synthesis` (stubbed; ships at bootstrap) |
| VED engineering | `INV-*` (count abstraction over existing protocol allowlist) | retrospective; `VEDIP-0001` follow-up | `protocol` (default; existing behavior) |
| VBD bridge | `VBD-INV-N` | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` | `bridge` (VBD-INV-1/2/3 + later VBD-INV-4 retroactive CFSS rename) |
| `all` | union | composite | `all` (runs all registered sets) |

## Numbered-proposal lineage

| Lineage | Status | Reference |
|---------|--------|-----------|
| **VSDIP-0001** | v1.0 FINAL | `wiki/methodology/vsd_methodology_v1_FINAL.md` |
| **VSDIP-0002** | v2.0 FINAL | `wiki/methodology/vsd_volume_2_final.md` |
| **VSDIP-0003** | pre-bootstrap strengthening (pending; authored Stream A.5) | (forthcoming) |
| **VEDIP-0001** | retroactive engineering documentation (pending) | per VBDIP-0001 §8 |
| **VBDIP-0001** | v1.0 FROZEN at Phase O1-VBDIP-0001 Step 5 | `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` |
| **VBDIP-0002** | sidecar FROZEN-SPEC; awaiting numbering resolution (N1/N2'/N3 per VBDIP-0001 §3.3 reserves) | `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` |
| **VBDIP-0003** | reserved per VBDIP-0001 §3.3 (post-bootstrap discovery) | (reserved) |

## Cryptographic anchor

The architect Ed25519 signing key (`architect_key.pem`) is anchored to
the bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` via the
EIP-191 attestation at `eval/architect_key_attestation.json` (Phase
O1-VBDIP-0001 Step 4; committed 2026-05-10).

All future architect-signed methodology artifacts inherit trust from
this attestation. Architect key rotation requires Procedure-VSD-K1
(defined in `eval/PROCEDURES.md` when Stream A.5 of Phase
O1-VSD-BOOTSTRAP ships VSDIP-0003).

VBD-INV-1 (continuous deployer-verified provenance under fleet
expansion) is enforced procedurally by this anchor: any artifact whose
architect signature does not chain back to the bridge wallet
attestation fails the discipline.

## See also

- `wiki/methodology/INTEGRATION_PROVENANCE_2026-05-10.md` — the
  deferral-boundary witness manifest for VBDIP-0001 integration
- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` — VBDIP-0001 FROZEN proposal
- `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` — VBDIP-0002 (ZKBA) FROZEN-SPEC sidecar
- `wiki/methodology/vsd_methodology_v1_FINAL.md` — VSD v1.0 FINAL
- `wiki/methodology/vsd_volume_2_final.md` — VSD Volume 2 FINAL
- `wiki/methodology/phase_o1_vsd_bootstrap_canonical.md` — Phase O1-VSD-BOOTSTRAP canonical execution prompt
- `wiki/methodology/claude_code_master_resumption_prompt.md` — Master resumption prompt
