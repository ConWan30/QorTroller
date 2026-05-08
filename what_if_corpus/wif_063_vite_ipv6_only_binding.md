# WHAT_IF Entry — Vite Dev Server IPv6-Only Binding On Windows (2026-05-07)

**Source**: Empirical "Connection refused" errors when curl-testing Vite
proxy during Phase O1 C9 frontend audit
**Phase**: O1 C9 audit (operational finding; no code commit needed —
documented as gotcha for future contributors)
**Validation**: CLOSED via this WIF entry + diagnostic command in
documentation

---

## WIF-063 — Vite Binds `::1` (IPv6 localhost) Only On Windows; Browser Works But IPv4 Tooling Fails

**Operator-observed symptom**: During the Phase O1 C9 frontend integration
audit, multiple `curl -sS http://127.0.0.1:5173/` calls returned "Connection
refused" while `Get-NetTCPConnection -LocalPort 5173` showed Vite was in
LISTEN state with the correct PID. The browser at `http://localhost:5173`
worked fine.

**W1 — Failure mode (root-caused via PowerShell TCP audit)**:

Vite dev server (Node.js HTTP) binds **only** to `::1` (IPv6 localhost) on
Windows by default. PowerShell `Get-NetTCPConnection` revealed:
```
LocalAddress LocalPort State  OwningProcess
::1          5173      Listen 13336
```

No IPv4 (`127.0.0.1`) listener exists. So:
- ✅ `http://localhost:5173` (browser) → Windows resolves `localhost` to
  `::1` → connects via IPv6 → works
- ✅ `http://[::1]:5173` (curl IPv6 syntax) → connects via IPv6 → works
- ❌ `http://127.0.0.1:5173` (curl IPv4 default) → no IPv4 listener →
  Connection refused

This silently produces false alarms in operational audits (curl-based
endpoint smoke tests) and causes confusion when "Vite is running" but
"the URL doesn't work."

**Generalized lesson**: Windows asyncio + Node.js + browsers all have
their own quirks around IPv4 vs IPv6 localhost resolution. When a service
"appears to be listening but won't respond," check **which address family**
it's bound to before assuming it's a service-side issue. PowerShell
`Get-NetTCPConnection` shows `LocalAddress` which distinguishes `::1` from
`127.0.0.1` from `0.0.0.0`.

**W2 — Closure (operational documentation)**:

Diagnostic commands for future audits:
```powershell
# What's listening on port 5173?
Get-NetTCPConnection -LocalPort 5173 -State Listen | Format-Table LocalAddress, OwningProcess

# If LocalAddress = ::1, use IPv6 syntax for curl/PowerShell tests:
curl -6 http://[::1]:5173/
Invoke-WebRequest -Uri "http://[::1]:5173/" -UseBasicParsing
```

Optional fix (if IPv4 is desired): set Vite config `server.host = '0.0.0.0'`
or pass `--host 127.0.0.1` to `npm run dev`. Current behavior is acceptable
for operator-only frontend; documenting the gotcha is sufficient.

**Operational impact**: Without WIF-063 documented, future audits that
curl-test the frontend will produce false "Vite down" reports + unnecessary
restart cycles. Browser-based testing is unaffected.

**Cross-references**:
- Phase O1 C9 frontend audit session 2026-05-07 — empirical finding
- Vite default host config: `server.host` defaults to undefined which Node
  resolves to family-dependent localhost
- Bridge by contrast binds `0.0.0.0:8080` (both IPv4 + IPv6 listeners)
