
# =========================================================
# STRATEGYSIM - STRATEGIC DECISIONS ROUTES
# =========================================================

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from flask_login import current_user

from app.database.connection import get_db

from app.utils.decorators import (
    authenticated_required,
    roles_required,
)

from app.strategic_decisions import strategic_decisions_bp

from app.strategic_decisions.forms import (
    DecisionMatrixForm,
    DecisionOptionForm,
    DecisionCriterionForm,
    DecisionScoreForm,
)

from app.services.decision_engine import (
    DecisionError,
    DecisionNotFoundError,
    DecisionValidationError,
    create_decision_matrix,
    add_decision_option,
    add_decision_criterion,
    save_decision_score,
    get_decision_matrix,
    get_decision_matrices,
    get_decision_options,
    get_decision_criteria,
    get_decision_scores,
    calculate_decision_rankings,
)


# =========================================================
# PERMISSIONS
# =========================================================

WRITE_ROLES = ("Administrator", "Analyst")


# =========================================================
# FORM CHOICE HELPERS
# =========================================================

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


def _populate_matrix_form(form):
    form.company_id.choices = _company_choices()


def _populate_score_form(form, matrix_id):
    options = get_decision_options(matrix_id)
    criteria = get_decision_criteria(matrix_id)

    form.option_id.choices = [
        (0, "Select an alternative")
    ] + [
        (item["id"], item["option_name"])
        for item in options
    ]

    form.criterion_id.choices = [
        (0, "Select a criterion")
    ] + [
        (item["id"], item["criterion_name"])
        for item in criteria
    ]


# =========================================================
# DECISION DASHBOARD
# =========================================================

@strategic_decisions_bp.route("/")
@authenticated_required
def index():

    matrices = get_decision_matrices()

    total_decisions = len(matrices)

    total_alternatives = sum(
        item["option_count"] for item in matrices
    )

    total_criteria = sum(
        item["criterion_count"] for item in matrices
    )

    return render_template(
        "strategic_decisions/index.html",
        matrices=matrices,
        total_decisions=total_decisions,
        total_alternatives=total_alternatives,
        total_criteria=total_criteria,
    )


# =========================================================
# CREATE DECISION MATRIX
# =========================================================

@strategic_decisions_bp.route("/new", methods=["GET", "POST"])
@roles_required(*WRITE_ROLES)
def new():

    form = DecisionMatrixForm()
    _populate_matrix_form(form)

    if form.validate_on_submit():

        try:
            matrix_id = create_decision_matrix(
                company_id=form.company_id.data,
                matrix_name=form.matrix_name.data,
                objective=form.objective.data,
                description=form.description.data,
                created_by=current_user.id,
            )

            flash(
                "Strategic decision created successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "strategic_decisions.detail",
                    matrix_id=matrix_id
                )
            )

        except DecisionError as exc:
            flash(str(exc), "error")

    return render_template(
        "strategic_decisions/form.html",
        form=form,
    )


# =========================================================
# DECISION DETAILS
# =========================================================

@strategic_decisions_bp.route("/<int:matrix_id>")
@authenticated_required
def detail(matrix_id):

    try:
        matrix = get_decision_matrix(matrix_id)

        options = get_decision_options(matrix_id)
        criteria = get_decision_criteria(matrix_id)
        scores = get_decision_scores(matrix_id)

        rankings = calculate_decision_rankings(matrix_id)

    except DecisionValidationError:
        rankings = []
        matrix = get_decision_matrix(matrix_id)
        options = get_decision_options(matrix_id)
        criteria = get_decision_criteria(matrix_id)
        scores = get_decision_scores(matrix_id)

    except DecisionNotFoundError:
        flash("Decision matrix not found.", "error")
        return redirect(
            url_for("strategic_decisions.index")
        )

    option_form = DecisionOptionForm()
    criterion_form = DecisionCriterionForm()
    score_form = DecisionScoreForm()

    _populate_score_form(score_form, matrix_id)

    return render_template(
        "strategic_decisions/detail.html",
        matrix=matrix,
        options=options,
        criteria=criteria,
        scores=scores,
        rankings=rankings,
        option_form=option_form,
        criterion_form=criterion_form,
        score_form=score_form,
    )


# =========================================================
# ADD STRATEGIC ALTERNATIVE
# =========================================================

@strategic_decisions_bp.route(
    "/<int:matrix_id>/options/new",
    methods=["POST"]
)
@roles_required(*WRITE_ROLES)
def add_option(matrix_id):

    form = DecisionOptionForm()

    if form.validate_on_submit():

        try:
            add_decision_option(
                matrix_id=matrix_id,
                option_name=form.option_name.data,
                description=form.description.data,
                created_by=current_user.id,
            )

            flash(
                "Strategic alternative added successfully.",
                "success"
            )

        except DecisionError as exc:
            flash(str(exc), "error")

    else:
        flash(
            "Please provide a valid alternative name.",
            "error"
        )

    return redirect(
        url_for(
            "strategic_decisions.detail",
            matrix_id=matrix_id
        )
    )


# =========================================================
# ADD EVALUATION CRITERION
# =========================================================

@strategic_decisions_bp.route(
    "/<int:matrix_id>/criteria/new",
    methods=["POST"]
)
@roles_required(*WRITE_ROLES)
def add_criterion(matrix_id):

    form = DecisionCriterionForm()

    if form.validate_on_submit():

        try:
            add_decision_criterion(
                matrix_id=matrix_id,
                criterion_name=form.criterion_name.data,
                weight=form.weight.data,
                description=form.description.data,
                created_by=current_user.id,
            )

            flash(
                "Evaluation criterion added successfully.",
                "success"
            )

        except DecisionError as exc:
            flash(str(exc), "error")

    else:
        flash(
            "Please provide a valid criterion and weight.",
            "error"
        )

    return redirect(
        url_for(
            "strategic_decisions.detail",
            matrix_id=matrix_id
        )
    )


# =========================================================
# SAVE ALTERNATIVE EVALUATION
# =========================================================

@strategic_decisions_bp.route(
    "/<int:matrix_id>/evaluate",
    methods=["POST"]
)
@roles_required(*WRITE_ROLES)
def evaluate(matrix_id):

    form = DecisionScoreForm()
    _populate_score_form(form, matrix_id)

    if form.validate_on_submit():

        try:
            save_decision_score(
                matrix_id=matrix_id,
                option_id=form.option_id.data,
                criterion_id=form.criterion_id.data,
                score=form.score.data,
                justification=form.justification.data,
                updated_by=current_user.id,
            )

            flash(
                "Alternative evaluation saved successfully.",
                "success"
            )

        except DecisionError as exc:
            flash(str(exc), "error")

    else:
        flash(
            "Please provide a valid evaluation.",
            "error"
        )

    return redirect(
        url_for(
            "strategic_decisions.detail",
            matrix_id=matrix_id
        )
    )


# =========================================================
# DECISION HISTORY
# =========================================================

@strategic_decisions_bp.route("/history")
@authenticated_required
def history():

    matrices = get_decision_matrices()

    return render_template(
        "strategic_decisions/history.html",
        matrices=matrices,
    )
