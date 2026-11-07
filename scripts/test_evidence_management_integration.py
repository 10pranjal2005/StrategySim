
"""
Integration tests for Evidence Management Service.

All database writes are performed against a temporary database copy.
The original StrategySim database is never modified.
"""

import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import g

from app import create_app
from app.database.connection import get_database_path, get_db

from app.evidence.services import (
    EvidenceError,
    EvidenceValidationError,
    create_evidence,
    get_evidence_details,
    get_evidence_records,
    update_evidence,
    delete_evidence,
)

from app.strategic_analysis.evidence_service import (
    create_evidence_link,
)


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


def expect_error(name, callback):
    try:
        callback()
    except EvidenceError:
        check(name, True)
    except Exception as exc:
        check(name, False)
        print(f"       Unexpected error: {type(exc).__name__}: {exc}")
    else:
        check(name, False)
        print("       Expected an EvidenceError, but no error was raised.")


def main():
    print("\nSTRATEGYSIM EVIDENCE MANAGEMENT INTEGRATION TEST")
    print("=" * 58)

    app = create_app()

    with app.app_context():
        original_db = get_database_path()

    if not original_db.exists():
        raise FileNotFoundError(f"Database not found: {original_db}")

    with tempfile.TemporaryDirectory(
        prefix="strategysim_evidence_management_"
    ) as temp_directory:

        temporary_db = Path(temp_directory) / "strategysim_test.db"
        shutil.copy2(original_db, temporary_db)

        app.config["DATABASE_PATH"] = str(temporary_db)

        print(f"Original database: {original_db}")
        print(f"Temporary database: {temporary_db}")
        print("[OK] Original database copied successfully.")

        with app.app_context():
            db = get_db()

            try:
                actor = db.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE role = 'Administrator'
                      AND is_active = 1
                    ORDER BY id
                    LIMIT 1
                    """
                ).fetchone()

                company = db.execute(
                    """
                    SELECT id
                    FROM companies
                    ORDER BY id
                    LIMIT 1
                    """
                ).fetchone()

                if actor is None:
                    raise RuntimeError("No active Administrator found.")

                if company is None:
                    raise RuntimeError("No company found.")

                actor_id = actor["id"]
                company_id = company["id"]

                # Create a SWOT assessment and factor for link testing.
                cursor = db.execute(
                    """
                    INSERT INTO swot_assessments (
                        company_id,
                        assessment_name,
                        assessment_date,
                        summary,
                        created_by
                    )
                    VALUES (?, ?, DATE('now'), ?, ?)
                    """,
                    (
                        company_id,
                        "Evidence Management Test",
                        "Temporary assessment for integration testing.",
                        actor_id,
                    ),
                )

                assessment_id = cursor.lastrowid

                cursor = db.execute(
                    """
                    INSERT INTO swot_factors (
                        assessment_id,
                        factor_type,
                        factor_name,
                        description,
                        strategic_importance
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        assessment_id,
                        "Strength",
                        "Evidence management test factor",
                        "Temporary factor for evidence deletion testing.",
                        4,
                    ),
                )

                factor_id = cursor.lastrowid
                db.commit()

                print(f"Administrator ID: {actor_id}")
                print(f"Company ID: {company_id}")
                print(f"Temporary SWOT factor ID: {factor_id}")

                # 1. Create evidence.
                created = create_evidence(
                    title="Evidence Management Integration Record",
                    acting_user_id=actor_id,
                    description="Temporary record for CRUD integration testing.",
                    source_type="Manual",
                    source_name="Integration Test",
                    source_url="https://example.com/test-evidence",
                    entity_type="Company",
                    entity_id=company_id,
                    reliability_score=4,
                )

                evidence_id = created.get("id") if isinstance(created, dict) else None

                check(
                    "Create evidence record",
                    evidence_id is not None
                    and created.get("title")
                    == "Evidence Management Integration Record",
                )

                # 2. Retrieve details.
                details = get_evidence_details(evidence_id)

                check(
                    "Retrieve evidence details",
                    details["id"] == evidence_id
                    and details["source_type"] == "Manual"
                    and details["reliability_score"] == 4,
                )

                # 3. List records.
                records = get_evidence_records(
                    limit=100,
                    offset=0,
                    search="Evidence Management Integration Record",
                )

                check(
                    "List and search evidence records",
                    any(record["id"] == evidence_id for record in records),
                )

                # 4. Filter by source type.
                filtered = get_evidence_records(
                    source_type="Manual",
                    limit=100,
                )

                check(
                    "Filter evidence by source type",
                    any(record["id"] == evidence_id for record in filtered),
                )

                # 5. Update evidence.
                updated = update_evidence(
                    evidence_id=evidence_id,
                    acting_user_id=actor_id,
                    updates={
                        "title": "Updated Evidence Management Record",
                        "description": "Updated description for integration testing.",
                        "reliability_score": 5,
                    },
                )

                check(
                    "Update evidence metadata",
                    updated["title"] == "Updated Evidence Management Record"
                    and updated["reliability_score"] == 5,
                )

                # 6. Reject invalid input.
                expect_error(
                    "Reject invalid evidence source type",
                    lambda: create_evidence(
                        title="Invalid Source Test",
                        acting_user_id=actor_id,
                        source_type="Unsupported Source",
                    ),
                )

                expect_error(
                    "Reject invalid reliability score",
                    lambda: create_evidence(
                        title="Invalid Score Test",
                        acting_user_id=actor_id,
                        reliability_score=9,
                    ),
                )

                expect_error(
                    "Reject unsupported update fields",
                    lambda: update_evidence(
                        evidence_id=evidence_id,
                        acting_user_id=actor_id,
                        updates={"uploaded_by": actor_id},
                    ),
                )

                # 7. Create a strategic-analysis evidence association.
                link = create_evidence_link(
                    evidence_id=evidence_id,
                    analysis_type="SWOT",
                    analysis_record_id=factor_id,
                    acting_user_id=actor_id,
                )

                check(
                    "Link evidence to a SWOT factor",
                    isinstance(link, dict)
                    and link.get("evidence_id") == evidence_id,
                )

                # 8. Verify association exists before deletion.
                link_count_before = db.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM strategic_analysis_evidence
                    WHERE evidence_id = ?
                    """,
                    (evidence_id,),
                ).fetchone()["total"]

                check(
                    "Verify strategic-analysis association",
                    link_count_before == 1,
                )

                # 9. Delete evidence and verify cascading association deletion.
                deleted = delete_evidence(
                    evidence_id=evidence_id,
                    acting_user_id=actor_id,
                )

                check(
                    "Delete evidence record",
                    isinstance(deleted, dict)
                    and deleted.get("deleted") is True
                    and deleted.get("id") == evidence_id
                    and deleted.get("removed_associations") == 1,
                )

                evidence_after_delete = db.execute(
                    "SELECT id FROM evidence WHERE id = ?",
                    (evidence_id,),
                ).fetchone()

                check(
                    "Deleted evidence is no longer present",
                    evidence_after_delete is None,
                )

                links_after_delete = db.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM strategic_analysis_evidence
                    WHERE evidence_id = ?
                    """,
                    (evidence_id,),
                ).fetchone()["total"]

                check(
                    "Linked associations are removed by cascade",
                    links_after_delete == 0,
                )

                # 10. Reject retrieval of deleted evidence.
                expect_error(
                    "Reject retrieval of deleted evidence",
                    lambda: get_evidence_details(evidence_id),
                )

                # 11. Verify audit records.
                audit_rows = db.execute(
                    """
                    SELECT action, entity_type, entity_id
                    FROM audit_logs
                    WHERE entity_type = 'Evidence'
                      AND entity_id = ?
                    ORDER BY id
                    """,
                    (evidence_id,),
                ).fetchall()

                audit_actions = {
                    row["action"] for row in audit_rows
                }

                expected_actions = {
                    "CREATE_EVIDENCE",
                    "UPDATE_EVIDENCE",
                    "DELETE_EVIDENCE",
                }

                check(
                    "Create, update and delete audit entries",
                    expected_actions.issubset(audit_actions),
                )

                if not expected_actions.issubset(audit_actions):
                    print("       Actual audit actions:", sorted(audit_actions))

                # 12. Database integrity.
                integrity = db.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]

                foreign_key_errors = db.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()

                check(
                    "SQLite integrity check",
                    integrity == "ok",
                )

                check(
                    "SQLite foreign-key check",
                    len(foreign_key_errors) == 0,
                )

            finally:
                db.rollback()
                db.close()
                g.pop("db", None)

    print("\n" + "=" * 58)
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print(f"TOTAL:  {passed + failed}")

    if failed:
        print("\nEVIDENCE MANAGEMENT INTEGRATION TEST FAILED.")
        raise SystemExit(1)

    print("\nALL EVIDENCE MANAGEMENT INTEGRATION TESTS PASSED.")
    print("The original database was not modified.")


if __name__ == "__main__":
    main()
