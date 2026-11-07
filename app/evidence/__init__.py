
"""
Evidence Management Blueprint.
"""

from flask import Blueprint

evidence_bp = Blueprint(
    "evidence",
    __name__,
    url_prefix="/evidence",
)

from app.evidence import routes  # noqa: E402, F401
