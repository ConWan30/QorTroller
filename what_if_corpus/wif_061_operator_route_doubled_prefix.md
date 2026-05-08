# WHAT_IF Entry — Operator Endpoint Doubled-Prefix Codebase Convention (2026-05-07)

**Source**: Empirical 404s when frontend C5/C8 hooks tried to reach
operator-agent endpoints during Phase O1 C9 activation
**Phase**: O1 C9.1 (closure shipped commit `9bbab6ed`)
**Validation**: CLOSED via static-check test in Phase O1 C10 + memory entry +
12-precedent codebase audit

---

## WIF-061 — Sub-App Mount Path + Route Path Compose Into A Doubled URL

**Operator-observed symptom**: After Phase O1 C9 bridge boot, frontend
C5 (DeveloperView drawer) + C8 (cross-view badge) showed nothing. Browser
DevTools showed all 3 hook URLs (`/operator/operator-agent-shadow-log`,
`/operator/operator-agent-drift-log`, `/operator/operator-agent-activation-log`)
returning 404 from the bridge.

**W1 — Failure mode (root-caused via static codebase audit)**:

The bridge's operator app is mounted at `/operator` (`main.py:445`):
```python
app.mount("/operator", _op_app)
```

But the **codebase convention** (precedent across 12+ existing operator
endpoints — watchdog-status, suspension/propose, gic-reset, force-corpus-snapshot,
override-gameplay-context, record-category-consent, etc.) is for route
declarations *inside* `_op_app` to ALSO include the `/operator/` prefix:
```python
@app.get("/operator/watchdog-status")  # inside operator app
```

Result: full URL composes to `/operator` (mount) + `/operator/X` (route)
= `/operator/operator/X`. The frontend `_OP_PREFIX = '/operator'` then
prepends ONE `/operator`, so frontend hook paths must include
`/operator/X` for the composed URL `/operator/operator/X` to match.

The C5 hooks I shipped initially called paths *without* the inner
`/operator/` prefix:
```js
get('/operator-agent-shadow-log', ...)  // WRONG
```

This produced `/operator/operator-agent-shadow-log` — single prefix —
which 404'd against the doubled-prefix routes.

**Generalized lesson**: Codebase conventions that look "redundant" or
"weird" often encode reality. When my first instinct was to "clean up"
the doubled prefix by removing the inner `/operator/` from C2/C5 routes,
that would have broken parity with all 12+ existing endpoints. The
correct fix was to update C5 hook paths to match the convention.

**W2 — Closure (commit `9bbab6ed`)**:

Frontend hooks updated to use codebase-convention paths:
```js
get('/operator/operator-agent-shadow-log', ...)  // CORRECT
```

Memory file `feedback_operator_route_doubled_prefix.md` lists 12 precedent
endpoints + the rule + the bug history.

Phase O1 C10 E2E test (commit `51be8db6`) added Phase 6 — a **static check
that locks the C9.1 lesson into CI**:
```python
def test_phase_6_endpoints_match_codebase_convention(self):
    # Regex-asserts operator_api.py contains the 3 doubled-prefix routes
    # If a future contributor "cleans up" the doubled prefix, this fails
    # BEFORE bridge restart in production.
```

**Operational impact**: Without WIF-061 closure, every new operator
endpoint added to the codebase risks the same path-shape mismatch.

**Cross-references**:
- Commit `9bbab6ed` — frontend hook path fix
- Commit `51be8db6` — Phase O1 C10 static-check test
- Memory `feedback_operator_route_doubled_prefix.md` — rule + 12-precedent list
- Predecessor pattern: Phase O1 C5 frontend drawer (commit `003ea85c`) had
  the bug; C9.1 caught it at activation time
