
from flask import (
    Blueprint,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    request
)

from flask_login import current_user

from app.database.connection import get_db

from app.utils.decorators import administrator_required

from app.users.forms import (
    CreateUserForm,
    EditUserForm
)

from app.users.services import (
    create_user_account,
    update_user_account,
    get_user_details,
    update_user_status,
    UserAlreadyExistsError,
    InvalidUserRoleError,
    UserNotFoundError,
    LastActiveAdministratorError,
    SelfRoleChangeError,
    SelfDeactivationError
)

from app.services.audit_service import (
    get_audit_logs,
    get_audit_log_summary
)


# ---------------------------------------------------------
# USER MANAGEMENT BLUEPRINT
# ---------------------------------------------------------

users_bp = Blueprint(
    "users",
    __name__,
    url_prefix="/users"
)


# ---------------------------------------------------------
# USER DIRECTORY API
# EXISTING JSON ENDPOINT - PRESERVED
# ---------------------------------------------------------

@users_bp.route("/", methods=["GET"])
@administrator_required
def user_directory():

    database = get_db()

    rows = database.execute(
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
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()

    users = []

    for row in rows:
        users.append({
            "id": row["id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "last_login_at": row["last_login_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    total_users = len(users)

    active_users = sum(
        1 for user in users
        if user["is_active"]
    )

    inactive_users = total_users - active_users

    role_counts = {
        "Administrator": 0,
        "Analyst": 0,
        "Viewer": 0
    }

    for user in users:
        if user["role"] in role_counts:
            role_counts[user["role"]] += 1

    return jsonify({
        "status": "success",
        "module": "user_management",
        "message": "User directory retrieved successfully.",
        "summary": {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "role_counts": role_counts
        },
        "users": users
    }), 200


# ---------------------------------------------------------
# USER DIRECTORY HTML PAGE
# NEW ADMINISTRATIVE INTERFACE
# ---------------------------------------------------------

@users_bp.route("/directory", methods=["GET"])
@administrator_required
def user_directory_page():

    database = get_db()

    rows = database.execute(
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
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()

    users = [
        {
            "id": row["id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "last_login_at": row["last_login_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]

    total_users = len(users)

    active_users = sum(
        1 for user in users
        if user["is_active"]
    )

    inactive_users = total_users - active_users

    role_counts = {
        "Administrator": 0,
        "Analyst": 0,
        "Viewer": 0
    }

    for user in users:
        if user["role"] in role_counts:
            role_counts[user["role"]] += 1

    return render_template(
        "users/directory.html",
        users=users,
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        role_counts=role_counts
    )


# ---------------------------------------------------------
# CREATE USER
# EXISTING HTML ROUTE - PRESERVED
# ---------------------------------------------------------

@users_bp.route("/create", methods=["GET", "POST"])
@administrator_required
def create_user():

    form = CreateUserForm()

    if form.validate_on_submit():

        try:
            user_id = create_user_account(
                full_name=form.full_name.data,
                email=form.email.data,
                password=form.password.data,
                role=form.role.data,
                created_by=current_user.id
            )

            flash(
                f"User account created successfully. User ID: {user_id}",
                "success"
            )

            return redirect(
                url_for("users.create_user")
            )

        except UserAlreadyExistsError as error:
            flash(str(error), "danger")

        except InvalidUserRoleError as error:
            flash(str(error), "danger")

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash(
                "An unexpected error occurred while creating the account.",
                "danger"
            )

    return render_template(
        "users/create_user.html",
        form=form
    )


# ---------------------------------------------------------
# EDIT USER
# EXISTING HTML ROUTE - PRESERVED
# ---------------------------------------------------------

@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@administrator_required
def edit_user(user_id):

    user = get_user_details(user_id)

    if user is None:
        abort(404)

    form = EditUserForm()

    if form.validate_on_submit():

        try:
            update_user_account(
                user_id=user_id,
                full_name=form.full_name.data,
                email=form.email.data,
                role=form.role.data,
                acting_admin_id=current_user.id
            )

            flash(
                "User account updated successfully.",
                "success"
            )

            return redirect(
                url_for("users.edit_user", user_id=user_id)
            )

        except UserAlreadyExistsError as error:
            flash(str(error), "danger")

        except LastActiveAdministratorError as error:
            flash(str(error), "danger")

        except SelfRoleChangeError as error:
            flash(str(error), "danger")

        except InvalidUserRoleError as error:
            flash(str(error), "danger")

        except UserNotFoundError:
            abort(404)

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash(
                "An unexpected error occurred while updating the account.",
                "danger"
            )

    elif not form.is_submitted():

        form.full_name.data = user["full_name"]
        form.email.data = user["email"]
        form.role.data = user["role"]

    return render_template(
        "users/edit_user.html",
        form=form,
        user=user
    )


# ---------------------------------------------------------
# ACTIVATE USER
# EXISTING ROUTE - PRESERVED
# ---------------------------------------------------------

@users_bp.route("/<int:user_id>/activate", methods=["POST"])
@administrator_required
def activate_user(user_id):

    try:
        changed = update_user_status(
            user_id=user_id,
            is_active=True,
            acting_admin_id=current_user.id
        )

        if changed:
            flash(
                "User account activated successfully.",
                "success"
            )
        else:
            flash(
                "This account is already active.",
                "warning"
            )

    except UserNotFoundError:
        abort(404)

    except Exception:
        flash(
            "The account could not be activated.",
            "danger"
        )

    return redirect(
        url_for("users.edit_user", user_id=user_id)
    )


# ---------------------------------------------------------
# DEACTIVATE USER
# EXISTING ROUTE - PRESERVED
# ---------------------------------------------------------

@users_bp.route("/<int:user_id>/deactivate", methods=["POST"])
@administrator_required
def deactivate_user(user_id):

    try:
        changed = update_user_status(
            user_id=user_id,
            is_active=False,
            acting_admin_id=current_user.id
        )

        if changed:
            flash(
                "User account deactivated successfully.",
                "success"
            )
        else:
            flash(
                "This account is already inactive.",
                "warning"
            )

    except UserNotFoundError:
        abort(404)

    except SelfDeactivationError as error:
        flash(str(error), "danger")

    except LastActiveAdministratorError as error:
        flash(str(error), "danger")

    except Exception:
        flash(
            "The account could not be deactivated.",
            "danger"
        )

    return redirect(
        url_for("users.edit_user", user_id=user_id)
    )


# ---------------------------------------------------------
# AUDIT LOG API
# EXISTING JSON ENDPOINT - PRESERVED
# ---------------------------------------------------------

@users_bp.route("/audit", methods=["GET"])
@administrator_required
def audit_directory():

    try:
        limit = request.args.get("limit", default=100, type=int)
        offset = request.args.get("offset", default=0, type=int)

        logs = get_audit_logs(
            limit=limit,
            offset=offset
        )

        summary = get_audit_log_summary()

        return jsonify({
            "status": "success",
            "module": "audit_management",
            "message": "Audit records retrieved successfully.",
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned_records": len(logs)
            },
            "summary": summary,
            "audit_logs": logs
        }), 200

    except ValueError as error:

        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:

        return jsonify({
            "status": "error",
            "message": "Unable to retrieve audit records."
        }), 500


# ---------------------------------------------------------
# AUDIT LOG HTML PAGE
# NEW ADMINISTRATIVE INTERFACE
# ---------------------------------------------------------

@users_bp.route("/audit/page", methods=["GET"])
@administrator_required
def audit_page():

    try:
        page = request.args.get("page", default=1, type=int)

        if page is None or page < 1:
            page = 1

        limit = 25

        summary = get_audit_log_summary()
        total_logs = summary["total_logs"]

        total_pages = max(
            1,
            (total_logs + limit - 1) // limit
        )

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * limit

        logs = get_audit_logs(
            limit=limit,
            offset=offset
        )

        return render_template(
            "users/audit_logs.html",
            logs=logs,
            summary=summary,
            total_logs=total_logs,
            page=page,
            limit=limit,
            total_pages=total_pages
        )

    except ValueError as error:

        flash(str(error), "danger")

        return redirect(
            url_for("dashboard.dashboard_home")
        )

    except Exception:

        flash(
            "Unable to load audit records.",
            "danger"
        )

        return redirect(
            url_for("dashboard.dashboard_home")
        )
