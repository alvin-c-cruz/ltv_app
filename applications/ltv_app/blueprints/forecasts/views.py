from flask import Blueprint, render_template, send_file, current_app
import os

from .. database import get_db
from .. auth import login_required

from ltv_app.extensions import Forecast

bp = Blueprint('forecasts', __name__, template_folder="pages", url_prefix="/forecasts")


@bp.route("/")
@login_required
def home():
    context = {}
    return render_template('forecasts/home.html', **context)


@bp.route("/transaction_forecast")
@login_required
def transaction_forecast():
    code = "2333"

    f = Forecast.transaction_and_forecast(
        db=get_db(),
        code=code,
        template_path=os.path.join(current_app.instance_path, "excel_templates"),
        save_path=os.path.join(current_app.instance_path, "temp")
    )

    return send_file('{}'.format(f.filename), as_attachment=True, cache_timeout=0)
