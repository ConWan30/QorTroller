"""Inspect the adjudication pipeline tables to find where the chain stalls."""
import sqlite3

DB = r"C:\Users\Contr\.vapi\bridge.db"
c = sqlite3.connect(DB)

def count(table):
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception as exc:
        return f"ERR: {exc}"

print("=== PIPELINE TABLE COUNTS ===")
for t in ("records", "agent_rulings", "ruling_validation_log"):
    print(f"  {t:36s} {count(t)}")

# How many records in the last 30 minutes?
recent = c.execute(
    "SELECT COUNT(*) FROM records WHERE created_at > strftime('%s','now') - 1800"
).fetchone()[0]
print(f"  records last 30 min                  {recent}")

# Latest 3 records — show inference, status
print()
print("=== LATEST 3 RECORDS ===")
for row in c.execute(
    "SELECT counter, action, inference, status, created_at FROM records "
    "ORDER BY created_at DESC LIMIT 3"
).fetchall():
    print(f"  counter={row[0]} action={row[1]} inference=0x{row[2]:02x} status={row[3]} ts={row[4]}")

# Most recent agent_rulings if any
print()
print("=== LATEST 3 AGENT_RULINGS ===")
rulings = c.execute(
    "SELECT id, device_id, verdict, confidence, dry_run, created_at FROM agent_rulings "
    "ORDER BY created_at DESC LIMIT 3"
).fetchall()
if not rulings:
    print("  (no rulings produced)")
else:
    for row in rulings:
        print(f"  id={row[0]} device={row[1][:16]} verdict={row[2]} conf={row[3]} dry={row[4]} ts={row[5]}")

# Most recent ruling_validation_log if any
print()
print("=== LATEST 3 RULING_VALIDATION_LOG ===")
validations = c.execute(
    "SELECT id, ruling_id, divergence, pcc_state, pcc_host_state, "
    "gameplay_context, grind_chain_hash, gic_ts_ns, created_at "
    "FROM ruling_validation_log ORDER BY created_at DESC LIMIT 3"
).fetchall()
if not validations:
    print("  (no validation records)")
else:
    for row in validations:
        ch = row[6][:16] + "..." if row[6] else "NULL"
        print(f"  id={row[0]} ruling_id={row[1]} div={row[2]} pcc={row[3]}/{row[4]} gctx={row[5]} chain_hash={ch} gic_ts={row[7]} ts={row[8]}")

# What does session adjudicator look for?
# Look at agent_events for recent activity
print()
print("=== RECENT AGENT_EVENTS (any agent activity) ===")
events = c.execute(
    "SELECT event_type, source, target, created_at FROM agent_events "
    "ORDER BY created_at DESC LIMIT 5"
).fetchall()
if not events:
    print("  (no agent events)")
else:
    for row in events:
        print(f"  {row[3]:>12} {row[1]:>30} -> {row[2]:>20} : {row[0]}")

c.close()
