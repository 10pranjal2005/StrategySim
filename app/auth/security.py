
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ---------------------------------------------------------
# PASSWORD HASHING
# ---------------------------------------------------------

def hash_password(password):
    """
    Converts a plain-text password into a secure hash.

    The resulting hash is stored in the database.

    Returns:
        Secure password hash.
    """

    if not password:

        raise ValueError(
            "Password cannot be empty."
        )

    return generate_password_hash(
        password,
        method="scrypt"
    )


# ---------------------------------------------------------
# PASSWORD VERIFICATION
# ---------------------------------------------------------

def verify_password(password_hash, password):
    """
    Checks whether a supplied password matches
    the stored password hash.

    Returns:
        True if the password matches.
        False otherwise.
    """

    if not password_hash or not password:

        return False

    try:

        return check_password_hash(
            password_hash,
            password
        )

    except (ValueError, TypeError):

        return False
