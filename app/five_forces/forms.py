
"""StrategySim - Five Forces WTForms."""

from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    SelectField,
    TextAreaField,
    DateField,
    IntegerField,
    DecimalField,
    SubmitField,
)

from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
    ValidationError,
)

from app.five_forces.services import FORCES


class FiveForcesAssessmentForm(FlaskForm):
    """Create and update a Five Forces assessment."""

    company_id = SelectField(
        "Company",
        coerce=int,
        validators=[DataRequired(message="Select a company.")],
    )

    assessment_name = StringField(
        "Assessment Name",
        validators=[
            DataRequired(message="Assessment name is required."),
            Length(max=150),
        ],
    )

    assessment_date = DateField(
        "Assessment Date",
        format="%Y-%m-%d",
        validators=[Optional()],
    )

    summary = TextAreaField(
        "Assessment Summary",
        validators=[
            Optional(),
            Length(max=5000),
        ],
    )

    submit = SubmitField("Save Assessment")


class FiveForcesIndicatorForm(FlaskForm):
    """Create and update an indicator under a competitive force."""

    force_name = SelectField(
        "Competitive Force",
        choices=[(force, force) for force in FORCES],
        validators=[DataRequired(message="Select a competitive force.")],
    )

    indicator_name = StringField(
        "Indicator Name",
        validators=[
            DataRequired(message="Indicator name is required."),
            Length(max=200),
        ],
    )

    score = IntegerField(
        "Force Intensity Score (1–5)",
        validators=[
            DataRequired(message="Enter a score."),
            NumberRange(
                min=1,
                max=5,
                message="Score must be between 1 and 5.",
            ),
        ],
    )

    weight = DecimalField(
        "Indicator Weight",
        places=2,
        default=1,
        validators=[
            DataRequired(message="Enter an indicator weight."),
            NumberRange(
                min=0.01,
                message="Weight must be greater than zero.",
            ),
        ],
    )

    explanation = TextAreaField(
        "Explanation",
        validators=[
            Optional(),
            Length(max=5000),
        ],
    )

    evidence_id = StringField(
        "Evidence Record ID (Optional)",
        validators=[Optional(), Length(max=20)],
    )

    submit = SubmitField("Save Indicator")

    def validate_evidence_id(self, field):
        """Accept only a positive integer evidence ID or blank."""

        value = (field.data or "").strip()

        if not value:
            field.data = None
            return

        if not value.isdigit() or int(value) <= 0:
            raise ValidationError(
                "Evidence ID must be a positive integer."
            )

        field.data = str(int(value))


class FiveForcesFilterForm(FlaskForm):
    """Filter assessments."""

    company_id = SelectField(
        "Company",
        coerce=int,
        validators=[Optional()],
    )

    search = StringField(
        "Search",
        validators=[Optional(), Length(max=150)],
    )

    submit = SubmitField("Filter")


class DeleteFiveForcesForm(FlaskForm):
    """CSRF-protected deletion form."""

    submit = SubmitField("Delete")
