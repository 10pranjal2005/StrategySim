"""Forms for managing supplier facilities."""

from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    StringField,
    TextAreaField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
)


class FacilityForm(FlaskForm):
    """Create or update a supplier facility."""

    supplier_id = SelectField(
        "Supplier",
        coerce=int,
        validators=[DataRequired()],
    )

    facility_name = StringField(
        "Facility Name",
        validators=[
            DataRequired(),
            Length(max=200),
        ],
    )

    facility_type = StringField(
        "Facility Type",
        validators=[
            Optional(),
            Length(max=100),
        ],
    )

    country = StringField(
        "Country",
        validators=[
            Optional(),
            Length(max=100),
        ],
    )

    city = StringField(
        "City",
        validators=[
            Optional(),
            Length(max=100),
        ],
    )

    capacity_description = TextAreaField(
        "Capacity Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    operational_status = SelectField(
        "Operational Status",
        choices=[
            ("Active", "Active"),
            ("Inactive", "Inactive"),
            ("Disrupted", "Disrupted"),
        ],
        validators=[DataRequired()],
    )

    submit = SubmitField("Save Facility")


class DeleteFacilityForm(FlaskForm):
    """Delete a supplier facility."""

    submit = SubmitField("Delete Facility")