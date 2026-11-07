from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    BooleanField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
)


class ComponentForm(FlaskForm):
    name = StringField(
        "Component Name",
        validators=[
            DataRequired(),
            Length(max=150),
        ],
    )

    component_code = StringField(
        "Component Code",
        validators=[
            Optional(),
            Length(max=50),
        ],
    )

    category = StringField(
        "Category",
        validators=[
            Optional(),
            Length(max=100),
        ],
    )

    description = TextAreaField(
        "Description",
        validators=[Optional()],
    )

    criticality = SelectField(
        "Criticality",
        choices=[
            ("Low", "Low"),
            ("Medium", "Medium"),
            ("High", "High"),
            ("Critical", "Critical"),
        ],
        validators=[DataRequired()],
        default="Medium",
    )

    is_active = BooleanField(
        "Active",
        default=True,
    )

    submit = SubmitField("Save Component")


class DeleteComponentForm(FlaskForm):
    submit = SubmitField("Delete Component")