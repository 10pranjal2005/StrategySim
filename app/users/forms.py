
from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    PasswordField,
    SelectField,
    SubmitField
)

from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length
)


# ---------------------------------------------------------
# CREATE USER FORM
# ---------------------------------------------------------

class CreateUserForm(FlaskForm):
    """
    Form used by Administrators to create Analyst
    and Viewer accounts.
    """

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(
                min=2,
                max=100,
                message="Full name must contain between 2 and 100 characters."
            )
        ]
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Enter a valid email address."),
            Length(
                max=254,
                message="Email address is too long."
            )
        ]
    )

    role = SelectField(
        "User Role",
        choices=[
            ("Analyst", "Analyst"),
            ("Viewer", "Viewer")
        ],
        validators=[
            DataRequired(message="Select a user role.")
        ]
    )

    password = PasswordField(
        "Temporary Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(
                min=12,
                max=128,
                message="Password must contain between 12 and 128 characters."
            )
        ]
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm the password."),
            EqualTo(
                "password",
                message="The passwords do not match."
            )
        ]
    )

    submit = SubmitField("Create User")


# ---------------------------------------------------------
# EDIT USER FORM
# ---------------------------------------------------------

class EditUserForm(FlaskForm):
    """
    Form used by Administrators to update user details
    and assign a role.
    """

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(
                min=2,
                max=100,
                message="Full name must contain between 2 and 100 characters."
            )
        ]
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Enter a valid email address."),
            Length(
                max=254,
                message="Email address is too long."
            )
        ]
    )

    role = SelectField(
        "User Role",
        choices=[
            ("Administrator", "Administrator"),
            ("Analyst", "Analyst"),
            ("Viewer", "Viewer")
        ],
        validators=[
            DataRequired(message="Select a user role.")
        ]
    )

    submit = SubmitField("Save Changes")
