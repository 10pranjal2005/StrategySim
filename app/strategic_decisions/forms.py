
# =========================================================
# STRATEGYSIM - STRATEGIC DECISIONS FORMS
# =========================================================

from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    FloatField,
    IntegerField,
    SubmitField,
)

from wtforms.validators import (
    DataRequired,
    Length,
    NumberRange,
    Optional,
)


# =========================================================
# CREATE DECISION MATRIX FORM
# =========================================================

class DecisionMatrixForm(FlaskForm):

    company_id = SelectField(
        "Target Company",
        coerce=int,
        choices=[],
        validators=[DataRequired()],
    )

    matrix_name = StringField(
        "Decision Name",
        validators=[
            DataRequired(),
            Length(max=200),
        ],
    )

    objective = TextAreaField(
        "Decision Objective",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    description = TextAreaField(
        "Decision Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    submit = SubmitField("Create Decision")


# =========================================================
# ADD STRATEGIC ALTERNATIVE FORM
# =========================================================

class DecisionOptionForm(FlaskForm):

    option_name = StringField(
        "Alternative Name",
        validators=[
            DataRequired(),
            Length(max=200),
        ],
    )

    description = TextAreaField(
        "Alternative Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    submit = SubmitField("Add Alternative")


# =========================================================
# ADD EVALUATION CRITERION FORM
# =========================================================

class DecisionCriterionForm(FlaskForm):

    criterion_name = StringField(
        "Criterion Name",
        validators=[
            DataRequired(),
            Length(max=200),
        ],
    )

    weight = FloatField(
        "Criterion Weight",
        validators=[
            DataRequired(),
            NumberRange(
                min=0,
                message="Weight cannot be negative.",
            ),
        ],
    )

    description = TextAreaField(
        "Criterion Description",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    submit = SubmitField("Add Criterion")


# =========================================================
# ALTERNATIVE EVALUATION FORM
# =========================================================

class DecisionScoreForm(FlaskForm):

    option_id = SelectField(
        "Strategic Alternative",
        coerce=int,
        choices=[],
        validators=[DataRequired()],
    )

    criterion_id = SelectField(
        "Evaluation Criterion",
        coerce=int,
        choices=[],
        validators=[DataRequired()],
    )

    score = IntegerField(
        "Score (1–5)",
        validators=[
            DataRequired(),
            NumberRange(
                min=1,
                max=5,
                message="Score must be between 1 and 5.",
            ),
        ],
    )

    justification = TextAreaField(
        "Evaluation Justification",
        validators=[
            Optional(),
            Length(max=2000),
        ],
    )

    submit = SubmitField("Save Evaluation")


# =========================================================
# DECISION FILTER FORM
# =========================================================

class DecisionFilterForm(FlaskForm):

    company_id = SelectField(
        "Company",
        coerce=int,
        choices=[],
        validators=[Optional()],
    )

    submit = SubmitField("Filter Decisions")
