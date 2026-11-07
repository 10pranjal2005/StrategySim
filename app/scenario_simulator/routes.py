
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from app.database.connection import get_db
from app.utils.decorators import (
    authenticated_required,
    roles_required,
)
from app.scenario_simulator import scenario_simulator_bp
from app.scenario_simulator.forms import ScenarioForm, ScenarioFilterForm
from app.services.scenario_engine import (
    create_scenario,
    get_scenarios,
    get_scenario,
    get_scenario_results,
    simulate_scenario,
    archive_scenario,
    ScenarioError,
)
from flask_login import current_user

WRITE_ROLES = ("Administrator", "Analyst")


def _company_choices():
    database = get_db()

    rows = database.execute(
        """
        SELECT id, name
        FROM companies
        WHERE company_type = 'Target'
        ORDER BY name
        """
    ).fetchall()

    return [
        (row["id"], row["name"])
        for row in rows
    ]

def _supplier_choices():
    database = get_db()

    rows = database.execute(
        """
        SELECT id, name, supplier_code
        FROM suppliers
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    return [(0, "Select a supplier")] + [
        (
            row["id"],
            f"{row['name']} ({row['supplier_code']})"
        )
        for row in rows
    ]


def _component_choices():
    database = get_db()

    rows = database.execute(
        """
        SELECT id, name, component_code
        FROM components
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    return [(0, "Select a component")] + [
        (
            row["id"],
            f"{row['name']} ({row['component_code']})"
        )
        for row in rows
    ]

def _populate_scenario_form(form):
    form.company_id.choices = _company_choices()
    form.supplier_id.choices = _supplier_choices()
    form.component_id.choices = _component_choices()


@scenario_simulator_bp.route("/")
@authenticated_required
def index():
    form = ScenarioFilterForm()
    form.company_id.choices = [(0, "All Companies")] + _company_choices()

    company_id = request.args.get("company_id", type=int)
    status = request.args.get("status", type=str)

    scenarios = get_scenarios(
        company_id=company_id if company_id else None,
        status=status if status else None,
    )

    all_scenarios = get_scenarios()

    counts = {
        "total": len(all_scenarios),
        "draft": sum(1 for item in all_scenarios if item["status"] == "Draft"),
        "simulated": sum(1 for item in all_scenarios if item["status"] == "Simulated"),
        "archived": sum(1 for item in all_scenarios if item["status"] == "Archived"),
    }

    return render_template(
        "scenario_simulator/index.html",
        scenarios=scenarios,
        counts=counts,
        form=form,
        selected_company=company_id or 0,
        selected_status=status or "",
    )


@scenario_simulator_bp.route("/new", methods=["GET", "POST"])
@roles_required(*WRITE_ROLES)
def create():
    form = ScenarioForm()
    _populate_scenario_form(form)

    if form.validate_on_submit():
        scenario_type = form.scenario_type.data

        parameters = {}

        if scenario_type == "supplier_price_increase":
                parameters["price_increase_percent"] = (
                form.price_increase_percent.data
            )
        if form.supplier_id.data:
                parameters["supplier_id"] = form.supplier_id.data
        if form.component_id.data:
                parameters["component_id"] = form.component_id.data

        elif scenario_type == "supplier_unavailability":
            parameters["supplier_id"] = form.supplier_id.data
            if form.unavailability_duration_days.data:
                parameters["duration_days"] = form.unavailability_duration_days.data

        elif scenario_type == "raw_material_shortage":
            parameters["component_id"] = form.component_id.data
            parameters["shortage_percent"] = form.shortage_percent.data

        elif scenario_type == "demand_decline":
            parameters["demand_decline_percent"] = form.demand_decline_percent.data

        elif scenario_type == "competitor_entry":
            parameters["market_share_impact_percent"] = (
                form.market_share_impact_percent.data
            )

        elif scenario_type == "substitute_technology":
            parameters["demand_impact_percent"] = form.demand_impact_percent.data

        try:
            scenario_id = create_scenario(
                company_id=form.company_id.data,
                scenario_name=form.scenario_name.data,
                scenario_type=scenario_type,
                parameters=parameters,
                created_by=current_user.id,
                description=form.description.data,
            )

            flash("Scenario created successfully.", "success")
            return redirect(
                url_for(
                    "scenario_simulator.detail",
                    scenario_id=scenario_id,
                )
            )

        except ScenarioError as exc:
            flash(str(exc), "danger")

    return render_template(
        "scenario_simulator/form.html",
        form=form,
        page_title="Create Scenario",
    )


@scenario_simulator_bp.route("/<int:scenario_id>")
@authenticated_required
def detail(scenario_id):
    try:
        scenario = get_scenario(scenario_id)
        results = get_scenario_results(scenario_id)

    except ScenarioError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("scenario_simulator.index"))

    return render_template(
        "scenario_simulator/detail.html",
        scenario=scenario,
        results=results,
    )


@scenario_simulator_bp.route("/<int:scenario_id>/simulate", methods=["POST"])
@roles_required(*WRITE_ROLES)
def simulate(scenario_id):
    try:
        from flask_login import current_user

        simulate_scenario(
            scenario_id=scenario_id,
            executed_by=current_user.id,
        )
        flash("Scenario simulation completed successfully.", "success")

    except ScenarioError as exc:
        flash(str(exc), "danger")

    return redirect(
        url_for(
            "scenario_simulator.detail",
            scenario_id=scenario_id,
        )
    )


@scenario_simulator_bp.route("/<int:scenario_id>/archive", methods=["POST"])
@roles_required(*WRITE_ROLES)
def archive(scenario_id):
    try:
        from flask_login import current_user

        archive_scenario(
            scenario_id=scenario_id,
            archived_by=current_user.id,
        )
        flash("Scenario archived successfully.", "success")

    except ScenarioError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("scenario_simulator.index"))


@scenario_simulator_bp.route("/history")
@authenticated_required
def history():
    scenarios = get_scenarios()

    return render_template(
        "scenario_simulator/history.html",
        scenarios=scenarios,
    )
