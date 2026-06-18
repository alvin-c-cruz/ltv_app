from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, Length, Optional


class CurrencyForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=10)])
    name = StringField("Name", validators=[Optional(), Length(max=100)])
    priority = IntegerField("Priority", validators=[Optional()], default=0)
