from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField
from datetime import datetime


class DateForm(FlaskForm):
    trade_date = DateField(label="Trade Date", default=datetime.today())
    submit = SubmitField(label="Refresh")
