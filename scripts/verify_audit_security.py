
import sys
import uuid

from pathlib import Path


# ---------------------------------------------------------
# PROJECT ROOT
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------
# APPLICATION IMPORTS
# ---------------------------------------------------------

from app import create_app

from app.database.connection import get_db

from app.users.services import (
    create_user_account,
    update_user_account,
    update_user_status,
    SelfDeactivationError
)

from app.services.audit_service import (
    get_audit_logs,
    get_audit_log_summary
)


# ---------------------------------------------------------
# INITIALIZE TEST APPLICATION
# ---------------------------------------------------------

app = create_app("testing")

test_user_id = None


with app.app_context():

    print("\n")
    print("=" * 55)
    print(" STRATEGYSIM FINAL AUDIT AND SECURITY VERIFICATION")
    print("=" * 55)

    database = get_db()

    administrator = database.execute(
        """
        SELECT id
        FROM users
        WHERE role = 'Administrator'
          AND is_active = 1
        LIMIT 1
        """
    ).fetchone()

    if administrator is None:
        raise RuntimeError(
            "An active Administrator account is required."
        )

    administrator_id = administrator["id"]

    print("\nAdministrator account: FOUND")

    try:

        # -------------------------------------------------
        # TEST 1: CREATE TEST USER
        # -------------------------------------------------

        unique_identifier = uuid.uuid4().hex[:10]

        test_email = (
            f"strategysim.audit.{unique_identifier}@example.com"
        )

        test_password = (
            f"AuditTest!{unique_identifier}"
        )

        test_user_id = create_user_account(
            full_name="StrategySim Audit Test User",
            email=test_email,
            password=test_password,
            role="Viewer",
            created_by=administrator_id
        )

        print("1. User creation audit: PASSED")

        # -------------------------------------------------
        # TEST 2: UPDATE TEST USER
        # -------------------------------------------------

        update_user_account(
            user_id=test_user_id,
            full_name="StrategySim Updated Audit User",
            email=test_email,
            role="Analyst",
            acting_admin_id=administrator_id
        )

        print("2. User update audit: PASSED")

        # -------------------------------------------------
        # TEST 3: DEACTIVATE TEST USER
        # -------------------------------------------------

        deactivation_result = update_user_status(
            user_id=test_user_id,
            is_active=False,
            acting_admin_id=administrator_id
        )

        assert deactivation_result is True

        print("3. User deactivation audit: PASSED")

        # -------------------------------------------------
        # TEST 4: REACTIVATE TEST USER
        # -------------------------------------------------

        activation_result = update_user_status(
            user_id=test_user_id,
            is_active=True,
            acting_admin_id=administrator_id
        )

        assert activation_result is True

        print("4. User activation audit: PASSED")

        # -------------------------------------------------
        # TEST 5: VERIFY AUDIT RECORDS
        # -------------------------------------------------

        logs = get_audit_logs(
            limit=500,
            offset=0
        )

        test_logs = [
            log for log in logs
            if log["entity_type"] == "User"
            and log["entity_id"] == test_user_id
        ]

        expected_actions = {
            "USER_CREATED",
            "USER_UPDATED",
            "USER_DEACTIVATED",
            "USER_ACTIVATED"
        }

        recorded_actions = {
            log["action"]
            for log in test_logs
        }

        assert expected_actions.issubset(recorded_actions), (
            "One or more expected audit actions are missing."
        )

        print("5. All four audit records: PASSED")

        # -------------------------------------------------
        # TEST 6: VERIFY ADMINISTRATOR ID
        # -------------------------------------------------

        for log in test_logs:

            assert log["user_id"] == administrator_id, (
                "Incorrect Administrator ID in audit record."
            )

            assert log["performed_by"] is not None

        print("6. Administrator identification: PASSED")

        # -------------------------------------------------
        # TEST 7: VERIFY AUDIT DETAILS
        # -------------------------------------------------

        for log in test_logs:

            assert log["description"]
            assert log["entity_type"] == "User"
            assert log["entity_id"] == test_user_id

        print("7. Audit record details: PASSED")

        # -------------------------------------------------
        # TEST 8: CHECK PASSWORD EXPOSURE
        # -------------------------------------------------

        for log in test_logs:

            description = (
                log["description"] or ""
            ).lower()

            assert test_password.lower() not in description

            assert "password_hash" not in description

        print("8. No password exposure in audit records: PASSED")

        # -------------------------------------------------
        # TEST 9: SELF-DEACTIVATION PROTECTION
        # -------------------------------------------------

        try:

            update_user_status(
                user_id=administrator_id,
                is_active=False,
                acting_admin_id=administrator_id
            )

            raise AssertionError(
                "Administrator self-deactivation was allowed."
            )

        except SelfDeactivationError:

            print("9. Administrator self-deactivation protection: PASSED")

        # -------------------------------------------------
        # TEST 10: AUDIT SUMMARY
        # -------------------------------------------------

        summary = get_audit_log_summary()

        for action in expected_actions:

            assert summary["action_counts"].get(action, 0) >= 1

        print("10. Audit summary verification: PASSED")

        # -------------------------------------------------
        # TEST 11: PAGINATION VALIDATION
        # -------------------------------------------------

        try:

            get_audit_logs(
                limit=1000,
                offset=0
            )

            raise AssertionError(
                "Invalid pagination limit was accepted."
            )

        except ValueError:

            print("11. Pagination validation: PASSED")

        # -------------------------------------------------
        # TEST 12: UNAUTHENTICATED ACCESS
        # -------------------------------------------------

        with app.test_client() as client:

            response = client.get(
                "/users/audit",
                follow_redirects=False
            )

            assert response.status_code == 302, (
                "Unauthenticated access was not redirected."
            )

        print("12. Unauthenticated access protection: PASSED")

        # -------------------------------------------------
        # TEST 13: FINAL ACCOUNT VERIFICATION
        # -------------------------------------------------

        original_accounts = database.execute(
            """
            SELECT id, role, is_active
            FROM users
            WHERE id = ?
            """,
            (administrator_id,)
        ).fetchone()

        assert original_accounts is not None
        assert original_accounts["role"] == "Administrator"
        assert original_accounts["is_active"] == 1

        print("13. Existing Administrator account: PASSED")

        print("\n" + "=" * 55)
        print(" ALL AUDIT AND SECURITY TESTS PASSED")
        print("=" * 55)

    finally:

        # Remove only the temporary verification account.
        # Audit records remain preserved.

        if test_user_id is not None:

            database.execute(
                """
                DELETE FROM users
                WHERE id = ?
                """,
                (test_user_id,)
            )

            database.commit()

            print("\nTemporary test account cleaned up.")
            print("Existing user accounts preserved.")
            print("Audit records preserved.")
