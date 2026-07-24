"""OPERATOR-RUN no-spend preflight for the Manufacturer Root CA HSM flip (Ceremony B).

Run AFTER you provision the P-256 AWS KMS key + alias, BEFORE any re-issue / re-anchor / IOTX spend. Proves
the KMS-backed CA produces device certificates that verify, so a misconfigured key is caught for free.

  MFG_CA_BACKEND=kms VAPI_KMS_MFG_CA_ALIAS=alias/qortroller-mfg-ca AWS_REGION=us-east-1 \\
    python scripts/mfg_ca_hsm_preflight.py

Needs YOUR AWS creds (this is your infra). It NEVER calls the chain, NEVER spends, NEVER provisions.
Exit 0 = KMS CA ready. It does NOT mean the existing on-chain device can be re-anchored — see the VMDR
one-shot note in docs/path-a-mfg-ca-hsm-migration.md.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def main(argv=None) -> int:
    which = os.getenv("MFG_CA_BACKEND", "software").strip().lower()
    alias = os.getenv("VAPI_KMS_MFG_CA_ALIAS", "").strip()
    if which != "kms" or not alias:
        print("ERROR: set MFG_CA_BACKEND=kms and VAPI_KMS_MFG_CA_ALIAS=<your P-256 CA alias> first.")
        return 2

    try:
        from bridge.vapi_bridge.manufacturer_root_ca import (
            DEFAULT_ROOT_CA_KEY_PATH, ManufacturerRootCA)
        from bridge.vapi_bridge.mfg_ca_readiness import check_ca_readiness
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: bridge import failed: {exc!r}")
        return 2

    # KMS key metadata (describe_key) — best-effort; None if boto3/creds unavailable (soft).
    region = os.getenv("AWS_REGION", "us-east-1")
    key_metadata = None
    try:
        import boto3
        key_metadata = boto3.client("kms", region_name=region).describe_key(KeyId=alias)["KeyMetadata"]
    except Exception as exc:  # noqa: BLE001
        print(f"[preflight] describe_key unavailable ({exc!r}) — metadata checks skipped (soft).")

    # prior software CA pubkey, if the software key file still exists (proves this is a NEW root).
    prior = None
    try:
        p = Path(DEFAULT_ROOT_CA_KEY_PATH)
        if p.exists():
            prior = json.loads(p.read_text(encoding="utf-8")).get("public_key_hex")
    except Exception:  # noqa: BLE001
        prior = None
    if not prior:
        print("[preflight] prior software CA pubkey not found — new-root is NOT proven this run (crypto "
              "readiness still checked; confirm the KMS key is genuinely a fresh root, not a re-import).")

    try:
        ca = ManufacturerRootCA()   # MFG_CA_BACKEND=kms -> KMSIdentityBackend on the alias
        r = check_ca_readiness(ca, prior_software_ca_pubkey_hex=prior, key_metadata=key_metadata)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: readiness check errored (KMS CA not usable): {exc!r}")
        return 1

    print("=== MFG Root CA HSM readiness ===")
    for k in ("is_p256_65b", "canary_verifies", "full_cert_verifies", "key_enabled", "key_usage_ok",
              "key_spec_ok", "is_new_root"):
        print(f"  {k:18}: {r.get(k)}")
    print(f"  new issuer pubkey : {str(r.get('new_issuer_pubkey_hex'))[:34]}...")
    for w in r.get("warnings", []):
        print(f"  ! {w}")
    print(f"\n  READY: {r['ready']}  ({r['reason']})")
    print("\n  NOTE: readiness != the existing device can be re-anchored. VMDR registerDevice is ONE-SHOT;")
    print("  581a836c cannot move to this new root without an updateBirthCertHash contract path or a")
    print("  net-new-devices-only policy. See docs/path-a-mfg-ca-hsm-migration.md. No chain/spend was done.")
    return 0 if r["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
