
"""
Supplier Network Forms

Forms for registering, editing, and filtering suppliers.
"""

from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    FloatField,
    BooleanField,
    SubmitField,
)

from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
)


RISK_LEVEL_CHOICES = [
    ("Low", "Low"),
    ("Medium", "Medium"),
    ("High", "High"),
    ("Critical", "Critical"),
]


class SupplierForm(FlaskForm):
    """Shared fields for creating and editing suppliers."""

    name = StringField(
        "Supplier Name",
        validators=[
            DataRequired(message="Supplier name is required."),
            Length(min=2, max=255),
        ],
    )

    supplier_code = StringField(
        "Supplier Code",
        validators=[
            Optional(),
            Length(max=100),
        ],
    )

    parent_supplier_id = SelectField(
        "Parent Supplier",
        choices=[("", "No Parent Supplier")],
        validators=[Optional()],
    )

    country = StringField(
        "Country",
        validators=[Optional(), Length(max=100)],
    )

    headquarters = StringField(
        "Headquarters",
        validators=[Optional(), Length(max=255)],
    )

    supplier_type = StringField(
        "Supplier Type",
        validators=[Optional(), Length(max=100)],
    )

    tier_level = IntegerField(
        "Supplier Tier",
        default=1,
        validators=[
            DataRequired(message="Supplier tier is required."),
            NumberRange(min=1, message="Tier must be at least 1."),
        ],
    )

    risk_level = SelectField(
        "Risk Level",
        choices=RISK_LEVEL_CHOICES,
        validators=[DataRequired()],
    )

    financial_dependency_score = FloatField(
        "Financial Dependency Score",
        validators=[
            Optional(),
            NumberRange(min=0, max=100),
        ],
    )

    operational_risk_score = FloatField(
        "Operational Risk Score",
        validators=[
            Optional(),
            NumberRange(min=0, max=100),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[Optional(), Length(max=5000)],
    )

    is_active = BooleanField(
        "Active Supplier",
        default=True,
    )

    submit = SubmitField("Save Supplier")


class CreateSupplierForm(SupplierForm):
    """Supplier registration form."""

    submit = SubmitField("Create Supplier")


class EditSupplierForm(SupplierForm):
    """Supplier editing form."""

    submit = SubmitField("Save Changes")


class SupplierFilterForm(FlaskForm):
    """Supplier register filters."""

    search = StringField(
        "Search Suppliers",
        validators=[Optional(), Length(max=255)],
    )

    risk_level = SelectField(
        "Risk Level",
        choices=[("", "All Risk Levels")] + RISK_LEVEL_CHOICES,
        validators=[Optional()],
    )

    submit = SubmitField("Apply Filters")


class DeleteSupplierForm(FlaskForm):
    """CSRF-protected supplier deletion form."""

    submit = SubmitField("Delete Supplier")
