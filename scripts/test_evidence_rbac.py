import sys
import shutil
import sqlite3
import tempfile
from pathlib import Path

# ---------------------------------------------------------
# PROJECT PATH
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------
# APPLICATION IMPORTS
# ---------------------------------------------------------

from app import create_app, login_manager
from app.config import configurations


# ---------------------------------------------------------
# TEST CONFIGURATION
# ---------------------------------------------------------

ORIGINAL_DATABASE = PROJECT_ROOT / "instance" / "strategysim.db"

EXPECTED_ROLES = {
    "Administrator",
    "Analyst",
    "Viewer",
}


# ---------------------------------------------------------
# TEST UTILITIES
# ---------------------------------------------------------

passed = 0
failed = 0


def check(label, actual, expected):
    global passed, failed

    if actual == expected:
        passed += 1
        print(f"[PASS] {label}: HTTP {actual}")
    else:
        failed += 1
        print(
            f"[FAIL] {label}: "
            f"expected HTTP {expected}, got HTTP {actual}"
        )


def authenticate_as(client, user):
    """
    Establish an authenticated Flask-Login test session.
    Session protection is disabled only in this test process.
    """

    with client.session_transaction() as session:
        session.clear()
        session["_user_id"] = str(user["id"])
        session["_fresh"] = True


# ---------------------------------------------------------
# MAIN TEST
# ---------------------------------------------------------

