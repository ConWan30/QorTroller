# CONCEPT: PoAC Wire Format

[VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

## FROZEN — DO NOT MODIFY

The 228-byte Proof of Autonomous Cognition (PoAC) wire format is the foundational
cryptographic primitive of VAPI. It has been frozen since Phase 1. Any modification
invalidates every prior proof in the chain.

## Format [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
| Bytes   | Content                     |
|---------|-----------------------------|
| 0–163   | 164-byte signed body        |
| 164–227 | 64-byte ECDSA-P256 signature |
| Total   | 228 bytes                   |
```

## Chain Link Hash [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
record_hash = SHA-256(raw[0:164])
```

Body ONLY. Not the full 228 bytes. The signature bytes are EXCLUDED from the hash.
This is a permanent invariant. Any reference to the full 228-byte slice (body+signature) is WRONG — only the 164-byte body is hashed.

## Device Identity [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
deviceId = keccak256(pubkey)
```

Never swap deviceId with record_hash. They are different things serving different
purposes: record_hash links sessions in the chain; deviceId identifies the hardware.

## Hardware Context [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

Capture rate: 1,002 Hz USB polling (DualShock Edge CFI-ZCP1).
One PoAC record produced per cognition cycle.
Injection margin: 14,000x (accelerometer), 10,000x (gyroscope) — bot injection is
physically detectable because it would require unrealistic signal magnitudes.

## CHEAT_CODES [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

Hard codes block tournament eligibility immediately:

| Code | Name | Detection |
|------|------|-----------|
| 0x28 | DRIVER_INJECT | IMU gravity vector + HID/XInput discrepancy |
| 0x29 | WALLHACK | TinyML behavioral classifier |
| 0x2A | AIMBOT | TinyML behavioral classifier |

Advisory codes (never block, contribute to humanity_probability):

| Code | Name | Layer |
|------|------|-------|
| 0x2B | TEMPORAL_BOT | L5 — temporal rhythm |
| 0x30 | BIOMETRIC_ANOMALY | L4 — Mahalanobis |
| 0x31 | IMU_PRESS_DECOUPLED | L2B — causal latency |
| 0x32 | STICK_IMU_DECOUPLED | L2C — cross-correlation |
| 0x33 | GSR_CORRELATION_ABSENT | L7 — advisory only, always |

## Related Pages

- [[zk_circuit]]
- [[l4_thresholds]]
- [[agent_fleet]]
- [[separation_ratio]]
