import os
import shutil
import sqlite3
import tempfile
import traceback

from app import create_app
from app.value_chain.services import (
    ValueChainError,
    ValueChainValidationError,
    create_value_chain_assessment,
    get_value_chain_assessment,
    get_value_chain_assessments,
    update_value_chain_assessment,
    delete_value_chain_assessment,
    create_value_chain_activity,
    get_value_chain_activity,
    get_value_chain_activities,
    update_value_chain_activity,
    delete_value_chain_activity,
)
from app.evidence.services import create_evidence


SOURCE_DB = os.path.join("instance", "strategysim.db")
ADMIN_ID = 1
COMPANY_ID = 1

passed = 0
failed = 0


def check(description, condition):
    global passed, failed

    if condition:
        passed += 1
        print(f"[PASS] {description}")
    else:
        failed += 1
        print(f"[FAIL] {description}")


def expect_error(description, function):
    global passed, failed

    try:
        function()
    except ValueChainError:
        passed += 1
        print(f"[PASS] {description}")
    except Exception as exc:
        failed += 1
        print(f"[FAIL] {description}: Unexpected {type(exc).__name__}: {exc}")
    else:
        failed += 1
        print(f"[FAIL] {description}: Expected an error but none occurred")


def db_query(database_path, query, parameters=()):
    connection = sqlite3.connect(database_path)

    try:
        return connection.execute(query, parameters).fetchall()
    finally:
        connection.close()


