
"""
StrategySim - SWOT Service Integration Tests

Tests SWOT CRUD, validation, evidence associations,
audit logging, and database integrity.

All test records are created in a temporary database copy.
The original database is not used for test CRUD operations.
"""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from flask import g

from app import create_app
from app.database.connection import get_db
from app.swot.services import (
    SWOTValidationError,
    SWOTNotFoundError,
    create_swot_assessment,
    get_swot_assessment,
    get_swot_assessments,
    update_swot_assessment,
    delete_swot_assessment,
    create_swot_factor,
    get_swot_factor,
    get_swot_factors,
    update_swot_factor,
    delete_swot_factor,
)
from app.evidence.services import create_evidence
from app.strategic_analysis.evidence_service import (
    create_evidence_link,
    get_evidence_links,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DB = PROJECT_ROOT / "instance" / "strategysim.db"

passed = 0
failed = 0


def check(name, callback):
    global passed, failed

    try:
        callback()
        passed += 1
        print(f"[PASS] {name}")
    except Exception as error:
        failed += 1
        print(f"[FAIL] {name}: {error}")


def expect_exception(expected_exception, callback):
    try:
        callback()
    except expected_exception:
        return

    raise AssertionError(
        f"Expected {expected_exception.__name__} "
        "but no such exception was raised."
    )


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    global passed, failed

    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(
            f"Database not found: {ORIGINAL_DB}"
        )

    print("=" * 70)
    print("STRATEGYSIM - SWOT SERVICE INTEGRATION TESTS")
    print("=" * 70)

    with tempfile.TemporaryDirectory(
        prefix="strategysim_swot_test_"
    ) as temporary_directory:

        temporary_db = (
            Path(temporary_directory) / "strategysim_test.db"
        )

        shutil.copy2(ORIGINAL_DB, temporary_db)

        print(f"\nOriginal database: {ORIGINAL_DB}")
        print(f"Temporary database: {temporary_db}")
        print("[OK] Temporary database copy created.")

        # Application initialization is performed normally.
        # All test CRUD operations below use the temporary copy.
        app = create_app()
        app.config["DATABASE_PATH"] = str(temporary_db)

        with app.app_context():
            # Discard any connection retained during application
            # initialization so subsequent connections use the copy.
            old_connection = g.pop("db", None)

            if old_connection is not None:
                old_connection.close()

            database = get_db()

            # -------------------------------------------------
            # SELECT TEST ACTORS AND COMPANY
            # -------------------------------------------------

            admin = database.execute(
                """
                SELECT id, full_name
                FROM users
                WHERE role = 'Administrator'
                  AND is_active = 1
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()

            company = database.execute(
                """
                SELECT id, name
                FROM companies
                ORDER BY id
                LIMIT 1
                """
            ).fetchone()

            assert_true(admin is not None, "No active Administrator found.")
            assert_true(company is not None, "No company found.")

            admin_id = admin["id"]
            company_id = company["id"]

            print("\nTest actor:")
            print(f" Administrator: {admin['full_name']} (ID {admin_id})")
            print(f" Company: {company['name']} (ID {company_id})")

            original_user_count = database.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

            original_company_count = database.execute(
                "SELECT COUNT(*) FROM companies"
            ).fetchone()[0]

            # -------------------------------------------------
            # 1. CREATE SWOT ASSESSMENT
            # -------------------------------------------------

            assessment = create_swot_assessment(
                company_id=company_id,
                assessment_name="SWOT Integration Test",
                acting_user_id=admin_id,
                assessment_date="2026-11-07",
                summary="Temporary integration test assessment.",
            )

            assessment_id = assessment["id"]

            check(
                "Create SWOT assessment",
                lambda: assert_true(
                    assessment["assessment_name"]
                    == "SWOT Integration Test",
                    "Assessment name does not match.",
                ),
            )

            # -------------------------------------------------
            # 2. READ ASSESSMENT
            # -------------------------------------------------

            retrieved_assessment = get_swot_assessment(
                assessment_id
            )

            check(
                "Retrieve SWOT assessment",
                lambda: assert_true(
                    retrieved_assessment["id"] == assessment_id,
                    "Assessment ID does not match.",
                ),
            )

            # -------------------------------------------------
            # 3. LIST AND FILTER ASSESSMENTS
            # -------------------------------------------------

            assessments = get_swot_assessments(
                company_id=company_id,
                limit=100,
                offset=0,
            )

            check(
                "List SWOT assessments by company",
                lambda: assert_true(
                    any(
                        item["id"] == assessment_id
                        for item in assessments
                    ),
                    "Created assessment missing from list.",
                ),
            )

            searched = get_swot_assessments(
                search="SWOT Integration Test"
            )

            check(
                "Search SWOT assessments",
                lambda: assert_true(
                    any(
                        item["id"] == assessment_id
                        for item in searched
                    ),
                    "Assessment missing from search results.",
                ),
            )

            # -------------------------------------------------
            # 4. UPDATE ASSESSMENT
            # -------------------------------------------------

            updated_assessment = update_swot_assessment(
                assessment_id=assessment_id,
                acting_user_id=admin_id,
                updates={
                    "assessment_name": "Updated SWOT Integration Test",
                    "summary": "Updated integration test summary.",
                },
            )

            check(
                "Update SWOT assessment",
                lambda: assert_true(
                    updated_assessment["assessment_name"]
                    == "Updated SWOT Integration Test",
                    "Assessment was not updated.",
                ),
            )

            # -------------------------------------------------
            # 5. CREATE ALL FOUR SWOT FACTOR TYPES
            # -------------------------------------------------

            factor_definitions = [
                (
                    "Strength",
                    "Strong engineering capability",
                    5,
                ),
                (
                    "Weakness",
                    "Limited distribution network",
                    3,
                ),
                (
                    "Opportunity",
                    "Expansion into new markets",
                    4,
                ),
                (
                    "Threat",
                    "Increasing competitive pressure",
                    2,
                ),
            ]

            factor_ids = {}

            for factor_type, factor_name, importance in (
                factor_definitions
            ):
                factor = create_swot_factor(
                    assessment_id=assessment_id,
                    factor_type=factor_type,
                    factor_name=factor_name,
                    acting_user_id=admin_id,
                    description=(
                        f"Integration test description for {factor_type}."
                    ),
                    importance=importance,
                )

                factor_ids[factor_type] = factor["id"]

            check(
                "Create all four SWOT factor types",
                lambda: assert_true(
                    len(factor_ids) == 4,
                    "Not all four SWOT factors were created.",
                ),
            )

            # -------------------------------------------------
            # 6. READ FACTORS
            # -------------------------------------------------

            factors = get_swot_factors(assessment_id)

            check(
                "Retrieve all SWOT factors",
                lambda: assert_true(
                    len(factors) == 4,
                    f"Expected 4 factors, found {len(factors)}.",
                ),
            )

            # -------------------------------------------------
            # 7. FILTER FACTORS BY TYPE
            # -------------------------------------------------

            strengths = get_swot_factors(
                assessment_id,
                factor_type="Strength",
            )

            check(
                "Filter SWOT factors by type",
                lambda: assert_true(
                    len(strengths) == 1
                    and strengths[0]["factor_type"] == "Strength",
                    "Strength filter returned incorrect results.",
                ),
            )

            # -------------------------------------------------
            # 8. VERIFY STRATEGIC IMPORTANCE
            # -------------------------------------------------

            strength = get_swot_factor(
                factor_ids["Strength"]
            )

            check(
                "Verify strategic_importance database column",
                lambda: assert_true(
                    strength["strategic_importance"] == 5,
                    "Strategic importance was not stored correctly.",
                ),
            )

            # -------------------------------------------------
            # 9. UPDATE FACTOR
            # -------------------------------------------------

            updated_factor = update_swot_factor(
                factor_id=factor_ids["Strength"],
                acting_user_id=admin_id,
                updates={
                    "factor_name": "Strong R&D capability",
                    "description": "Updated strength description.",
                    "importance": 4,
                },
            )

            check(
                "Update SWOT factor",
                lambda: assert_true(
                    updated_factor["factor_name"]
                    == "Strong R&D capability"
                    and updated_factor["strategic_importance"] == 4,
                    "Factor update failed.",
                ),
            )

            # -------------------------------------------------
            # 10. INVALID FACTOR TYPE
            # -------------------------------------------------

            check(
                "Reject invalid SWOT factor type",
                lambda: expect_exception(
                    SWOTValidationError,
                    lambda: create_swot_factor(
                        assessment_id=assessment_id,
                        factor_type="Neutral",
                        factor_name="Invalid factor",
                        acting_user_id=admin_id,
                    ),
                ),
            )

            # -------------------------------------------------
            # 11. INVALID IMPORTANCE
            # -------------------------------------------------

            check(
                "Reject importance score outside 1-5",
                lambda: expect_exception(
                    SWOTValidationError,
                    lambda: create_swot_factor(
                        assessment_id=assessment_id,
                        factor_type="Strength",
                        factor_name="Invalid importance",
                        acting_user_id=admin_id,
                        importance=6,
                    ),
                ),
            )

            # -------------------------------------------------
            # 12. MISSING ASSESSMENT
            # -------------------------------------------------

            check(
                "Reject missing assessment reference",
                lambda: expect_exception(
                    SWOTNotFoundError,
                    lambda: create_swot_factor(
                        assessment_id=99999999,
                        factor_type="Strength",
                        factor_name="Invalid reference",
                        acting_user_id=admin_id,
                    ),
                ),
            )

            # -------------------------------------------------
            # 13. CREATE EVIDENCE
            # -------------------------------------------------

            evidence = create_evidence(
                title="SWOT Integration Test Evidence",
                acting_user_id=admin_id,
                description=(
                    "Temporary evidence record for SWOT testing."
                ),
                source_type="Internal Research",
                source_name="StrategySim Integration Test",
                entity_type="Company",
                entity_id=company_id,
                reliability_score=5,
            )

            evidence_id = evidence["id"]

            check(
                "Create evidence for SWOT testing",
                lambda: assert_true(
                    evidence_id > 0,
                    "Evidence record was not created.",
                ),
            )

            # -------------------------------------------------
            # 14. LINK EVIDENCE TO SWOT FACTOR
            # -------------------------------------------------

            linked_factor_id = factor_ids["Strength"]

            create_evidence_link(
                evidence_id=evidence_id,
                analysis_type="SWOT",
                analysis_record_id=linked_factor_id,
                acting_user_id=admin_id,
            )

            links = get_evidence_links(
                analysis_type="SWOT",
                analysis_record_id=linked_factor_id,
            )

            check(
                "Link evidence to SWOT factor",
                lambda: assert_true(
                    any(
                        item["evidence_id"] == evidence_id
                        for item in links
                    ),
                    "Evidence association was not found.",
                ),
            )

            # -------------------------------------------------
            # 15. DELETE FACTOR AND CHECK EVIDENCE PRESERVATION
            # -------------------------------------------------

            deleted_factor_id = factor_ids["Strength"]

            delete_swot_factor(
                factor_id=deleted_factor_id,
                acting_user_id=admin_id,
            )

            deleted_factor = database.execute(
                """
                SELECT id
                FROM swot_factors
                WHERE id = ?
                """,
                (deleted_factor_id,),
            ).fetchone()

            remaining_evidence = database.execute(
                """
                SELECT id
                FROM evidence
                WHERE id = ?
                """,
                (evidence_id,),
            ).fetchone()

            remaining_link = database.execute(
                """
                SELECT id
                FROM strategic_analysis_evidence
                WHERE analysis_type = 'SWOT'
                  AND analysis_record_id = ?
                """,
                (deleted_factor_id,),
            ).fetchone()

            check(
                "Delete factor without deleting evidence",
                lambda: (
                    assert_true(
                        deleted_factor is None,
                        "Deleted factor still exists.",
                    ),
                    assert_true(
                        remaining_evidence is not None,
                        "Evidence record was incorrectly deleted.",
                    ),
                    assert_true(
                        remaining_link is None,
                        "Evidence association was not deleted.",
                    ),
                ),
            )

            # -------------------------------------------------
            # 16. DELETE ASSESSMENT AND CHECK CASCADE
            # -------------------------------------------------

            remaining_factor_ids = [
                factor_ids["Weakness"],
                factor_ids["Opportunity"],
                factor_ids["Threat"],
            ]

            delete_swot_assessment(
                assessment_id=assessment_id,
                acting_user_id=admin_id,
            )

            assessment_after_delete = database.execute(
                """
                SELECT id
                FROM swot_assessments
                WHERE id = ?
                """,
                (assessment_id,),
            ).fetchone()

            factors_after_delete = database.execute(
                """
                SELECT id
                FROM swot_factors
                WHERE assessment_id = ?
                """,
                (assessment_id,),
            ).fetchall()

            check(
                "Delete assessment and cascade its factors",
                lambda: (
                    assert_true(
                        assessment_after_delete is None,
                        "Assessment still exists after deletion.",
                    ),
                    assert_true(
                        len(factors_after_delete) == 0,
                        "Assessment factors were not cascade deleted.",
                    ),
                ),
            )

            # -------------------------------------------------
            # 17. VERIFY AUDIT LOGGING
            # -------------------------------------------------

            audit_count = database.execute(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE user_id = ?
                  AND entity_type IN (
                      'SWOT Assessment',
                      'SWOT Factor'
                  )
                """,
                (admin_id,),
            ).fetchone()[0]

            check(
                "Verify SWOT audit logging",
                lambda: assert_true(
                    audit_count >= 8,
                    f"Expected at least 8 SWOT audit records, "
                    f"found {audit_count}.",
                ),
            )

            # -------------------------------------------------
            # 18. VERIFY EVIDENCE STILL EXISTS
            # -------------------------------------------------

            evidence_after_assessment_delete = database.execute(
                """
                SELECT id
                FROM evidence
                WHERE id = ?
                """,
                (evidence_id,),
            ).fetchone()

            check(
                "Preserve evidence after assessment deletion",
                lambda: assert_true(
                    evidence_after_assessment_delete is not None,
                    "Evidence record was unexpectedly deleted.",
                ),
            )

            # -------------------------------------------------
            # 19. VERIFY EXISTING USERS AND COMPANIES
            # -------------------------------------------------

            user_count = database.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

            company_count = database.execute(
                "SELECT COUNT(*) FROM companies"
            ).fetchone()[0]

            check(
                "Preserve existing users and companies",
                lambda: (
                    assert_true(
                        user_count == original_user_count,
                        "User count changed during testing.",
                    ),
                    assert_true(
                        company_count == original_company_count,
                        "Company count changed during testing.",
                    ),
                ),
            )

            database.commit()

        # -----------------------------------------------------
        # 20. SQLITE INTEGRITY AND FOREIGN KEY CHECKS
        # -----------------------------------------------------

        verification_db = sqlite3.connect(temporary_db)

        integrity_result = verification_db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_key_errors = verification_db.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        verification_db.close()

        check(
            "SQLite integrity check",
            lambda: assert_true(
                integrity_result == "ok",
                f"Integrity check returned: {integrity_result}",
            ),
        )

        check(
            "SQLite foreign-key check",
            lambda: assert_true(
                len(foreign_key_errors) == 0,
                f"Foreign-key errors: {foreign_key_errors}",
            ),
        )

    # ---------------------------------------------------------
    # FINAL RESULTS
    # ---------------------------------------------------------

    print("\n" + "=" * 70)
    print("SWOT INTEGRATION TEST RESULTS")
    print("=" * 70)
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print(f"TOTAL:  {passed + failed}")

    if failed:
        print("\nSWOT INTEGRATION TESTS FAILED.")
        raise SystemExit(1)

    print("\nALL SWOT INTEGRATION TESTS PASSED.")
    print("The original database was not used for test CRUD operations.")


if __name__ == "__main__":
    main()
