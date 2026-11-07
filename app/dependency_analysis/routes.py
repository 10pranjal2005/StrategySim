"""Routes for Supply Chain Dependency Analysis."""

from flask import (
    abort,
    render_template,
    flash,
    redirect,
    url_for,
)

from app.dependency_analysis import dependency_analysis_bp

from app.dependency_analysis.services import (
    get_dependency_dashboard,
    get_component_dependency_details,
    DependencyAnalysisError,
    DependencyComponentNotFoundError,
)

from app.utils.decorators import authenticated_required


@dependency_analysis_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    """Display the dependency analysis dashboard."""

    try:
        dashboard = get_dependency_dashboard()

    except DependencyAnalysisError as error:
        flash(str(error), "error")
        dashboard = {
            "summary": {},
            "components": [],
            "supplier_spend": [],
            "procurement_records": [],
            "facilities": [],
            "disrupted_facility_records": [],
        }

    return render_template(
        "dependency_analysis/index.html",
        dashboard=dashboard,
    )


@dependency_analysis_bp.route(
    "/components/<int:component_id>",
    methods=["GET"],
)
@authenticated_required
def component_detail(component_id):
    """Display dependency information for one component."""

    try:
        details = get_component_dependency_details(
            component_id
        )

    except DependencyComponentNotFoundError:
        abort(404)

    except DependencyAnalysisError as error:
        flash(str(error), "error")
        return redirect(
            url_for("dependency_analysis.index")
        )

    return render_template(
        "dependency_analysis/component_detail.html",
        details=details,
    )