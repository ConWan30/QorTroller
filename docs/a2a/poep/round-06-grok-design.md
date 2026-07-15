# A2A-POEP-P2 · Round 06 · grok-design (Q7)

**Q7 — L6B human-reflex `policy_ref` allowlist / denylist**

| Set | Exact `policy_ref` values |
|-----|---------------------------|
| **ALLOW (counts as L6B human-reflex)** | `desk_operator_still` |
| **DENY (exclude by construction)** | `CCO_T0_POLICY_v1_OPTION_C` · `(null)` / missing · `desk_operator_squeeze` |
| **FUTURE stamp (registered-Edge campaign)** | `edge_operator_reflex_v1` |

**Rule (B2):** PoEP/RBM corpus queries MUST `policy_ref IN allowlist` (today: only `desk_operator_still`); never trust `REFLEX_OBSERVED=1` alone. **B1** still applies post-filter: IMU-corroborated peak>floor AND latency ∈ [80,350] ms AND not latency-artifact + burst-dedup.
