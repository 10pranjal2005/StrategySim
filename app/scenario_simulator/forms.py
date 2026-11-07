
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    FloatField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
)


SCENARIO_TYPE_CHOICES = [
    ("supplier_price_increase", "Supplier Price Increase"),
    ("supplier_unavailability", "Supplier Unavailability"),
    ("raw_material_shortage", "Raw Material Shortage"),
    ("demand_decline", "Demand Decline"),
    ("competitor_entry", "Competitor Entry"),
    ("substitute_technology", "Substitute Technology"),
]


class ScenarioForm(FlaskForm):
    """Form for creating a strategic business scenario."""

    scenario_name = StringField(
        "Scenario Name",
        validators=[
            DataRequired(message="Scenario name is required."),
            Length(max=150),
        ],
    )

    company_id = SelectField(
        "Company",
        coerce=int,
        validators=[DataRequired()],
    )

    scenario_type = SelectField(
        "Scenario Type",
        choices=SCENARIO_TYPE_CHOICES,
        validators=[DataRequired()],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    # Supplier Price Increase
    price_increase_percent = FloatField(
        "Price Increase (%)",
        validators=[
            Optional(),
            NumberRange(min=0.01, max=1000),
        ],
    )

    # Supplier Unavailability
    # Supplier selection
    supplier_id = SelectField(
        "Supplier",
        coerce=int,
        choices=[(0, "Select a supplier")],
        validators=[Optional()],
    )

    unavailability_duration_days = IntegerField(
        "Unavailability Duration (Days)",
        validators=[Optional(), NumberRange(min=1, max=3650)],
    )

    # Component selection
    component_id = SelectField(
        "Component",
        coerce=int,
        choices=[(0, "Select a component")],
        validators=[Optional()],
    )

    shortage_percent = FloatField(
        "Shortage (%)",
        validators=[
            Optional(),
            NumberRange(min=0.01, max=100),
        ],
    )

    # Demand Decline
    demand_decline_percent = FloatField(
        "Demand Decline (%)",
        validators=[
            Optional(),
            NumberRange(min=0.01, max=100),
        ],
    )

    # Competitor Entry
    market_share_impact_percent = FloatField(
        "Estimated Market Share Impact (%)",
        validators=[
            Optional(),
            NumberRange(min=0.01, max=100),
        ],
    )

    # Substitute Technology
    demand_impact_percent = FloatField(
        "Estimated Demand Impact (%)",
        validators=[
            Optional(),
            NumberRange(min=0.01, max=100),
        ],
    )

    submit = SubmitField("Create Scenario")


class ScenarioFilterForm(FlaskForm):
    """Filters for the scenario dashboard and history."""

    company_id = SelectField(
        "Company",
        coerce=int,
        validators=[Optional()],
    )

    status = SelectField(
        "Status",
        choices=[
            ("", "All Statuses"),
            ("Draft", "Draft"),
            ("Simulated", "Simulated"),
            ("Archived", "Archived"),
        ],
        validators=[Optional()],
    )

    submit = SubmitField("Apply Filters")
