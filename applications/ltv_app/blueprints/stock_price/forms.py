from flask_wtf import FlaskForm
from wtforms import DateField, SubmitField


class DateForm(FlaskForm):
    trade_date = DateField(
        label="Trade Date",
    )

