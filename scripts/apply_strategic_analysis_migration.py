
"""
StrategySim - Strategic Analysis Migration Runner

Migration:
    001_strategic_analysis.sql

Purpose:
    Safely apply the initial Strategic Analysis database migration.

Safety:
    - Uses the existing configured SQLite database.
    - Never deletes or recreates the database.
    - Uses an explicit SQLite transaction.
    - Records applied migrations.
    - Checks database integrity and foreign keys.
    - Verifies existing user, company and audit-log counts.
"""

import sqlite3
import sys
from pathlib import Path

from app import create_app
from app.database.connection import get_database_path


MIGRATION_NAME = "001_strategic_analysis"

EXPECTED_NEW_TABLES = {
    "swot_assessments",
    "swot_factors",
    "pestle_assessments",
    "pestle_factors",
    "strategic_analysis_evidence",
}

REQUIRED_EXISTING_TABLES = {
    "companies",
    "users",
    "audit_logs",
    "evidence",
}

PROTECTED_TABLES = (
    "users",
    "companies",
    "audit_logs",
)


def get_project_root():
    """Return the StrategySim project root directory."""
    return Path(__file__).resolve().parents[1]


def get_migration_path():
    """Return the path to migration 001."""
    return (
        get_project_root()
        / "app"
        / "database"
        / "migrations"
        / "001_strategic_analysis.sql"
    )


def get_table_names(connection):
    """Return all SQLite table names."""
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()

    return {row[0] for row in rows}


def get_record_counts(connection, table_names):
    """Capture record counts for protected existing tables."""
    counts = {}

    for table_name in PROTECTED_TABLES:
        if table_name not in table_names:
            raise RuntimeError(
                f"Required existing table is missing: {table_name}"
            )

        result = connection.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()

        counts[table_name] = result[0]

    return counts


def check_integrity(connection):
    """Run SQLite integrity and foreign-key checks."""
    integrity_result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()

    if not integrity_result or integrity_result[0] != "ok":
        raise RuntimeError(
            f"SQLite integrity check failed: {integrity_result}"
        )

    foreign_key_errors = connection.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if foreign_key_errors:
        raise RuntimeError(
            "Foreign-key check failed:\n"
            + "\n".join(str(row) for row in foreign_key_errors)
        )


