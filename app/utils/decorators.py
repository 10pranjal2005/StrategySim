
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


# ---------------------------------------------------------
# ROLE-BASED AUTHORIZATION
# ---------------------------------------------------------

def roles_required(*allowed_roles):
    """
    Restrict access to users whose roles are explicitly allowed.

    Example:
        @roles_required("Administrator", "Analyst")
    """

    if not allowed_roles:
        raise ValueError("At least one allowed role must be specified.")

    valid_roles = {
        "Administrator",
        "Analyst",
        "Viewer"
    }

    if not set(allowed_roles).issubset(valid_roles):
        raise ValueError("An invalid user role was specified.")

    def decorator(view_function):

        @wraps(view_function)
        @login_required
        def wrapped_view(*args, **kwargs):

            if not current_user.has_role(*allowed_roles):
                abort(403)

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


# ---------------------------------------------------------
# ADMINISTRATOR ACCESS
# ---------------------------------------------------------

def administrator_required(view_function):
    """
    Allow access exclusively to Administrators.
    """

    return roles_required("Administrator")(view_function)


# ---------------------------------------------------------
# ANALYST ACCESS
# ---------------------------------------------------------

def analyst_required(view_function):
    """
    Allow access to Administrators and Analysts.
    """

    return roles_required(
        "Administrator",
        "Analyst"
    )(view_function)


# ---------------------------------------------------------
# AUTHENTICATED USER ACCESS
# ---------------------------------------------------------

def authenticated_required(view_function):
    """
    Allow access to any authenticated and active user.
    """

    return login_required(view_function)
