import sqlite3
import tempfile
import traceback
import sys

from pathlib import Path

# =========================================================
# PROJECT ROOT IMPORT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from flask import Flask

from app.database.connection import get_db, close_db
from app.competitors.services import (
    get_competitors,
    get_competitor_details,
    get_company_competitors,
    create_competitor_relationship,
    update_competitor_relationship,
    delete_competitor_relationship,
    CompetitorNotFoundError,
    TargetCompanyNotFoundError,
    CompetitorRelationshipNotFoundError,
    InvalidCompetitorDataError,
    DuplicateCompetitorRelationshipError,
    InvalidCompetitorRelationshipError,
)


# =========================================================
# PATH CONFIGURATION
# =========================================================


SCHEMA_PATH = (
    PROJECT_ROOT
    / "app"
    / "database"
    / "schema.sql"
)


# =========================================================
# TEST RESULT TRACKING
# =========================================================

passed = 0
failed = 0


def report_success(message):
    global passed
    passed += 1
    print(f"[PASS] {message}")


def report_failure(message):
    global failed
    failed += 1
    print(f"[FAIL] {message}")


def run_check(description, callback):
    """
    Execute one test and record its result.
    """

    try:
        callback()
        report_success(description)

    except Exception as error:
        report_failure(description)
        print(f"       Error: {error}")
        traceback.print_exc()


def expect_exception(exception_type, callback):
    """
    Confirm that an operation raises the expected exception.
    """

    try:
        callback()

    except exception_type:
        return True

    except Exception as error:
        raise AssertionError(
            f"Expected {exception_type.__name__}, "
            f"but received {type(error).__name__}: {error}"
        )

    raise AssertionError(
        f"Expected {exception_type.__name__}, "
        "but no exception was raised."
    )


# =========================================================
# TEMPORARY DATABASE INITIALIZATION
# =========================================================

def initialize_test_database(database_path):
    """
    Create an isolated SQLite database using the actual
    StrategySim database schema.
    """

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_PATH}"
        )

    schema_sql = SCHEMA_PATH.read_text(
        encoding="utf-8"
    )

    connection = sqlite3.connect(database_path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema_sql)

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if integrity != "ok":
            raise RuntimeError(
                f"Temporary database integrity failed: {integrity}"
            )

        if foreign_key_errors:
            raise RuntimeError(
                f"Temporary database foreign key errors: "
                f"{foreign_key_errors}"
            )

        connection.commit()

    finally:
        connection.close()


# =========================================================
# TEST DATA CREATION
# =========================================================

