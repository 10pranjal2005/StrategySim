from flask import Blueprint

value_chain_bp = Blueprint(
    "value_chain",
    __name__,
    url_prefix="/value-chain"
)

# Import routes to register all Value Chain endpoints.
from app.value_chain import routes