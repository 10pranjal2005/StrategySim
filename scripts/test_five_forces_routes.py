
"""
StrategySim - Five Forces Route Integration Tests.

All test data is created in a temporary copy of the database.
The original database is never modified.
"""

import shutil
import tempfile
from pathlib import Path

from app import create_app, login_manager
from app.database.connection import get_db

from app.five_forces.services import (
    FORCES,
    create_five_forces_assessment,
    create_five_forces_indicator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "instance" / "strategysim.db"

COMPANY_ID = 1

USERS = {
    "Administrator": 1,
    "Analyst": 8,
    "Viewer": 10,
}

passed = 0
failed = 0


def check(name, condition):
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {name}")
    else:
        failed += 1
        print(f"[FAIL] {name}")


def login_as(client, user_id):
    """Establish a Flask-Login test session without a password."""

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_get(client, path, expected_status, description):
    response = client.get(
        path,
        follow_redirects=False
    )

    check(
        description,
        response.status_code == expected_status
    )

    if response.status_code != expected_status:
        print(
            f"       Expected {expected_status}, "
            f"received {response.status_code}"
        )

    return response


def run_tests():

    global passed, failed

    if not SOURCE_DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {SOURCE_DATABASE}"
        )

    with tempfile.TemporaryDirectory(
        prefix="strategysim_five_forces_routes_"
    ) as temporary_directory:

        temporary_database = (
            Path(temporary_directory) / "test_strategysim.db"
        )

        shutil.copy2(
            SOURCE_DATABASE,
            temporary_database
        )

        print("\nTemporary database created.")
        print("Original database will not be modified.\n")

        app = create_app()

        # Disable strong session protection only for this isolated
        # test process because the test client uses manually-created sessions.
        login_manager.session_protection = None

        # Override the database before opening test requests.
        app.config["DATABASE_PATH"] = str(temporary_database)
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        # -------------------------------------------------
        # VERIFY TEST USERS AND CREATE TEST DATA
        # -------------------------------------------------

        with app.app_context():

            database = get_db()

            for role, user_id in USERS.items():

                user = database.execute(
                    """
                    SELECT id, role, is_active
                    FROM users
                    WHERE id = ?
                    """,
                    (user_id,)
                ).fetchone()

                if (
                    user is None
                    or user["role"] != role
                    or not user["is_active"]
                ):
                    raise RuntimeError(
                        f"Test user {role} (ID {user_id}) "
                        "is missing, inactive, or has an unexpected role."
                    )

            company = database.execute(
                """
                SELECT id, name
                FROM companies
                WHERE id = ?
                """,
                (COMPANY_ID,)
            ).fetchone()

            if company is None:
                raise RuntimeError(
                    "Test company ID 1 was not found."
                )

            assessment = create_five_forces_assessment(
                company_id=COMPANY_ID,
                assessment_name="Five Forces Route Test",
                acting_user_id=USERS["Administrator"],
                assessment_date="2026-11-07",
                summary="Temporary route integration test."
            )

            assessment_id = assessment["id"]

            indicator = create_five_forces_indicator(
                assessment_id=assessment_id,
                force_name=FORCES[0],
                indicator_name="Route Test Buyer Indicator",
                score=3,
                weight=1,
                acting_user_id=USERS["Administrator"],
                explanation="Temporary route test indicator."
            )

            indicator_id = indicator["id"]

            database.commit()

            print(f"Test company: {company['name']}")
            print(f"Test assessment ID: {assessment_id}")
            print(f"Test indicator ID: {indicator_id}\n")

        client = app.test_client()

        assessment_url = f"/five-forces/{assessment_id}"
        assessment_edit_url = (
            f"/five-forces/{assessment_id}/edit"
        )
        indicator_create_url = (
            f"/five-forces/{assessment_id}/indicators/new"
        )
        indicator_edit_url = (
            f"/five-forces/indicators/{indicator_id}/edit"
        )

        # -------------------------------------------------
        # TEST 1: ANONYMOUS ACCESS
        # -------------------------------------------------

        print("\n--- ANONYMOUS ACCESS ---")

        test_get(
            client,
            "/five-forces/",
            302,
            "Anonymous user redirected from index"
        )

        test_get(
            client,
            "/five-forces/new",
            302,
            "Anonymous user redirected from create page"
        )

        test_get(
            client,
            assessment_url,
            302,
            "Anonymous user redirected from detail page"
        )

        # -------------------------------------------------
        # TEST 2: ADMINISTRATOR ACCESS
        # -------------------------------------------------

        print("\n--- ADMINISTRATOR ACCESS ---")

        login_as(
            client,
            USERS["Administrator"]
        )

        test_get(
            client,
            "/five-forces/",
            200,
            "Administrator can view assessment index"
        )

        test_get(
            client,
            "/five-forces/new",
            200,
            "Administrator can open assessment creation form"
        )

        detail_response = test_get(
            client,
            assessment_url,
            200,
            "Administrator can view assessment detail"
        )

        check(
            "Detail page displays test indicator",
            b"Route Test Buyer Indicator"
            in detail_response.data
        )

        test_get(
            client,
            assessment_edit_url,
            200,
            "Administrator can open assessment edit form"
        )

        test_get(
            client,
            indicator_create_url,
            200,
            "Administrator can open indicator creation form"
        )

        test_get(
            client,
            indicator_edit_url,
            200,
            "Administrator can open indicator edit form"
        )

        client.get("/auth/logout")

        # -------------------------------------------------
        # TEST 3: ANALYST ACCESS
        # -------------------------------------------------

        print("\n--- ANALYST ACCESS ---")

        login_as(
            client,
            USERS["Analyst"]
        )

        test_get(
            client,
            "/five-forces/",
            200,
            "Analyst can view assessment index"
        )

        test_get(
            client,
            "/five-forces/new",
            200,
            "Analyst can open assessment creation form"
        )

        test_get(
            client,
            assessment_url,
            200,
            "Analyst can view assessment detail"
        )

        test_get(
            client,
            assessment_edit_url,
            200,
            "Analyst can open assessment edit form"
        )

        test_get(
            client,
            indicator_create_url,
            200,
            "Analyst can open indicator creation form"
        )

        test_get(
            client,
            indicator_edit_url,
            200,
            "Analyst can open indicator edit form"
        )

        client.get("/auth/logout")

        # -------------------------------------------------
        # TEST 4: VIEWER READ-ONLY ACCESS
        # -------------------------------------------------

        print("\n--- VIEWER ACCESS ---")

        login_as(
            client,
            USERS["Viewer"]
        )

        test_get(
            client,
            "/five-forces/",
            200,
            "Viewer can view assessment index"
        )

        viewer_detail = test_get(
            client,
            assessment_url,
            200,
            "Viewer can view assessment detail"
        )

        check(
            "Viewer can see assessment indicator",
            b"Route Test Buyer Indicator"
            in viewer_detail.data
        )

        test_get(
            client,
            "/five-forces/new",
            403,
            "Viewer cannot open assessment creation form"
        )

        test_get(
            client,
            assessment_edit_url,
            403,
            "Viewer cannot open assessment edit form"
        )

        test_get(
            client,
            indicator_create_url,
            403,
            "Viewer cannot open indicator creation form"
        )

        test_get(
            client,
            indicator_edit_url,
            403,
            "Viewer cannot open indicator edit form"
        )

        # -------------------------------------------------
        # FINAL SUMMARY
        # -------------------------------------------------

        print("\n" + "=" * 55)
        print("FIVE FORCES ROUTE TEST RESULTS")
        print("=" * 55)

        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Total:  {passed + failed}")

        print("=" * 55)

        if failed:
            raise SystemExit(1)

        print("\nAll Five Forces route tests passed.")


if __name__ == "__main__":
    run_tests()
