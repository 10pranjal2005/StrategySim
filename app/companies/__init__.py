
from flask import Blueprint


# ---------------------------------------------------------
# COMPANY INTELLIGENCE BLUEPRINT
# ---------------------------------------------------------

companies_bp = Blueprint(
    "companies",
    __name__,
    url_prefix="/companies"
)


# ---------------------------------------------------------
# REGISTER COMPANY ROUTES
# ---------------------------------------------------------

from app.companies import routes
