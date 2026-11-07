
"""
Evidence Management Routes

Read access: Administrator, Analyst, Viewer
Write access: Administrator, Analyst
"""

from flask import (
    render_template,
    redirect,
    url_for,
    request,
    flash,
    abort,
)

from flask_login import current_user

from app.evidence import evidence_bp
from app.evidence.forms import (
    CreateEvidenceForm,
    EditEvidenceForm,
    EvidenceFilterForm,
    DeleteEvidenceForm,
)

from app.evidence.services import (
    EvidenceError,
    EvidenceNotFoundError,
    EvidenceValidationError,
    create_evidence,
    get_evidence_details,
    get_evidence_records,
    update_evidence,
    delete_evidence,
)

from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)


def _form_service_data(form):
    """Convert validated form fields into service arguments."""

    reliability_score = form.reliability_score.data
    entity_type = form.entity_type.data
    entity_id = form.entity_id.data

    return {
        "title": form.title.data,
        "description": form.description.data or None,
        "source_type": form.source_type.data,
        "source_name": form.source_name.data or None,
        "source_url": form.source_url.data or None,
        "file_path": form.file_path.data or None,
        "entity_type": entity_type or None,
        "entity_id": entity_id if entity_type else None,
        "reliability_score": (
            int(reliability_score)
            if reliability_score not in (None, "")
            else None
        ),
    }


def _populate_form(form, evidence):
    """Populate an evidence form from a database record."""

    form.title.data = evidence["title"]
    form.description.data = evidence["description"]
    form.source_type.data = evidence["source_type"]
    form.source_name.data = evidence["source_name"]
    form.source_url.data = evidence["source_url"]
    form.file_path.data = evidence["file_path"]
    form.entity_type.data = evidence["entity_type"] or ""
    form.entity_id.data = evidence["entity_id"]

    form.reliability_score.data = (
        str(evidence["reliability_score"])
        if evidence["reliability_score"] is not None
        else ""
    )


@evidence_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    """Display the evidence register."""

    filter_form = EvidenceFilterForm(request.args)

    search = request.args.get("search", "").strip() or None
    source_type = request.args.get("source_type", "").strip() or None

    try:
        if not filter_form.validate():
            search = None
            source_type = None

        evidence_records = get_evidence_records(
            limit=100,
            offset=0,
            search=search,
            source_type=source_type,
        )

        return render_template(
            "evidence/index.html",
            evidence_records=evidence_records,
            filter_form=filter_form,
        )

    except EvidenceError as exc:
        flash(str(exc), "error")

        return render_template(
            "evidence/index.html",
            evidence_records=[],
            filter_form=filter_form,
        )


@evidence_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    """Create a new evidence record."""

    form = CreateEvidenceForm()

    if form.validate_on_submit():
        try:
            evidence = create_evidence(
                acting_user_id=current_user.id,
                **_form_service_data(form),
            )

            flash("Evidence record created successfully.", "success")

            return redirect(
                url_for(
                    "evidence.detail",
                    evidence_id=evidence["id"],
                )
            )

        except EvidenceError as exc:
            flash(str(exc), "error")

    return render_template(
        "evidence/form.html",
        form=form,
        page_title="Add Evidence",
        submit_label="Create Evidence",
    )


@evidence_bp.route("/<int:evidence_id>", methods=["GET"])
@authenticated_required
def detail(evidence_id):
    """Display an individual evidence record."""

    try:
        evidence = get_evidence_details(evidence_id)

    except EvidenceNotFoundError:
        abort(404)

    except EvidenceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("evidence.index"))

    delete_form = DeleteEvidenceForm()

    return render_template(
        "evidence/detail.html",
        evidence=evidence,
        delete_form=delete_form,
    )


@evidence_bp.route("/<int:evidence_id>/edit", methods=["GET", "POST"])
@analyst_required
def edit(evidence_id):
    """Edit an existing evidence record."""

    try:
        evidence = get_evidence_details(evidence_id)

    except EvidenceNotFoundError:
        abort(404)

    except EvidenceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("evidence.index"))

    form = EditEvidenceForm()

    if request.method == "GET":
        _populate_form(form, evidence)

    if form.validate_on_submit():
        try:
            updated_evidence = update_evidence(
                evidence_id=evidence_id,
                acting_user_id=current_user.id,
                updates=_form_service_data(form),
            )

            flash("Evidence record updated successfully.", "success")

            return redirect(
                url_for(
                    "evidence.detail",
                    evidence_id=updated_evidence["id"],
                )
            )

        except EvidenceError as exc:
            flash(str(exc), "error")

    return render_template(
        "evidence/form.html",
        form=form,
        page_title="Edit Evidence",
        submit_label="Save Changes",
        evidence=evidence,
    )


@evidence_bp.route("/<int:evidence_id>/delete", methods=["POST"])
@analyst_required
def delete(evidence_id):
    """Delete an evidence record and its linked associations."""

    form = DeleteEvidenceForm()

    if not form.validate_on_submit():
        flash("Invalid deletion request. Please try again.", "error")
        return redirect(
            url_for(
                "evidence.detail",
                evidence_id=evidence_id,
            )
        )

    try:
        delete_evidence(
            evidence_id=evidence_id,
            acting_user_id=current_user.id,
        )

        flash(
            "Evidence record and its linked associations were deleted.",
            "success",
        )

    except EvidenceNotFoundError:
        abort(404)

    except EvidenceError as exc:
        flash(str(exc), "error")

        return redirect(
            url_for(
                "evidence.detail",
                evidence_id=evidence_id,
            )
        )

    return redirect(url_for("evidence.index"))
