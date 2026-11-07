from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    HiddenField
)

from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo
)


class AdministratorSetupForm(FlaskForm):

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Please enter your full name."),
            Length(min=2, max=100)
        ]
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(),
            Email(),
            Length(max=254)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=12, max=128)
        ]
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo(
                "password",
                message="Passwords must match."
            )
        ]
    )

    submit = SubmitField("Create Administrator Account")


class LoginForm(FlaskForm):

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(),
            Email(),
            Length(max=254)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(max=128)
        ]
    )

    next = HiddenField()

    submit = SubmitField("Sign In")


class RegistrationForm(FlaskForm):

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Please enter your full name."),
            Length(
                min=2,
                max=100,
                message="Name must contain 2 to 100 characters."
            )
        ]
    )

    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Please enter your email."),
            Email(message="Enter a valid email address."),
            Length(max=254)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(
                min=12,
                max=128,
                message="Password must contain at least 12 characters."
            )
        ]
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo(
                "password",
                message="Passwords do not match."
            )
        ]
    )

    submit = SubmitField("Create Account")