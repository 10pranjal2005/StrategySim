from app.suppliers.mapping_forms import SupplierComponentMappingForm

from app.suppliers.services import (
    add_supplier_component,
    get_supplier_component,
    get_supplier_components,
    update_supplier_component,
    remove_supplier_component,
    get_supplier_records,
    SupplierComponentError,
)

from app.database import get_db

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)

from flask_login import current_user

from app.suppliers.component_forms import (
    ComponentForm,
    DeleteComponentForm,
)

from app.suppliers.services import (
    create_component,
    get_component_details,
    get_component_records,
    update_component,
    delete_component,
    SupplierError,
)

from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)


supplier_components_bp = Blueprint(
    "supplier_components",
    __name__,
    url_prefix="/components",
)


def _handle_component_error(error):
    flash(str(error), "error")


@supplier_components_bp.route("/")
@authenticated_required
def index():
    search = request.args.get("search", "").strip()
    criticality = request.args.get("criticality", "").strip()
    active_only = request.args.get("active_only") == "1"

    components = get_component_records(
        search=search or None,
        criticality=criticality or None,
        active_only=active_only,
    )

    return render_template(
        "suppliers/components/index.html",
        components=components,
        search=search,
        criticality=criticality,
        active_only=active_only,
    )


@supplier_components_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    form = ComponentForm()

    if form.validate_on_submit():
        try:
            component = create_component(
                acting_user_id=current_user.id,
                name=form.name.data,
                component_code=form.component_code.data,
                category=form.category.data,
                description=form.description.data,
                criticality=form.criticality.data,
                is_active=form.is_active.data,
            )

            flash("Component registered successfully.", "success")

            return redirect(
                url_for(
                    "supplier_components.detail",
                    component_id=component["id"],
                )
            )

        except SupplierError as error:
            _handle_component_error(error)

    return render_template(
        "suppliers/components/form.html",
        form=form,
        page_heading="Register Component",
        is_edit=False,
    )


@supplier_components_bp.route("/<int:component_id>")
@authenticated_required
def detail(component_id):
    component = get_component_details(component_id)

    if component is None:
        flash("Component not found.", "error")
        return redirect(url_for("supplier_components.index"))

        database = get_db()

        component_suppliers = database.execute(
            """
            SELECT
                sc.id,
                sc.supplier_id,
                sc.component_id,
                sc.unit_cost,
                sc.lead_time_days,
                sc.dependency_share_percent,
                sc.is_alternative,
                s.name AS supplier_name,
                s.supplier_code,
                s.country,
                s.risk_level,
                s.is_active AS supplier_is_active
            FROM supplier_components AS sc
            JOIN suppliers AS s
                ON s.id = sc.supplier_id
            WHERE sc.component_id = ?
            ORDER BY s.name
            """,
            (component_id,),
        ).fetchall()

        return render_template(
            "suppliers/components/detail.html",
            component=component,
            component_suppliers=component_suppliers,
            delete_form=DeleteComponentForm(),
        )


