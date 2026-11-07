
"""
Supplier Network Routes

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

from app.suppliers import suppliers_bp

from app.suppliers.forms import (
    CreateSupplierForm,
    EditSupplierForm,
    SupplierFilterForm,
    DeleteSupplierForm,
)

from app.suppliers.services import (
    SupplierError,
    SupplierNotFoundError,
    SupplierValidationError,
    create_supplier,
    get_supplier_details,
    get_supplier_records,
    update_supplier,
    delete_supplier,
)

from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)

from app.database import get_db

from app.database import get_db

from app.suppliers.relationship_forms import (
    SupplierRelationshipForm,
)

from app.suppliers.services import (
    create_supplier_relationship,
    get_supplier_relationships,
    delete_supplier_relationship,
    SupplierRelationshipError,
)

def _form_service_data(form):
    """Convert validated supplier form fields into service data."""

    parent_id = form.parent_supplier_id.data

    return {
        "name": form.name.data,
        "supplier_code": form.supplier_code.data or None,
        "parent_supplier_id": int(parent_id) if parent_id else None,
        "country": form.country.data or None,
        "headquarters": form.headquarters.data or None,
        "supplier_type": form.supplier_type.data or None,
        "tier_level": form.tier_level.data,
        "risk_level": form.risk_level.data,
        "financial_dependency_score": (
            form.financial_dependency_score.data
        ),
        "operational_risk_score": (
            form.operational_risk_score.data
        ),
        "description": form.description.data or None,
        "is_active": form.is_active.data,
    }


def _populate_form(form, supplier):
    """Populate the supplier form from a database record."""

    form.name.data = supplier["name"]
    form.supplier_code.data = supplier["supplier_code"]
    form.parent_supplier_id.data = (
        str(supplier["parent_supplier_id"])
        if supplier["parent_supplier_id"] is not None
        else ""
    )
    form.country.data = supplier["country"]
    form.headquarters.data = supplier["headquarters"]
    form.supplier_type.data = supplier["supplier_type"]
    form.tier_level.data = supplier["tier_level"]
    form.risk_level.data = supplier["risk_level"]
    form.financial_dependency_score.data = (
        supplier["financial_dependency_score"]
    )
    form.operational_risk_score.data = (
        supplier["operational_risk_score"]
    )
    form.description.data = supplier["description"]
    form.is_active.data = bool(supplier["is_active"])


def _set_parent_choices(form, exclude_supplier_id=None):
    """Populate parent supplier choices."""

    suppliers = get_supplier_records(
        active_only=True,
        limit=500,
        offset=0,
    )

    form.parent_supplier_id.choices = [
        ("", "No Parent Supplier")
    ]

    for supplier in suppliers:
        if supplier["id"] == exclude_supplier_id:
            continue

        form.parent_supplier_id.choices.append(
            (str(supplier["id"]), supplier["name"])
        )


def _handle_supplier_error(error):
    """Display a supplier service error."""

    flash(str(error), "error")


@suppliers_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    """Display the supplier register."""

    filter_form = SupplierFilterForm(request.args)

    search = request.args.get("search", "").strip() or None
    risk_level = request.args.get("risk_level", "").strip() or None

    try:
        if not filter_form.validate():
            search = None
            risk_level = None

        supplier_records = get_supplier_records(
            search=search,
            risk_level=risk_level,
            limit=100,
            offset=0,
        )

        return render_template(
            "suppliers/index.html",
            supplier_records=supplier_records,
            filter_form=filter_form,
        )

    except SupplierError as exc:
        _handle_supplier_error(exc)

        return render_template(
            "suppliers/index.html",
            supplier_records=[],
            filter_form=filter_form,
        )


@suppliers_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    """Register a new supplier."""

    form = CreateSupplierForm()
    _set_parent_choices(form)

    if form.validate_on_submit():
        try:
            supplier = create_supplier(
                acting_user_id=current_user.id,
                **_form_service_data(form),
            )

            flash(
                "Supplier registered successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "suppliers.detail",
                    supplier_id=supplier["id"],
                )
            )

        except SupplierError as exc:
            _handle_supplier_error(exc)

    return render_template(
        "suppliers/form.html",
        form=form,
        page_title="Add Supplier",
        submit_label="Create Supplier",
    )


@suppliers_bp.route("/<int:supplier_id>", methods=["GET"])
@authenticated_required
def detail(supplier_id):
    """Display supplier details."""

    try:
        supplier = get_supplier_details(supplier_id)

    except SupplierNotFoundError:
        abort(404)

    except SupplierError as exc:
        _handle_supplier_error(exc)
        return redirect(url_for("suppliers.index"))

    database = get_db()

    supplier_components = database.execute(
        """
        SELECT
            sc.id,
            sc.supplier_id,
            sc.component_id,
            sc.unit_cost,
            sc.lead_time_days,
            sc.dependency_share_percent,
            sc.is_alternative,
            c.name AS component_name,
            c.component_code,
            c.category,
            c.criticality,
            c.is_active AS component_is_active
        FROM supplier_components AS sc
        JOIN components AS c
            ON c.id = sc.component_id
        WHERE sc.supplier_id = ?
        ORDER BY c.name
        """,
        (supplier_id,),
    ).fetchall()

    supplier_facilities = database.execute(
            """
            SELECT
                f.id,
                f.supplier_id,
                f.facility_name,
                f.facility_type,
                f.country,
                f.city,
                f.capacity_description,
                f.operational_status,
                f.created_at
            FROM facilities AS f
            WHERE f.supplier_id = ?
            ORDER BY f.facility_name
            """,
            (supplier_id,),
    ).fetchall()

    delete_form = DeleteSupplierForm()

    return render_template(
        "suppliers/detail.html",
        supplier=supplier,
        supplier_components=supplier_components,
        supplier_facilities=supplier_facilities,
        delete_form=delete_form,
    )

@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@analyst_required
def edit(supplier_id):
    """Edit an existing supplier."""

    try:
        supplier = get_supplier_details(supplier_id)

    except SupplierNotFoundError:
        abort(404)

    except SupplierError as exc:
        _handle_supplier_error(exc)
        return redirect(url_for("suppliers.index"))

    form = EditSupplierForm()

    _set_parent_choices(
        form,
        exclude_supplier_id=supplier_id,
    )

    if request.method == "GET":
        _populate_form(form, supplier)

    if form.validate_on_submit():
        try:
            updated_supplier = update_supplier(
                supplier_id=supplier_id,
                acting_user_id=current_user.id,
                updates=_form_service_data(form),
            )

            flash(
                "Supplier updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "suppliers.detail",
                    supplier_id=updated_supplier["id"],
                )
            )

        except SupplierError as exc:
            _handle_supplier_error(exc)

    return render_template(
        "suppliers/form.html",
        form=form,
        page_title="Edit Supplier",
        submit_label="Save Changes",
        supplier=supplier,
    )


@suppliers_bp.route(
    "/<int:supplier_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(supplier_id):
    """Delete a supplier."""

    form = DeleteSupplierForm()

    if not form.validate_on_submit():
        flash(
            "Invalid deletion request. Please try again.",
            "error",
        )
        return redirect(
            url_for(
                "suppliers.detail",
                supplier_id=supplier_id,
            )
        )

    try:
        delete_supplier(
            supplier_id=supplier_id,
            acting_user_id=current_user.id,
        )

        flash(
            "Supplier deleted successfully.",
            "success",
        )

    except SupplierNotFoundError:
        abort(404)

    except SupplierError as exc:
        _handle_supplier_error(exc)

        return redirect(
            url_for(
                "suppliers.detail",
                supplier_id=supplier_id,
            )
        )

    return redirect(url_for("suppliers.index"))
