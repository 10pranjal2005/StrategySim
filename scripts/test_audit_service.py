
import sys
from pathlib import Path

# Add the StrategySim project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app import create_app
from app.database.connection import get_db

from app.services.audit_service import (
    record_audit_log,
    get_audit_logs,
    get_audit_log_summary
)


app = create_app("testing")


with app.app_context():

    print("\nTesting StrategySim Audit Logging...\n")

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
            "No active Administrator account was found."
        )

    administrator_id = administrator["id"]

    # Create a test audit entry.
    record_audit_log(
        user_id=administrator_id,
        action="AUDIT_TEST",
        entity_type="System",
        entity_id=None,
        description="Audit service verification."
    )

    print("Audit record creation: PASSED")

    # Retrieve audit records.
    logs = get_audit_logs(limit=10)

    matching_logs = [
        log for log in logs
        if log["action"] == "AUDIT_TEST"
        and log["user_id"] == administrator_id
    ]

    assert matching_logs, "Test audit record was not found."

    print("Audit record retrieval: PASSED")

    # Check audit record details.
    test_log = matching_logs[0]

    assert test_log["performed_by"] is not None
    assert test_log["entity_type"] == "System"
    assert test_log["description"] == (
        "Audit service verification."
    )

    print("Audit record details: PASSED")

    # Check summary.
    summary = get_audit_log_summary()

    assert summary["total_logs"] >= 1
    assert summary["action_counts"]["AUDIT_TEST"] >= 1

    print("Audit summary: PASSED")

    # Check pagination validation.
    try:
        get_audit_logs(limit=1000)
        raise AssertionError("Invalid limit was accepted.")
    except ValueError:
        print("Audit pagination validation: PASSED")

    print("\nALL AUDIT SERVICE TESTS PASSED.")
