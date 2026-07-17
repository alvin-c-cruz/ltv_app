from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
from wtforms.validators import DataRequired
from ... tz import ph_today


class Form(FlaskForm):
    report_date = DateField(
        label="Report Date",
        validators=[DataRequired()],
        # ph_today (not ph_today()) -- WTForms calls a callable default fresh
        # per form instantiation; a pre-evaluated value would freeze at import
        # time (server start) until the process restarts. Also fixes this
        # previously being UTC (datetime.utcnow()), not Manila time.
        default=ph_today
    )

    submit = SubmitField(
        label="Generate"
    )