def create_test_records(database):
    """
    Insert test user, industries and companies.

    All records exist only in the temporary database.
    """

    cursor = database.cursor()

    cursor.execute(
        """
        INSERT INTO users (
            full_name,
            email,
            password_hash,
            role,
            is_active
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "StrategySim Test Administrator",
            "test-admin@strategysim.invalid",
            "test-password-hash",
            "Administrator",
            1
        )
    )

    user_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO industries (
            name,
            sector,
            description,
            geography,
            industry_type
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Test Electric Two-Wheeler Industry",
            "Automotive",
            "Illustrative industry created for isolated testing.",
            "India",
            "Electric Vehicles"
        )
    )

    industry_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO industries (
            name,
            sector,
            description,
            geography,
            industry_type
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "Test Other Industry",
            "Other",
            "Separate industry for validation testing.",
            "India",
            "Other"
        )
    )

    other_industry_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO companies (
            industry_id,
            name,
            company_type,
            description,
            headquarters,
            is_demo,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            industry_id,
            "VoltEdge Test Motors",
            "Target",
            "Illustrative target company for testing.",
            "Chennai, India",
            1,
            user_id
        )
    )

    target_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO companies (
            industry_id,
            name,
            company_type,
            description,
            headquarters,
            is_demo,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            industry_id,
            "Test Competitor One",
            "Competitor",
            "Illustrative competitor for testing.",
            "India",
            1,
            user_id
        )
    )

    competitor_one_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO companies (
            industry_id,
            name,
            company_type,
            description,
            headquarters,
            is_demo,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            industry_id,
            "Test Competitor Two",
            "Competitor",
            "Second illustrative competitor for testing.",
            "India",
            1,
            user_id
        )
    )

    competitor_two_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO companies (
            industry_id,
            name,
            company_type,
            description,
            headquarters,
            is_demo,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            other_industry_id,
            "Competitor From Other Industry",
            "Competitor",
            "Illustrative competitor from another industry.",
            "India",
            1,
            user_id
        )
    )

    other_industry_competitor_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO companies (
            industry_id,
            name,
            company_type,
            description,
            headquarters,
            is_demo,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            industry_id,
            "Test Other Company",
            "Other",
            "Company with an unsupported competitor role.",
            "India",
            1,
            user_id
        )
    )

    other_company_id = cursor.lastrowid

    database.commit()

    return {
        "user_id": user_id,
        "industry_id": industry_id,
        "other_industry_id": other_industry_id,
        "target_id": target_id,
        "competitor_one_id": competitor_one_id,
        "competitor_two_id": competitor_two_id,
        "other_industry_competitor_id": other_industry_competitor_id,
        "other_company_id": other_company_id,
    }


# =========================================================
# TEST EXECUTION
# =========================================================

def execute_tests(database):
    """
    Run competitor service tests inside an isolated
    Flask application context.
    """

    global passed, failed

    test_data = create_test_records(database)

    user_id = test_data["user_id"]
    target_id = test_data["target_id"]
    competitor_one_id = test_data["competitor_one_id"]
    competitor_two_id = test_data["competitor_two_id"]
    other_industry_competitor_id = test_data[
        "other_industry_competitor_id"
    ]
    other_company_id = test_data["other_company_id"]

    print("\n" + "=" * 65)
    print("STRATEGYSIM - COMPETITOR SERVICE TESTS")
    print("=" * 65)

    print("\nTEST 1: Competitor Directory")

    def test_directory():
        result = get_competitors(
            industry_id=test_data["industry_id"]
        )

        assert result["total"] == 2
        assert len(result["items"]) == 2

        names = {
            item["name"]
            for item in result["items"]
        }

        assert "Test Competitor One" in names
        assert "Test Competitor Two" in names

    run_check(
        "Competitor directory returns the correct records.",
        test_directory
    )

    print("\nTEST 2: Competitor Search")

    def test_search():
        result = get_competitors(
            search="Competitor One",
            industry_id=test_data["industry_id"]
        )

        assert result["total"] == 1
        assert result["items"][0]["name"] == "Test Competitor One"

    run_check(
        "Competitor search and industry filtering work.",
        test_search
    )

    print("\nTEST 3: Competitor Profile")

    def test_profile():
        result = get_competitor_details(
            competitor_one_id
        )

        assert result["id"] == competitor_one_id
        assert result["company_type"] == "Competitor"
        assert result["relationship_count"] == 0
        assert result["relationships"] == []

    run_check(
        "Competitor profile is retrieved correctly.",
        test_profile
    )

    print("\nTEST 4: Empty Target Relationships")

    def test_empty_relationships():
        result = get_company_competitors(target_id)

        assert result["total"] == 0
        assert result["items"] == []
        assert result["target_company"]["id"] == target_id

    run_check(
        "Target company returns an empty relationship list.",
        test_empty_relationships
    )

    print("\nTEST 5: Relationship Creation")

    relationship_id = None

    def test_create_relationship():
        nonlocal relationship_id

        relationship_id = create_competitor_relationship(
            target_company_id=target_id,
            competitor_id=competitor_one_id,
            acting_user_id=user_id,
            competitive_strength=4,
            notes="Illustrative test relationship."
        )

        assert isinstance(relationship_id, int)
        assert relationship_id > 0

        database_row = get_db().execute(
            """
            SELECT *
            FROM competitor_relationships
            WHERE id = ?
            """,
            (relationship_id,)
        ).fetchone()

        assert database_row is not None
        assert database_row["company_id"] == target_id
        assert database_row["competitor_id"] == competitor_one_id
        assert database_row["competitive_strength"] == 4

    run_check(
        "Competitor relationship is created successfully.",
        test_create_relationship
    )

    print("\nTEST 6: Duplicate Relationship Prevention")

    def test_duplicate():
        expect_exception(
            DuplicateCompetitorRelationshipError,
            lambda: create_competitor_relationship(
                target_company_id=target_id,
                competitor_id=competitor_one_id,
                acting_user_id=user_id,
                competitive_strength=3
            )
        )

    run_check(
        "Duplicate relationships are rejected.",
        test_duplicate
    )

    print("\nTEST 7: Self-Relationship Prevention")

    def test_self_relationship():
        expect_exception(
            InvalidCompetitorRelationshipError,
            lambda: create_competitor_relationship(
                target_company_id=target_id,
                competitor_id=target_id,
                acting_user_id=user_id
            )
        )

    run_check(
        "A company cannot be its own competitor.",
        test_self_relationship
    )

    print("\nTEST 8: Company Type Validation")

    def test_company_type():
        expect_exception(
            InvalidCompetitorRelationshipError,
            lambda: create_competitor_relationship(
                target_company_id=target_id,
                competitor_id=other_company_id,
                acting_user_id=user_id
            )
        )

    run_check(
        "Companies with the wrong company type are rejected.",
        test_company_type
    )

    print("\nTEST 9: Industry Validation")

    def test_industry():
        expect_exception(
            InvalidCompetitorRelationshipError,
            lambda: create_competitor_relationship(
                target_company_id=target_id,
                competitor_id=other_industry_competitor_id,
                acting_user_id=user_id
            )
        )

    run_check(
        "Companies from different industries cannot be linked.",
        test_industry
    )

    print("\nTEST 10: Competitive Strength Validation")

    def test_strength():
        expect_exception(
            InvalidCompetitorDataError,
            lambda: create_competitor_relationship(
                target_company_id=target_id,
                competitor_id=competitor_two_id,
                acting_user_id=user_id,
                competitive_strength=6
            )
        )

    run_check(
        "Competitive strength outside the 1-5 range is rejected.",
        test_strength
    )

    print("\nTEST 11: Relationship Update")

    def test_update():
        result = update_competitor_relationship(
            relationship_id=relationship_id,
            acting_user_id=user_id,
            competitive_strength=5,
            notes="Updated illustrative test relationship."
        )

        assert result == relationship_id

        updated = get_db().execute(
            """
            SELECT competitive_strength, notes
            FROM competitor_relationships
            WHERE id = ?
            """,
            (relationship_id,)
        ).fetchone()

        assert updated["competitive_strength"] == 5
        assert updated["notes"] == (
            "Updated illustrative test relationship."
        )

    run_check(
        "Relationship strength and notes update successfully.",
        test_update
    )

    print("\nTEST 12: Target Company Relationship Retrieval")

    def test_target_relationships():
        result = get_company_competitors(target_id)

        assert result["total"] == 1

        item = result["items"][0]

        assert item["competitor_id"] == competitor_one_id
        assert item["competitive_strength"] == 5

    run_check(
        "Target company retrieves its competitor relationship.",
        test_target_relationships
    )

    print("\nTEST 13: Competitor Profile Relationship Retrieval")

    def test_competitor_relationships():
        result = get_competitor_details(
            competitor_one_id
        )

        assert result["relationship_count"] == 1

        relationship = result["relationships"][0]

        assert relationship["target_company_id"] == target_id
        assert relationship["target_company_name"] == (
            "VoltEdge Test Motors"
        )

    run_check(
        "Competitor profile displays its associated target company.",
        test_competitor_relationships
    )

    print("\nTEST 14: Audit Logging")

    def test_audit_logging():
        rows = get_db().execute(
            """
            SELECT action, entity_type, entity_id
            FROM audit_logs
            WHERE entity_type = 'competitor_relationship'
            ORDER BY id ASC
            """
        ).fetchall()

        actions = [row["action"] for row in rows]

        assert "CREATE" in actions
        assert "UPDATE" in actions

        assert any(
            row["entity_id"] == relationship_id
            for row in rows
        )

    run_check(
        "Create and update operations produce audit records.",
        test_audit_logging
    )

    print("\nTEST 15: Transaction Rollback")

    def test_transaction_rollback():
        initial_count = get_db().execute(
            """
            SELECT COUNT(*)
            FROM competitor_relationships
            """
        ).fetchone()[0]

        expect_exception(
            sqlite3.IntegrityError,
            lambda: create_competitor_relationship(
                target_company_id=target_id,
                competitor_id=competitor_two_id,
                acting_user_id=999999,
                competitive_strength=3,
                notes="This operation must roll back."
            )
        )

        final_count = get_db().execute(
            """
            SELECT COUNT(*)
            FROM competitor_relationships
            """
        ).fetchone()[0]

        assert final_count == initial_count

        audit_count = get_db().execute(
            """
            SELECT COUNT(*)
            FROM audit_logs
            WHERE description LIKE '%Test Competitor Two%'
            """
        ).fetchone()[0]

        assert audit_count == 0

    run_check(
        "Failed audit insertion rolls back the relationship.",
        test_transaction_rollback
    )

    print("\nTEST 16: Relationship Deletion")

    def test_delete_relationship():
        result = delete_competitor_relationship(
            relationship_id=relationship_id,
            acting_user_id=user_id
        )

        assert result is True

        relationship = get_db().execute(
            """
            SELECT id
            FROM competitor_relationships
            WHERE id = ?
            """,
            (relationship_id,)
        ).fetchone()

        assert relationship is None

    run_check(
        "Relationship is deleted successfully.",
        test_delete_relationship
    )

    print("\nTEST 17: Company Preservation")

    def test_company_preservation():
        target = get_db().execute(
            "SELECT id FROM companies WHERE id = ?",
            (target_id,)
        ).fetchone()

        competitor = get_db().execute(
            "SELECT id FROM companies WHERE id = ?",
            (competitor_one_id,)
        ).fetchone()

        assert target is not None
        assert competitor is not None

    run_check(
        "Deleting a relationship preserves both companies.",
        test_company_preservation
    )

    print("\nTEST 18: Deleted Relationship Cannot Be Updated")

    def test_update_deleted_relationship():
        expect_exception(
            CompetitorRelationshipNotFoundError,
            lambda: update_competitor_relationship(
                relationship_id=relationship_id,
                acting_user_id=user_id,
                competitive_strength=3
            )
        )

    run_check(
        "A deleted relationship cannot be updated.",
        test_update_deleted_relationship
    )

    print("\nTEST 19: Missing Competitor Validation")

    def test_missing_competitor():
        expect_exception(
            CompetitorNotFoundError,
            lambda: get_competitor_details(999999)
        )

    run_check(
        "Missing competitor IDs are handled correctly.",
        test_missing_competitor
    )

    print("\nTEST 20: Missing Target Validation")

    def test_missing_target():
        expect_exception(
            TargetCompanyNotFoundError,
            lambda: get_company_competitors(999999)
        )

    run_check(
        "Missing target company IDs are handled correctly.",
        test_missing_target
    )

    print("\nTEST 21: Missing Relationship Validation")

    def test_missing_relationship():
        expect_exception(
            CompetitorRelationshipNotFoundError,
            lambda: delete_competitor_relationship(
                relationship_id=999999,
                acting_user_id=user_id
            )
        )

    run_check(
        "Missing relationship IDs are handled correctly.",
        test_missing_relationship
    )

    print("\nTEST 22: Database Integrity")

    def test_integrity():
        integrity = get_db().execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        foreign_key_errors = get_db().execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert integrity == "ok"
        assert foreign_key_errors == []

    run_check(
        "Temporary database integrity and foreign keys are valid.",
        test_integrity
    )


# =========================================================
# MAIN EXECUTION
# =========================================================

def main():
    global passed, failed

    print("\nPreparing isolated competitor service test database...")

    with tempfile.TemporaryDirectory(
        prefix="strategysim_competitor_tests_"
    ) as temporary_directory:

        database_path = (
            Path(temporary_directory)
            / "competitor_test.db"
        )

        try:
            initialize_test_database(database_path)

            app = Flask("StrategySimCompetitorTests")

            app.config["DATABASE_PATH"] = str(
                database_path.resolve()
            )

            with app.app_context():

                try:
                    database = get_db()

                    execute_tests(database)

                finally:
                    close_db()

        except Exception as error:
            failed += 1

            print("\n[FATAL TEST ERROR]")
            print(error)
            traceback.print_exc()

    print("\n" + "=" * 65)
    print("COMPETITOR SERVICE TEST SUMMARY")
    print("=" * 65)

    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")

    if failed == 0:
        print("\nRESULT: ALL TESTS PASSED")
    else:
        print("\nRESULT: SOME TESTS FAILED")

    print("\nTemporary database cleanup completed.")
    print("Your original StrategySim database was not modified.")
    print("=" * 65)

    return failed == 0


if __name__ == "__main__":
    success = main()

    if not success:
        raise SystemExit(1)
