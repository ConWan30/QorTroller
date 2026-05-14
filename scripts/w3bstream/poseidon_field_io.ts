/**
 * poseidon_field_io.ts -- Phase O4-W3B-POSEIDON-AS Stream I.2
 *
 * Byte-interface helpers for the protocol-internal AssemblyScript
 * Poseidon(BN254) module: conversion between the on-wire 32-byte big-endian
 * field-element encoding and the internal 4xu64 little-endian limb
 * representation used by poseidon_bn254.ts.
 *
 * This matches the circomlibjs F.toObject() / F.fromObject() convention
 * exactly -- 32-byte big-endian, with values >= p reduced mod p on input. It
 * is also the encoding the VAPI W3bstream applet uses on the wire.
 *
 * The substantive conversion logic lives in poseidon_bn254.ts (feFromBytesBE /
 * feToBytesBE), where it was needed for I.1a's modular-arithmetic layer and
 * I.1b's arity entry points. This file exists per the phase plan (Stream I.2)
 * as the named byte-interface module; it thin-wraps the poseidon_bn254.ts
 * helpers so callers can depend on a stable, intent-named surface without
 * reaching into the arithmetic module.
 *
 * Field element representation: StaticArray<u64> length 4, little-endian limbs
 * (limb[0] = least significant 64 bits). Fully reduced (< p).
 */

import { feFromBytesBE, feToBytesBE } from "./poseidon_bn254";

// ---------------------------------------------------------------------------
// bytes32 <-> field element (pointer-based)
// ---------------------------------------------------------------------------

/**
 * bytes32_to_field -- read a 32-byte big-endian buffer at `ptr` into a BN254
 * field element. The value is reduced mod p if the input is >= p (matching
 * circomlibjs F.fromObject(), which reduces). `ptr` must point to at least 32
 * readable bytes. Returns a fresh, fully reduced 4xu64 little-endian field
 * element.
 */
export function bytes32_to_field(ptr: i32): StaticArray<u64> {
  return feFromBytesBE(ptr);
}

/**
 * field_to_bytes32 -- write a BN254 field element as a 32-byte big-endian
 * buffer at `outPtr`. `outPtr` must point to at least 32 writable bytes. The
 * element is assumed already reduced (< p) -- every element produced by the
 * poseidon_bn254.ts module satisfies this. Matches circomlibjs F.toObject()
 * byte order.
 */
export function field_to_bytes32(field: StaticArray<u64>, outPtr: i32): void {
  feToBytesBE(field, outPtr);
}

// ---------------------------------------------------------------------------
// bytes32 <-> field element (ArrayBuffer-based convenience)
// ---------------------------------------------------------------------------

/**
 * bytes32_buf_to_field -- convenience wrapper accepting a 32-byte ArrayBuffer
 * (the shape the applet receives field elements in) instead of a raw pointer.
 */
export function bytes32_buf_to_field(buf: ArrayBuffer): StaticArray<u64> {
  return feFromBytesBE(<i32>changetype<usize>(buf));
}

/**
 * field_to_bytes32_buf -- convenience wrapper returning a freshly allocated
 * 32-byte ArrayBuffer holding the big-endian encoding of `field`.
 */
export function field_to_bytes32_buf(field: StaticArray<u64>): ArrayBuffer {
  const buf = new ArrayBuffer(32);
  feToBytesBE(field, <i32>changetype<usize>(buf));
  return buf;
}

// ---------------------------------------------------------------------------
// I.2 smoke-test entry point
// ---------------------------------------------------------------------------

/**
 * smoke_io_roundtrip -- writes a small u64 value into a 32-byte buffer
 * big-endian via field_to_bytes32, reads it back via bytes32_to_field, and
 * returns limb[0]. For any v < 2^64 the round-trip is the identity, so the
 * I.2 harness asserts smoke_io_roundtrip(v) == v.
 */
export function smoke_io_roundtrip(v: u64): u64 {
  const fe = new StaticArray<u64>(4);
  fe[0] = v; fe[1] = 0; fe[2] = 0; fe[3] = 0;
  const buf = new ArrayBuffer(32);
  const ptr = <i32>changetype<usize>(buf);
  field_to_bytes32(fe, ptr);
  const back = bytes32_to_field(ptr);
  return back[0];
}
