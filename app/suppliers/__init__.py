
"""
Supplier Network Blueprint.
"""

from flask import Blueprint

suppliers_bp = Blueprint(
    "suppliers",
    __name__,
    url_prefix="/suppliers",
)

from app.suppliers import routes  # noqa: E402, F401
