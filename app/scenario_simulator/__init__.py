
from flask import Blueprint

scenario_simulator_bp = Blueprint(
    "scenario_simulator",
    __name__,
    url_prefix="/scenario-simulator",
)

# Import routes so their decorators register endpoints on the blueprint.
from app.scenario_simulator import routes as _routes
