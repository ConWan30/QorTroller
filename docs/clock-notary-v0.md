# Clock Notary v0 — truth plane

Qoresence remains the eyes. QorTroller becomes the notary of the same clock, after the gamer says so.

## In this repo

- Pack: `compose/clock-notary/`
- Entry: `python scripts/clock_notary_wrap.py wrap --envelope observation-envelope.json --consent compose/clock-notary/fixtures/gamer-consent.json --out notary-wrap.json`
- Consent view: `compose/clock-notary/clock_notary/consent_view.py` — local only while `CHAIN_SUBMISSION_PAUSED` (default true)

## Rails

- `signed_by` must equal `gamer`. `bridge` / `operator` / protocol names are refused.
- PORT-CERT-lite is advisory, never-ban, `humanity_claim: false`.
- WMP precursor is action-channel only. No IMU / phi export.
- Do not fold HDMI / OCR into `poep_enabled`.
- No chain write in v0. Operator keeps merge authority.

Sister draft: Qoresence PR 184.