def main():
    global passed, failed

    passed = 0
    failed = 0

    if not ORIGINAL_DATABASE.exists():
        raise FileNotFoundError(
            f"Original database not found: {ORIGINAL_DATABASE}"
        )

    with tempfile.TemporaryDirectory(
        prefix="strategysim_evidence_rbac_"
    ) as temporary_directory:

        temporary_database = (
            Path(temporary_directory) / "strategysim_test.db"
        )

        # -------------------------------------------------
        # STEP 1: COPY ORIGINAL DATABASE
        # -------------------------------------------------

        shutil.copy2(
            ORIGINAL_DATABASE,
            temporary_database
        )

        print("[OK] Temporary database copy created.")

        connection = sqlite3.connect(temporary_database)
        connection.row_factory = sqlite3.Row

        users = connection.execute(
            """
            SELECT id, full_name, role, is_active
            FROM users
            WHERE role IN ('Administrator', 'Analyst', 'Viewer')
              AND is_active = 1
            ORDER BY id
            """
        ).fetchall()

        connection.close()

        users_by_role = {
            user["role"]: dict(user)
            for user in users
        }

        missing_roles = EXPECTED_ROLES - set(users_by_role)

        if missing_roles:
            raise RuntimeError(
                "Missing active test accounts for roles: "
                + ", ".join(sorted(missing_roles))
            )

        print("\n[OK] Active test accounts found:")

        for role in sorted(EXPECTED_ROLES):
            user = users_by_role[role]
            print(
                f"  {role}: user ID {user['id']} "
                f"({user['full_name']})"
            )

        # -------------------------------------------------
        # STEP 2: CREATE ISOLATED TEST CONFIGURATION
        # -------------------------------------------------

        base_config = configurations["development"]

        TestConfig = type(
            "EvidenceRBACTestConfig",
            (base_config,),
            {
                "DATABASE_PATH": str(temporary_database),
                "WTF_CSRF_ENABLED": False,
                "TESTING": True,
            },
        )

        configurations["evidence_rbac_test"] = TestConfig

        try:
            app = create_app("evidence_rbac_test")

            # Disable session protection only for this test.
            # Production configuration is not modified.
            original_session_protection = (
                login_manager.session_protection
            )

            login_manager.session_protection = None

            try:
                client = app.test_client()

                # -----------------------------------------
                # STEP 3: CREATE TEMPORARY EVIDENCE RECORD
                # -----------------------------------------

                from app.evidence.services import create_evidence

                admin_id = users_by_role["Administrator"]["id"]

                with app.app_context():
                    evidence = create_evidence(
                        title="RBAC Temporary Test Evidence",
                        acting_user_id=admin_id,
                        description=(
                            "Temporary record created exclusively "
                            "for Evidence RBAC testing."
                        ),
                        source_type="Manual",
                        source_name="RBAC Test Script",
                        reliability_score=4,
                    )

                evidence_id = evidence["id"]

                print(
                    "\n[OK] Temporary evidence record created "
                    f"with ID {evidence_id}."
                )

                # -----------------------------------------
                # STEP 4: VIEW PERMISSION TESTS
                # -----------------------------------------

                print("\nVIEW PERMISSION TESTS")
                print("-" * 55)

                for role in [
                    "Administrator",
                    "Analyst",
                    "Viewer",
                ]:
                    authenticate_as(
                        client,
                        users_by_role[role]
                    )

                    response = client.get("/evidence/")

                    check(
                        f"{role} can view Evidence Repository",
                        response.status_code,
                        200,
                    )

                # -----------------------------------------
                # STEP 5: CREATE PERMISSION TESTS
                # -----------------------------------------

                print("\nCREATE PERMISSION TESTS")
                print("-" * 55)

                create_data = {
                    "title": "Viewer Create Permission Test",
                    "description": "Permission test only",
                    "source_type": "Manual",
                    "source_name": "RBAC Test",
                    "source_url": "",
                    "file_path": "",
                    "entity_type": "",
                    "entity_id": "",
                    "reliability_score": "4",
                }

                for role, expected in [
                    ("Administrator", 200),
                    ("Analyst", 200),
                    ("Viewer", 403),
                ]:
                    authenticate_as(
                        client,
                        users_by_role[role]
                    )

                    response = client.get("/evidence/new")

                    check(
                        f"{role} create-page access",
                        response.status_code,
                        expected,
                    )

                # Viewer must also be blocked on POST.
                authenticate_as(
                    client,
                    users_by_role["Viewer"]
                )

                response = client.post(
                    "/evidence/new",
                    data=create_data,
                )

                check(
                    "Viewer cannot submit evidence creation",
                    response.status_code,
                    403,
                )

                # -----------------------------------------
                # STEP 6: EDIT PAGE PERMISSION TESTS
                # -----------------------------------------

                print("\nEDIT PERMISSION TESTS")
                print("-" * 55)

                for role, expected in [
                    ("Administrator", 200),
                    ("Analyst", 200),
                    ("Viewer", 403),
                ]:
                    authenticate_as(
                        client,
                        users_by_role[role]
                    )

                    response = client.get(
                        f"/evidence/{evidence_id}/edit"
                    )

                    check(
                        f"{role} edit-page access",
                        response.status_code,
                        expected,
                    )

                # -----------------------------------------
                # STEP 7: VIEWER EDIT POST TEST
                # -----------------------------------------

                print("\nEDIT SUBMISSION PERMISSION TEST")
                print("-" * 55)

                edit_data = {
                    "title": "Viewer Attempted Modification",
                    "description": "This must not be saved.",
                    "source_type": "Manual",
                    "source_name": "RBAC Test",
                    "source_url": "",
                    "file_path": "",
                    "entity_type": "",
                    "entity_id": "",
                    "reliability_score": "4",
                }

                authenticate_as(
                    client,
                    users_by_role["Viewer"]
                )

                response = client.post(
                    f"/evidence/{evidence_id}/edit",
                    data=edit_data,
                )

                check(
                    "Viewer cannot submit evidence edits",
                    response.status_code,
                    403,
                )

                # -----------------------------------------
                # STEP 8: VIEWER DELETE POST TEST
                # -----------------------------------------

                print("\nDELETE PERMISSION TEST")
                print("-" * 55)

                authenticate_as(
                    client,
                    users_by_role["Viewer"]
                )

                response = client.post(
                    f"/evidence/{evidence_id}/delete"
                )

                check(
                    "Viewer cannot delete evidence",
                    response.status_code,
                    403,
                )

                # -----------------------------------------
                # STEP 9: VERIFY RECORD REMAINS UNCHANGED
                # -----------------------------------------

                print("\nDATA PRESERVATION TEST")
                print("-" * 55)

                connection = sqlite3.connect(
                    temporary_database
                )
                connection.row_factory = sqlite3.Row

                remaining_evidence = connection.execute(
                    """
                    SELECT id, title
                    FROM evidence
                    WHERE id = ?
                    """,
                    (evidence_id,),
                ).fetchone()

                connection.close()

                if remaining_evidence is not None:
                    passed += 1
                    print(
                        "[PASS] Temporary evidence record "
                        "still exists after Viewer requests."
                    )
                else:
                    failed += 1
                    print(
                        "[FAIL] Temporary evidence record "
                        "was unexpectedly deleted."
                    )

                if (
                    remaining_evidence is not None
                    and remaining_evidence["title"]
                    == "RBAC Temporary Test Evidence"
                ):
                    passed += 1
                    print(
                        "[PASS] Evidence title remains unchanged."
                    )
                else:
                    failed += 1
                    print(
                        "[FAIL] Evidence title was modified."
                    )

                # -----------------------------------------
                # STEP 10: DATABASE INTEGRITY
                # -----------------------------------------

                print("\nDATABASE INTEGRITY TEST")
                print("-" * 55)

                connection = sqlite3.connect(
                    temporary_database
                )

                integrity_result = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]

                foreign_key_result = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()

                connection.close()

                if integrity_result == "ok":
                    passed += 1
                    print("[PASS] SQLite integrity check.")
                else:
                    failed += 1
                    print(
                        "[FAIL] SQLite integrity check: "
                        f"{integrity_result}"
                    )

                if not foreign_key_result:
                    passed += 1
                    print("[PASS] Foreign-key check.")
                else:
                    failed += 1
                    print(
                        "[FAIL] Foreign-key violations found."
                    )

            finally:
                login_manager.session_protection = (
                    original_session_protection
                )

        finally:
            configurations.pop(
                "evidence_rbac_test",
                None
            )

    # -----------------------------------------------------
    # FINAL SUMMARY
    # -----------------------------------------------------

    print("\n" + "=" * 55)
    print("EVIDENCE RBAC TEST SUMMARY")
    print("=" * 55)

    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")

    print("\n[OK] All test operations used a temporary database copy.")
    print("[OK] The original database was not used for test CRUD.")

    if failed == 0:
        print("\nALL EVIDENCE RBAC TESTS PASSED.")
    else:
        print("\nSOME EVIDENCE RBAC TESTS FAILED.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()