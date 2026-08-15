# How to clone and verify with zero secrets

```powershell
git clone https://github.com/ConWan30/QorTroller.git
cd QorTroller
python scripts/vapi_invariant_gate.py
python scripts/verify_wmp_ladder.py
```

That path is the one designed for strangers, journalists, and organizers.

If a command asks for `bridge/.env`, a PAT, or a wallet key, you have left the public verify path. Stop and check `PRIVACY.md`.
