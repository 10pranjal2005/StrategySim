
"""StrategySim - Porter's Five Forces routes."""

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
)

from flask_login import current_user

from app.five_forces import five_forces_bp

from app.five_forces.forms import (
    FiveForcesAssessmentForm,
    FiveForcesIndicatorForm,
    FiveForcesFilterForm,
    DeleteFiveForcesForm,
)

from app.five_forces.services import (
    FiveForcesError,
    FiveForcesValidationError,
    FiveForcesNotFoundError,
    create_five_forces_assessment,
    get_five_forces_assessment,
    get_five_forces_assessments,
    update_five_forces_assessment,
    delete_five_forces_assessment,
    create_five_forces_indicator,
    get_five_forces_indicator,
    update_five_forces_indicator,
    delete_five_forces_indicator,
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
    """Load available companies into the assessment form."""

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
    """Populate an assessment form for editing."""

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


def _populate_indicator_form(form, indicator):
    """Populate an indicator form for editing."""

    form.force_name.data = indicator["force_name"]
    form.indicator_name.data = indicator["indicator_name"]
    form.score.data = indicator["score"]
    form.weight.data = Decimal(str(indicator["weight"]))
    form.explanation.data = indicator.get("explanation") or ""

    evidence_id = indicator.get("evidence_id")
    form.evidence_id.data = (
        str(evidence_id) if evidence_id is not None else ""
    )


def _assessment_form_data(form):
    """Convert validated assessment form data."""

    assessment_date = form.assessment_date.data

    return {
        "company_id": form.company_id.data,
        "assessment_name": form.assessment_name.data,
        "assessment_date": (
            assessment_date.isoformat()
            if assessment_date else None
        ),
        "summary": form.summary.data,
    }


def _indicator_form_data(form):
    """Convert validated indicator form data."""

    try:
        weight = float(form.weight.data)
    except (TypeError, ValueError, InvalidOperation):
        raise FiveForcesValidationError(
            "Indicator weight must be a valid positive number."
        )

    evidence_id = form.evidence_id.data

    return {
        "force_name": form.force_name.data,
        "indicator_name": form.indicator_name.data,
        "score": form.score.data,
        "weight": weight,
        "explanation": form.explanation.data,
        "evidence_id": (
            int(evidence_id) if evidence_id else None
        ),
    }


def _handle_service_error(error):
    """Translate service exceptions into appropriate responses."""

    if isinstance(error, FiveForcesNotFoundError):
        abort(404)

    if isinstance(error, FiveForcesValidationError):
        flash(str(error), "error")
        return

    if isinstance(error, FiveForcesError):
        flash(str(error), "error")
        return

    raise error


def _load_assessment_or_404(assessment_id):
    """Load an assessment and return 404 if it does not exist."""

    assessment = get_five_forces_assessment(assessment_id)

    if assessment is None:
        abort(404)

    return assessment


# =========================================================
# ASSESSMENT LIST
# =========================================================

@five_forces_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    """Display Five Forces assessments."""

    form = FiveForcesFilterForm()

    search = request.args.get("search", "").strip() or None
    company_id = request.args.get("company_id", type=int)

    companies = get_db().execute(
        """
        SELECT id, name
        FROM companies
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    form.company_id.choices = [
        (0, "All Companies")
    ] + [
        (company["id"], company["name"])
        for company in companies
    ]

    try:
        assessments = get_five_forces_assessments(
            company_id=company_id,
            limit=100,
            offset=0,
            search=search,
        )

        return render_template(
            "five_forces/index.html",
            assessments=assessments,
            companies=companies,
            selected_company_id=company_id,
            search=search or "",
            form=form,
        )

    except FiveForcesError as error:
        _handle_service_error(error)

        return render_template(
            "five_forces/index.html",
            assessments=[],
            companies=companies,
            selected_company_id=company_id,
            search=search or "",
            form=form,
        )


# =========================================================
# CREATE ASSESSMENT
# =========================================================

@five_forces_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    """Create a Five Forces assessment."""

    form = FiveForcesAssessmentForm()
    companies = _load_company_choices(form)

    if not companies:
        flash(
            "Create a company before starting a Five Forces assessment.",
            "warning",
        )
        return redirect(url_for("five_forces.index"))

    if form.validate_on_submit():
        try:
            data = _assessment_form_data(form)

            assessment = create_five_forces_assessment(
                company_id=data["company_id"],
                assessment_name=data["assessment_name"],
                acting_user_id=current_user.id,
                assessment_date=data["assessment_date"],
                summary=data["summary"],
            )

            flash(
                "Five Forces assessment created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "five_forces.detail",
                    assessment_id=assessment["id"],
                )
            )

        except FiveForcesError as error:
            _handle_service_error(error)

    return render_template(
        "five_forces/assessment_form.html",
        form=form,
        page_title="Create Five Forces Assessment",
        is_edit=False,
    )


# =========================================================
# ASSESSMENT DETAIL
# =========================================================

@five_forces_bp.route("/<int:assessment_id>", methods=["GET"])
@authenticated_required
def detail(assessment_id):
    """Display assessment scores and indicators."""

    assessment = _load_assessment_or_404(assessment_id)

    delete_form = DeleteFiveForcesForm()

    return render_template(
        "five_forces/detail.html",
        assessment=assessment,
        delete_form=delete_form,
    )


# =========================================================
# UPDATE ASSESSMENT
# =========================================================

@five_forces_bp.route(
    "/<int:assessment_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit(assessment_id):
    """Update assessment details."""

    assessment = _load_assessment_or_404(assessment_id)

    form = FiveForcesAssessmentForm()
    _load_company_choices(form)

    if request.method == "GET":
        _populate_assessment_form(form, assessment)

    if form.validate_on_submit():
        try:
            data = _assessment_form_data(form)

            if data["company_id"] != assessment["company_id"]:
                flash(
                    "Changing the company of an existing assessment "
                    "is not supported.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "five_forces.edit",
                        assessment_id=assessment_id,
                    )
                )

            updated = update_five_forces_assessment(
                assessment_id=assessment_id,
                acting_user_id=current_user.id,
                updates={
                    "assessment_name": data["assessment_name"],
                    "assessment_date": data["assessment_date"],
                    "summary": data["summary"],
                },
            )

            flash(
                "Five Forces assessment updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "five_forces.detail",
                    assessment_id=updated["id"],
                )
            )

        except FiveForcesError as error:
            _handle_service_error(error)

    return render_template(
        "five_forces/assessment_form.html",
        form=form,
        page_title="Edit Five Forces Assessment",
        is_edit=True,
        assessment=assessment,
    )


# =========================================================
# DELETE ASSESSMENT
# =========================================================

@five_forces_bp.route(
    "/<int:assessment_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(assessment_id):
    """Delete an assessment using a CSRF-protected POST."""

    form = DeleteFiveForcesForm()

    if not form.validate_on_submit():
        flash("Invalid deletion request.", "error")
        return redirect(url_for("five_forces.index"))

    try:
        delete_five_forces_assessment(
            assessment_id=assessment_id,
            acting_user_id=current_user.id,
        )

        flash(
            "Five Forces assessment deleted successfully.",
            "success",
        )

    except FiveForcesNotFoundError:
        abort(404)

    except FiveForcesError as error:
        _handle_service_error(error)

    return redirect(url_for("five_forces.index"))


# =========================================================
# CREATE INDICATOR
# =========================================================

@five_forces_bp.route(
    "/<int:assessment_id>/indicators/new",
    methods=["GET", "POST"],
)
@analyst_required
def create_indicator(assessment_id):
    """Add an indicator to a competitive force."""

    assessment = _load_assessment_or_404(assessment_id)
    form = FiveForcesIndicatorForm()

    if form.validate_on_submit():
        try:
            data = _indicator_form_data(form)

            create_five_forces_indicator(
                assessment_id=assessment_id,
                acting_user_id=current_user.id,
                **data,
            )

            flash(
                "Five Forces indicator added successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "five_forces.detail",
                    assessment_id=assessment_id,
                )
            )

        except FiveForcesError as error:
            _handle_service_error(error)

    return render_template(
        "five_forces/indicator_form.html",
        form=form,
        assessment=assessment,
        page_title="Add Five Forces Indicator",
        is_edit=False,
    )


# =========================================================
# UPDATE INDICATOR
# =========================================================

@five_forces_bp.route(
    "/indicators/<int:indicator_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit_indicator(indicator_id):
    """Update an existing indicator."""

    indicator = get_five_forces_indicator(indicator_id)

    if indicator is None:
        abort(404)

    assessment = _load_assessment_or_404(
        indicator["assessment_id"]
    )

    form = FiveForcesIndicatorForm()

    if request.method == "GET":
        _populate_indicator_form(form, indicator)

    if form.validate_on_submit():
        try:
            data = _indicator_form_data(form)

            update_five_forces_indicator(
                indicator_id=indicator_id,
                acting_user_id=current_user.id,
                updates=data,
            )

            flash(
                "Five Forces indicator updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "five_forces.detail",
                    assessment_id=assessment["id"],
                )
            )

        except FiveForcesError as error:
            _handle_service_error(error)

    return render_template(
        "five_forces/indicator_form.html",
        form=form,
        assessment=assessment,
        page_title="Edit Five Forces Indicator",
        is_edit=True,
        indicator=indicator,
    )


# =========================================================
# DELETE INDICATOR
# =========================================================

@five_forces_bp.route(
    "/indicators/<int:indicator_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete_indicator(indicator_id):
    """Delete an indicator using a CSRF-protected POST."""

    form = DeleteFiveForcesForm()

    if not form.validate_on_submit():
        flash("Invalid deletion request.", "error")
        return redirect(url_for("five_forces.index"))

    indicator = get_five_forces_indicator(indicator_id)

    if indicator is None:
        abort(404)

    assessment_id = indicator["assessment_id"]

    try:
        delete_five_forces_indicator(
            indicator_id=indicator_id,
            acting_user_id=current_user.id,
        )

        flash(
            "Five Forces indicator deleted successfully.",
            "success",
        )

    except FiveForcesNotFoundError:
        abort(404)

    except FiveForcesError as error:
        _handle_service_error(error)

    return redirect(
        url_for(
            "five_forces.detail",
            assessment_id=assessment_id,
        )
    )
