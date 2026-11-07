from flask import Blueprint


# =========================================================
# COMPETITOR INTELLIGENCE BLUEPRINT
# =========================================================

competitors_bp = Blueprint(
    "competitors",
    __name__,
    url_prefix="/competitors"
)


# =========================================================
# ROUTE REGISTRATION
# =========================================================

from app.competitors import routes