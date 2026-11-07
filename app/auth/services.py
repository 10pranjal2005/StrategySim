
import sqlite3

from app.database.connection import get_db

from app.auth.security import (
    hash_password,
    verify_password
)

from app.users.models import User


# ---------------------------------------------------------
# CUSTOM SETUP EXCEPTIONS
# ---------------------------------------------------------

class SetupAlreadyCompletedError(Exception):
    """
    Raised when an initial administrator already exists.
    """
    pass


class EmailAlreadyExistsError(Exception):
    """
    Raised when the supplied email is already registered.
    """
    pass


# ---------------------------------------------------------
# INITIAL SETUP STATUS
# ---------------------------------------------------------

def is_initial_setup_required():
    """
    Checks whether StrategySim requires initial setup.

    Returns:
        True: No administrator exists.
        False: An administrator already exists.
    """

    database = get_db()

    result = database.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE role = ?
        """,
        ("Administrator",)
    ).fetchone()

    administrator_count = result[0]

    return administrator_count == 0


# ---------------------------------------------------------
# CREATE INITIAL ADMINISTRATOR
# ---------------------------------------------------------

def create_initial_administrator(
    full_name,
    email,
    password
):
    """
    Creates the first StrategySim administrator.
    """

    full_name = full_name.strip()

    email = email.strip().lower()

    password_hash = hash_password(password)

    database = get_db()

    try:

        database.execute(
            "BEGIN IMMEDIATE"
        )

        existing_administrator = database.execute(
            """
            SELECT id
            FROM users
            WHERE role = ?
            LIMIT 1
            """,
            ("Administrator",)
        ).fetchone()

        if existing_administrator:

            raise SetupAlreadyCompletedError(
                "Initial administrator setup has already been completed."
            )

        existing_user = database.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:

            raise EmailAlreadyExistsError(
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
            (
                full_name,
                email,
                password_hash,
                "Administrator",
                1
            )
        )

        administrator_id = cursor.lastrowid

        database.commit()

        return administrator_id

    except sqlite3.IntegrityError as error:

        database.rollback()

        if "users.email" in str(error).lower():

            raise EmailAlreadyExistsError(
                "An account with this email address already exists."
            ) from error

        raise

    except Exception:

        database.rollback()

        raise


# ---------------------------------------------------------
# AUTHENTICATE USER
# ---------------------------------------------------------

def authenticate_user(email, password):
    """
    Authenticates a user using their email and password.

    Returns:
        User object if authentication succeeds.
        None if credentials are invalid or account is inactive.

    The same failure result is returned for invalid
    credentials and inactive accounts.
    """

    if not email or not password:

        return None

    email = email.strip()

    user = User.get_by_email(email)

    if user is None:

        return None

    if not user.is_active:

        return None

    password_is_valid = verify_password(
        user.password_hash,
        password
    )

    if not password_is_valid:

        return None

    return user


# ---------------------------------------------------------
# UPDATE LAST LOGIN
# ---------------------------------------------------------

def update_last_login(user_id):
    """
    Updates the last_login_at timestamp for a user.

    Returns:
        True if a user record was updated.
        False if no matching user exists.
    """

    database = get_db()

    cursor = database.execute(
        """
        UPDATE users

        SET
            last_login_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP

        WHERE id = ?
          AND is_active = 1
        """,
        (user_id,)
    )

    database.commit()

    return cursor.rowcount == 1

def create_registered_user(full_name, email, password):
    """
    Creates a public registration account.

    Public registrations are always assigned the Viewer role.
    Role selection is deliberately not accepted from the client.
    """

    import sqlite3

    from app.database.connection import get_db
    from app.auth.security import hash_password
    from app.services.audit_service import record_audit_log

    full_name = full_name.strip()
    email = email.strip().lower()

    if not full_name or not email or not password:
        raise ValueError("All registration fields are required.")

    if len(full_name) < 2 or len(full_name) > 100:
        raise ValueError("Please enter a valid full name.")

    if len(password) < 12 or len(password) > 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    database = get_db()

    try:
        database.execute("BEGIN IMMEDIATE")

        existing_user = database.execute(
            """
            SELECT id
            FROM users
            WHERE LOWER(email) = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:
            database.rollback()
            raise EmailAlreadyExistsError(
                "An account with this email already exists."
            )

        password_hash = hash_password(password)

        cursor = database.execute(
            """
            INSERT INTO users (
                full_name,
                email,
                password_hash,
                role,
                is_active
            )
            VALUES (?, ?, ?, 'Viewer', 1)
            """,
            (
                full_name,
                email,
                password_hash
            )
        )

        user_id = cursor.lastrowid
        database.commit()

    except EmailAlreadyExistsError:
        raise

    except sqlite3.IntegrityError as error:
        database.rollback()

        raise EmailAlreadyExistsError(
            "An account with this email already exists."
        ) from error

    except Exception:
        database.rollback()
        raise

    # Record the successful registration using the existing
    # application audit service.
    record_audit_log(
        user_id=user_id,
        action="CREATE",
        entity_type="User",
        entity_id=user_id,
        description="New user registered through public registration."
    )

    return user_id