
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
# VERIFY INITIAL ADMINISTRATOR
# ---------------------------------------------------------

def verify_initial_administrator():

    connection = sqlite3.connect(DATABASE_PATH)

    try:

        print("\n" + "=" * 55)
        print("INITIAL ADMINISTRATOR VERIFICATION")
        print("=" * 55)

        # Count administrator accounts.

        administrator_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE role = ?
            """,
            ("Administrator",)
        ).fetchone()[0]

        print(
            "\nAdministrator accounts:",
            administrator_count
        )

        # Retrieve the account without exposing
        # its password hash.

        administrator = connection.execute(
            """
            SELECT
                id,
                role,
                is_active,
                created_at
            FROM users
            WHERE role = ?
            ORDER BY id
            """,
            ("Administrator",)
        ).fetchone()

        if administrator is None:

            print("\nERROR: No administrator found.")

            return

        print("\nACCOUNT DETAILS")
        print("-" * 55)

        print("Administrator ID:", administrator[0])

        print("Role:", administrator[1])

        print("Active:", bool(administrator[2]))

        print("Created at:", administrator[3])

        # Verify password hash storage without displaying it.

        password_hash = connection.execute(
            """
            SELECT password_hash
            FROM users
            WHERE id = ?
            """,
            (administrator[0],)
        ).fetchone()[0]

        hash_is_stored = (
            isinstance(password_hash, str)
            and password_hash.startswith("scrypt:")
        )

        print(
            "\nSecure password hash stored:",
            hash_is_stored
        )

        # Final checks.

        if (
            administrator_count == 1
            and administrator[1] == "Administrator"
            and administrator[2] == 1
            and hash_is_stored
        ):

            print("\nFINAL RESULT: ALL CHECKS PASSED")

        else:

            print("\nFINAL RESULT: VERIFICATION FAILED")

    finally:

        connection.close()

    print("\n" + "=" * 55)


if __name__ == "__main__":

    verify_initial_administrator()
