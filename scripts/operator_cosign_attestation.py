"""OPERATOR-RUN co-sign tool — adds the operator's non-repudiable co-signature to a Guardian-signed SEL
graduation attestation. This is the operator half of REAL non-repudiation (grok round-17).

TRUST MODEL: the operator's key is supplied ONLY via the OPERATOR_ATTEST_PRIVATE_KEY env, set by the
operator in THEIR OWN shell — NEVER in bridge/.env, never committed, never in the bridge process. The
bridge holds Guardian's AWS creds (so it can produce Guardian's signature) but it does NOT hold this key,
which is exactly why the operator half cannot be forged. The tool REFUSES if the key derives the bridge
wallet (there would be no non-repudiation then), mirroring set-world-model-consent.js.

  OPERATOR_ATTEST_PRIVATE_KEY=0x... python scripts/operator_cosign_attestation.py <attestation.json> [--out X]

The Guardian attestation must have been created with operator_id == YOUR address (attest_graduation
operator_id=<your 0x address>), else the tool refuses — the operator cannot override the signed decision.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_sel_cosign import (  # noqa: E402
    add_operator_cosignature,
    assert_operator_key_not_bridge,
    verify_dual_signed_attestation,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Operator co-sign a Guardian SEL graduation attestation")
    parser.add_argument("attestation_json", help="path to the Guardian-signed attestation record JSON")
    parser.add_argument("--out", default=None, help="output path (default: <input>.dualsigned.json)")
    args = parser.parse_args(argv)

    pk_hex = os.getenv("OPERATOR_ATTEST_PRIVATE_KEY", "").strip()
    if not pk_hex:
        print("ERROR: set OPERATOR_ATTEST_PRIVATE_KEY to YOUR operator key (never in bridge/.env, never "
              "committed). This is the key the bridge must not hold.")
        return 2

    try:
        from eth_keys import keys
        priv = keys.PrivateKey(bytes.fromhex(pk_hex.removeprefix("0x")))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: OPERATOR_ATTEST_PRIVATE_KEY is not a valid secp256k1 key: {exc!r}")
        return 2
    address = priv.public_key.to_checksum_address()

    try:
        assert_operator_key_not_bridge(address)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 3

    try:
        record = json.loads(Path(args.attestation_json).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not read attestation JSON: {exc!r}")
        return 2

    op_id = str(record.get("operator_id", ""))
    if op_id.lower() != address.lower():
        print(f"ERROR: attestation operator_id {op_id!r} != your address {address}. The Guardian "
              "attestation must be created FOR your address (attest_graduation operator_id=<your 0x addr>).")
        return 4

    def operator_sign(digest: bytes) -> bytes:
        return priv.sign_msg_hash(digest).to_bytes()

    try:
        dual = add_operator_cosignature(record, operator_sign=operator_sign)
    except ValueError as exc:
        print(f"ERROR: co-sign refused: {exc}")
        return 5

    v = verify_dual_signed_attestation(dual)
    out_path = args.out or (str(Path(args.attestation_json).with_suffix("")) + ".dualsigned.json")
    Path(out_path).write_text(json.dumps(dual, indent=2), encoding="utf-8")
    print(f"[cosign] operator {address} co-signed -> {out_path}")
    print(f"[cosign] fully_authorized={v['fully_authorized']} "
          f"(guardian_ok={v['guardian_ok']} operator_id_authenticated={v['operator_id_authenticated']})")
    print("[cosign] this proves the KEYHOLDER of operator_id authorized the package alongside Guardian — "
          "not a named human's cognitive intent. SEL still never auto-applies.")
    return 0 if v["fully_authorized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
