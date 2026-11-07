
"""Integration tests for Five Forces POST routes.

All writes are performed against a temporary database copy.
The original StrategySim database is not modified.
"""

import shutil
import tempfile
from pathlib import Path

from app import create_app, login_manager
from app.database.connection import get_db


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "instance" / "strategysim.db"

ADMIN_ID = 1
COMPANY_ID = 1


def check(label, condition, details=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")

    if not condition and details:
        print(f"       {details}")

    return bool(condition)


def post_check(client, label, path, data=None):
    response = client.post(
        path,
        data=data or {},
        follow_redirects=False
    )

    passed = response.status_code == 302

    details = ""
    if not passed:
        details = (
            f"Expected redirect (302), received "
            f"{response.status_code}. "
            f"Response: {response.get_data(as_text=True)[:700]}"
        )

    return check(label, passed, details)


def database_value(app, query, parameters=()):
    with app.app_context():
        db = get_db()
        row = db.execute(query, parameters).fetchone()
        return row[0] if row else None


def main():

    if not SOURCE_DATABASE.exists():
        print("ERROR: Original database was not found.")
        return

    results = []

    with tempfile.TemporaryDirectory(
        prefix="strategysim_five_forces_post_"
    ) as temporary_directory:

        temporary_database = (
            Path(temporary_directory) / "strategysim_test.db"
        )

        shutil.copy2(SOURCE_DATABASE, temporary_database)

        print("\nTemporary database created.")
        print("Original database will not be modified.\n")

        app = create_app()

        # Test-only configuration.
        app.config["DATABASE_PATH"] = str(temporary_database)
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False

        # Manually-created test sessions do not have a browser fingerprint.
        # This setting applies only to this test process.
        login_manager.session_protection = None

        with app.app_context():
            db = get_db()

            admin = db.execute(
                """
                SELECT id, is_active
                FROM users
                WHERE id = ?
                """,
                (ADMIN_ID,)
            ).fetchone()

            company = db.execute(
                """
                SELECT id, name
                FROM companies
                WHERE id = ?
                """,
                (COMPANY_ID,)
            ).fetchone()

            if admin is None or not admin["is_active"]:
                print("ERROR: Active Administrator ID 1 not found.")
                return

            if company is None:
                print("ERROR: Test company ID 1 not found.")
                return

            initial_audit_count = db.execute(
                "SELECT COUNT(*) FROM audit_logs"
            ).fetchone()[0]

        print("Test company:", company["name"])
        print("\n--- ADMINISTRATOR SESSION ---")

        client = app.test_client()

        with client.session_transaction() as session:
            session["_user_id"] = str(ADMIN_ID)
            session["_fresh"] = True

        # -------------------------------------------------
        # 1. CREATE ASSESSMENT
        # -------------------------------------------------

        print("\n--- CREATE ASSESSMENT ---")

        results.append(post_check(
            client,
            "Create assessment",
            "/five-forces/new",
            {
                "company_id": str(COMPANY_ID),
                "assessment_name": "POST Route Integration Test",
                "assessment_date": "2026-11-07",
                "summary": "Temporary POST route integration test."
            }
        ))

        assessment_id = database_value(
            app,
            """
            SELECT id
            FROM five_forces_assessments
            WHERE assessment_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ("POST Route Integration Test",)
        )

        results.append(check(
            "Assessment record created in database",
            assessment_id is not None
        ))

        if assessment_id is None:
            print("\nAssessment creation failed. Remaining tests skipped.")
            return

        # -------------------------------------------------
        # 2. EDIT ASSESSMENT
        # -------------------------------------------------

        print("\n--- EDIT ASSESSMENT ---")

        results.append(post_check(
            client,
            "Edit assessment",
            f"/five-forces/{assessment_id}/edit",
            {
                "company_id": str(COMPANY_ID),
                "assessment_name": "POST Route Integration Test Updated",
                "assessment_date": "2026-11-07",
                "summary": "Updated temporary integration test."
            }
        ))

        updated_name = database_value(
            app,
            """
            SELECT assessment_name
            FROM five_forces_assessments
            WHERE id = ?
            """,
            (assessment_id,)
        )

        results.append(check(
            "Assessment update persisted",
            updated_name == "POST Route Integration Test Updated"
        ))

        # -------------------------------------------------
        # 3. CREATE INDICATOR
        # -------------------------------------------------

        print("\n--- CREATE INDICATOR ---")

        results.append(post_check(
            client,
            "Create Buyer Power indicator",
            f"/five-forces/{assessment_id}/indicators/new",
            {
                "force_name": "Buyer Power",
                "indicator_name": "Customer Concentration",
                "score": "4",
                "weight": "1.5",
                "explanation": "Temporary test indicator.",
                "evidence_id": ""
            }
        ))

        indicator_id = database_value(
            app,
            """
            SELECT id
            FROM five_forces_indicators
            WHERE assessment_id = ?
              AND indicator_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (assessment_id, "Customer Concentration")
        )

        results.append(check(
            "Indicator record created in database",
            indicator_id is not None
        ))

        if indicator_id is None:
            print("\nIndicator creation failed. Remaining tests skipped.")
            return

        # -------------------------------------------------
        # 4. EDIT INDICATOR
        # -------------------------------------------------

        print("\n--- EDIT INDICATOR ---")

        results.append(post_check(
            client,
            "Edit indicator",
            f"/five-forces/indicators/{indicator_id}/edit",
            {
                "force_name": "Buyer Power",
                "indicator_name": "Customer Concentration Updated",
                "score": "5",
                "weight": "2.0",
                "explanation": "Updated temporary test indicator.",
                "evidence_id": ""
            }
        ))

        updated_indicator = database_value(
            app,
            """
            SELECT indicator_name
            FROM five_forces_indicators
            WHERE id = ?
            """,
            (indicator_id,)
        )

        results.append(check(
            "Indicator update persisted",
            updated_indicator == "Customer Concentration Updated"
        ))

        # -------------------------------------------------
        # 5. DELETE INDICATOR
        # -------------------------------------------------

        print("\n--- DELETE INDICATOR ---")

        results.append(post_check(
            client,
            "Delete indicator",
            f"/five-forces/indicators/{indicator_id}/delete"
        ))

        indicator_exists = database_value(
            app,
            """
            SELECT COUNT(*)
            FROM five_forces_indicators
            WHERE id = ?
            """,
            (indicator_id,)
        )

        results.append(check(
            "Indicator removed from database",
            indicator_exists == 0
        ))

        # -------------------------------------------------
        # 6. DELETE ASSESSMENT
        # -------------------------------------------------

        print("\n--- DELETE ASSESSMENT ---")

        results.append(post_check(
            client,
            "Delete assessment",
            f"/five-forces/{assessment_id}/delete"
        ))

        assessment_exists = database_value(
            app,
            """
            SELECT COUNT(*)
            FROM five_forces_assessments
            WHERE id = ?
            """,
            (assessment_id,)
        )

        results.append(check(
            "Assessment removed from database",
            assessment_exists == 0
        ))

        # -------------------------------------------------
        # 7. AUDIT LOG VERIFICATION
        # -------------------------------------------------

        print("\n--- AUDIT VERIFICATION ---")

        final_audit_count = database_value(
            app,
            "SELECT COUNT(*) FROM audit_logs"
        )

        results.append(check(
            "Audit log entries recorded",
            final_audit_count > initial_audit_count,
            (
                f"Before: {initial_audit_count}, "
                f"After: {final_audit_count}"
            )
        ))

        # -------------------------------------------------
        # 8. DATABASE INTEGRITY
        # -------------------------------------------------

        print("\n--- DATABASE INTEGRITY ---")

        integrity = database_value(
            app,
            "PRAGMA integrity_check"
        )

        results.append(check(
            "SQLite integrity check",
            integrity == "ok",
            str(integrity)
        ))

        with app.app_context():
            db = get_db()
            foreign_key_errors = db.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

        results.append(check(
            "Foreign key check",
            len(foreign_key_errors) == 0,
            str(foreign_key_errors[:5])
        ))

        # -------------------------------------------------
        # FINAL RESULTS
        # -------------------------------------------------

        passed = sum(results)
        failed = len(results) - passed

        print("\n" + "=" * 55)
        print("FIVE FORCES POST ROUTE TEST RESULTS")
        print("=" * 55)
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Total:  {len(results)}")
        print("=" * 55)

        if failed == 0:
            print("All Five Forces POST route tests passed.")
        else:
            print("Some Five Forces POST route tests failed.")

        print("\nTemporary database will now be discarded.")


if __name__ == "__main__":
    main()
