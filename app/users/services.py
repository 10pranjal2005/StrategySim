
import sqlite3

from app.database.connection import get_db

from app.auth.security import hash_password

from app.services.audit_service import record_audit_log


# ---------------------------------------------------------
# USER MANAGEMENT EXCEPTIONS
# ---------------------------------------------------------

class UserAlreadyExistsError(Exception):
    pass


class InvalidUserRoleError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class LastActiveAdministratorError(Exception):
    pass


class SelfRoleChangeError(Exception):
    pass


class SelfDeactivationError(Exception):
    pass


# ---------------------------------------------------------
# CREATE USER ACCOUNT
# ---------------------------------------------------------

def create_user_account(full_name, email, password, role, created_by):

    full_name = full_name.strip()
    email = email.strip().lower()

    allowed_roles = {"Analyst", "Viewer"}

    if role not in allowed_roles:
        raise InvalidUserRoleError(
            "Only Analyst and Viewer accounts can be created here."
        )

    if not full_name:
        raise ValueError("Full name cannot be empty.")

    if not email:
        raise ValueError("Email address cannot be empty.")

    if not password or len(password) < 12 or len(password) > 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    try:
        created_by = int(created_by)
    except (TypeError, ValueError):
        raise ValueError("Invalid Administrator identifier.")

    password_hash = hash_password(password)
    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        existing_user = database.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            LIMIT 1
            """,
            (email,)
        ).fetchone()

        if existing_user:
            raise UserAlreadyExistsError(
                "An account with this email address already exists."
            )

        cursor = database.execute(
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
            (full_name, email, password_hash, role, 1)
        )

        user_id = cursor.lastrowid

        record_audit_log(
            user_id=created_by,
            action="USER_CREATED",
            entity_type="User",
            entity_id=user_id,
            description=(
                f"Created {role} account for {full_name} ({email})."
            ),
            commit=False
        )

        database.commit()

        return user_id

    except sqlite3.IntegrityError as error:
        database.rollback()

        if "users.email" in str(error).lower():
            raise UserAlreadyExistsError(
                "An account with this email address already exists."
            ) from error

        raise

    except Exception:
        database.rollback()
        raise


# ---------------------------------------------------------
# GET USER DETAILS FOR EDITING
# ---------------------------------------------------------

def get_user_details(user_id):

    database = get_db()

    row = database.execute(
        """
        SELECT
            id,
            full_name,
            email,
            role,
            is_active,
            last_login_at,
            created_at,
            updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    if row is None:
        return None

    return dict(row)


# ---------------------------------------------------------
# UPDATE USER ACCOUNT
# ---------------------------------------------------------

def update_user_account(
    user_id,
    full_name,
    email,
    role,
    acting_admin_id
):

    try:
        user_id = int(user_id)
        acting_admin_id = int(acting_admin_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid user identifier.")

    full_name = full_name.strip()
    email = email.strip().lower()

    allowed_roles = {
        "Administrator",
        "Analyst",
        "Viewer"
    }

    if role not in allowed_roles:
        raise InvalidUserRoleError(
            "The selected user role is invalid."
        )

    if not full_name:
        raise ValueError("Full name cannot be empty.")

    if not email:
        raise ValueError("Email address cannot be empty.")

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        target_user = database.execute(
            """
            SELECT id, full_name, email, role, is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if target_user is None:
            raise UserNotFoundError(
                "The requested user account does not exist."
            )

        current_role = target_user["role"]
        target_is_active = bool(target_user["is_active"])

        if user_id == acting_admin_id and role != current_role:
            raise SelfRoleChangeError(
                "You cannot change your own account role."
            )

        if (
            current_role == "Administrator"
            and target_is_active
            and role != "Administrator"
        ):

            active_admin_count = database.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE role = 'Administrator'
                  AND is_active = 1
                """
            ).fetchone()[0]

            if active_admin_count <= 1:
                raise LastActiveAdministratorError(
                    "The last active Administrator cannot be demoted."
                )

        existing_user = database.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
              AND id != ?
            LIMIT 1
            """,
            (email, user_id)
        ).fetchone()

        if existing_user:
            raise UserAlreadyExistsError(
                "Another account already uses this email address."
            )

        database.execute(
            """
            UPDATE users
            SET
                full_name = ?,
                email = ?,
                role = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (full_name, email, role, user_id)
        )

        record_audit_log(
            user_id=acting_admin_id,
            action="USER_UPDATED",
            entity_type="User",
            entity_id=user_id,
            description=(
                f"Updated account details for user ID {user_id}. "
                f"Role: {current_role} to {role}."
            ),
            commit=False
        )

        database.commit()

        return True

    except sqlite3.IntegrityError as error:
        database.rollback()

        if "users.email" in str(error).lower():
            raise UserAlreadyExistsError(
                "Another account already uses this email address."
            ) from error

        raise

    except Exception:
        database.rollback()
        raise


# ---------------------------------------------------------
# ACTIVATE OR DEACTIVATE USER ACCOUNT
# ---------------------------------------------------------

def update_user_status(user_id, is_active, acting_admin_id):

    try:
        user_id = int(user_id)
        acting_admin_id = int(acting_admin_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid user identifier.")

    if not isinstance(is_active, bool):
        raise ValueError("Invalid account status.")

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        target_user = database.execute(
            """
            SELECT
                id,
                full_name,
                email,
                role,
                is_active
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if target_user is None:
            raise UserNotFoundError(
                "The requested user account does not exist."
            )

        currently_active = bool(target_user["is_active"])
        target_role = target_user["role"]

        if currently_active == is_active:
            database.rollback()
            return False

        if not is_active and user_id == acting_admin_id:
            raise SelfDeactivationError(
                "You cannot deactivate your own account."
            )

        if not is_active and target_role == "Administrator":

            active_admin_count = database.execute(
                """
                SELECT COUNT(*)
                FROM users
                WHERE role = 'Administrator'
                  AND is_active = 1
                """
            ).fetchone()[0]

            if active_admin_count <= 1:
                raise LastActiveAdministratorError(
                    "The last active Administrator cannot be deactivated."
                )

        database.execute(
            """
            UPDATE users
            SET
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if is_active else 0, user_id)
        )

        action = (
            "USER_ACTIVATED"
            if is_active
            else "USER_DEACTIVATED"
        )

        action_description = (
            "Activated"
            if is_active
            else "Deactivated"
        )

        record_audit_log(
            user_id=acting_admin_id,
            action=action,
            entity_type="User",
            entity_id=user_id,
            description=(
                f"{action_description} account for "
                f"{target_user['full_name']} "
                f"({target_user['email']})."
            ),
            commit=False
        )

        database.commit()

        return True

    except Exception:
        database.rollback()
        raise
