
from flask_login import UserMixin

from app.database.connection import get_db


# ---------------------------------------------------------
# USER MODEL
# ---------------------------------------------------------

class User(UserMixin):
    """
    Represents an authenticated StrategySim user.

    User records are stored in the SQLite users table.
    """

    def __init__(
        self,
        user_id,
        full_name,
        email,
        password_hash,
        role,
        is_active,
        last_login_at=None,
        created_at=None,
        updated_at=None
    ):

        self.id = str(user_id)

        self.full_name = full_name

        self.email = email

        self.password_hash = password_hash

        self.role = role

        self._is_active = bool(is_active)

        self.last_login_at = last_login_at

        self.created_at = created_at

        self.updated_at = updated_at

    # -----------------------------------------------------
    # ACCOUNT STATUS
    # -----------------------------------------------------

    @property
    def is_active(self):
        """
        Flask-Login uses this property to determine whether
        an account is permitted to authenticate.
        """

        return self._is_active

    # -----------------------------------------------------
    # ROLE VALIDATION
    # -----------------------------------------------------

    def has_role(self, *allowed_roles):
        """
        Checks whether the user has one of the supplied roles.

        Example:
            user.has_role("Administrator")
        """

        return self.role in allowed_roles

    @property
    def is_administrator(self):

        return self.role == "Administrator"

    @property
    def is_analyst(self):

        return self.role == "Analyst"

    @property
    def is_viewer(self):

        return self.role == "Viewer"

    # -----------------------------------------------------
    # DATABASE ROW CONVERSION
    # -----------------------------------------------------

    @classmethod
    def from_row(cls, row):
        """
        Converts a SQLite database row into a User object.
        """

        if row is None:
            return None

        return cls(
            user_id=row["id"],
            full_name=row["full_name"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=row["is_active"],
            last_login_at=row["last_login_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    # -----------------------------------------------------
    # RETRIEVE USER BY ID
    # -----------------------------------------------------

    @classmethod
    def get_by_id(cls, user_id):
        """
        Retrieves a user using their database ID.

        Returns:
            User object if found.
            None if the user does not exist.
        """

        try:
            user_id = int(user_id)

        except (TypeError, ValueError):

            return None

        database = get_db()

        row = database.execute(
            """
            SELECT
                id,
                full_name,
                email,
                password_hash,
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

        return cls.from_row(row)

    # -----------------------------------------------------
    # RETRIEVE USER BY EMAIL
    # -----------------------------------------------------

    @classmethod
    def get_by_email(cls, email):
        """
        Retrieves a user using their email address.

        The database column already uses COLLATE NOCASE,
        so email matching is case-insensitive.
        """

        if not email:
            return None

        database = get_db()

        row = database.execute(
            """
            SELECT
                id,
                full_name,
                email,
                password_hash,
                role,
                is_active,
                last_login_at,
                created_at,
                updated_at
            FROM users
            WHERE email = ?
            """,
            (email.strip(),)
        ).fetchone()

        return cls.from_row(row)
