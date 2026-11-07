
from flask import Blueprint, render_template

from flask_login import login_required

from app.utils.decorators import (
    administrator_required,
    analyst_required
)


# ---------------------------------------------------------
# DASHBOARD BLUEPRINT
# ---------------------------------------------------------

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard"
)


# ---------------------------------------------------------
# MAIN DASHBOARD PAGE
# ---------------------------------------------------------

@dashboard_bp.route("/", methods=["GET"])
@login_required
def dashboard_home():
    """
    Renders the authenticated StrategySim dashboard.

    All authenticated roles can access the dashboard.
    """

    return render_template(
        "dashboard/index.html"
    )


# ---------------------------------------------------------
# GENERAL DASHBOARD ACCESS
# ---------------------------------------------------------

@dashboard_bp.route("/status", methods=["GET"])
@login_required
def dashboard_status():

    return {
        "status": "success",
        "module": "dashboard",
        "message": "Dashboard access granted.",
        "access_level": "authenticated"
    }, 200


# ---------------------------------------------------------
# ANALYST-LEVEL ACCESS
# ---------------------------------------------------------

@dashboard_bp.route("/analysis-status", methods=["GET"])
@analyst_required
def analysis_status():

    return {
        "status": "success",
        "module": "dashboard",
        "message": "Analytical access granted.",
        "access_level": "analyst"
    }, 200


# ---------------------------------------------------------
# ADMINISTRATOR-LEVEL ACCESS
# ---------------------------------------------------------

@dashboard_bp.route("/admin-status", methods=["GET"])
@administrator_required
def administrator_status():

    return {
        "status": "success",
        "module": "dashboard",
        "message": "Administrator access granted.",
        "access_level": "administrator"
    }, 200
