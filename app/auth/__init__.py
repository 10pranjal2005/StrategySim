
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify
)

from flask_login import (
    current_user,
    login_user,
    logout_user,
    login_required
)

from app.auth.forms import (
    AdministratorSetupForm,
    LoginForm,
    RegistrationForm
)

from app.auth.services import (
    is_initial_setup_required,
    create_initial_administrator,
    authenticate_user,
    update_last_login,
    create_registered_user,
    SetupAlreadyCompletedError,
    EmailAlreadyExistsError
)


# ---------------------------------------------------------
# AUTHENTICATION BLUEPRINT
# ---------------------------------------------------------

auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


# ---------------------------------------------------------
# SAFE REDIRECT VALIDATION
# ---------------------------------------------------------

def is_safe_redirect_url(target):
    """
    Prevents external or unsafe redirect destinations.

    Only local absolute paths are accepted.
    """

    if not target:
        return False

    try:
        parsed_url = urlsplit(target)

        return (
            not parsed_url.scheme
            and not parsed_url.netloc
            and parsed_url.path.startswith("/")
            and not parsed_url.path.startswith("//")
            and "\\" not in target
            and "\r" not in target
            and "\n" not in target
        )

    except ValueError:
        return False


# ---------------------------------------------------------
# AUTHENTICATION STATUS
# ---------------------------------------------------------

@auth_bp.route(
    "/status",
    methods=["GET"]
)
def auth_status():

    return jsonify({
        "status": "success",
        "module": "authentication",
        "message": "Authentication module is registered."
    }), 200


# ---------------------------------------------------------
# INITIAL ADMINISTRATOR SETUP
# ---------------------------------------------------------

@auth_bp.route(
    "/setup",
    methods=["GET", "POST"]
)
def initial_setup():
    """
    Creates the first StrategySim administrator.
    """

    if not is_initial_setup_required():

        return render_template(
            "auth/setup_closed.html"
        ), 403

    form = AdministratorSetupForm()

    if form.validate_on_submit():

        try:

            administrator_id = create_initial_administrator(
                full_name=form.full_name.data,
                email=form.email.data,
                password=form.password.data
            )

            flash(
                "Your administrator account has been created successfully.",
                "success"
            )

            return render_template(
                "auth/setup_complete.html",
                administrator_id=administrator_id
            ), 201

        except SetupAlreadyCompletedError:

            return render_template(
                "auth/setup_closed.html"
            ), 403

        except EmailAlreadyExistsError:

            form.email.errors.append(
                "This email address is already registered."
            )

            flash(
                "Please use a different email address.",
                "danger"
            )

        except Exception:

            flash(
                "Administrator creation failed. Please try again.",
                "danger"
            )

    return render_template(
        "auth/setup.html",
        form=form
    )


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

@auth_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():
    """
    Authenticates an existing StrategySim user.

    All authenticated users are redirected to the
    graphical dashboard unless a safe local next URL
    has explicitly been requested.
    """

    # -----------------------------------------------------
    # CHECK INITIAL SETUP
    # -----------------------------------------------------

    if is_initial_setup_required():

        return redirect(
            url_for("auth.initial_setup")
        )

    # -----------------------------------------------------
    # HANDLE ALREADY AUTHENTICATED USERS
    # -----------------------------------------------------

    if current_user.is_authenticated:

        target = request.args.get("next", "")

        if is_safe_redirect_url(target):

            return redirect(target)

        return redirect(
            url_for("dashboard.dashboard_home")
        )

    # -----------------------------------------------------
    # CREATE LOGIN FORM
    # -----------------------------------------------------

    form = LoginForm()

    if request.method == "GET":

        form.next.data = request.args.get(
            "next",
            ""
        )

    # -----------------------------------------------------
    # PROCESS LOGIN SUBMISSION
    # -----------------------------------------------------

    if form.validate_on_submit():

        user = authenticate_user(
            email=form.email.data,
            password=form.password.data
        )

        if user is None:

            flash(
                "Invalid email address or password.",
                "danger"
            )

            return render_template(
                "auth/login.html",
                form=form
            ), 401

        # Update last login before creating the session.

        login_timestamp_updated = update_last_login(
            user.id
        )

        if not login_timestamp_updated:

            flash(
                "Unable to complete sign in. Please try again.",
                "danger"
            )

            return render_template(
                "auth/login.html",
                form=form
            ), 500

        # -------------------------------------------------
        # CREATE AUTHENTICATED SESSION
        # -------------------------------------------------

        login_user(
            user,
            remember=False,
            fresh=True
        )

        # -------------------------------------------------
        # VALIDATE REDIRECT DESTINATION
        # -------------------------------------------------

        target = form.next.data

        if is_safe_redirect_url(target):

            return redirect(target)

        # -------------------------------------------------
        # DEFAULT REDIRECT: GRAPHICAL DASHBOARD
        # -------------------------------------------------

        return redirect(
            url_for("dashboard.dashboard_home")
        )

    # -----------------------------------------------------
    # DISPLAY LOGIN PAGE
    # -----------------------------------------------------

    return render_template(
        "auth/login.html",
        form=form
    )

@auth_bp.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    # The initial administrator must be created first.
    if is_initial_setup_required():
        return redirect(url_for("auth.setup"))

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard_home"))

    form = RegistrationForm()

    if form.validate_on_submit():

        try:
            create_registered_user(
                full_name=form.full_name.data,
                email=form.email.data,
                password=form.password.data
            )

            flash(
                "Your account has been created successfully. "
                "Please sign in.",
                "success"
            )

            return redirect(url_for("auth.login"))

        except EmailAlreadyExistsError as error:

            flash(str(error), "danger")

        except Exception:

            flash(
                "We could not create your account. "
                "Please try again.",
                "danger"
            )

    return render_template(
        "auth/register.html",
        form=form
    )


# ---------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------

@auth_bp.route(
    "/logout",
    methods=["POST"]
)
@login_required
def logout():
    """
    Logs out the current authenticated user.

    Logout uses POST to prevent unwanted logout
    requests triggered by external links or images.
    """

    logout_user()

    flash(
        "You have been signed out successfully.",
        "success"
    )

    return redirect(
        url_for("auth.login")
    )


# ---------------------------------------------------------
# CURRENT AUTHENTICATED USER
# ---------------------------------------------------------

@auth_bp.route(
    "/me",
    methods=["GET"]
)
@login_required
def current_session():
    """
    Returns information about the currently
    authenticated user.
    """

    return jsonify({

        "status": "success",

        "authenticated": True,

        "user": {

            "id": current_user.id,

            "full_name": current_user.full_name,

            "email": current_user.email,

            "role": current_user.role

        }

    }), 200
