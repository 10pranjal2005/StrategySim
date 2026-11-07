
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.auth.security import hash_password


TEST_PASSWORD = "StrategySimTest@2026"

TEST_USERS = [
    {
        "name": "StrategySim Test Analyst",
        "email": "rbac.analyst@example.com",
        "role": "Analyst"
    },
    {
        "name": "StrategySim Test Viewer",
        "email": "rbac.viewer@example.com",
        "role": "Viewer"
    }
]


def prepare_test_users(app):
    """
    Create or reset the temporary test accounts.
    """

    with app.app_context():

        from app.database.connection import get_db

        database = get_db()

        for user in TEST_USERS:

            database.execute(
                """
                INSERT INTO users (
                    full_name,
                    email,
                    password_hash,
                    role,
                    is_active
                )
                VALUES (?, ?, ?, ?, 1)

                ON CONFLICT(email) DO UPDATE SET
                    full_name = excluded.full_name,
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    is_active = 1
                """,
                (
                    user["name"],
                    user["email"],
                    hash_password(TEST_PASSWORD),
                    user["role"]
                )
            )

        database.commit()


def remove_test_users(app):
    """
    Remove only the temporary RBAC test accounts.
    """

    with app.app_context():

        from app.database.connection import get_db

        database = get_db()

        database.execute(
            """
            DELETE FROM users
            WHERE email IN (?, ?)
            """,
            (
                "rbac.analyst@example.com",
                "rbac.viewer@example.com"
            )
        )

        database.commit()


def login_as(client, email):
    """
    Authenticate a temporary test account.
    """

    response = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": TEST_PASSWORD
        },
        follow_redirects=False
    )

    return response.status_code == 302


def test_rbac():

    app = create_app("testing")

    all_passed = True

    print("\n" + "=" * 65)
    print("STRATEGYSIM RBAC VERIFICATION")
    print("=" * 65)

    try:

        # -------------------------------------------------
        # PREPARE ACCOUNTS
        # -------------------------------------------------

        prepare_test_users(app)

        print("\nTemporary test accounts prepared.")

        # IMPORTANT:
        # Do not keep an outer app.app_context() open here.
        # Each test-client request must receive its own
        # request/application context.

        # -------------------------------------------------
        # TEST ANALYST
        # -------------------------------------------------

        for user in TEST_USERS:

            print("\n" + "-" * 65)
            print("TESTING ROLE:", user["role"])
            print("-" * 65)

            client = app.test_client()

            login_successful = login_as(
                client,
                user["email"]
            )

            print(
                "Login:",
                "PASSED" if login_successful else "FAILED"
            )

            if not login_successful:

                all_passed = False
                continue

            # ---------------------------------------------
            # VERIFY AUTHENTICATED IDENTITY
            # ---------------------------------------------

            profile_response = client.get("/auth/me")

            profile_data = (
                profile_response.get_json()
                if profile_response.is_json
                else {}
            ) or {}

            authenticated_user = profile_data.get("user", {})

            actual_role = authenticated_user.get("role")

            print("Expected role:", user["role"])
            print("Actual role:", actual_role)

            role_correct = actual_role == user["role"]

            print(
                "Identity verification:",
                "PASSED" if role_correct else "FAILED"
            )

            if not role_correct:
                all_passed = False

            # ---------------------------------------------
            # VERIFY DASHBOARD ACCESS
            # ---------------------------------------------

            dashboard_response = client.get(
                "/dashboard/status"
            )

            dashboard_passed = (
                dashboard_response.status_code == 200
            )

            print(
                "Dashboard:",
                "PASSED" if dashboard_passed else "FAILED",
                "| HTTP",
                dashboard_response.status_code
            )

            if not dashboard_passed:
                all_passed = False

            # ---------------------------------------------
            # VERIFY ANALYTICAL ACCESS
            # ---------------------------------------------

            expected_analysis_status = (
                200 if user["role"] == "Analyst" else 403
            )

            analysis_response = client.get(
                "/dashboard/analysis-status"
            )

            analysis_passed = (
                analysis_response.status_code
                == expected_analysis_status
            )

            print(
                "Analytical access:",
                "PASSED" if analysis_passed else "FAILED",
                "| Expected:",
                expected_analysis_status,
                "| Received:",
                analysis_response.status_code
            )

            if not analysis_passed:
                all_passed = False

            # ---------------------------------------------
            # VERIFY ADMINISTRATOR ACCESS
            # ---------------------------------------------

            admin_response = client.get(
                "/dashboard/admin-status"
            )

            admin_passed = (
                admin_response.status_code == 403
            )

            print(
                "Administrator access:",
                "PASSED" if admin_passed else "FAILED",
                "| HTTP",
                admin_response.status_code
            )

            if not admin_passed:
                all_passed = False

            # ---------------------------------------------
            # LOG OUT TEST USER
            # ---------------------------------------------

            logout_response = client.post(
                "/auth/logout"
            )

            logout_passed = (
                logout_response.status_code == 302
            )

            print(
                "Logout:",
                "PASSED" if logout_passed else "FAILED"
            )

            if not logout_passed:
                all_passed = False

    finally:

        remove_test_users(app)

        print("\nTemporary test accounts removed.")
        print("Existing Administrator account preserved.")

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    print("\n" + "=" * 65)

    if all_passed:
        print("ALL ANALYST AND VIEWER RBAC TESTS PASSED")
    else:
        print("RBAC VERIFICATION FAILED")

    print("=" * 65)


if __name__ == "__main__":
    test_rbac()
