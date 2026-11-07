from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    FloatField,
    IntegerField,
    BooleanField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    NumberRange,
)


class SupplierComponentMappingForm(FlaskForm):
    supplier_id = SelectField(
        "Supplier",
        coerce=int,
        validators=[DataRequired()],
    )

    component_id = SelectField(
        "Component",
        coerce=int,
        validators=[DataRequired()],
    )

    unit_cost = FloatField(
        "Unit Cost",
        validators=[
            Optional(),
            NumberRange(min=0),
        ],
    )

    lead_time_days = IntegerField(
        "Lead Time (Days)",
        validators=[
            Optional(),
            NumberRange(min=0),
        ],
    )

    dependency_share_percent = FloatField(
        "Dependency Share (%)",
        validators=[
            Optional(),
            NumberRange(min=0, max=100),
        ],
    )

    is_alternative = BooleanField(
        "Alternative Supplier",
        default=False,
    )

    submit = SubmitField("Save Mapping")