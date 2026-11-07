from flask import Blueprint

strategic_decisions_bp = Blueprint(
    "strategic_decisions",
    __name__,
    url_prefix="/strategic-decisions",
)

from app.strategic_decisions import routes as _routes