def main():
    global passed, failed

    if not os.path.exists(SOURCE_DB):
        print(f"[ERROR] Database not found: {SOURCE_DB}")
        return

    temp_directory = tempfile.mkdtemp(prefix="value_chain_test_")
    temp_db = os.path.join(temp_directory, "strategysim_test.db")

    shutil.copy2(SOURCE_DB, temp_db)

    print("=" * 65)
    print("VALUE CHAIN SERVICE INTEGRATION TEST")
    print("=" * 65)
    print("Using temporary database copy.")
    print("Original database will not be modified.")
    print()

    app = create_app()
    app.config["DATABASE_PATH"] = temp_db
    app.config["TESTING"] = True

    try:
        with app.app_context():

            # -------------------------------------------------
            # 1. Initial database checks
            # -------------------------------------------------

            check(
                "Temporary database contains the Value Chain assessment table",
                len(db_query(
                    temp_db,
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='value_chain_assessments'"
                )) == 1
            )

            check(
                "Temporary database contains the Value Chain activity table",
                len(db_query(
                    temp_db,
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='value_chain_activities'"
                )) == 1
            )

            # -------------------------------------------------
            # 2. Create assessment
            # -------------------------------------------------

            assessment_id = create_value_chain_assessment(
                company_id=COMPANY_ID,
                assessment_name="Value Chain Integration Test",
                acting_user_id=ADMIN_ID,
                assessment_date="2026-11-07",
                summary="Temporary integration test assessment."
            )

            check(
                "Create Value Chain assessment",
                isinstance(assessment_id, int) and assessment_id > 0
            )

            assessment = get_value_chain_assessment(assessment_id)

            check(
                "Retrieve Value Chain assessment",
                assessment is not None
                and assessment["id"] == assessment_id
            )

            check(
                "Assessment contains company information",
                assessment.get("company_name") is not None
            )

            check(
                "New assessment initially has no activities",
                len(assessment.get("activities", [])) == 0
            )

            # -------------------------------------------------
            # 3. Assessment listing and search
            # -------------------------------------------------

            assessments = get_value_chain_assessments(
                company_id=COMPANY_ID
            )

            check(
                "List assessments by company",
                any(item["id"] == assessment_id for item in assessments)
            )

            search_results = get_value_chain_assessments(
                company_id=COMPANY_ID,
                search="Integration Test"
            )

            check(
                "Search assessments by name",
                any(item["id"] == assessment_id for item in search_results)
            )

            # -------------------------------------------------
            # 4. Create Primary and Support activities
            # -------------------------------------------------

            primary_id = create_value_chain_activity(
                assessment_id=assessment_id,
                activity_category="Primary",
                activity_name="Battery Manufacturing",
                acting_user_id=ADMIN_ID,
                description="Illustrative primary activity.",
                cost_contribution=35.5,
                strategic_importance=5,
                competitive_advantage="Efficient battery production."
            )

            check(
                "Create Primary activity",
                isinstance(primary_id, int) and primary_id > 0
            )

            support_id = create_value_chain_activity(
                assessment_id=assessment_id,
                activity_category="Support",
                activity_name="Human Resource Management",
                acting_user_id=ADMIN_ID,
                description="Illustrative support activity.",
                cost_contribution=10.0,
                strategic_importance=4,
                competitive_advantage="Skilled workforce."
            )

            check(
                "Create Support activity",
                isinstance(support_id, int) and support_id > 0
            )

            # -------------------------------------------------
            # 5. Retrieve activities
            # -------------------------------------------------

            primary = get_value_chain_activity(primary_id)
            support = get_value_chain_activity(support_id)

            check(
                "Retrieve Primary activity",
                primary is not None
                and primary["activity_name"] == "Battery Manufacturing"
            )

            check(
                "Retrieve Support activity",
                support is not None
                and support["activity_category"] == "Support"
            )

            all_activities = get_value_chain_activities(assessment_id)

            check(
                "Retrieve all activities",
                len(all_activities) == 2
            )

            primary_activities = get_value_chain_activities(
                assessment_id,
                activity_category="Primary"
            )

            support_activities = get_value_chain_activities(
                assessment_id,
                activity_category="Support"
            )

            check(
                "Filter Primary activities",
                len(primary_activities) == 1
                and primary_activities[0]["id"] == primary_id
            )

            check(
                "Filter Support activities",
                len(support_activities) == 1
                and support_activities[0]["id"] == support_id
            )

            # -------------------------------------------------
            # 6. Update activity
            # -------------------------------------------------

            update_value_chain_activity(
                primary_id,
                ADMIN_ID,
                {
                    "activity_name": "Advanced Battery Manufacturing",
                    "description": "Updated illustrative description.",
                    "cost_contribution": 40.0,
                    "strategic_importance": 5,
                    "competitive_advantage": "Improved production efficiency."
                }
            )

            updated_activity = get_value_chain_activity(primary_id)

            check(
                "Update activity details",
                updated_activity["activity_name"]
                == "Advanced Battery Manufacturing"
            )

            check(
                "Updated activity cost contribution",
                float(updated_activity["cost_contribution"]) == 40.0
            )

            # -------------------------------------------------
            # 7. Update assessment
            # -------------------------------------------------

            update_value_chain_assessment(
                assessment_id,
                ADMIN_ID,
                {
                    "assessment_name": "Updated Value Chain Assessment",
                    "summary": "Updated integration test summary."
                }
            )

            updated_assessment = get_value_chain_assessment(assessment_id)

            check(
                "Update assessment name",
                updated_assessment["assessment_name"]
                == "Updated Value Chain Assessment"
            )

            check(
                "Update assessment summary",
                updated_assessment["summary"]
                == "Updated integration test summary."
            )

            # -------------------------------------------------
            # 8. Validation tests
            # -------------------------------------------------

            expect_error(
                "Reject invalid activity category",
                lambda: create_value_chain_activity(
                    assessment_id,
                    "Invalid Category",
                    "Invalid Activity",
                    ADMIN_ID
                )
            )

            expect_error(
                "Reject strategic importance outside 1-5",
                lambda: create_value_chain_activity(
                    assessment_id,
                    "Primary",
                    "Invalid Importance",
                    ADMIN_ID,
                    strategic_importance=6
                )
            )

            expect_error(
                "Reject negative cost contribution",
                lambda: create_value_chain_activity(
                    assessment_id,
                    "Primary",
                    "Invalid Cost",
                    ADMIN_ID,
                    cost_contribution=-10
                )
            )

            expect_error(
                "Reject nonexistent evidence ID",
                lambda: create_value_chain_activity(
                    assessment_id,
                    "Primary",
                    "Invalid Evidence",
                    ADMIN_ID,
                    evidence_id=999999999
                )
            )

            # -------------------------------------------------
            # 9. Evidence association
            # -------------------------------------------------

            evidence_record = create_evidence(
                title="Value Chain Test Evidence",
                acting_user_id=ADMIN_ID,
                description="Temporary evidence for integration testing.",
                source_type="Manual",
                source_name="Integration Test"
            )

            # The existing evidence service returns a dictionary.
            # Extract its database ID for the Value Chain service.
            if isinstance(evidence_record, dict):
                evidence_id = evidence_record.get("id")
            else:
                evidence_id = evidence_record

            check(
                "Create evidence record",
                isinstance(evidence_id, int) and evidence_id > 0
            )

            evidence_activity_id = create_value_chain_activity(
                assessment_id=assessment_id,
                activity_category="Primary",
                activity_name="Evidence Linked Activity",
                acting_user_id=ADMIN_ID,
                description="Activity associated with test evidence.",
                evidence_id=evidence_id
            )

            evidence_activity = get_value_chain_activity(
                evidence_activity_id
            )

            check(
                "Create activity with evidence association",
                evidence_activity.get("evidence_id") == evidence_id
            )

            check(
                "Retrieve associated evidence title",
                evidence_activity.get("evidence_title")
                == "Value Chain Test Evidence"
            )

            association_rows = db_query(
                temp_db,
                """
                SELECT evidence_id, analysis_type, analysis_record_id
                FROM strategic_analysis_evidence
                WHERE analysis_type = 'VALUE_CHAIN'
                  AND analysis_record_id = ?
                """,
                (evidence_activity_id,)
            )

            check(
                "Evidence association stored correctly",
                len(association_rows) == 1
                and association_rows[0][0] == evidence_id
            )

            # -------------------------------------------------
            # 10. Delete activity and verify evidence preservation
            # -------------------------------------------------

            delete_value_chain_activity(
                evidence_activity_id,
                ADMIN_ID
            )

            deleted_activity = db_query(
                temp_db,
                "SELECT id FROM value_chain_activities WHERE id = ?",
                (evidence_activity_id,)
            )

            remaining_associations = db_query(
                temp_db,
                """
                SELECT id FROM strategic_analysis_evidence
                WHERE analysis_type = 'VALUE_CHAIN'
                  AND analysis_record_id = ?
                """,
                (evidence_activity_id,)
            )

            preserved_evidence = db_query(
                temp_db,
                "SELECT id FROM evidence WHERE id = ?",
                (evidence_id,)
            )

            check(
                "Delete activity",
                len(deleted_activity) == 0
            )

            check(
                "Remove evidence association after activity deletion",
                len(remaining_associations) == 0
            )

            check(
                "Preserve evidence record after activity deletion",
                len(preserved_evidence) == 1
            )

            # -------------------------------------------------
            # 11. Delete remaining assessment
            # -------------------------------------------------

            delete_value_chain_assessment(
                assessment_id,
                ADMIN_ID
            )

            deleted_assessment = db_query(
                temp_db,
                "SELECT id FROM value_chain_assessments WHERE id = ?",
                (assessment_id,)
            )

            remaining_activities = db_query(
                temp_db,
                "SELECT id FROM value_chain_activities WHERE assessment_id = ?",
                (assessment_id,)
            )

            check(
                "Delete Value Chain assessment",
                len(deleted_assessment) == 0
            )

            check(
                "Cascade-delete remaining activities",
                len(remaining_activities) == 0
            )

            # -------------------------------------------------
            # 12. Audit log checks
            # -------------------------------------------------

            audit_rows = db_query(
                temp_db,
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE entity_type LIKE '%VALUE_CHAIN%'
                   OR entity_type LIKE '%Value Chain%'
                   OR description LIKE '%Value Chain%'
                """
            )

            check(
                "Value Chain operations recorded in audit logs",
                audit_rows[0][0] > 0
            )

            # -------------------------------------------------
            # 13. Database integrity
            # -------------------------------------------------

            integrity = db_query(
                temp_db,
                "PRAGMA integrity_check"
            )

            check(
                "Database integrity check",
                integrity == [("ok",)]
            )

            foreign_keys = db_query(
                temp_db,
                "PRAGMA foreign_key_check"
            )

            check(
                "Foreign key check",
                len(foreign_keys) == 0
            )

            print()
            print("=" * 65)
            print("VALUE CHAIN SERVICE TEST SUMMARY")
            print("=" * 65)
            print(f"Passed: {passed}")
            print(f"Failed: {failed}")
            print(f"Total:  {passed + failed}")
            print("=" * 65)

    except Exception as exc:
        failed += 1
        print()
        print("[ERROR] Integration test stopped unexpectedly.")
        print(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()

    finally:
        shutil.rmtree(temp_directory, ignore_errors=True)

    if failed == 0:
        print("\nAll Value Chain service integration tests passed.")
    else:
        print(f"\nIntegration testing finished with {failed} failure(s).")


if __name__ == "__main__":
    main()