from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional
from ltv2.constants import BEHAVIOR_CATEGORIES


class TransactionTypeForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    behavior_category = SelectField("Behavior Category",
                                    choices=[(b, b) for b in BEHAVIOR_CATEGORIES],
                                    validators=[DataRequired()])
    priority = IntegerField("Priority", validators=[Optional()], default=0)
