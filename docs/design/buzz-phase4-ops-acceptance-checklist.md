# Phase 4 ACP Gateway — Ops Acceptance Checklist

**Status:** OPERATOR-LOCAL (cannot be completed from a remote session)  
**Code:** `scripts/qortroller_acp_gateway.py` (`de50a6d`)  
**Runbook:** `docs/design/buzz-phase4-acp-gateway-runbook.md`  
**Parent:** `docs/design/buzz-phase4-acp-grok-devin-addendum.md`

Phase 4 is **code-landed**. This checklist closes **ops acceptance** (G5-OPS).

---

## Prerequisites

- [ ] Repo on `main` at or after `de50a6d`
- [ ] Phase 1–3 bot still green (`scripts/qortroller_buzz_bot.py`)
- [ ] `scripts/.env` present (see `scripts/qortroller_buzz_bot.env.example`)
- [ ] Operator Nostr hex pubkey known
- [ ] Live `#rig-ops` channel reachable

---

## Step 1 — Wire the operator allow-list

In `scripts/.env`:

```
ACP_OPERATOR_PUBKEYS=<your_operator_hex_pubkey>
ACP_RIG_OPS_CHANNEL_ID=<rig-ops-uuid>   # or rely on first BUZZ_CHANNEL_IDS entry
ACP_BOT_HANDLE=@EA
```

Fail-closed rule: empty `ACP_OPERATOR_PUBKEYS` rejects every command.

- [ ] Pubkey set
- [ ] Channel ID confirmed

---

## Step 2 — Local `--eval` smoke (no relay publish)

```powershell
python scripts/qortroller_acp_gateway.py --eval "@EA health"
python scripts/qortroller_acp_gateway.py --eval "@EA invariant status"
python scripts/qortroller_acp_gateway.py --eval "@EA run pytest bridge/tests/test_qortroller_acp_gateway.py"
python scripts/qortroller_acp_gateway.py --eval "@EA exec rm -rf /"
```

Expected:

| Command | Expected reply shape |
|---|---|
| health | `[grok-build] health — ea: ok \| oracle: ok \| shell-false: ok` |
| invariant | `[grok-build] PV-CI PASS — 188 invariants` (or current live count) |
| pytest | `[grok-build] pytest …: N passed …` |
| banned | `rejected: outside the ACP allow-list …` |

- [ ] All four match expected shape
- [ ] No secrets / nsec / keys in any reply

---

## Step 3 — Dry-run against live channel

```powershell
$env:ACP_DRY_RUN="1"
python scripts/qortroller_acp_gateway.py
```

Post in `#rig-ops` (from the operator key):

1. `@EA health`
2. `@EA invariant status`
3. `@EA ceremony steps`
4. `@EA diagnose bridge capture lag`

Confirm process logs parse → authorize → route → audit **without** executing tools.
Check `audits/acp_gateway.jsonl` (gitignored) for four records.

- [ ] Dry-run parses and audits
- [ ] No tool subprocesses spawned

---

## Step 4 — Live acceptance (no dry-run)

```powershell
Remove-Item Env:ACP_DRY_RUN -ErrorAction SilentlyContinue
python scripts/qortroller_acp_gateway.py
```

Post in `#rig-ops`:

| # | Mention | Pass criterion |
|---|---|---|
| 1 | `@EA health` | In-thread digest with component block |
| 2 | `@EA invariant status` | In-thread PV-CI PASS + count |
| 3 | `@EA run pytest bridge/tests/test_qortroller_acp_gateway.py` | In-thread pass summary |
| 4 | `@EA diagnose <topic>` | Queued-for-Devin reply; row in `audits/acp_devin_queue.jsonl` |
| 5 | `@EA exec rm -rf /` | Named rejection; audited as `banned_tool_surface` |

- [ ] All five pass
- [ ] No chain interaction
- [ ] No raw HID / IMU / L4 / frames / full PoAC in any reply
- [ ] `python scripts/vapi_invariant_gate.py` still PASS

---

## Sign-off

| Field | Value |
|---|---|
| Operator | |
| Date (UTC) | |
| Main SHA at sign-off | |
| PV-CI count observed | |
| Notes | |

Once signed, **G5-OPS is closed**. Phase 5 may then pursue WP-A (done in-repo) and WP-C without treating ACP replies as population evidence.

---

**End of Phase 4 Ops Acceptance Checklist**