@supplier_components_bp.route(
    "/<int:component_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit(component_id):
    component = get_component_details(component_id)

    if component is None:
        flash("Component not found.", "error")
        return redirect(url_for("supplier_components.index"))

    form = ComponentForm()

    if request.method == "GET":
        form.name.data = component["name"]
        form.component_code.data = component.get("component_code")
        form.category.data = component.get("category")
        form.description.data = component.get("description")
        form.criticality.data = component["criticality"]
        form.is_active.data = bool(component["is_active"])

    if form.validate_on_submit():
        try:
            update_component(
                component_id=component_id,
                acting_user_id=current_user.id,
                updates={
                    "name": form.name.data,
                    "component_code": form.component_code.data,
                    "category": form.category.data,
                    "description": form.description.data,
                    "criticality": form.criticality.data,
                    "is_active": form.is_active.data,
                },
            )

            flash("Component updated successfully.", "success")

            return redirect(
                url_for(
                    "supplier_components.detail",
                    component_id=component_id,
                )
            )

        except SupplierError as error:
            _handle_component_error(error)

    return render_template(
        "suppliers/components/form.html",
        form=form,
        page_heading="Edit Component",
        is_edit=True,
        component=component,
    )


@supplier_components_bp.route(
    "/<int:component_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(component_id):
    form = DeleteComponentForm()

    if not form.validate_on_submit():
        flash("Invalid deletion request.", "error")
        return redirect(
            url_for(
                "supplier_components.detail",
                component_id=component_id,
            )
        )

    try:
        delete_component(
            component_id=component_id,
            acting_user_id=current_user.id,
        )

        flash("Component deleted successfully.", "success")

    except SupplierError as error:
        _handle_component_error(error)

        return redirect(
            url_for(
                "supplier_components.detail",
                component_id=component_id,
            )
        )

    return redirect(url_for("supplier_components.index"))

def _populate_mapping_choices(form):
    database = get_db()

    suppliers = database.execute(
        """
        SELECT id, name
        FROM suppliers
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    components = database.execute(
        """
        SELECT id, name
        FROM components
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    form.supplier_id.choices = [
        (row["id"], row["name"]) for row in suppliers
    ]

    form.component_id.choices = [
        (row["id"], row["name"]) for row in components
    ]


@supplier_components_bp.route(
    "/mappings/new",
    methods=["GET", "POST"],
)
@analyst_required
def create_mapping():
    form = SupplierComponentMappingForm()
    _populate_mapping_choices(form)

    if request.method == "GET":
        supplier_id = request.args.get("supplier_id", type=int)
        component_id = request.args.get("component_id", type=int)

        if supplier_id:
            form.supplier_id.data = supplier_id

        if component_id:
            form.component_id.data = component_id

    if form.validate_on_submit():
        try:
            mapping = add_supplier_component(
                acting_user_id=current_user.id,
                supplier_id=form.supplier_id.data,
                component_id=form.component_id.data,
                unit_cost=form.unit_cost.data,
                lead_time_days=form.lead_time_days.data,
                dependency_share_percent=form.dependency_share_percent.data,
                is_alternative=form.is_alternative.data,
            )

            flash("Supplier-component mapping created successfully.", "success")

            return redirect(
                url_for(
                    "supplier_components.detail",
                    component_id=form.component_id.data,
                )
            )

        except SupplierComponentError as error:
            flash(str(error), "error")

    return render_template(
        "suppliers/components/mapping_form.html",
        form=form,
        page_heading="Add Supplier–Component Mapping",
    )


@supplier_components_bp.route(
    "/mappings/<int:mapping_id>/edit",
    methods=["GET", "POST"],
)
@analyst_required
def edit_mapping(mapping_id):
    mapping = get_supplier_component(mapping_id)

    if mapping is None:
        flash("Supplier-component mapping not found.", "error")
        return redirect(url_for("supplier_components.index"))

    form = SupplierComponentMappingForm()
    _populate_mapping_choices(form)

    if request.method == "GET":
        form.supplier_id.data = mapping["supplier_id"]
        form.component_id.data = mapping["component_id"]
        form.unit_cost.data = mapping.get("unit_cost")
        form.lead_time_days.data = mapping.get("lead_time_days")
        form.dependency_share_percent.data = mapping.get(
            "dependency_share_percent"
        )
        form.is_alternative.data = bool(mapping["is_alternative"])

    if form.validate_on_submit():
        try:
            update_supplier_component(
                mapping_id=mapping_id,
                acting_user_id=current_user.id,
                updates={
                    "supplier_id": form.supplier_id.data,
                    "component_id": form.component_id.data,
                    "unit_cost": form.unit_cost.data,
                    "lead_time_days": form.lead_time_days.data,
                    "dependency_share_percent": form.dependency_share_percent.data,
                    "is_alternative": form.is_alternative.data,
                },
            )

            flash("Supplier-component mapping updated successfully.", "success")

            return redirect(
                url_for(
                    "supplier_components.detail",
                    component_id=form.component_id.data,
                )
            )

        except SupplierComponentError as error:
            flash(str(error), "error")

    return render_template(
        "suppliers/components/mapping_form.html",
        form=form,
        page_heading="Edit Supplier–Component Mapping",
    )


@supplier_components_bp.route(
    "/mappings/<int:mapping_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete_mapping(mapping_id):
    mapping = get_supplier_component(mapping_id)

    if mapping is None:
        flash("Supplier-component mapping not found.", "error")
        return redirect(url_for("supplier_components.index"))

    component_id = mapping["component_id"]

    try:
        remove_supplier_component(
            mapping_id=mapping_id,
            acting_user_id=current_user.id,
        )

        flash("Supplier-component mapping removed successfully.", "success")

    except SupplierComponentError as error:
        flash(str(error), "error")

    return redirect(
        url_for(
            "supplier_components.detail",
            component_id=component_id,
        )
    )