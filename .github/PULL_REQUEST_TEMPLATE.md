## Summary

<!-- Why this change? What does it improve? -->

## Plane affected

- [ ] Bridge / protocol
- [ ] Contracts
- [ ] Frontend
- [ ] Docs / Pages / community
- [ ] Tests / PV-CI

## Test plan

- [ ] `python scripts/vapi_invariant_gate.py` still passes
- [ ] Targeted pytest for the files I touched
- [ ] No secrets, PATs, nsec, wallet keys, or `.env` files committed
- [ ] User-facing changes updated `README.md` or `site/`

## Checklist

- [ ] I have read `CONTRIBUTING.md` and `PRIVACY.md`.
- [ ] I did not loosen a FROZEN-v1 commitment or the 228-byte PoAC wire format.
- [ ] New flags / lobes default OFF if they touch hardware, chain, or network.
