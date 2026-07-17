from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
from ... tz import ph_today


class DateForm(FlaskForm):
    # ph_today (not ph_today()) -- WTForms calls a callable default fresh per
    # form instantiation; a pre-evaluated value would freeze at import time
    # (server start) until the process restarts.
    trade_date = DateField(label="Trade Date", default=ph_today)
    submit = SubmitField(label="Refresh")
