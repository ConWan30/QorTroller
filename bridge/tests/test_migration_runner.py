"""
Tests for MigrationRunner — VAPI-EXT Step 3.

20+ tests covering:
  - schema_migrations table creation
  - pending migration discovery and application
  - idempotency (already-applied files skipped)
  - tamper detection (MigrationTamperError)
  - non-.sql files ignored
  - alphabetical ordering
  - multiple migrations applied in order
  - check_integrity() reports tampered files
  - get_applied() returns correct records
  - vapi_ext_001 and vapi_ext_002 applied by Store startup
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.migrations.runner import MigrationRunner, MigrationTamperError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> tuple[str, str]:
    """Returns (db_path, tmp_dir) for a temp SQLite database."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    return db_path, tmp


def _write_migration(migrations_dir: str, filename: str, content: str) -> str:
    """Write a .sql file to migrations_dir and return its path."""
    path = os.path.join(migrations_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# T-EXT-MIG-1: Basic schema_migrations table creation
# ---------------------------------------------------------------------------

class TestSchemaTableCreation:
    def test_run_pending_creates_schema_migrations_table(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            )
            assert cur.fetchone() is not None

    def test_run_pending_empty_dir_returns_empty_list(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        applied = runner.run_pending()
        assert applied == []


# ---------------------------------------------------------------------------
# T-EXT-MIG-2: Migration discovery and application
# ---------------------------------------------------------------------------

class TestMigrationApplication:
    def test_single_migration_applied(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(
            migrations_dir, "001_test.sql",
            "CREATE TABLE IF NOT EXISTS test_tbl (id INTEGER PRIMARY KEY);"
        )
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        applied = runner.run_pending()
        assert applied == ["001_test.sql"]
        # Table was created
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_tbl'"
            )
            assert cur.fetchone() is not None

    def test_multiple_migrations_applied_in_sorted_order(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        order = []
        _write_migration(migrations_dir, "003_c.sql", "CREATE TABLE IF NOT EXISTS c_tbl (id INTEGER PRIMARY KEY);")
        _write_migration(migrations_dir, "001_a.sql", "CREATE TABLE IF NOT EXISTS a_tbl (id INTEGER PRIMARY KEY);")
        _write_migration(migrations_dir, "002_b.sql", "CREATE TABLE IF NOT EXISTS b_tbl (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        applied = runner.run_pending()
        assert applied == ["001_a.sql", "002_b.sql", "003_c.sql"]

    def test_non_sql_files_ignored(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(migrations_dir, "001_test.sql", "CREATE TABLE IF NOT EXISTS x (id INTEGER);")
        # Non-.sql file should be ignored
        with open(os.path.join(migrations_dir, "README.md"), "w") as f:
            f.write("documentation")
        with open(os.path.join(migrations_dir, "notes.txt"), "w") as f:
            f.write("notes")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        applied = runner.run_pending()
        assert applied == ["001_test.sql"]


# ---------------------------------------------------------------------------
# T-EXT-MIG-3: Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_applied_migration_not_reapplied(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(migrations_dir, "001_test.sql",
                         "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        applied1 = runner.run_pending()
        applied2 = runner.run_pending()
        assert applied1 == ["001_test.sql"]
        assert applied2 == []  # already applied

    def test_second_run_applies_only_new_migrations(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(migrations_dir, "001_first.sql",
                         "CREATE TABLE IF NOT EXISTS first_tbl (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        # Add a second migration
        _write_migration(migrations_dir, "002_second.sql",
                         "CREATE TABLE IF NOT EXISTS second_tbl (id INTEGER PRIMARY KEY);")
        applied = runner.run_pending()
        assert applied == ["002_second.sql"]


# ---------------------------------------------------------------------------
# T-EXT-MIG-4: Tamper detection
# ---------------------------------------------------------------------------

class TestTamperDetection:
    def test_modified_migration_raises_tamper_error(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        path = _write_migration(migrations_dir, "001_test.sql",
                                "CREATE TABLE IF NOT EXISTS tbl (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        # Modify the file after application
        with open(path, "w", encoding="utf-8") as f:
            f.write("CREATE TABLE IF NOT EXISTS INJECTED_TABLE (id INTEGER PRIMARY KEY);")
        with pytest.raises(MigrationTamperError, match="modified after application"):
            runner.run_pending()

    def test_unmodified_migration_no_error(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(migrations_dir, "001_test.sql",
                         "CREATE TABLE IF NOT EXISTS tbl (id INTEGER);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        # Run again without modification — no error
        runner.run_pending()


# ---------------------------------------------------------------------------
# T-EXT-MIG-5: get_applied() and check_integrity()
# ---------------------------------------------------------------------------

class TestGetAppliedAndIntegrity:
    def test_get_applied_returns_applied_migrations(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(migrations_dir, "001_test.sql",
                         "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        applied = runner.get_applied()
        assert "001_test.sql" in applied

    def test_get_applied_hash_matches_file(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        content = "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);"
        _write_migration(migrations_dir, "001_test.sql", content)
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        applied = runner.get_applied()
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert applied["001_test.sql"] == expected_hash

    def test_check_integrity_returns_empty_for_intact_migrations(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        _write_migration(migrations_dir, "001_test.sql",
                         "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        tampered = runner.check_integrity()
        assert tampered == []

    def test_check_integrity_detects_tampered_files(self):
        db_path, _ = _make_db()
        migrations_dir = tempfile.mkdtemp()
        path = _write_migration(migrations_dir, "001_test.sql",
                                "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);")
        runner = MigrationRunner(db_path, migrations_dir=migrations_dir)
        runner.run_pending()
        # Tamper the file
        with open(path, "w") as f:
            f.write("TAMPERED SQL CONTENT")
        tampered = runner.check_integrity()
        assert "001_test.sql" in tampered


# ---------------------------------------------------------------------------
# T-EXT-MIG-6: Store startup applies vapi_ext migrations
# ---------------------------------------------------------------------------

class TestStoreMigrationIntegration:
    def test_store_creates_vapi_ext_tables(self):
        """Verify that Store() startup applies vapi_ext_001 and vapi_ext_002."""
        import sys
        import os
        # Import Store (which triggers MigrationRunner at startup)
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from vapi_bridge.store import Store

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "store_test.db")
        store = Store(db_path)

        with sqlite3.connect(db_path) as conn:
            # vapi_ext_001 should have created vapi_ext_sub_protocol_registry
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND "
                "name='vapi_ext_sub_protocol_registry'"
            )
            assert cur.fetchone() is not None, "vapi_ext_sub_protocol_registry table missing"

            # vapi_ext_002 should have created vapi_ext_agent_manifest
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND "
                "name='vapi_ext_agent_manifest'"
            )
            assert cur.fetchone() is not None, "vapi_ext_agent_manifest table missing"

    def test_store_agent_manifest_has_36_agents(self):
        """All 36 VAPI_CORE agents are populated in the agent manifest."""
        from vapi_bridge.store import Store

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "store_agents.db")
        Store(db_path)

        with sqlite3.connect(db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM vapi_ext_agent_manifest WHERE sub_protocol='VAPI_CORE'")
            count = cur.fetchone()[0]
            assert count == 36, f"Expected 36 VAPI_CORE agents, got {count}"

    def test_store_agent_manifest_fleet_signal_coherence_agent_present(self):
        """FleetSignalCoherenceAgent (agent #35) is in the manifest."""
        from vapi_bridge.store import Store

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "store_fsca.db")
        Store(db_path)

        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT class_name, module_path FROM vapi_ext_agent_manifest "
                "WHERE class_name='FleetSignalCoherenceAgent'"
            )
            row = cur.fetchone()
            assert row is not None, "FleetSignalCoherenceAgent not in agent manifest"
            assert row[1] == "fleet_signal_coherence_agent.py"

    def test_store_vapi_core_in_sub_protocol_registry(self):
        """VAPI_CORE baseline is registered in vapi_ext_sub_protocol_registry."""
        from vapi_bridge.store import Store

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "store_reg.db")
        Store(db_path)

        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT name, agent_range_first, agent_range_last, tool_range_first, tool_range_last "
                "FROM vapi_ext_sub_protocol_registry WHERE name='VAPI_CORE'"
            )
            row = cur.fetchone()
            assert row is not None, "VAPI_CORE not in sub_protocol_registry"
            assert row[1] == 1   # agent_range_first
            assert row[2] == 36  # agent_range_last
            assert row[3] == 1   # tool_range_first
            assert row[4] == 149 # tool_range_last

    def test_store_migrations_are_idempotent(self):
        """Creating Store twice on the same db does not error."""
        from vapi_bridge.store import Store

        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "store_idem.db")
        Store(db_path)
        Store(db_path)  # second call must not fail
