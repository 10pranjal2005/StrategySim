from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    DecimalField,
    DateField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
    ValidationError,
)


class ValueChainAssessmentForm(FlaskForm):
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
            Length(max=2000),
        ],
    )

    submit = SubmitField("Save Assessment")


class ValueChainActivityForm(FlaskForm):
    activity_category = SelectField(
        "Activity Category",
        choices=[
            ("Primary", "Primary Activity"),
            ("Support", "Support Activity"),
        ],
        validators=[DataRequired()],
    )

    activity_name = StringField(
        "Activity Name",
        validators=[
            DataRequired(message="Activity name is required."),
            Length(max=150),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    cost_contribution = DecimalField(
        "Cost Contribution",
        validators=[
            Optional(),
            NumberRange(
                min=0,
                message="Cost contribution cannot be negative.",
            ),
        ],
        places=2,
    )

    strategic_importance = IntegerField(
        "Strategic Importance",
        validators=[
            Optional(),
            NumberRange(
                min=1,
                max=5,
                message="Strategic importance must be between 1 and 5.",
            ),
        ],
    )

    competitive_advantage = TextAreaField(
        "Competitive Advantage",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    evidence_id = IntegerField(
        "Evidence ID",
        validators=[
            Optional(),
            NumberRange(
                min=1,
                message="Evidence ID must be a positive integer.",
            ),
        ],
    )

    submit = SubmitField("Save Activity")


class ValueChainFilterForm(FlaskForm):
    search = StringField(
        "Search Assessments",
        validators=[
            Optional(),
            Length(max=150),
        ],
    )

    submit = SubmitField("Search")


class DeleteValueChainForm(FlaskForm):
    submit = SubmitField("Delete")