from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
from wtforms.validators import DataRequired
from datetime import datetime


class Form(FlaskForm):
    report_date = DateField(
        label="Report Date",
        validators=[DataRequired()],
        default=datetime.utcnow()
    )

    submit = SubmitField(
        label="Generate"
    )
