# VSD Note Schemas (frontmatter)

All notes are markdown with YAML frontmatter. Cross-references use stable `id`s. The harness
(`.vsd/vsd_eval_harness.py`) enforces the fields marked **required**.

Common fields: `type` (required), `id` (required), `created`, `deployer` (bridge wallet),
`refs` (list of ids), `manifest` (auto: `manifests/notes/<id>/<rev>.manifest.json`).

| Note type | Routine? (loop-signed) | Extra required fields |
|-----------|------------------------|-----------------------|
| `claim` | yes | `confidence` ∈ 8 estimative words · `effort` (int min) · `deployer` == bridge wallet |
| `synthesis` | yes | same honesty fields as `claim` |
| `ingredient` | yes | (external-source note; provenance only) |
| `pbsa` | yes | `phase_from`, `phase_to` (the boundary this cycle crosses) |
| `decision` | **no** — operator-pending | (architect decision; loop writes a STUB manifest, operator co-signs) |

**8 estimative words:** certain · highly-likely · likely · possible · unlikely · highly-unlikely ·
almost-certainly-not · remote.

Routine notes are signed by the loop with the architect Ed25519 key. Decision notes (and any
`eval/` re-freeze) are operator-signed only — the maker drafts, the operator decides.
