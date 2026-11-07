from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import current_user

from app.value_chain import value_chain_bp
from app.value_chain.forms import (
    ValueChainAssessmentForm,
    ValueChainActivityForm,
    ValueChainFilterForm,
    DeleteValueChainForm,
)
from app.value_chain.services import (
    ValueChainError,
    ValueChainNotFoundError,
    create_value_chain_assessment,
    get_value_chain_assessment,
    get_value_chain_assessments,
    update_value_chain_assessment,
    delete_value_chain_assessment,
    create_value_chain_activity,
    get_value_chain_activity,
    update_value_chain_activity,
    delete_value_chain_activity,
)
from app.database.connection import get_db
from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)


def _get_companies():
    """Return companies for the assessment company selector."""
    db = get_db()

    return db.execute(
        """
        SELECT id, name
        FROM companies
        ORDER BY name
        """
    ).fetchall()


def _get_evidence_records():
    """Return available evidence records for activity association."""
    from app.evidence.services import get_evidence_records

    return get_evidence_records(limit=100)


def _get_activity_updates(form):
    """Convert validated activity form data into service update values."""
    return {
        "activity_category": form.activity_category.data,
        "activity_name": form.activity_name.data,
        "description": form.description.data,
        "cost_contribution": (
            float(form.cost_contribution.data)
            if form.cost_contribution.data is not None
            else None
        ),
        "strategic_importance": form.strategic_importance.data,
        "competitive_advantage": form.competitive_advantage.data,
    }


# ---------------------------------------------------------
# 1. VALUE CHAIN ASSESSMENT INDEX
# ---------------------------------------------------------

@value_chain_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    form = ValueChainFilterForm()

    search = request.args.get("search", "").strip() or None

    if search:
        form.search.data = search

    assessments = get_value_chain_assessments(
        search=search
    )

    return render_template(
        "value_chain/index.html",
        assessments=assessments,
        form=form,
    )


# ---------------------------------------------------------
# 2. CREATE ASSESSMENT
# ---------------------------------------------------------

@value_chain_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    form = ValueChainAssessmentForm()
    companies = _get_companies()

    if form.validate_on_submit():

        company_id = request.form.get(
            "company_id",
            type=int,
        )

        if not company_id:
            flash(
                "Please select a company.",
                "danger",
            )

            return render_template(
                "value_chain/assessment_form.html",
                form=form,
                companies=companies,
                assessment=None,
                mode="create",
            )

        try:
            assessment_id = create_value_chain_assessment(
                company_id=company_id,
                assessment_name=form.assessment_name.data,
                acting_user_id=current_user.id,
                assessment_date=(
                    form.assessment_date.data.isoformat()
                    if form.assessment_date.data
                    else None
                ),
                summary=form.summary.data,
            )

            flash(
                "Value Chain assessment created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "value_chain.detail",
                    assessment_id=assessment_id,
                )
            )

        except ValueChainError as exc:
            flash(str(exc), "danger")

    return render_template(
        "value_chain/assessment_form.html",
        form=form,
        companies=companies,
        assessment=None,
        mode="create",
    )


# ---------------------------------------------------------
# 3. ASSESSMENT DETAIL
# ---------------------------------------------------------

@value_chain_bp.route("/<int:assessment_id>", methods=["GET"])
@authenticated_required
def detail(assessment_id):
    try:
        assessment = get_value_chain_assessment(
            assessment_id
        )

        return render_template(
            "value_chain/detail.html",
            assessment=assessment,
            delete_form=DeleteValueChainForm(),
        )

    except ValueChainNotFoundError:
        flash(
            "Value Chain assessment not found.",
            "danger",
        )

        return redirect(
            url_for("value_chain.index")
        )


# ---------------------------------------------------------
# 4. EDIT ASSESSMENT
# ---------------------------------------------------------

@value_chain_bp.route(
    "/<int:assessment_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit(assessment_id):

    try:
        assessment = get_value_chain_assessment(
            assessment_id
        )

        form = ValueChainAssessmentForm(
            data={
                "assessment_name": assessment["assessment_name"],
                "assessment_date": assessment["assessment_date"],
                "summary": assessment["summary"],
            }
        )

        if form.validate_on_submit():

            updates = {
                "assessment_name": form.assessment_name.data,
                "assessment_date": (
                    form.assessment_date.data.isoformat()
                    if form.assessment_date.data
                    else None
                ),
                "summary": form.summary.data,
            }

            update_value_chain_assessment(
                assessment_id,
                current_user.id,
                updates,
            )

            flash(
                "Value Chain assessment updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "value_chain.detail",
                    assessment_id=assessment_id,
                )
            )

        return render_template(
            "value_chain/assessment_form.html",
            form=form,
            companies=_get_companies(),
            assessment=assessment,
            mode="edit",
        )

    except ValueChainNotFoundError:
        flash(
            "Value Chain assessment not found.",
            "danger",
        )

        return redirect(
            url_for("value_chain.index")
        )

    except ValueChainError as exc:
        flash(str(exc), "danger")

        return redirect(
            url_for(
                "value_chain.detail",
                assessment_id=assessment_id,
            )
        )


