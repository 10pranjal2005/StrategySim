"""StrategySim - SWOT Analysis Routes."""

from datetime import date

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)
from flask_login import current_user

from app.swot import swot_bp
from app.swot.forms import (
    SWOTAssessmentForm,
    SWOTFactorForm,
    SWOTAssessmentFilterForm,
    DeleteSWOTForm,
)
from app.swot.services import (
    SWOTError,
    SWOTValidationError,
    SWOTNotFoundError,
    create_swot_assessment,
    get_swot_assessment,
    get_swot_assessments,
    update_swot_assessment,
    delete_swot_assessment,
    create_swot_factor,
    get_swot_factor,
    update_swot_factor,
    delete_swot_factor,
)
from app.database.connection import get_db
from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)


# =========================================================
# HELPERS
# =========================================================

def _load_company_choices(form):
    """Populate the company selector from existing companies."""

    companies = get_db().execute(
        """
        SELECT id, name
        FROM companies
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    form.company_id.choices = [
        (company["id"], company["name"])
        for company in companies
    ]

    return companies


def _populate_assessment_form(form, assessment):
    """Populate assessment form fields."""

    form.company_id.data = assessment["company_id"]
    form.assessment_name.data = assessment["assessment_name"]

    assessment_date = assessment.get("assessment_date")

    if assessment_date:
        try:
            form.assessment_date.data = date.fromisoformat(
                assessment_date[:10]
            )
        except (TypeError, ValueError):
            form.assessment_date.data = None

    form.summary.data = assessment.get("summary") or ""


def _populate_factor_form(form, factor):
    """Populate factor form fields."""

    form.factor_type.data = factor["factor_type"]
    form.factor_name.data = factor["factor_name"]
    form.description.data = factor.get("description") or ""

    importance = factor.get("strategic_importance")

    form.importance.data = (
        str(importance) if importance is not None else ""
    )


def _assessment_form_data(form):
    """Convert validated assessment form data to service arguments."""

    assessment_date = form.assessment_date.data

    return {
        "company_id": form.company_id.data,
        "assessment_name": form.assessment_name.data,
        "assessment_date": (
            assessment_date.isoformat()
            if assessment_date
            else None
        ),
        "summary": form.summary.data,
    }


def _factor_form_data(form):
    """Convert validated factor form data to service arguments."""

    importance = form.importance.data

    return {
        "factor_type": form.factor_type.data,
        "factor_name": form.factor_name.data,
        "description": form.description.data,
        "importance": (
            int(importance) if importance else None
        ),
    }


def _handle_service_error(error):
    """Translate known service errors into user-facing messages."""

    if isinstance(error, SWOTNotFoundError):
        abort(404)

    if isinstance(error, SWOTValidationError):
        flash(str(error), "error")
        return

    if isinstance(error, SWOTError):
        flash(str(error), "error")
        return

    raise error


# =========================================================
# ASSESSMENT LIST
# =========================================================

@swot_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    """Display SWOT assessments."""

    form = SWOTAssessmentFilterForm()

    search = request.args.get("search", "").strip() or None
    company_id = request.args.get("company_id", type=int)

    try:
        assessments = get_swot_assessments(
            company_id=company_id,
            limit=100,
            offset=0,
            search=search,
        )

        companies = get_db().execute(
            """
            SELECT id, name
            FROM companies
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

        return render_template(
            "swot/index.html",
            assessments=assessments,
            companies=companies,
            selected_company_id=company_id,
            search=search or "",
            form=form,
        )

    except SWOTError as error:
        _handle_service_error(error)

        return render_template(
            "swot/index.html",
            assessments=[],
            companies=[],
            selected_company_id=company_id,
            search=search or "",
            form=form,
        )


# =========================================================
# CREATE ASSESSMENT
# =========================================================

@swot_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    """Create a new SWOT assessment."""

    form = SWOTAssessmentForm()
    companies = _load_company_choices(form)

    if not companies:
        flash(
            "Create a company before starting a SWOT assessment.",
            "warning",
        )
        return redirect(url_for("swot.index"))

    if form.validate_on_submit():
        try:
            data = _assessment_form_data(form)

            assessment = create_swot_assessment(
                company_id=data["company_id"],
                assessment_name=data["assessment_name"],
                acting_user_id=current_user.id,
                assessment_date=data["assessment_date"],
                summary=data["summary"],
            )

            flash(
                "SWOT assessment created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "swot.detail",
                    assessment_id=assessment["id"],
                )
            )

        except SWOTError as error:
            _handle_service_error(error)

    return render_template(
        "swot/assessment_form.html",
        form=form,
        mode="create",
        assessment=None,
    )


# =========================================================
# ASSESSMENT DETAIL
# =========================================================

@swot_bp.route("/<int:assessment_id>", methods=["GET"])
@authenticated_required
def detail(assessment_id):
    """Display one SWOT assessment and its factors."""

    try:
        assessment = get_swot_assessment(assessment_id)

        delete_form = DeleteSWOTForm()

        return render_template(
            "swot/detail.html",
            assessment=assessment,
            delete_form=delete_form,
        )

    except SWOTNotFoundError:
        abort(404)

    except SWOTError as error:
        _handle_service_error(error)
        abort(500)


# =========================================================
# UPDATE ASSESSMENT
# =========================================================

