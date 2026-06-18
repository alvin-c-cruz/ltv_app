from flask_wtf import FlaskForm
from wtforms import SelectField, DateField
from wtforms.validators import DataRequired


class HolidayForm(FlaskForm):
    currency_id = SelectField("Currency", coerce=int, validators=[DataRequired()])
    holiday_date = DateField("Holiday Date", validators=[DataRequired()])
