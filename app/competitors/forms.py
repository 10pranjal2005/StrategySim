from flask_wtf import FlaskForm

from wtforms import (
    IntegerField,
    SelectField,
    SubmitField,
    TextAreaField,
)

from wtforms.validators import (
    InputRequired,
    Length,
    NumberRange,
    Optional,
)


# =========================================================
# COMPETITIVE STRENGTH CHOICES
# =========================================================

COMPETITIVE_STRENGTH_CHOICES = [
    ("", "Not specified"),
    ("1", "1 - Very Low"),
    ("2", "2 - Low"),
    ("3", "3 - Moderate"),
    ("4", "4 - High"),
    ("5", "5 - Very High"),
]


# =========================================================
# ADD COMPETITOR RELATIONSHIP FORM
# =========================================================

class CompetitorRelationshipForm(FlaskForm):
    """
    Form used to associate an existing competitor
    with a target company.

    Competitor choices must be populated by the route
    before validate_on_submit() is called.
    """

    competitor_id = SelectField(
        "Competitor",
        coerce=int,
        choices=[],
        validators=[
            InputRequired(
                message="Please select a competitor."
            ),
        ],
    )

    competitive_strength = SelectField(
        "Competitive Strength",
        choices=COMPETITIVE_STRENGTH_CHOICES,
        default="",
        validators=[
            Optional(),
        ],
    )

    notes = TextAreaField(
        "Relationship Notes",
        validators=[
            Optional(),
            Length(
                max=2000,
                message=(
                    "Relationship notes cannot exceed "
                    "2000 characters."
                ),
            ),
        ],
    )

    submit = SubmitField("Add Competitor")


# =========================================================
# UPDATE COMPETITOR RELATIONSHIP FORM
# =========================================================

class CompetitorRelationshipUpdateForm(FlaskForm):
    """
    Form used to update the competitive strength
    and notes of an existing relationship.

    The competitor and target company cannot be changed
    through this form. A relationship must be deleted
    and recreated if its companies need to change.
    """

    competitive_strength = SelectField(
        "Competitive Strength",
        choices=COMPETITIVE_STRENGTH_CHOICES,
        default="",
        validators=[
            Optional(),
        ],
    )

    notes = TextAreaField(
        "Relationship Notes",
        validators=[
            Optional(),
            Length(
                max=2000,
                message=(
                    "Relationship notes cannot exceed "
                    "2000 characters."
                ),
            ),
        ],
    )

    submit = SubmitField("Update Relationship")


# =========================================================
# DELETE COMPETITOR RELATIONSHIP FORM
# =========================================================

class DeleteCompetitorRelationshipForm(FlaskForm):
    """
    CSRF-protected form used to delete only a
    competitor relationship.
    """

    submit = SubmitField("Remove Relationship")