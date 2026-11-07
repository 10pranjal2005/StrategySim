"""Forms for managing supplier relationships."""

from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    FloatField,
    TextAreaField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    NumberRange,
    Length,
)


class SupplierRelationshipForm(FlaskForm):
    """Create a relationship between two suppliers."""

    source_supplier_id = SelectField(
        "Source Supplier",
        coerce=int,
        validators=[DataRequired()],
    )

    target_supplier_id = SelectField(
        "Target Supplier",
        coerce=int,
        validators=[DataRequired()],
    )

    relationship_type = SelectField(
        "Relationship Type",
        choices=[
            ("Parent-Subsidiary", "Parent–Subsidiary"),
            ("Strategic Partnership", "Strategic Partnership"),
            ("Supply Agreement", "Supply Agreement"),
            ("Manufacturing Partnership", "Manufacturing Partnership"),
            ("Joint Venture", "Joint Venture"),
            ("Other", "Other"),
        ],
        validators=[DataRequired()],
    )

    dependency_strength = FloatField(
        "Dependency Strength (%)",
        validators=[
            Optional(),
            NumberRange(
                min=0,
                max=100,
                message="Dependency strength must be between 0 and 100.",
            ),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    submit = SubmitField("Create Relationship")

class DeleteSupplierRelationshipForm(FlaskForm):
    """Form for deleting a supplier relationship."""

    submit = SubmitField("Delete Relationship")