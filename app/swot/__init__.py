
"""StrategySim - SWOT Analysis Blueprint."""

from flask import Blueprint

swot_bp = Blueprint(
    "swot",
    __name__,
    url_prefix="/swot",
)

from app.swot import routes  # noqa: E402, F401
