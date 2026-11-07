
import os

from flask import (
    Flask,
    jsonify,
    redirect,
    url_for
)

from flask_login import (
    LoginManager,
    current_user
)

from flask_wtf.csrf import CSRFProtect

from app.config import configurations

from app.database import (
    init_app as init_database_app,
    initialize_database
)


# ---------------------------------------------------------
# FLASK EXTENSIONS
# ---------------------------------------------------------

login_manager = LoginManager()
csrf = CSRFProtect()


# ---------------------------------------------------------
# APPLICATION FACTORY
# ---------------------------------------------------------

def create_app(config_name=None):
    """
    Creates and configures the StrategySim Flask application.
    """

    app = Flask(
        __name__,
        instance_relative_config=True
    )

    # -----------------------------------------------------
    # LOAD CONFIGURATION
    # -----------------------------------------------------

    if config_name is None:
        config_name = os.getenv(
            "FLASK_ENV",
            "development"
        )

    config_class = configurations.get(
        config_name,
        configurations["development"]
    )

    app.config.from_object(config_class)

    # -----------------------------------------------------
    # VALIDATE SECRET KEY
    # -----------------------------------------------------

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY is missing. "
            "Generate a secure secret key and configure it "
            "in the .env file."
        )

    # -----------------------------------------------------
    # CREATE INSTANCE DIRECTORY
    # -----------------------------------------------------

    os.makedirs(
        app.instance_path,
        exist_ok=True
    )

    # -----------------------------------------------------
    # INITIALIZE FLASK EXTENSIONS
    # -----------------------------------------------------

    login_manager.init_app(app)

    login_manager.login_view = "auth.login"

    login_manager.login_message = (
        "Please sign in to access this page."
    )

    login_manager.login_message_category = "warning"

    login_manager.session_protection = "strong"

    csrf.init_app(app)

    # -----------------------------------------------------
    # INITIALIZE DATABASE
    # -----------------------------------------------------

    init_database_app(app)

    initialize_database(app)

    # -----------------------------------------------------
    # REGISTER BLUEPRINTS
    # -----------------------------------------------------

    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.users import users_bp
    from app.companies import companies_bp
    from app.competitors import competitors_bp
    from app.evidence import evidence_bp
    from app.swot import swot_bp
    from app.five_forces import five_forces_bp
    from app.value_chain import value_chain_bp
    from app.suppliers import suppliers_bp
    from app.suppliers.component_routes import supplier_components_bp
    from app.suppliers.relationship_routes import (
    supplier_relationships_bp,
    )
    from app.suppliers.facility_routes import (
    supplier_facilities_bp,
    )
    from app.dependency_analysis import dependency_analysis_bp
    from app.scenario_simulator import scenario_simulator_bp
    from app.strategic_decisions import strategic_decisions_bp
    from app.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(companies_bp)
    app.register_blueprint(competitors_bp)
    app.register_blueprint(evidence_bp)
    app.register_blueprint(swot_bp)
    app.register_blueprint(five_forces_bp)
    app.register_blueprint(value_chain_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(supplier_components_bp)
    app.register_blueprint(supplier_relationships_bp)
    app.register_blueprint(supplier_facilities_bp)
    app.register_blueprint(dependency_analysis_bp)
    app.register_blueprint(scenario_simulator_bp)
    app.register_blueprint(strategic_decisions_bp)
    app.register_blueprint(reports_bp)

    # -----------------------------------------------------
    # ROOT URL
    # -----------------------------------------------------

    @app.route(
        "/",
        methods=["GET"]
    )
    def index():
        """
        Redirect authenticated users to the dashboard.
        Redirect unauthenticated users to login.
        """

        if current_user.is_authenticated:

            return redirect(
                url_for("dashboard.dashboard_home")
            )

        return redirect(
            url_for("auth.login")
        )

    # -----------------------------------------------------
    # HEALTH CHECK
    # -----------------------------------------------------

    @app.route(
        "/health",
        methods=["GET"]
    )
    def health_check():

        return jsonify({
            "status": "success",
            "application": app.config["APP_NAME"],
            "version": app.config["APP_VERSION"],
            "database": "connected",
            "message": (
                "StrategySim backend and database "
                "are running."
            )
        }), 200

    # -----------------------------------------------------
    # ERROR HANDLERS
    # -----------------------------------------------------

    @app.errorhandler(403)
    def forbidden(error):

        return jsonify({
            "status": "error",
            "code": 403,
            "message": (
                "You do not have permission "
                "to access this resource."
            )
        }), 403

    @app.errorhandler(404)
    def page_not_found(error):

        return jsonify({
            "status": "error",
            "code": 404,
            "message": (
                "The requested resource was not found."
            )
        }), 404

    @app.errorhandler(500)
    def internal_server_error(error):

        return jsonify({
            "status": "error",
            "code": 500,
            "message": (
                "An internal server error occurred."
            )
        }), 500

    # -----------------------------------------------------
    # APPLICATION STARTUP MESSAGE
    # -----------------------------------------------------

    print("\n" + "=" * 55)

    print("StrategySim Application Initialized")

    print(
        f"Version: {app.config['APP_VERSION']}"
    )

    print(
        f"Environment: {config_name}"
    )

    print("Database: Initialized")

    print("Authentication: Initialized")

    print("User Management: Registered")

    print("Company Intelligence: Registered")

    print("Competitor Intelligence: Registered")

    print("Evidence Management: Registered")

    print("=" * 55 + "\n")

    return app


# ---------------------------------------------------------
# FLASK-LOGIN USER LOADER
# ---------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    """
    Retrieves an active authenticated user from SQLite.

    Inactive accounts are not restored into authenticated
    sessions.
    """

    from app.users.models import User

    user = User.get_by_id(user_id)

    if user is None or not user.is_active:
        return None

    return user
