
"""StrategySim - SWOT Analysis Forms."""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DateField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
)


FACTOR_TYPE_CHOICES = [
    ("Strength", "Strength"),
    ("Weakness", "Weakness"),
    ("Opportunity", "Opportunity"),
    ("Threat", "Threat"),
]


class SWOTAssessmentForm(FlaskForm):
    """Create and edit SWOT assessments."""

    company_id = SelectField(
        "Company",
        coerce=int,
        validators=[DataRequired(message="Please select a company.")],
    )

    assessment_name = StringField(
        "Assessment Name",
        validators=[
            DataRequired(message="Assessment name is required."),
            Length(min=3, max=150),
        ],
    )

    assessment_date = DateField(
        "Assessment Date",
        validators=[Optional()],
        format="%Y-%m-%d",
    )

    summary = TextAreaField(
        "Summary",
        validators=[
            Optional(),
            Length(max=10000),
        ],
    )

    submit = SubmitField("Save Assessment")


class SWOTFactorForm(FlaskForm):
    """Create and edit individual SWOT factors."""

    factor_type = SelectField(
        "Factor Type",
        choices=FACTOR_TYPE_CHOICES,
        validators=[DataRequired()],
    )

    factor_name = StringField(
        "Factor Name",
        validators=[
            DataRequired(message="Factor name is required."),
            Length(min=3, max=200),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=5000),
        ],
    )

    importance = SelectField(
        "Strategic Importance",
        choices=[
            ("", "Not rated"),
            ("1", "1 - Very Low"),
            ("2", "2 - Low"),
            ("3", "3 - Moderate"),
            ("4", "4 - High"),
            ("5", "5 - Very High"),
        ],
        validators=[Optional()],
    )

    submit = SubmitField("Save Factor")


class SWOTAssessmentFilterForm(FlaskForm):
    """Filter SWOT assessments."""

    search = StringField(
        "Search",
        validators=[
            Optional(),
            Length(max=150),
        ],
    )

    submit = SubmitField("Search")


class DeleteSWOTForm(FlaskForm):
    """CSRF-protected deletion form."""

    submit = SubmitField("Delete")
