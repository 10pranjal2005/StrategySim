"""Routes for managing supplier facilities."""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    abort,
    request,
)
from flask_login import current_user

from app.database import get_db
from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)

from app.suppliers.facility_forms import (
    FacilityForm,
    DeleteFacilityForm,
)

from app.suppliers.services import (
    create_facility,
    get_facility_details,
    get_facility_records,
    update_facility,
    delete_facility,
    SupplierError,
    FacilityNotFoundError,
)


supplier_facilities_bp = Blueprint(
    "supplier_facilities",
    __name__,
    url_prefix="/facilities",
)


def _populate_supplier_choices(form):
    database = get_db()

    suppliers = database.execute(
        """
        SELECT id, name
        FROM suppliers
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    form.supplier_id.choices = [
        (supplier["id"], supplier["name"])
        for supplier in suppliers
    ]


def _populate_form(form, facility):
    form.supplier_id.data = facility["supplier_id"]
    form.facility_name.data = facility["facility_name"]
    form.facility_type.data = facility["facility_type"]
    form.country.data = facility["country"]
    form.city.data = facility["city"]
    form.capacity_description.data = facility["capacity_description"]
    form.operational_status.data = facility["operational_status"]


def _form_data(form):
    return {
        "facility_name": form.facility_name.data,
        "facility_type": form.facility_type.data,
        "country": form.country.data,
        "city": form.city.data,
        "capacity_description": form.capacity_description.data,
        "operational_status": form.operational_status.data,
    }


def _handle_facility_error(error):
    flash(str(error), "error")


@supplier_facilities_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    supplier_id = request.args.get("supplier_id", type=int)

    try:
        facilities = get_facility_records(
            supplier_id=supplier_id
        )
    except SupplierError as error:
        _handle_facility_error(error)
        facilities = []
        supplier_id = None

    return render_template(
        "suppliers/facilities/index.html",
        facilities=facilities,
        supplier_id=supplier_id,
    )


@supplier_facilities_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    form = FacilityForm()
    _populate_supplier_choices(form)

    if form.validate_on_submit():
        try:
            facility = create_facility(
                acting_user_id=current_user.id,
                supplier_id=form.supplier_id.data,
                **_form_data(form),
            )

            flash(
                "Supplier facility created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "supplier_facilities.detail",
                    facility_id=facility["id"],
                )
            )

        except SupplierError as error:
            _handle_facility_error(error)

    return render_template(
        "suppliers/facilities/form.html",
        form=form,
        page_title="Add Supplier Facility",
    )


@supplier_facilities_bp.route(
    "/<int:facility_id>",
    methods=["GET"],
)
@authenticated_required
def detail(facility_id):
    try:
        facility = get_facility_details(facility_id)
    except FacilityNotFoundError:
        abort(404)
    except SupplierError as error:
        _handle_facility_error(error)
        return redirect(url_for("supplier_facilities.index"))

    delete_form = DeleteFacilityForm()

    return render_template(
        "suppliers/facilities/detail.html",
        facility=facility,
        delete_form=delete_form,
    )


@supplier_facilities_bp.route(
    "/<int:facility_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit(facility_id):
    try:
        facility = get_facility_details(facility_id)
    except FacilityNotFoundError:
        abort(404)
    except SupplierError as error:
        _handle_facility_error(error)
        return redirect(url_for("supplier_facilities.index"))

    form = FacilityForm()
    _populate_supplier_choices(form)
    form.supplier_id.validators = []

    if request.method == "GET":
        _populate_form(form, facility)

    if form.validate_on_submit():
        try:
            updated_facility = update_facility(
                facility_id=facility_id,
                acting_user_id=current_user.id,
                updates=_form_data(form),
            )

            flash(
                "Supplier facility updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "supplier_facilities.detail",
                    facility_id=updated_facility["id"],
                )
            )

        except SupplierError as error:
            _handle_facility_error(error)

    return render_template(
        "suppliers/facilities/form.html",
        form=form,
        facility=facility,
        page_title="Edit Supplier Facility",
    )


@supplier_facilities_bp.route(
    "/<int:facility_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(facility_id):
    form = DeleteFacilityForm()

    if form.validate_on_submit():
        try:
            delete_facility(
                facility_id=facility_id,
                acting_user_id=current_user.id,
            )

            flash(
                "Supplier facility deleted successfully.",
                "success",
            )

        except SupplierError as error:
            _handle_facility_error(error)

    else:
        flash(
            "Invalid request. Please try again.",
            "error",
        )

    return redirect(
        url_for("supplier_facilities.index")
    )