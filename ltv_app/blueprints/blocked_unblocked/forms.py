from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired

from ...tz import ph_today


class EditionForm(FlaskForm):
    # ph_today, not ph_today(): WTForms calls it per form, so the default never freezes at server start.
    report_date = DateField(label="Edition date", validators=[DataRequired()], default=ph_today)
    price_file = FileField(label="Price set, a Yahoo portfolio CSV (optional)",
                           validators=[FileAllowed(["csv"], "A Yahoo portfolio CSV")])
    price_text = TextAreaField(label="Or paste prices, one 'code price' per line (optional)")
    submit = SubmitField(label="Generate")
