
import sqlite3
from pathlib import Path


DATABASE_PATH = Path("instance/strategysim.db")


def inspect_database():
    if not DATABASE_PATH.exists():
        print(f"ERROR: Database not found: {DATABASE_PATH}")
        return

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        print("\n========== DATABASE OVERVIEW ==========")
        print(f"Database: {DATABASE_PATH}")
        print(f"Total tables: {len(tables)}")

        for table in tables:
            table_name = table["name"]

            columns = connection.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall()

            print(f"\nTABLE: {table_name}")
            print("-" * 60)

            for column in columns:
                print(
                    f"  {column['name']} "
                    f"({column['type']})"
                )

        print("\n========== DATABASE INTEGRITY ==========")

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_keys = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print(f"Integrity check: {integrity}")
        print(f"Foreign key violations: {len(foreign_keys)}")

    finally:
        connection.close()


if __name__ == "__main__":
    inspect_database()
