from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import current_user

from app.database import get_db
from app.utils.decorators import (
    authenticated_required,
    analyst_required,
)

from app.suppliers.relationship_forms import (
    SupplierRelationshipForm,
    DeleteSupplierRelationshipForm,
)

from app.suppliers.services import (
    create_supplier_relationship,
    get_supplier_relationships,
    delete_supplier_relationship,
    SupplierRelationshipError,
)


supplier_relationships_bp = Blueprint(
    "supplier_relationships",
    __name__,
    url_prefix="/supplier-relationships",
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

    choices = [
        (supplier["id"], supplier["name"])
        for supplier in suppliers
    ]

    form.source_supplier_id.choices = choices
    form.target_supplier_id.choices = choices


def _handle_relationship_error(error):
    flash(str(error), "error")


@supplier_relationships_bp.route("/", methods=["GET"])
@authenticated_required
def index():
    supplier_id = request.args.get("supplier_id", type=int)

    try:
        relationships = get_supplier_relationships(
            supplier_id=supplier_id
        )
    except SupplierRelationshipError as error:
        _handle_relationship_error(error)
        relationships = []
        supplier_id = None

    delete_form = DeleteSupplierRelationshipForm()

    return render_template(
        "suppliers/relationships/index.html",
        relationships=relationships,
        delete_form=delete_form,
        supplier_id=supplier_id,
    )


@supplier_relationships_bp.route("/new", methods=["GET", "POST"])
@analyst_required
def create():
    form = SupplierRelationshipForm()
    _populate_supplier_choices(form)

    if form.validate_on_submit():
        try:
            if (
                form.source_supplier_id.data
                == form.target_supplier_id.data
            ):
                flash(
                    "A supplier cannot have a relationship with itself.",
                    "error",
                )
            else:
                create_supplier_relationship(
                    acting_user_id=current_user.id,
                    source_supplier_id=form.source_supplier_id.data,
                    target_supplier_id=form.target_supplier_id.data,
                    relationship_type=form.relationship_type.data,
                    dependency_strength=form.dependency_strength.data,
                    description=form.description.data,
                )

                flash(
                    "Supplier relationship created successfully.",
                    "success",
                )

                return redirect(
                    url_for("supplier_relationships.index")
                )

        except SupplierRelationshipError as error:
            _handle_relationship_error(error)

    return render_template(
        "suppliers/relationships/form.html",
        form=form,
        page_title="Create Supplier Relationship",
    )


@supplier_relationships_bp.route(
    "/<int:relationship_id>/delete",
    methods=["POST"],
)
@analyst_required
def delete(relationship_id):
    form = DeleteSupplierRelationshipForm()

    if form.validate_on_submit():
        try:
            delete_supplier_relationship(
                relationship_id=relationship_id,
                acting_user_id=current_user.id,
            )

            flash(
                "Supplier relationship deleted successfully.",
                "success",
            )

        except SupplierRelationshipError as error:
            _handle_relationship_error(error)

    else:
        flash(
            "Invalid request. Please try again.",
            "error",
        )

    return redirect(
        url_for("supplier_relationships.index")
    )