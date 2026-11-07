
import shutil
import tempfile
from pathlib import Path

from flask import g

from app import create_app, login_manager
from app.database.connection import get_db
from app.swot.services import (
    create_swot_assessment,
    create_swot_factor,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DATABASE = PROJECT_ROOT / "instance" / "strategysim.db"

ADMIN_ID = 1
ANALYST_ID = 8
VIEWER_ID = 10
COMPANY_ID = 1

PASSED = 0
FAILED = 0


def check(description, condition):
    global PASSED, FAILED

    if condition:
        PASSED += 1
        print(f"[PASS] {description}")
    else:
        FAILED += 1
        print(f"[FAIL] {description}")


def authenticate(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def main():
    global PASSED, FAILED

    if not ORIGINAL_DATABASE.exists():
        raise FileNotFoundError(
            f"Original database not found: {ORIGINAL_DATABASE}"
        )

    with tempfile.TemporaryDirectory(
        prefix="strategysim_swot_test_"
    ) as temporary_directory:

        temporary_database = (
            Path(temporary_directory) / "strategysim_test.db"
        )

        shutil.copy2(
            ORIGINAL_DATABASE,
            temporary_database
        )

        print("[OK] Temporary database copy created.")

        app = create_app()

        app.config.update(
            TESTING=True,
            DATABASE_PATH=str(temporary_database),
        )

        login_manager.session_protection = None

        with app.app_context():

            old_connection = g.pop("db", None)

            if old_connection is not None:
                old_connection.close()

            database = get_db()

            users = database.execute(
                """
                SELECT id, full_name, role, is_active
                FROM users
                WHERE id IN (?, ?, ?)
                ORDER BY id
                """,
                (ADMIN_ID, ANALYST_ID, VIEWER_ID)
            ).fetchall()

            print("\nTest accounts:")

            for user in users:
                print(
                    f"  {user['id']} | "
                    f"{user['full_name']} | "
                    f"{user['role']} | "
                    f"Active: {user['is_active']}"
                )

            check(
                "All three test accounts exist and are active.",
                len(users) == 3
                and all(user["is_active"] for user in users)
            )

            company = database.execute(
                """
                SELECT id, name
                FROM companies
                WHERE id = ?
                """,
                (COMPANY_ID,)
            ).fetchone()

            check(
                "Test company exists.",
                company is not None
            )

            if company is None:
                raise RuntimeError(
                    "Company ID 1 is not available in the test database."
                )

            database.commit()

            # Create assessment in the temporary database.
            assessment = create_swot_assessment(
                company_id=COMPANY_ID,
                assessment_name="SWOT Route Integration Test",
                acting_user_id=ANALYST_ID,
                summary="Temporary integration-test assessment."
            )

            if not isinstance(assessment, dict):
                raise RuntimeError(
                    "create_swot_assessment() did not return a dictionary."
                )

            assessment_id = assessment.get("id")

            if not assessment_id:
                raise RuntimeError(
                    "Assessment result does not contain an ID."
                )

            # Create factor using the assessment ID.
            factor = create_swot_factor(
                assessment_id=assessment_id,
                factor_type="Strength",
                factor_name="Test operational capability",
                acting_user_id=ANALYST_ID,
                description="Temporary test factor.",
                importance=4
            )

            if not isinstance(factor, dict):
                raise RuntimeError(
                    "create_swot_factor() did not return a dictionary."
                )

            factor_id = factor.get("id")

            if not factor_id:
                raise RuntimeError(
                    "Factor result does not contain an ID."
                )

            print(f"\nTemporary assessment ID: {assessment_id}")
            print(f"Temporary factor ID: {factor_id}")

            check(
                "Temporary assessment created successfully.",
                bool(assessment_id)
            )

            check(
                "Temporary factor created successfully.",
                bool(factor_id)
            )

        app.testing = True

        view_routes = [
            ("/swot/", "SWOT assessment directory"),
            (
                f"/swot/{assessment_id}",
                "SWOT assessment details"
            ),
        ]

        editable_routes = [
            ("/swot/new", "Create assessment page"),
            (
                f"/swot/{assessment_id}/edit",
                "Edit assessment page"
            ),
            (
                f"/swot/{assessment_id}/factors/new",
                "Create factor page"
            ),
            (
                f"/swot/factors/{factor_id}/edit",
                "Edit factor page"
            ),
        ]

        print("\nADMINISTRATOR ACCESS TESTS")

        admin_client = app.test_client()
        authenticate(admin_client, ADMIN_ID)

        for path, description in view_routes + editable_routes:
            response = admin_client.get(path)

            check(
                f"Administrator can access {description}.",
                response.status_code == 200
            )

        print("\nANALYST ACCESS TESTS")

        analyst_client = app.test_client()
        authenticate(analyst_client, ANALYST_ID)

        for path, description in view_routes + editable_routes:
            response = analyst_client.get(path)

            check(
                f"Analyst can access {description}.",
                response.status_code == 200
            )

        print("\nVIEWER ACCESS TESTS")

        viewer_client = app.test_client()
        authenticate(viewer_client, VIEWER_ID)

        for path, description in view_routes:
            response = viewer_client.get(path)

            check(
                f"Viewer can access {description}.",
                response.status_code == 200
            )

        for path, description in editable_routes:
            response = viewer_client.get(path)

            check(
                f"Viewer cannot access {description}.",
                response.status_code == 403
            )

        print("\nUNAUTHENTICATED ACCESS TESTS")

        anonymous_client = app.test_client()

        for path, description in view_routes + editable_routes:
            response = anonymous_client.get(
                path,
                follow_redirects=False
            )

            check(
                f"Anonymous user is redirected from {description}.",
                response.status_code == 302
                and "/auth/login" in response.headers.get(
                    "Location", ""
                )
            )

        print("\nDATABASE INTEGRITY TESTS")

        with app.app_context():

            database = get_db()

            integrity = database.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            foreign_key_errors = database.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            check(
                "Temporary database integrity check passed.",
                integrity == "ok"
            )

            check(
                "Temporary database foreign-key check passed.",
                len(foreign_key_errors) == 0
            )

            temporary_assessment = database.execute(
                """
                SELECT id
                FROM swot_assessments
                WHERE id = ?
                """,
                (assessment_id,)
            ).fetchone()

            temporary_factor = database.execute(
                """
                SELECT id
                FROM swot_factors
                WHERE id = ?
                """,
                (factor_id,)
            ).fetchone()

            check(
                "Temporary assessment remains available.",
                temporary_assessment is not None
            )

            check(
                "Temporary factor remains available.",
                temporary_factor is not None
            )

        print("\n" + "=" * 55)
        print("SWOT ROUTE INTEGRATION TEST RESULTS")
        print("=" * 55)
        print(f"Passed: {PASSED}")
        print(f"Failed: {FAILED}")
        print(f"Total:  {PASSED + FAILED}")

        if FAILED:
            print("\nSOME TESTS FAILED.")
            raise SystemExit(1)

        print("\nALL SWOT ROUTE INTEGRATION TESTS PASSED.")
        print("The original database was not used for test CRUD operations.")


if __name__ == "__main__":
    main()
