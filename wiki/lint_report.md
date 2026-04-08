# VAPI Wiki Lint Report
Generated: 2026-04-08T01:17:20.959418+00:00
Wiki health score: 0/100

## Summary

| Issue | Count | Severity |
|-------|-------|----------|
| Invariant violations in wiki | 1 | P0 |
| [NEEDS_PROVENANCE] flags | 4 | P0 |
| [CONTRADICTION: unresolved] | 4 | P1 |
| [WIKI_GAP] flags | 0 | P1 |
| Blocked update backlog | 0 | P1 |
| Orphan pages | 22 | P2 |
| [DESIGNED:] stale claims | 0 | P2 |

## P0 Actions (resolve before next ingest)
- briefs\brief_VAPI_INVARIANTS.md_166.md: CHAIN_HASH: Must be SHA-256(raw[:164]) — signature bytes exc...

## P1 Actions
- briefs\brief_MEMORY.md_166.md
- briefs\brief_VAPI_AGENTS.md_166.md
- briefs\brief_VAPI_INVARIANTS.md_166.md
- briefs\brief_VAPI_WHAT_IF.md_166.md

## P2 Actions
- briefs\brief_MEMORY.md_166.md
- briefs\brief_VAPI_AGENTS.md_166.md
- briefs\brief_VAPI_INVARIANTS.md_166.md
- briefs\brief_VAPI_WHAT_IF.md_166.md
- concepts\epistemic_consensus.md

## Commands to Resolve
```bash
# Re-ingest source files to fill provenance gaps
python vapi_wiki.py brief MEMORY.md 166
python vapi_wiki.py brief VAPI_INVARIANTS.md 166

# Feed gaps to AutoResearch
python vapi_wiki.py autoresearch_feed

# Take snapshot after resolving
python vapi_wiki.py snapshot
```
