# Clock Notary v0 + I/O ledger

Qoresence exports the eyes. This repo wraps after gamer consent.

`out_edge` is optional. DualSense-on-PS5 with no PC pad reports is success.
Never trust `wrap.status`. Recompute `clock_commitment`.

```bash
python scripts/clock_notary_wrap.py wrap \
  --envelope observation-envelope.json \
  --consent compose/clock-notary/fixtures/gamer-consent.json \
  --out notary-wrap.json

python scripts/clock_notary_verify.py \
  --envelope observation-envelope.json \
  --wrap notary-wrap.json
```
