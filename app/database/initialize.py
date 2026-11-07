
import sqlite3

from pathlib import Path

from app.database.connection import get_db, get_database_path


# ---------------------------------------------------------
# SCHEMA FILE LOCATION
# ---------------------------------------------------------

SCHEMA_PATH = (
    Path(__file__).resolve().parent / "schema.sql"
)


# ---------------------------------------------------------
# INITIALIZE DATABASE
# ---------------------------------------------------------

def initialize_database(app):
    """
    Initializes the StrategySim SQLite database.

    This function:
        1. Creates the database directory.
        2. Reads the SQL schema.
        3. Creates all required tables and indexes.
        4. Checks database integrity.
        5. Checks foreign key consistency.

    Existing data is preserved because the schema uses
    CREATE TABLE IF NOT EXISTS.
    """

    print("\nInitializing StrategySim database...")

    # -----------------------------------------------------
    # CHECK SCHEMA FILE
    # -----------------------------------------------------

    if not SCHEMA_PATH.exists():

        raise FileNotFoundError(
            f"Database schema not found: {SCHEMA_PATH}"
        )

    schema_sql = SCHEMA_PATH.read_text(
        encoding="utf-8"
    )

    # -----------------------------------------------------
    # ACTIVATE FLASK APPLICATION CONTEXT
    # -----------------------------------------------------

    with app.app_context():

        # Resolve the database location only after the
        # application context has been activated.

        database_path = get_database_path()

        database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # -------------------------------------------------
        # CREATE TABLES AND INDEXES
        # -------------------------------------------------

        database = get_db()

        try:

            database.executescript(schema_sql)

            database.commit()

        except sqlite3.Error as error:

            database.rollback()

            raise RuntimeError(
                f"Database schema initialization failed: {error}"
            ) from error

        # -------------------------------------------------
        # DATABASE INTEGRITY CHECK
        # -------------------------------------------------

        integrity_result = database.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        if integrity_result[0] != "ok":

            raise RuntimeError(
                "SQLite database integrity check failed: "
                f"{integrity_result[0]}"
            )

        # -------------------------------------------------
        # FOREIGN KEY CHECK
        # -------------------------------------------------

        foreign_key_errors = database.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_errors:

            raise RuntimeError(
                "Database foreign key validation failed: "
                f"{len(foreign_key_errors)} issue(s) found."
            )

        # -------------------------------------------------
        # COUNT CREATED TABLES
        # -------------------------------------------------

        tables = database.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        table_count = len(tables)

    # -----------------------------------------------------
    # INITIALIZATION SUCCESS
    # -----------------------------------------------------

    print("-" * 55)

    print(
        "StrategySim database initialized successfully."
    )

    print(
        f"Database location: {database_path}"
    )

    print(
        f"Tables created/verified: {table_count}"
    )

    print(
        "Integrity check: PASSED"
    )

    print(
        "Foreign key check: PASSED"
    )

    print("-" * 55)

    return database_path
