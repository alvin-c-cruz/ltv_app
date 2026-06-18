from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Optional
from ltv2.constants import TRANSACTION_BASES


class BankForm(FlaskForm):
    bank_code = StringField("Bank Code", validators=[DataRequired(), Length(max=20)])
    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    report_label = StringField("Report Label", validators=[Optional(), Length(max=150)])
    transaction_basis = SelectField(
        "Transaction Basis",
        choices=[(b, b) for b in TRANSACTION_BASES],
    )
    priority = IntegerField("Priority", validators=[Optional()], default=0)
