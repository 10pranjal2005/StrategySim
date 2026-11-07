import sys
from pathlib import Path
from getpass import getpass

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


def test_authentication():

    app = create_app("testing")
    client = app.test_client()

    print("\n" + "=" * 60)
    print("STRATEGYSIM COMPLETE AUTHENTICATION TEST")
    print("=" * 60)

    with app.app_context():

        from app.database.connection import get_db

        database = get_db()

        administrator = database.execute(
            """
            SELECT id, email, role, is_active
            FROM users
            WHERE role = ?
            LIMIT 1
            """,
            ("Administrator",)
        ).fetchone()

        if administrator is None:
            raise RuntimeError("Administrator account not found.")

        email = administrator["email"]

        print("\nAdministrator email:", email)
        print("Administrator role:", administrator["role"])

        password = getpass(
            "\nEnter administrator password (input hidden): "
        )

        # -------------------------------------------------
        # TEST 1: SUCCESSFUL LOGIN
        # -------------------------------------------------

        login_response = client.post(
            "/auth/login",
            data={
                "email": email,
                "password": password
            },
            follow_redirects=False
        )

        login_successful = login_response.status_code == 302

        print(
            "\nSuccessful login:",
            "PASSED" if login_successful else "FAILED"
        )

        if not login_successful:
            print("Login response status:", login_response.status_code)
            return

        # -------------------------------------------------
        # TEST 2: AUTHENTICATED USER ACCESS
        # -------------------------------------------------

        profile_response = client.get("/auth/me")

        profile_successful = (
            profile_response.status_code == 200
        )

        print(
            "Authenticated profile access:",
            "PASSED" if profile_successful else "FAILED"
        )

        if profile_successful:

            profile = profile_response.get_json() or {}

            print(
                "Profile response fields:",
                sorted(profile.keys())
            )

            print(
                "Returned user role:",
                profile.get("role", "Not present")
            )

        # -------------------------------------------------
        # TEST 3: LAST LOGIN UPDATE
        # -------------------------------------------------

        updated_user = database.execute(
            """
            SELECT last_login_at
            FROM users
            WHERE id = ?
            """,
            (administrator["id"],)
        ).fetchone()

        last_login_updated = (
            updated_user is not None
            and updated_user["last_login_at"] is not None
        )

        print(
            "Last login timestamp updated:",
            "PASSED" if last_login_updated else "FAILED"
        )

        # -------------------------------------------------
        # TEST 4: LOGOUT
        # -------------------------------------------------

        logout_response = client.post(
            "/auth/logout",
            follow_redirects=False
        )

        logout_successful = logout_response.status_code == 302

        print(
            "Logout:",
            "PASSED" if logout_successful else "FAILED"
        )

        # -------------------------------------------------
        # TEST 5: ACCESS AFTER LOGOUT
        # -------------------------------------------------

        after_logout_response = client.get("/auth/me")

        access_blocked = (
            after_logout_response.status_code == 302
        )

        print(
            "Access blocked after logout:",
            "PASSED" if access_blocked else "FAILED"
        )

        # -------------------------------------------------
        # FINAL RESULT
        # -------------------------------------------------

        results = [
            login_successful,
            profile_successful,
            last_login_updated,
            logout_successful,
            access_blocked
        ]

        print("\n" + "=" * 60)

        if all(results):
            print("ALL AUTHENTICATION TESTS PASSED")
        else:
            print("SOME AUTHENTICATION TESTS FAILED")

        print("=" * 60)


if __name__ == "__main__":
    test_authentication()