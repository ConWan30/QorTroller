# Start with zero secrets

```powershell
git clone https://github.com/ConWan30/QorTroller.git
cd QorTroller
python scripts/vapi_invariant_gate.py
python scripts/verify_wmp_ladder.py
```

You do **not** need:

- a GitHub PAT
- a wallet private key
- a Buzz `nsec`
- `bridge/.env`
- a DualShock Edge (for the public verify path)

Hardware, Buzz, and chain writes are operator-only and env-gated. Copy `*.env.example` files locally. Never commit the filled copies.
