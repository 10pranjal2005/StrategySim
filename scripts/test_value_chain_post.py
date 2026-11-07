import os
import shutil
import sqlite3
import tempfile

from app import create_app, login_manager


def main():
    original_db = os.path.join("instance", "strategysim.db")

    if not os.path.exists(original_db):
        print("[FAIL] Original database not found.")
        return

    temporary_directory = tempfile.TemporaryDirectory()
    temporary_db = os.path.join(
        temporary_directory.name,
        "strategysim_post_test.db"
    )

    shutil.copy2(original_db, temporary_db)

    app = create_app()

    # Isolated test settings only.
    login_manager.session_protection = None

    app.config.update(
        TESTING=True,
        DATABASE_PATH=temporary_db,
        WTF_CSRF_ENABLED=False,
    )

    results = []

    def record_test(description, passed, detail=""):
        results.append(bool(passed))
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {description}")

        if detail:
            print("       ", detail)

    def admin_client():
        client = app.test_client()

        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True

        return client

    def viewer_client():
        client = app.test_client()

        with client.session_transaction() as session:
            session["_user_id"] = "10"
            session["_fresh"] = True

        return client

    def database_query(query, parameters=()):
        connection = sqlite3.connect(temporary_db)
        connection.row_factory = sqlite3.Row

        try:
            return connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

    try:
        admin = admin_client()
        viewer = viewer_client()

        assessment_id = None
        activity_id = None

        # --------------------------------------------------
        # 1. CREATE ASSESSMENT
        # --------------------------------------------------

        print("\n========== CREATE ASSESSMENT ==========")

        response = admin.post(
            "/value-chain/new",
            data={
                "company_id": "1",
                "assessment_name": "POST Integration Test",
                "assessment_date": "2026-11-07",
                "summary": "Temporary POST integration test assessment.",
            },
            follow_redirects=False,
        )

        record_test(
            "Administrator can create assessment",
            response.status_code in (302, 303),
            f"HTTP {response.status_code}"
        )

        row = database_query(
            """
            SELECT id, assessment_name, company_id
            FROM value_chain_assessments
            WHERE assessment_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ("POST Integration Test",)
        )

        record_test(
            "Assessment record saved correctly",
            row is not None
            and row["company_id"] == 1
            and row["assessment_name"] == "POST Integration Test"
        )

        if row is None:
            raise RuntimeError(
                "Assessment creation failed; cannot continue POST tests."
            )

        assessment_id = row["id"]

        # --------------------------------------------------
        # 2. UPDATE ASSESSMENT
        # --------------------------------------------------

        print("\n========== UPDATE ASSESSMENT ==========")

        response = admin.post(
            f"/value-chain/{assessment_id}/edit",
            data={
                "assessment_name": "POST Integration Test Updated",
                "assessment_date": "2026-11-08",
                "summary": "Updated temporary assessment summary.",
            },
            follow_redirects=False,
        )

        record_test(
            "Administrator can update assessment",
            response.status_code in (302, 303),
            f"HTTP {response.status_code}"
        )

        row = database_query(
            """
            SELECT assessment_name, summary, assessment_date
            FROM value_chain_assessments
            WHERE id = ?
            """,
            (assessment_id,)
        )

        record_test(
            "Assessment changes persisted",
            row is not None
            and row["assessment_name"] == "POST Integration Test Updated"
            and row["summary"] == "Updated temporary assessment summary."
        )

        # --------------------------------------------------
        # 3. CREATE ACTIVITY
        # --------------------------------------------------

        print("\n========== CREATE ACTIVITY ==========")

        response = admin.post(
            f"/value-chain/{assessment_id}/activities/new",
            data={
                "activity_category": "Primary",
                "activity_name": "Battery Manufacturing",
                "description": "Manufacturing battery packs.",
                "cost_contribution": "25.50",
                "strategic_importance": "5",
                "competitive_advantage": "Improved battery production capability.",
                "evidence_id": "",
            },
            follow_redirects=False,
        )

        record_test(
            "Administrator can create activity",
            response.status_code in (302, 303),
            f"HTTP {response.status_code}"
        )

        row = database_query(
            """
            SELECT id, activity_category, activity_name,
                   cost_contribution, strategic_importance
            FROM value_chain_activities
            WHERE assessment_id = ?
              AND activity_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (assessment_id, "Battery Manufacturing")
        )

        record_test(
            "Activity record saved correctly",
            row is not None
            and row["activity_category"] == "Primary"
            and row["cost_contribution"] == 25.5
            and row["strategic_importance"] == 5
        )

        if row is None:
            raise RuntimeError(
                "Activity creation failed; cannot continue POST tests."
            )

        activity_id = row["id"]

        # --------------------------------------------------
        # 4. UPDATE ACTIVITY
        # --------------------------------------------------

        print("\n========== UPDATE ACTIVITY ==========")

        response = admin.post(
            f"/value-chain/activities/{activity_id}/edit",
            data={
                "activity_category": "Support",
                "activity_name": "Battery Research and Development",
                "description": "Updated activity description.",
                "cost_contribution": "30.00",
                "strategic_importance": "4",
                "competitive_advantage": "Improved research capability.",
                "evidence_id": "",
            },
            follow_redirects=False,
        )

        record_test(
            "Administrator can update activity",
            response.status_code in (302, 303),
            f"HTTP {response.status_code}"
        )

        row = database_query(
            """
            SELECT activity_category, activity_name,
                   description, cost_contribution,
                   strategic_importance
            FROM value_chain_activities
            WHERE id = ?
            """,
            (activity_id,)
        )

        record_test(
            "Activity changes persisted",
            row is not None
            and row["activity_category"] == "Support"
            and row["activity_name"] == "Battery Research and Development"
            and row["cost_contribution"] == 30.0
            and row["strategic_importance"] == 4
        )

        # --------------------------------------------------
        # 5. VIEWER PERMISSION TESTS
        # --------------------------------------------------

        print("\n========== VIEWER POST RESTRICTIONS ==========")

        viewer_posts = [
            (
                "Viewer cannot create assessment",
                "/value-chain/new",
                {
                    "company_id": "1",
                    "assessment_name": "Viewer Unauthorized Assessment",
                    "assessment_date": "2026-11-07",
                    "summary": "Should not be created.",
                },
            ),
            (
                "Viewer cannot edit assessment",
                f"/value-chain/{assessment_id}/edit",
                {
                    "assessment_name": "Unauthorized Update",
                    "assessment_date": "2026-11-07",
                    "summary": "Should not be saved.",
                },
            ),
            (
                "Viewer cannot create activity",
                f"/value-chain/{assessment_id}/activities/new",
                {
                    "activity_category": "Primary",
                    "activity_name": "Unauthorized Activity",
                    "description": "Should not be created.",
                    "cost_contribution": "10",
                    "strategic_importance": "3",
                    "competitive_advantage": "",
                    "evidence_id": "",
                },
            ),
            (
                "Viewer cannot edit activity",
                f"/value-chain/activities/{activity_id}/edit",
                {
                    "activity_category": "Primary",
                    "activity_name": "Unauthorized Activity Update",
                    "description": "Should not be saved.",
                    "cost_contribution": "10",
                    "strategic_importance": "3",
                    "competitive_advantage": "",
                    "evidence_id": "",
                },
            ),
            (
                "Viewer cannot delete activity",
                f"/value-chain/activities/{activity_id}/delete",
                {},
            ),
            (
                "Viewer cannot delete assessment",
                f"/value-chain/{assessment_id}/delete",
                {},
            ),
        ]

        for description, url, data in viewer_posts:
            response = viewer.post(
                url,
                data=data,
                follow_redirects=False,
            )

            record_test(
                description,
                response.status_code == 403,
                f"HTTP {response.status_code}"
            )

        # Verify unauthorized creation did not occur.
        row = database_query(
            """
            SELECT COUNT(*) AS total
            FROM value_chain_assessments
            WHERE assessment_name = ?
            """,
            ("Viewer Unauthorized Assessment",)
        )

        record_test(
            "Viewer unauthorized assessment was not saved",
            row["total"] == 0
        )

        row = database_query(
            """
            SELECT COUNT(*) AS total
            FROM value_chain_activities
            WHERE activity_name IN (?, ?)
            """,
            (
                "Unauthorized Activity",
                "Unauthorized Activity Update",
            )
        )

        record_test(
            "Viewer unauthorized activities were not saved",
            row["total"] == 0
        )

        # --------------------------------------------------
        # 6. DELETE ACTIVITY
        # --------------------------------------------------

        print("\n========== DELETE ACTIVITY ==========")

        response = admin.post(
            f"/value-chain/activities/{activity_id}/delete",
            data={},
            follow_redirects=False,
        )

        record_test(
            "Administrator can delete activity",
            response.status_code in (302, 303),
            f"HTTP {response.status_code}"
        )

        row = database_query(
            """
            SELECT id
            FROM value_chain_activities
            WHERE id = ?
            """,
            (activity_id,)
        )

        record_test(
            "Deleted activity no longer exists",
            row is None
        )

        # --------------------------------------------------
        # 7. DELETE ASSESSMENT
        # --------------------------------------------------

        print("\n========== DELETE ASSESSMENT ==========")

        response = admin.post(
            f"/value-chain/{assessment_id}/delete",
            data={},
            follow_redirects=False,
        )

        record_test(
            "Administrator can delete assessment",
            response.status_code in (302, 303),
            f"HTTP {response.status_code}"
        )

        row = database_query(
            """
            SELECT id
            FROM value_chain_assessments
            WHERE id = ?
            """,
            (assessment_id,)
        )

        record_test(
            "Deleted assessment no longer exists",
            row is None
        )

        # --------------------------------------------------
        # 8. AUDIT LOGGING
        # --------------------------------------------------

        print("\n========== AUDIT LOGGING ==========")

        row = database_query(
            """
            SELECT COUNT(*) AS total
            FROM audit_logs
            WHERE entity_type IN (
                'VALUE_CHAIN_ASSESSMENT',
                'VALUE_CHAIN_ACTIVITY'
            )
            """
        )

        record_test(
            "Value Chain audit records created",
            row is not None and row["total"] >= 6,
            f"Matching audit records: {row['total'] if row else 0}"
        )

        # --------------------------------------------------
        # 9. DATABASE INTEGRITY
        # --------------------------------------------------

        print("\n========== DATABASE INTEGRITY ==========")

        connection = sqlite3.connect(temporary_db)

        try:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            foreign_keys = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

        finally:
            connection.close()

        record_test(
            "SQLite integrity check",
            integrity == "ok",
            integrity
        )

        record_test(
            "Foreign key check",
            len(foreign_keys) == 0,
            f"Violations: {len(foreign_keys)}"
        )

        # --------------------------------------------------
        # FINAL SUMMARY
        # --------------------------------------------------

        passed = sum(results)
        failed = len(results) - passed

        print("\n========================================")
        print("VALUE CHAIN POST TEST SUMMARY")
        print("========================================")
        print("Total tests:", len(results))
        print("Passed:", passed)
        print("Failed:", failed)

        if failed == 0:
            print("\nALL VALUE CHAIN POST TESTS PASSED.")
        else:
            print("\nSOME POST TESTS FAILED.")
            print("Please share the complete output.")

    finally:
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()