
"""StrategySim - Porter's Five Forces module."""

from flask import Blueprint

five_forces_bp = Blueprint(
    "five_forces",
    __name__,
    url_prefix="/five-forces"
)

from app.five_forces import routes
