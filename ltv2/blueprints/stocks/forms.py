from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired, Length, Optional


class StockForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=20)])
    company_name = StringField("Company Name", validators=[Optional(), Length(max=150)])
    stock_name = StringField("Stock Name", validators=[Optional(), Length(max=150)])
    yahoo_ticker = StringField("Yahoo Ticker", validators=[Optional(), Length(max=30)])
    security_code = StringField("Security Code", validators=[Optional(), Length(max=30)])
    currency_id = SelectField("Currency", coerce=int, validators=[DataRequired()])
