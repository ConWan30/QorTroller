# QorTroller — Disaster-Recovery Runbook (PUBLIC STUB)

**This is a stub. The operational runbook is intentionally private.**

The full disaster-recovery procedure — covering operator-machine total-loss
recovery, wallet/key custody, bridge DB backup/restore, KMS-rooted signing
recovery, and GitHub App OAuth recovery — contains sensitive operational
detail (key locations, credential inventories, infrastructure identifiers)
that must not live in a public repository.

It is maintained locally at:

```
docs/disaster-recovery-runbook.private.md   (gitignored — operator machine only)
```

## Why private

A disaster-recovery runbook is, by nature, a map of exactly where the
crown-jewel material lives and how to restore access to it. Publishing that
map lowers the cost of an attack. Per the protocol's security posture, the
operational runbook stays private; only this stub is public.

## What the private runbook covers (index only, no specifics)

1. Pre-incident operator checklist (backups that must exist before any loss)
2. Wallet key custody + continuity-first recovery
3. Bridge SQLite DB backup/restore (WAL-safe via `scripts/backup_store.py`)
4. KMS-rooted signing recovery (Guardian / Sentry)
5. GitHub App OAuth recovery
6. Post-restore integrity assertions
7. Backup cadence + off-site replication

## For operators

If you are the operator and the private companion is missing, reconstruct it
from your own secure backups — do not recreate its contents in any tracked
file. The pre-incident checklist (private §0) is the highest-leverage thing
to confirm is in place *before* any incident.

## Security findings

Security findings related to recovery posture (key custody, IAM scope,
single-copy material) are tracked privately and in the operator's own
hardening backlog — not enumerated here. The single highest-leverage standing
action remains backing up the Manufacturer Root CA material off-machine and
migrating it to an HSM-backed root (the long-term fix that also retires the
single-copy concern).

---

**History note:** earlier revisions of this path contained the full runbook
in public git history (it was first authored public, then privatized). Moving
it private now is forward-containment; it does not scrub prior commits. A
git-history rewrite is a separate operator-authorized decision (see the
F-CYCLE9-1 precedent — force-push to public `main` is on the
never-without-explicit-request list and would not clean existing clones/forks).
