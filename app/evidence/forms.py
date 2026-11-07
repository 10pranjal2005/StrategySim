
"""
Evidence Management Forms

Flask-WTF forms for creating, editing, filtering and deleting
evidence records.
"""

from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    IntegerField,
    SubmitField,
)

from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    NumberRange,
    URL,
)


SOURCE_TYPE_CHOICES = [
    ("Manual", "Manual"),
    ("CSV Import", "CSV Import"),
    ("External Source", "External Source"),
    ("Internal Research", "Internal Research"),
    ("Document", "Document"),
]

ENTITY_TYPE_CHOICES = [
    ("", "Not linked to an entity"),
    ("Company", "Company"),
]


class EvidenceForm(FlaskForm):
    """Shared fields for creating and editing evidence."""

    title = StringField(
        "Evidence Title",
        validators=[
            DataRequired(message="Evidence title is required."),
            Length(
                min=2,
                max=255,
                message="Title must contain between 2 and 255 characters.",
            ),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[
            Optional(),
            Length(
                max=5000,
                message="Description cannot exceed 5000 characters.",
            ),
        ],
    )

    source_type = SelectField(
        "Source Type",
        choices=SOURCE_TYPE_CHOICES,
        validators=[
            DataRequired(message="Select an evidence source type."),
        ],
    )

    source_name = StringField(
        "Source Name",
        validators=[
            Optional(),
            Length(max=255, message="Source name is too long."),
        ],
    )

    source_url = StringField(
        "Source URL",
        validators=[
            Optional(),
            URL(message="Enter a valid URL."),
            Length(max=2048, message="Source URL is too long."),
        ],
    )

    file_path = StringField(
        "File Path",
        validators=[
            Optional(),
            Length(max=1000, message="File path is too long."),
        ],
    )

    entity_type = SelectField(
        "Linked Entity Type",
        choices=ENTITY_TYPE_CHOICES,
        validators=[Optional()],
    )

    entity_id = IntegerField(
        "Linked Company ID",
        validators=[
            Optional(),
            NumberRange(
                min=1,
                message="Company ID must be a positive integer.",
            ),
        ],
    )

    reliability_score = SelectField(
        "Reliability Score",
        choices=[
            ("", "Not assessed"),
            ("1", "1 - Very Low"),
            ("2", "2 - Low"),
            ("3", "3 - Moderate"),
            ("4", "4 - High"),
            ("5", "5 - Very High"),
        ],
        validators=[Optional()],
    )

    submit = SubmitField("Save Evidence")


class CreateEvidenceForm(EvidenceForm):
    """Form used to create an evidence record."""

    submit = SubmitField("Create Evidence")


class EditEvidenceForm(EvidenceForm):
    """Form used to update an existing evidence record."""

    submit = SubmitField("Save Changes")


class EvidenceFilterForm(FlaskForm):
    """Optional filters for the evidence register."""

    search = StringField(
        "Search Evidence",
        validators=[
            Optional(),
            Length(max=255),
        ],
    )

    source_type = SelectField(
        "Source Type",
        choices=[("", "All Source Types")] + SOURCE_TYPE_CHOICES,
        validators=[Optional()],
    )

    submit = SubmitField("Apply Filters")


class DeleteEvidenceForm(FlaskForm):
    """CSRF-protected evidence deletion form."""

    submit = SubmitField("Delete Evidence")
