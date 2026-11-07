
import sys
import shutil
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import g
from app import create_app
from app.database.connection import get_database_path
from app.database import get_db

from app.strategic_analysis.evidence_service import (
    EvidenceLinkError,
    create_evidence_link,
    get_evidence_links,
    get_evidence_analysis_links,
    get_evidence_link_details,
    delete_evidence_link,
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


def expect_service_error(name, callback):
    try:
        callback()
    except EvidenceLinkError:
        check(name, True)
    except Exception as exc:
        check(name, False)
        print(
            f"       Unexpected exception: "
            f"{type(exc).__name__}: {exc}"
        )
    else:
        check(name, False)
        print("       Expected EvidenceLinkError, but no error was raised.")


def main():
    print("\nSTRATEGYSIM EVIDENCE SERVICE INTEGRATION TEST")
    print("=" * 55)

    app = create_app()

    with app.app_context():
        original_db = get_database_path()

    if not original_db.exists():
        raise FileNotFoundError(
            f"Original database not found: {original_db}"
        )

    with tempfile.TemporaryDirectory(
        prefix="strategysim_evidence_test_"
    ) as temp_directory:

        temporary_db = Path(temp_directory) / "strategysim_test.db"
        shutil.copy2(original_db, temporary_db)

        app.config["DATABASE_PATH"] = str(temporary_db)

        print(f"Original database: {original_db}")
        print(f"Temporary database: {temporary_db}")
        print("[OK] Temporary database copy created.")

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
                    raise RuntimeError(
                        "No active Administrator exists in the test database."
                    )

                if company is None:
                    raise RuntimeError(
                        "No company exists in the test database."
                    )

                actor_id = actor["id"]
                company_id = company["id"]

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
                        "Evidence Integration Test",
                        "Temporary integration-test assessment.",
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
                        "Test factor for evidence linking",
                        "Temporary factor used only in integration testing.",
                        4,
                    ),
                )

                factor_id = cursor.lastrowid

                cursor = db.execute(
                    """
                    INSERT INTO evidence (
                        title,
                        description,
                        source_type,
                        source_name,
                        entity_type,
                        entity_id,
                        reliability_score,
                        uploaded_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Temporary Evidence Test Record",
                        "Temporary evidence used for service integration testing.",
                        "Manual",
                        "StrategySim Integration Test",
                        "Company",
                        company_id,
                        4,
                        actor_id,
                    ),
                )

                evidence_id = cursor.lastrowid
                db.commit()

                print("\nTest records created in temporary database.")
                print(f"Administrator ID: {actor_id}")
                print(f"Company ID: {company_id}")
                print(f"SWOT factor ID: {factor_id}")
                print(f"Evidence ID: {evidence_id}")

                # 1. Create evidence link.
                created_link = create_evidence_link(
                    evidence_id=evidence_id,
                    analysis_type="SWOT",
                    analysis_record_id=factor_id,
                    acting_user_id=actor_id,
                )

                link_id = (
                    created_link.get("id")
                    if isinstance(created_link, dict)
                    else None
                )

                check(
                    "Evidence link creation returns link details",
                    isinstance(created_link, dict)
                    and link_id is not None
                    and created_link.get("evidence_id") == evidence_id,
                )

                # 2. Retrieve evidence linked to the SWOT factor.
                factor_links = get_evidence_links(
                    analysis_type="SWOT",
                    analysis_record_id=factor_id,
                )

                check(
                    "Retrieve evidence links for SWOT factor",
                    len(factor_links) == 1
                    and factor_links[0].get("evidence_id") == evidence_id
                    and factor_links[0].get("link_id") == link_id,
                )

                # 3. Retrieve analytical links for evidence.
                evidence_links = get_evidence_analysis_links(evidence_id)

                check(
                    "Retrieve reverse links for evidence",
                    len(evidence_links) == 1
                    and evidence_links[0].get("link_id") == link_id
                    and evidence_links[0].get("analysis_type") == "SWOT",
                )

                # 4. Retrieve individual link details.
                details = get_evidence_link_details(link_id)

                check(
                    "Retrieve individual evidence-link details",
                    isinstance(details, dict)
                    and details.get("link_id") == link_id
                    and details.get("evidence_id") == evidence_id,
                )

                # 5. Reject duplicate links.
                expect_service_error(
                    "Reject duplicate evidence links",
                    lambda: create_evidence_link(
                        evidence_id=evidence_id,
                        analysis_type="SWOT",
                        analysis_record_id=factor_id,
                        acting_user_id=actor_id,
                    ),
                )

                # 6. Reject nonexistent evidence.
                expect_service_error(
                    "Reject nonexistent evidence ID",
                    lambda: create_evidence_link(
                        evidence_id=999999999,
                        analysis_type="SWOT",
                        analysis_record_id=factor_id,
                        acting_user_id=actor_id,
                    ),
                )

                # 7. Reject nonexistent analytical record.
                expect_service_error(
                    "Reject nonexistent SWOT factor ID",
                    lambda: create_evidence_link(
                        evidence_id=evidence_id,
                        analysis_type="SWOT",
                        analysis_record_id=999999999,
                        acting_user_id=actor_id,
                    ),
                )

                # 8. Delete only the association.
                delete_result = delete_evidence_link(
                    link_id=link_id,
                    acting_user_id=actor_id,
                )

                check(
                    "Delete evidence association",
                    delete_result is not False,
                )

                remaining_links = get_evidence_links(
                    analysis_type="SWOT",
                    analysis_record_id=factor_id,
                )

                check(
                    "Deleted association is no longer returned",
                    len(remaining_links) == 0,
                )

                evidence_still_exists = db.execute(
                    "SELECT id FROM evidence WHERE id = ?",
                    (evidence_id,),
                ).fetchone()

                check(
                    "Evidence record remains after unlinking",
                    evidence_still_exists is not None,
                )

                # 9. Verify audit entries for link and unlink.
                audit_count = db.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_logs
                    WHERE entity_id = ?
                      AND action IN (
                          'CREATE_EVIDENCE_LINK',
                          'DELETE_EVIDENCE_LINK'
                      )
                    """,
                    (link_id,),
                ).fetchone()[0]

                check(
                    "Audit entries recorded for link operations",
                    audit_count >= 2,
                )

                # 10. Verify temporary database integrity.
                integrity = db.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]

                foreign_key_errors = db.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()

                check(
                    "Temporary database integrity",
                    integrity == "ok",
                )

                check(
                    "Temporary database foreign-key integrity",
                    len(foreign_key_errors) == 0,
                )

            finally:
                db.rollback()
                db.close()
                g.pop("db", None)

    print("\n" + "=" * 55)
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    print(f"TOTAL:  {passed + failed}")

    if failed:
        print("\nINTEGRATION TEST FAILED.")
        raise SystemExit(1)

    print("\nALL EVIDENCE SERVICE INTEGRATION TESTS PASSED.")
    print("The original database was not modified by test inserts/deletes.")


if __name__ == "__main__":
    main()