# ---------------------------------------------------------
# 5. DELETE ASSESSMENT
# ---------------------------------------------------------

@value_chain_bp.route(
    "/<int:assessment_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(assessment_id):

    form = DeleteValueChainForm()

    if not form.validate_on_submit():
        flash(
            "Invalid delete request.",
            "danger",
        )

        return redirect(
            url_for("value_chain.index")
        )

    try:
        delete_value_chain_assessment(
            assessment_id,
            current_user.id,
        )

        flash(
            "Value Chain assessment deleted successfully.",
            "success",
        )

    except ValueChainError as exc:
        flash(str(exc), "danger")

    return redirect(
        url_for("value_chain.index")
    )


# ---------------------------------------------------------
# 6. CREATE ACTIVITY
# ---------------------------------------------------------

@value_chain_bp.route(
    "/<int:assessment_id>/activities/new",
    methods=["GET", "POST"],
)
@analyst_required
def create_activity(assessment_id):

    try:
        assessment = get_value_chain_assessment(
            assessment_id
        )

        form = ValueChainActivityForm()

        if form.validate_on_submit():

            evidence_id = form.evidence_id.data

            activity_id = create_value_chain_activity(
                assessment_id=assessment_id,
                activity_category=form.activity_category.data,
                activity_name=form.activity_name.data,
                acting_user_id=current_user.id,
                description=form.description.data,
                cost_contribution=(
                    float(form.cost_contribution.data)
                    if form.cost_contribution.data is not None
                    else None
                ),
                strategic_importance=form.strategic_importance.data,
                competitive_advantage=form.competitive_advantage.data,
                evidence_id=evidence_id,
            )

            flash(
                "Value Chain activity added successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "value_chain.detail",
                    assessment_id=assessment_id,
                )
            )

        return render_template(
            "value_chain/activity_form.html",
            form=form,
            assessment=assessment,
            activity=None,
            evidence_records=_get_evidence_records(),
            mode="create",
        )

    except ValueChainNotFoundError:
        flash(
            "Value Chain assessment not found.",
            "danger",
        )

        return redirect(
            url_for("value_chain.index")
        )

    except ValueChainError as exc:
        flash(str(exc), "danger")

        return redirect(
            url_for(
                "value_chain.detail",
                assessment_id=assessment_id,
            )
        )


# ---------------------------------------------------------
# 7. EDIT ACTIVITY
# ---------------------------------------------------------

@value_chain_bp.route(
    "/activities/<int:activity_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit_activity(activity_id):

    try:
        activity = get_value_chain_activity(
            activity_id
        )

        assessment_id = activity["assessment_id"]

        assessment = get_value_chain_assessment(
            assessment_id
        )

        form = ValueChainActivityForm(
            data={
                "activity_category": activity["activity_category"],
                "activity_name": activity["activity_name"],
                "description": activity["description"],
                "cost_contribution": activity["cost_contribution"],
                "strategic_importance": activity["strategic_importance"],
                "competitive_advantage": activity["competitive_advantage"],
                "evidence_id": activity.get("evidence_id"),
            }
        )

        if form.validate_on_submit():

            updates = _get_activity_updates(form)

            update_value_chain_activity(
                activity_id,
                current_user.id,
                updates,
                evidence_id=form.evidence_id.data,
            )

            flash(
                "Value Chain activity updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "value_chain.detail",
                    assessment_id=assessment_id,
                )
            )

        return render_template(
            "value_chain/activity_form.html",
            form=form,
            assessment=assessment,
            activity=activity,
            evidence_records=_get_evidence_records(),
            mode="edit",
        )

    except ValueChainNotFoundError:
        flash(
            "Value Chain activity not found.",
            "danger",
        )

        return redirect(
            url_for("value_chain.index")
        )

    except ValueChainError as exc:
        flash(str(exc), "danger")

        return redirect(
            url_for("value_chain.index")
        )


# ---------------------------------------------------------
# 8. DELETE ACTIVITY
# ---------------------------------------------------------

@value_chain_bp.route(
    "/activities/<int:activity_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete_activity(activity_id):

    form = DeleteValueChainForm()

    if not form.validate_on_submit():
        flash(
            "Invalid delete request.",
            "danger",
        )

        return redirect(
            url_for("value_chain.index")
        )

    try:
        activity = get_value_chain_activity(
            activity_id
        )

        assessment_id = activity["assessment_id"]

        delete_value_chain_activity(
            activity_id,
            current_user.id,
        )

        flash(
            "Value Chain activity deleted successfully.",
            "success",
        )

        return redirect(
            url_for(
                "value_chain.detail",
                assessment_id=assessment_id,
            )
        )

    except ValueChainError as exc:
        flash(str(exc), "danger")

        return redirect(
            url_for("value_chain.index")
        )