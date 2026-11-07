
"""
StrategySim - Five Forces Service Integration Tests.

All test operations run against a temporary copy of the
existing database. The original database is never modified.
"""

import shutil
import tempfile
from pathlib import Path

from app import create_app
from app.database.connection import get_db

from app.five_forces.services import (
    FORCES,
    FiveForcesValidationError,
    FiveForcesNotFoundError,
    create_five_forces_assessment,
    get_five_forces_assessment,
    get_five_forces_assessments,
    update_five_forces_assessment,
    delete_five_forces_assessment,
    create_five_forces_indicator,
    get_five_forces_indicator,
    get_five_forces_indicators,
    update_five_forces_indicator,
    delete_five_forces_indicator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "instance" / "strategysim.db"

COMPANY_ID = 1
ADMIN_ID = 1


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


def expect_exception(name, exception_type, callback):
    global passed, failed

    try:
        callback()
    except exception_type:
        passed += 1
        print(f"[PASS] {name}")
    except Exception as error:
        failed += 1
        print(
            f"[FAIL] {name} "
            f"(unexpected {type(error).__name__}: {error})"
        )
    else:
        failed += 1
        print(f"[FAIL] {name} (exception was not raised)")


def run_tests():

    global passed, failed

    if not SOURCE_DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {SOURCE_DATABASE}"
        )

    with tempfile.TemporaryDirectory(
        prefix="strategysim_five_forces_"
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

        # Override the database path before opening the
        # application context used by the tests.
        app.config["DATABASE_PATH"] = str(
            temporary_database
        )

        with app.app_context():

            database = get_db()

            company = database.execute(
                """
                SELECT id, name
                FROM companies
                WHERE id = ?
                """,
                (COMPANY_ID,)
            ).fetchone()

            administrator = database.execute(
                """
                SELECT id, role, is_active
                FROM users
                WHERE id = ?
                """,
                (ADMIN_ID,)
            ).fetchone()

            if company is None:
                raise RuntimeError(
                    "Test company ID 1 was not found."
                )

            if (
                administrator is None
                or administrator["role"] != "Administrator"
                or not administrator["is_active"]
            ):
                raise RuntimeError(
                    "Test Administrator ID 1 is not active."
                )

            print(
                f"Test company: {company['name']} "
                f"(ID {COMPANY_ID})"
            )

            print("Test Administrator: ID 1\n")

            # -------------------------------------------------
            # TEST 1: CREATE ASSESSMENT
            # -------------------------------------------------

            assessment = create_five_forces_assessment(
                company_id=COMPANY_ID,
                assessment_name="Five Forces Integration Test",
                acting_user_id=ADMIN_ID,
                assessment_date="2026-11-07",
                summary="Temporary integration test assessment."
            )

            assessment_id = assessment["id"]

            check(
                "Create Five Forces assessment",
                assessment["assessment_name"]
                == "Five Forces Integration Test"
            )

            check(
                "New assessment has no overall score",
                assessment["overall_score"] is None
            )

            check(
                "New assessment has empty indicators",
                len(assessment["indicators"]) == 0
            )

            # -------------------------------------------------
            # TEST 2: READ AND LIST
            # -------------------------------------------------

            fetched = get_five_forces_assessment(
                assessment_id
            )

            check(
                "Retrieve assessment by ID",
                fetched is not None
                and fetched["id"] == assessment_id
            )

            listed = get_five_forces_assessments(
                company_id=COMPANY_ID,
                search="Five Forces Integration Test"
            )

            check(
                "List and search assessments",
                any(
                    row["id"] == assessment_id
                    for row in listed
                )
            )

            # -------------------------------------------------
            # TEST 3: CREATE ALL FIVE FORCES
            # -------------------------------------------------

            indicator_ids = {}

            scores = {
                "Buyer Power": 2,
                "Supplier Power": 3,
                "Competitive Rivalry": 4,
                "Threat of Substitution": 5,
                "Threat of New Entrants": 1,
            }

            for force in FORCES:
                indicator = create_five_forces_indicator(
                    assessment_id=assessment_id,
                    force_name=force,
                    indicator_name=f"Test indicator - {force}",
                    score=scores[force],
                    weight=1,
                    acting_user_id=ADMIN_ID,
                    explanation="Temporary test indicator."
                )

                indicator_ids[force] = indicator["id"]

            refreshed = get_five_forces_assessment(
                assessment_id
            )

            check(
                "Create indicators for all five forces",
                len(refreshed["indicators"]) == 5
            )

            check(
                "All five force scores calculated",
                all(
                    refreshed["score_summary"]["force_scores"][force]
                    == scores[force]
                    for force in FORCES
                )
            )

            check(
                "Overall score calculated correctly",
                refreshed["overall_score"] == 3.0
            )

            check(
                "Assessment marked complete",
                refreshed["score_summary"]["is_complete"] is True
            )

            # -------------------------------------------------
            # TEST 4: WEIGHTED CALCULATION
            # -------------------------------------------------

            weighted_indicator = create_five_forces_indicator(
                assessment_id=assessment_id,
                force_name="Buyer Power",
                indicator_name="Weighted calculation test",
                score=4,
                weight=3,
                acting_user_id=ADMIN_ID,
                explanation="Verifies weighted average."
            )

            refreshed = get_five_forces_assessment(
                assessment_id
            )

            # (2*1 + 4*3) / (1+3) = 3.5
            check(
                "Weighted force score calculation",
                refreshed["buyer_power_score"] == 3.5
            )

            # (3.5 + 3 + 4 + 5 + 1) / 5 = 3.3
            check(
                "Overall score recalculated after new indicator",
                refreshed["overall_score"] == 3.3
            )

            # -------------------------------------------------
            # TEST 5: INDICATOR RETRIEVAL
            # -------------------------------------------------

            indicator = get_five_forces_indicator(
                weighted_indicator["id"]
            )

            check(
                "Retrieve indicator by ID",
                indicator is not None
                and indicator["score"] == 4
            )

            buyer_indicators = get_five_forces_indicators(
                assessment_id,
                force_name="Buyer Power"
            )

            check(
                "Filter indicators by force",
                len(buyer_indicators) == 2
            )

            # -------------------------------------------------
            # TEST 6: UPDATE INDICATOR
            # -------------------------------------------------

            updated_indicator = update_five_forces_indicator(
                weighted_indicator["id"],
                ADMIN_ID,
                {
                    "score": 5,
                    "weight": 1,
                    "explanation": "Updated test explanation."
                }
            )

            check(
                "Update indicator fields",
                updated_indicator["score"] == 5
                and updated_indicator["weight"] == 1
            )

            refreshed = get_five_forces_assessment(
                assessment_id
            )

            # (2*1 + 5*1) / 2 = 3.5
            check(
                "Force score recalculated after update",
                refreshed["buyer_power_score"] == 3.5
            )

            # -------------------------------------------------
            # TEST 7: UPDATE ASSESSMENT
            # -------------------------------------------------

            updated_assessment = update_five_forces_assessment(
                assessment_id,
                ADMIN_ID,
                {
                    "assessment_name": "Updated Five Forces Test",
                    "summary": "Updated integration test summary."
                }
            )

            check(
                "Update assessment details",
                updated_assessment["assessment_name"]
                == "Updated Five Forces Test"
            )

            # -------------------------------------------------
            # TEST 8: VALIDATION
            # -------------------------------------------------

            expect_exception(
                "Reject invalid force name",
                FiveForcesValidationError,
                lambda: create_five_forces_indicator(
                    assessment_id,
                    "Invalid Force",
                    "Invalid indicator",
                    3,
                    1,
                    ADMIN_ID
                )
            )

            expect_exception(
                "Reject score outside 1-5",
                FiveForcesValidationError,
                lambda: create_five_forces_indicator(
                    assessment_id,
                    "Buyer Power",
                    "Invalid score indicator",
                    6,
                    1,
                    ADMIN_ID
                )
            )

            expect_exception(
                "Reject zero weight",
                FiveForcesValidationError,
                lambda: create_five_forces_indicator(
                    assessment_id,
                    "Buyer Power",
                    "Invalid weight indicator",
                    3,
                    0,
                    ADMIN_ID
                )
            )

            expect_exception(
                "Reject nonexistent evidence",
                FiveForcesNotFoundError,
                lambda: create_five_forces_indicator(
                    assessment_id,
                    "Buyer Power",
                    "Invalid evidence indicator",
                    3,
                    1,
                    ADMIN_ID,
                    evidence_id=999999999
                )
            )

            # -------------------------------------------------
            # TEST 9: DELETE INDICATOR
            # -------------------------------------------------

            deleted_indicator = delete_five_forces_indicator(
                weighted_indicator["id"],
                ADMIN_ID
            )

            check(
                "Delete indicator",
                deleted_indicator["deleted"] is True
            )

            check(
                "Deleted indicator no longer exists",
                get_five_forces_indicator(
                    weighted_indicator["id"]
                ) is None
            )

            # -------------------------------------------------
            # TEST 10: AUDIT LOGGING
            # -------------------------------------------------

            audit_count = database.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE entity_type = 'Five Forces Assessment'
                   OR entity_type = 'Five Forces Indicator'
                """
            ).fetchone()[0]

            check(
                "Audit events recorded",
                audit_count >= 10
            )

            # -------------------------------------------------
            # TEST 11: DELETE ASSESSMENT
            # -------------------------------------------------

            deleted = delete_five_forces_assessment(
                assessment_id,
                ADMIN_ID
            )

            check(
                "Delete assessment",
                deleted is True
            )

            check(
                "Assessment no longer exists",
                get_five_forces_assessment(
                    assessment_id
                ) is None
            )

            remaining_indicators = database.execute(
                """
                SELECT COUNT(*)
                FROM five_forces_indicators
                WHERE assessment_id = ?
                """,
                (assessment_id,)
            ).fetchone()[0]

            check(
                "Assessment deletion removes its indicators",
                remaining_indicators == 0
            )

            # -------------------------------------------------
            # DATABASE INTEGRITY
            # -------------------------------------------------

            integrity = database.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            foreign_key_errors = database.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            check(
                "Temporary database integrity",
                integrity == "ok"
            )

            check(
                "Temporary database foreign keys",
                len(foreign_key_errors) == 0
            )

            # Roll back any remaining transaction state.
            database.rollback()

        # Application context has closed its connection here.

    print("\n" + "=" * 55)
    print("FIVE FORCES SERVICE TEST RESULTS")
    print("=" * 55)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    print("=" * 55)

    if failed:
        raise SystemExit(1)

    print("\nAll Five Forces service integration tests passed.")


if __name__ == "__main__":
    run_tests()
