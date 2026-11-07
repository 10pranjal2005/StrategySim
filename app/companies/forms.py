
from datetime import datetime
from urllib.parse import urlsplit

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

DEFAULT_GEOGRAPHY = "India"

COMPANY_TYPE_CHOICES = [
    ("Target", "Target Company"),
    ("Competitor", "Competitor"),
    ("Other", "Other"),
]


# ---------------------------------------------------------
# CUSTOM VALIDATORS
# ---------------------------------------------------------

def validate_website(form, field):
    """
    Validate an optional website URL.

    Accepted examples:
        https://example.com
        http://www.example.com

    URLs must use HTTP or HTTPS and contain a hostname
    with a dot, matching the company service-layer rules.
    """

    value = (field.data or "").strip()

    if not value:
        return

    try:
        parsed_url = urlsplit(value)

        if parsed_url.scheme.lower() not in {"http", "https"}:
            raise ValidationError(
                "Website must begin with http:// or https://."
            )

        if not parsed_url.netloc or not parsed_url.hostname:
            raise ValidationError(
                "Enter a valid website URL."
            )

        if "." not in parsed_url.hostname:
            raise ValidationError(
                "Website hostname must contain a valid domain."
            )

    except ValueError:
        raise ValidationError(
            "Enter a valid website URL."
        )


def validate_founded_year(form, field):
    """
    Validate the company's founded year.

    Allowed range:
        1800 through the current year.
    """

    if field.data is None:
        return

    current_year = datetime.now().year

    if field.data < 1800:
        raise ValidationError(
            "Founded year cannot be earlier than 1800."
        )

    if field.data > current_year:
        raise ValidationError(
            "Founded year cannot be in the future."
        )


# ---------------------------------------------------------
# INDUSTRY FORM
# ---------------------------------------------------------

class IndustryForm(FlaskForm):
    """
    Form used for creating and editing industries.
    """

    name = StringField(
        "Industry Name",
        validators=[
            DataRequired(
                message="Industry name is required."
            ),
            Length(
                max=150,
                message="Industry name cannot exceed 150 characters."
            ),
        ],
    )

    sector = StringField(
        "Sector",
        validators=[
            Optional(),
            Length(
                max=150,
                message="Sector cannot exceed 150 characters."
            ),
        ],
    )

    industry_type = StringField(
        "Industry Type",
        validators=[
            Optional(),
            Length(
                max=150,
                message="Industry type cannot exceed 150 characters."
            ),
        ],
    )

    geography = StringField(
        "Geography",
        default=DEFAULT_GEOGRAPHY,
        validators=[
            DataRequired(
                message="Geography is required."
            ),
            Length(
                max=100,
                message="Geography cannot exceed 100 characters."
            ),
        ],
    )

    description = TextAreaField(
        "Industry Description",
        validators=[
            Optional(),
            Length(
                max=5000,
                message="Description cannot exceed 5000 characters."
            ),
        ],
    )

    submit = SubmitField("Save Industry")


# ---------------------------------------------------------
# COMPANY FORM
# ---------------------------------------------------------

class CompanyForm(FlaskForm):
    """
    Form used for creating and editing companies.

    The industry choices must be populated by the route
    before calling validate_on_submit().
    """

    name = StringField(
        "Company Name",
        validators=[
            DataRequired(
                message="Company name is required."
            ),
            Length(
                max=150,
                message="Company name cannot exceed 150 characters."
            ),
        ],
    )

    industry_id = SelectField(
        "Industry",
        coerce=int,
        choices=[],
        validators=[
            InputRequired(
                message="Please select an industry."
            ),
        ],
    )

    company_type = SelectField(
        "Company Type",
        choices=COMPANY_TYPE_CHOICES,
        validators=[
            DataRequired(
                message="Please select a company type."
            ),
        ],
    )

    description = TextAreaField(
        "Company Description",
        validators=[
            Optional(),
            Length(
                max=5000,
                message="Description cannot exceed 5000 characters."
            ),
        ],
    )

    headquarters = StringField(
        "Headquarters",
        validators=[
            Optional(),
            Length(
                max=200,
                message="Headquarters cannot exceed 200 characters."
            ),
        ],
    )

    website = StringField(
        "Website",
        validators=[
            Optional(),
            Length(
                max=500,
                message="Website cannot exceed 500 characters."
            ),
            validate_website,
        ],
    )

    annual_revenue = DecimalField(
        "Annual Revenue",
        places=2,
        validators=[
            Optional(),
            NumberRange(
                min=0,
                message="Annual revenue cannot be negative."
            ),
        ],
    )

    employee_count = IntegerField(
        "Employee Count",
        validators=[
            Optional(),
            NumberRange(
                min=0,
                message="Employee count cannot be negative."
            ),
        ],
    )

    market_share = DecimalField(
        "Market Share (%)",
        places=2,
        validators=[
            Optional(),
            NumberRange(
                min=0,
                max=100,
                message="Market share must be between 0 and 100."
            ),
        ],
    )

    founded_year = IntegerField(
        "Founded Year",
        validators=[
            Optional(),
            validate_founded_year,
        ],
    )

    is_demo = BooleanField(
        "Illustrative Demonstration Record"
    )

    submit = SubmitField("Save Company")
