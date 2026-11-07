"""Dependency Analysis module."""

from flask import Blueprint

dependency_analysis_bp = Blueprint(
    "dependency_analysis",
    __name__,
    url_prefix="/dependency-analysis",
)

from app.dependency_analysis import routes  # noqa: E402,F401