def ensure_migration_registry(connection):
    """Create the migration registry if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def migration_already_applied(connection):
    """Check whether this migration has already been recorded."""
    tables = get_table_names(connection)

    if "schema_migrations" not in tables:
        return False

    result = connection.execute(
        """
        SELECT 1
        FROM schema_migrations
        WHERE migration_name = ?
        """,
        (MIGRATION_NAME,),
    ).fetchone()

    return result is not None


def verify_new_tables(connection):
    """Verify that all expected tables were created."""
    actual_tables = get_table_names(connection)

    missing_tables = EXPECTED_NEW_TABLES - actual_tables

    if missing_tables:
        raise RuntimeError(
            "Migration verification failed. Missing tables: "
            + ", ".join(sorted(missing_tables))
        )

    return True


def apply_migration(database_path, migration_path):
    """Apply migration 001 transactionally."""

    if not database_path.exists():
        raise FileNotFoundError(
            f"Configured database does not exist: {database_path}"
        )

    if not migration_path.is_file():
        raise FileNotFoundError(
            f"Migration SQL file does not exist: {migration_path}"
        )

    migration_sql = migration_path.read_text(encoding="utf-8")

    if not migration_sql.strip():
        raise RuntimeError("Migration SQL file is empty.")

    print("\n============================================")
    print(" STRATEGYSIM - STRATEGIC ANALYSIS MIGRATION")
    print("============================================")

    print(f"\nDatabase: {database_path}")
    print(f"Migration: {migration_path.name}")

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
        timeout=10,
    )

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")

        # -------------------------------------------------
        # 1. Check existing database tables
        # -------------------------------------------------

        existing_tables = get_table_names(connection)

        missing_existing = (
            REQUIRED_EXISTING_TABLES - existing_tables
        )

        if missing_existing:
            raise RuntimeError(
                "Required existing database tables are missing: "
                + ", ".join(sorted(missing_existing))
            )

        print("\n[OK] Required existing tables found.")

        # -------------------------------------------------
        # 2. Check whether migration was already applied
        # -------------------------------------------------

        if migration_already_applied(connection):
            print(
                "\n[INFO] This migration is already recorded."
            )

            verify_new_tables(connection)
            check_integrity(connection)

            print("[OK] All five Strategic Analysis tables exist.")
            print("[OK] Database integrity check passed.")
            print("[OK] Foreign-key check passed.")
            print("\nNo changes were made.")

            return

        # -------------------------------------------------
        # 3. Capture protected record counts
        # -------------------------------------------------

        before_counts = get_record_counts(
            connection,
            existing_tables,
        )

        print("\nExisting record counts:")

        for table_name, count in before_counts.items():
            print(f"  {table_name}: {count}")

        # -------------------------------------------------
        # 4. Validate database before migration
        # -------------------------------------------------

        check_integrity(connection)

        print("\n[OK] Pre-migration integrity check passed.")
        print("[OK] Pre-migration foreign-key check passed.")

        # -------------------------------------------------
        # 5. Prepare transactional migration
        # -------------------------------------------------

        # The BEGIN and COMMIT statements are included
        # inside executescript so the complete migration,
        # including the registry entry, runs in one
        # explicit SQLite transaction.

        registry_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO schema_migrations (migration_name)
        VALUES ('001_strategic_analysis');
        """

        complete_script = (
            "BEGIN IMMEDIATE;\n"
            + migration_sql
            + "\n"
            + registry_sql
            + "\nCOMMIT;"
        )

        print("\nApplying migration...")

        connection.executescript(complete_script)

        print("[OK] Migration SQL executed.")

        # -------------------------------------------------
        # 6. Verify newly created tables
        # -------------------------------------------------

        verify_new_tables(connection)

        print("\n[OK] All five new tables verified.")

        # -------------------------------------------------
        # 7. Verify database integrity
        # -------------------------------------------------

        check_integrity(connection)

        print("[OK] Post-migration integrity check passed.")
        print("[OK] Post-migration foreign-key check passed.")

        # -------------------------------------------------
        # 8. Verify protected records remain unchanged
        # -------------------------------------------------

        after_tables = get_table_names(connection)

        after_counts = get_record_counts(
            connection,
            after_tables,
        )

        if before_counts != after_counts:
            raise RuntimeError(
                "Protected record counts changed during migration.\n"
                f"Before: {before_counts}\n"
                f"After: {after_counts}"
            )

        print("\nProtected record counts after migration:")

        for table_name, count in after_counts.items():
            print(f"  {table_name}: {count}")

        print(
            "\n[OK] Existing users, companies and audit logs "
            "remain unchanged."
        )

        # -------------------------------------------------
        # 9. Verify migration registry
        # -------------------------------------------------

        if not migration_already_applied(connection):
            raise RuntimeError(
                "Migration registry verification failed."
            )

        print("[OK] Migration recorded in schema_migrations.")

        print("\n============================================")
        print(" MIGRATION COMPLETED SUCCESSFULLY")
        print("============================================")

    except Exception:
        if connection.in_transaction:
            connection.rollback()

        print("\n[ERROR] Migration failed.")
        print("[INFO] Any uncommitted migration changes were rolled back.")

        raise

    finally:
        connection.close()


def main():
    """Initialize the existing app configuration and run migration."""

    app = create_app()

    with app.app_context():
        database_path = Path(get_database_path()).resolve()

    migration_path = get_migration_path()

    apply_migration(
        database_path=database_path,
        migration_path=migration_path,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nMigration runner stopped: {error}")
        sys.exit(1)
