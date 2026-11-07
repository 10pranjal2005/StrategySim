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
# INSPECT USERS TABLE
# ---------------------------------------------------------

def inspect_users_table():

    connection = sqlite3.connect(DATABASE_PATH)

    try:

        print("\n" + "=" * 55)
        print("STRATEGYSIM USERS TABLE INSPECTION")
        print("=" * 55)

        # Display the original CREATE TABLE statement.

        result = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = ?
              AND name = ?
            """,
            ("table", "users")
        ).fetchone()

        if result is None:

            print("ERROR: Users table not found.")
            return

        print("\nUSERS TABLE SCHEMA")
        print("-" * 55)

        print(result[0])

        # Display individual column information.

        columns = connection.execute(
            "PRAGMA table_info(users)"
        ).fetchall()

        print("\nCOLUMN DETAILS")
        print("-" * 55)

        for column in columns:

            print(
                f"Name: {column[1]} | "
                f"Type: {column[2]} | "
                f"Not Null: {column[3]} | "
                f"Default: {column[4]} | "
                f"Primary Key: {column[5]}"
            )

        # Display existing user count.

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        print("\nExisting user count:", user_count)

        # Display existing roles without exposing user details.

        roles = connection.execute(
            """
            SELECT role, COUNT(*)
            FROM users
            GROUP BY role
            """
        ).fetchall()

        print("\nEXISTING ROLE COUNTS")

        for role, count in roles:

            print(f"{role}: {count}")

    finally:

        connection.close()

    print("\n" + "=" * 55)


if __name__ == "__main__":

    inspect_users_table()