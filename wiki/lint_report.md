# VAPI Wiki Lint Report
Generated: 2026-04-08T01:39:00.619931+00:00
Health: 0/100

## Issues
| Type | Count | Priority |
|------|-------|----------|
| Invariant violations | 1 | P0 |
| [NEEDS_PROVENANCE] | 4 | P0 |
| [CONTRADICTION: unresolved] | 4 | P1 |
| [WIKI_GAP] | 0 | P1 |
| Orphan pages | 24 | P2 |

## P0 — Fix immediately
- briefs\brief_VAPI_INVARIANTS.md_166.md: CHAIN_HASH: Must be SHA-256(raw[:164]) — signature bytes exc
- briefs\brief_MEMORY.md_166.md
- briefs\brief_VAPI_AGENTS.md_166.md
- briefs\brief_VAPI_INVARIANTS.md_166.md
- briefs\brief_VAPI_WHAT_IF.md_166.md

## P1 — Fix before next phase close
- briefs\brief_MEMORY.md_166.md
- briefs\brief_VAPI_AGENTS.md_166.md
- briefs\brief_VAPI_INVARIANTS.md_166.md
- briefs\brief_VAPI_WHAT_IF.md_166.md

## Commands
```bash
python vapi_wiki_engine.py agent_feed        # refresh ratio from Agent 15
python vapi_wiki_engine.py sync_what_if      # sync W1 -> eval harness
python vapi_wiki_engine.py snapshot --anchor # commit + on-chain anchor
```