@swot_bp.route(
    "/<int:assessment_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit(assessment_id):
    """Edit an existing SWOT assessment."""

    try:
        assessment = get_swot_assessment(assessment_id)

        form = SWOTAssessmentForm()
        _load_company_choices(form)

        if request.method == "GET":
            _populate_assessment_form(form, assessment)

        if form.validate_on_submit():
            data = _assessment_form_data(form)

            # Company reassignment is not supported.
            # Check this BEFORE updating any assessment fields.
            if data["company_id"] != assessment["company_id"]:
                flash(
                    "Changing the company of an existing assessment "
                    "is not supported. No changes were saved.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "swot.edit",
                        assessment_id=assessment_id,
                    )
                )

            updated = update_swot_assessment(
                assessment_id=assessment_id,
                acting_user_id=current_user.id,
                updates={
                    "assessment_name": data["assessment_name"],
                    "assessment_date": data["assessment_date"],
                    "summary": data["summary"],
                },
            )

            flash(
                "SWOT assessment updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "swot.detail",
                    assessment_id=updated["id"],
                )
            )

        return render_template(
            "swot/assessment_form.html",
            form=form,
            mode="edit",
            assessment=assessment,
        )

    except SWOTNotFoundError:
        abort(404)

    except SWOTError as error:
        _handle_service_error(error)
        abort(500)


# =========================================================
# DELETE ASSESSMENT
# =========================================================

@swot_bp.route(
    "/<int:assessment_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(assessment_id):
    """Delete an assessment using a CSRF-protected POST."""

    form = DeleteSWOTForm()

    if not form.validate_on_submit():
        flash(
            "Invalid deletion request.",
            "error",
        )

        return redirect(url_for("swot.index"))

    try:
        delete_swot_assessment(
            assessment_id=assessment_id,
            acting_user_id=current_user.id,
        )

        flash(
            "SWOT assessment deleted successfully.",
            "success",
        )

    except SWOTNotFoundError:
        abort(404)

    except SWOTError as error:
        _handle_service_error(error)

    return redirect(url_for("swot.index"))


# =========================================================
# CREATE FACTOR
# =========================================================

@swot_bp.route(
    "/<int:assessment_id>/factors/new",
    methods=["GET", "POST"],
)
@analyst_required
def create_factor(assessment_id):
    """Add a factor to an assessment."""

    try:
        assessment = get_swot_assessment(assessment_id)
        form = SWOTFactorForm()

        if request.method == "GET":
            requested_type = request.args.get("factor_type", "").strip()

            valid_types = {
                "Strength",
                "Weakness",
                "Opportunity",
                "Threat",
            }

            if requested_type in valid_types:
                form.factor_type.data = requested_type

        if form.validate_on_submit():
            data = _factor_form_data(form)

            create_swot_factor(
                assessment_id=assessment_id,
                factor_type=data["factor_type"],
                factor_name=data["factor_name"],
                acting_user_id=current_user.id,
                description=data["description"],
                importance=data["importance"],
            )

            flash(
                "SWOT factor created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "swot.detail",
                    assessment_id=assessment_id,
                )
            )

        return render_template(
            "swot/factor_form.html",
            form=form,
            mode="create",
            assessment=assessment,
            factor=None,
        )

    except SWOTNotFoundError:
        abort(404)

    except SWOTError as error:
        _handle_service_error(error)
        abort(500)


# =========================================================
# UPDATE FACTOR
# =========================================================

@swot_bp.route(
    "/factors/<int:factor_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit_factor(factor_id):
    """Edit an existing SWOT factor."""

    try:
        factor = get_swot_factor(factor_id)
        assessment = get_swot_assessment(factor["assessment_id"])

        form = SWOTFactorForm()

        if request.method == "GET":
            _populate_factor_form(form, factor)

        if form.validate_on_submit():
            data = _factor_form_data(form)

            updated = update_swot_factor(
                factor_id=factor_id,
                acting_user_id=current_user.id,
                updates=data,
            )

            flash(
                "SWOT factor updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "swot.detail",
                    assessment_id=updated["assessment_id"],
                )
            )

        return render_template(
            "swot/factor_form.html",
            form=form,
            mode="edit",
            assessment=assessment,
            factor=factor,
        )

    except SWOTNotFoundError:
        abort(404)

    except SWOTError as error:
        _handle_service_error(error)
        abort(500)


# =========================================================
# DELETE FACTOR
# =========================================================

@swot_bp.route(
    "/factors/<int:factor_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete_factor(factor_id):
    """Delete a factor using a CSRF-protected POST."""

    form = DeleteSWOTForm()

    if not form.validate_on_submit():
        flash(
            "Invalid deletion request.",
            "error",
        )

        return redirect(url_for("swot.index"))

    try:
        factor = get_swot_factor(factor_id)
        assessment_id = factor["assessment_id"]

        delete_swot_factor(
            factor_id=factor_id,
            acting_user_id=current_user.id,
        )

        flash(
            "SWOT factor deleted successfully.",
            "success",
        )

        return redirect(
            url_for(
                "swot.detail",
                assessment_id=assessment_id,
            )
        )

    except SWOTNotFoundError:
        abort(404)

    except SWOTError as error:
        _handle_service_error(error)

    return redirect(url_for("swot.index"))