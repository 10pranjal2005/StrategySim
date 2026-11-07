
from flask import has_request_context, request

from app.database.connection import get_db


# ---------------------------------------------------------
# AUDIT LOGGING SERVICE
# ---------------------------------------------------------

def record_audit_log(
    user_id,
    action,
    entity_type=None,
    entity_id=None,
    description=None,
    commit=True
):
    """
    Records an application activity in the audit_logs table.

    commit=True:
        Commits the audit record immediately.

    commit=False:
        Adds the audit record to the current database
        transaction. The calling service must commit it.

    Passwords, password hashes and authentication secrets
    must never be included in audit descriptions.
    """

    if not action or not str(action).strip():
        raise ValueError("Audit action cannot be empty.")

    if not isinstance(commit, bool):
        raise ValueError("Invalid audit commit setting.")

    if user_id is not None:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid audit user identifier.")

    if entity_id is not None:
        try:
            entity_id = int(entity_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid audit entity identifier.")

    ip_address = None

    if has_request_context():
        ip_address = request.remote_addr

    database = get_db()

    database.execute(
        """
        INSERT INTO audit_logs (
            user_id,
            action,
            entity_type,
            entity_id,
            description,
            ip_address
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            str(action).strip(),
            entity_type,
            entity_id,
            description,
            ip_address
        )
    )

    if commit:
        database.commit()

    return True


# ---------------------------------------------------------
# RETRIEVE AUDIT LOGS
# ---------------------------------------------------------

def get_audit_logs(limit=100, offset=0):

    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        raise ValueError("Invalid audit pagination values.")

    if limit < 1 or limit > 500:
        raise ValueError("Audit limit must be between 1 and 500.")

    if offset < 0:
        raise ValueError("Audit offset cannot be negative.")

    database = get_db()

    rows = database.execute(
        """
        SELECT
            audit_logs.id,
            audit_logs.user_id,
            users.full_name AS performed_by,
            users.email AS performed_by_email,
            audit_logs.action,
            audit_logs.entity_type,
            audit_logs.entity_id,
            audit_logs.description,
            audit_logs.ip_address,
            audit_logs.created_at
        FROM audit_logs
        LEFT JOIN users
            ON users.id = audit_logs.user_id
        ORDER BY audit_logs.id DESC
        LIMIT ?
        OFFSET ?
        """,
        (limit, offset)
    ).fetchall()

    return [dict(row) for row in rows]


# ---------------------------------------------------------
# AUDIT LOG SUMMARY
# ---------------------------------------------------------

def get_audit_log_summary():

    database = get_db()

    total_logs = database.execute(
        """
        SELECT COUNT(*)
        FROM audit_logs
        """
    ).fetchone()[0]

    action_rows = database.execute(
        """
        SELECT
            action,
            COUNT(*) AS total
        FROM audit_logs
        GROUP BY action
        ORDER BY total DESC
        """
    ).fetchall()

    return {
        "total_logs": total_logs,
        "action_counts": {
            row["action"]: row["total"]
            for row in action_rows
        }
    }
