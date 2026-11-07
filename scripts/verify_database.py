import sqlite3

from pathlib import Path


# ---------------------------------------------------------
# DATABASE LOCATION
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_PATH = (
    PROJECT_ROOT / "instance" / "strategysim.db"
)


# ---------------------------------------------------------
# VERIFY DATABASE
# ---------------------------------------------------------

def verify_database():

    print("\n" + "=" * 55)
    print("STRATEGYSIM DATABASE VERIFICATION")
    print("=" * 55)

    # Check whether the database exists.

    print(
        "\nDatabase exists:",
        DATABASE_PATH.exists()
    )

    if not DATABASE_PATH.exists():

        print("ERROR: Database file not found.")
        return

    # Connect to the database.

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:

        # -------------------------------------------------
        # TABLE COUNT
        # -------------------------------------------------

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        print("\nTotal tables:", len(tables))

        # -------------------------------------------------
        # DISPLAY TABLES
        # -------------------------------------------------

        print("\nDATABASE TABLES")
        print("-" * 55)

        for index, table in enumerate(tables, start=1):

            print(f"{index:02d}. {table[0]}")

        # -------------------------------------------------
        # FOREIGN KEY CHECK
        # -------------------------------------------------

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("\nForeign key check:")

        if foreign_key_errors:

            print("FAILED")
            print(foreign_key_errors)

        else:

            print("PASSED")

        # -------------------------------------------------
        # INTEGRITY CHECK
        # -------------------------------------------------

        integrity_result = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        print("\nIntegrity check:", integrity_result.upper())

        # -------------------------------------------------
        # FINAL RESULT
        # -------------------------------------------------

        if (
            len(tables) == 22
            and not foreign_key_errors
            and integrity_result == "ok"
        ):

            print("\nFINAL RESULT: ALL CHECKS PASSED")

        else:

            print("\nFINAL RESULT: VERIFICATION NEEDS ATTENTION")

    finally:

        connection.close()

    print("\n" + "=" * 55)


# ---------------------------------------------------------
# EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":

    verify_database()