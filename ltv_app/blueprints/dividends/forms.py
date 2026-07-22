from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, DecimalField, FloatField
from wtforms.validators import DataRequired, NumberRange, Optional


class Form(FlaskForm):
    bank_id = SelectField(
        validators=[DataRequired()],
        label="Bank Account",
        render_kw={
            "class": "form-control",
            "autofocus": "autofocus",
        }
    )

    stock_id = SelectField(
        validators=[DataRequired()],
        label="Stock",
        render_kw={
            "class": "form-control",
        }
    )

    declaration_date = DateField(
        validators=[Optional()],
        label="Declaration Date",
        render_kw={
            "class": "form-control"
        }
    )

    ex_date = DateField(
        validators=[DataRequired()],
        label="Ex-Date",
        render_kw={
            "class": "form-control"
        }
    )

    record_date = DateField(
        validators=[Optional()],
        label="Record Date",
        render_kw={
            "class": "form-control"
        }
    )

    pay_out = DateField(
        validators=[DataRequired()],
        label="Pay Out Date",
        render_kw={
            "class": "form-control"
        }
    )

    nominal = FloatField(
        validators=[DataRequired()],
        label="Nominal",
        render_kw={
            "class": "form-control"
        }
    )

    ccy_id = SelectField(
        validators=[DataRequired()],
        label="Ccy",
        render_kw={
            "class": "form-control",
        }
    )

    dividends_per_share = FloatField(
        validators=[DataRequired()],
        label="Dividends per share",
        render_kw={
            "class": "form-control"
        }
    )
    tax = FloatField(
        label="Tax",
        render_kw={
            "class": "form-control"
        }
    )

    charges = FloatField(
        label="Charges",
        render_kw={
            "class": "form-control"
        }
    )

    status = SelectField(
        validators=[DataRequired()],
        label="Status",
        choices=["Actual", "Estimate"],
        render_kw={
            "class": "form-control",
        }
    )
