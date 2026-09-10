# Clock Notary — accessible door (truth plane)

Qoresence remains the eyes. QorTroller becomes the notary of the same clock, after the gamer says so.

Gamers do not come here first. They export from Session Theater Recap, then either seal there (local phrase) or wrap here.

## Wrap

```powershell
python scripts/clock_notary_wrap.py wrap --envelope observation-envelope.json --consent compose/clock-notary/fixtures/gamer-consent.json --out notary-wrap.json
```

`signed_by` must be the gamer. `bridge` / `operator` are refused.

## Verify without trusting this repo

```powershell
python scripts/clock_notary_verify.py --envelope observation-envelope.json --wrap notary-wrap.json
```

Recomputes `clock_commitment`. Ignores producer `status`. Checks gamer signature, advisory, never-ban, no humanity claim.

Chain view stays paused unless you unset `CHAIN_SUBMISSION_PAUSED`.
