from datetime import date

from flask import Blueprint, render_template, request, send_file

from .. auth import login_required
from .. database import get_db
from ...tz import ph_today

bp = Blueprint('ltv_stocks', __name__, template_folder='pages', url_prefix='/ltv-stocks')

# Same bank roster as the legacy `LTV_Stocks(*bank_accounts)` script invocation.
_BANK_IDS = ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG']


def _parse_date(val: str, default: date) -> date:
    try:
        return date.fromisoformat(val)
    except (TypeError, ValueError):
        return default


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    today = ph_today()
    if request.method == 'POST':
        report_date = _parse_date(request.form.get('report_date'), today)
    else:
        report_date = _parse_date(request.args.get('report_date'), today)

    # The web page only toggles the Download button (see pages/ltv_stocks/home.html);
    # it does not render any report data, so `data` just needs to be truthy.
    data = {'report_date': report_date}

    return render_template('ltv_stocks/home.html',
                           data=data,
                           report_date=str(report_date))


@bp.route('/download', methods=['POST'])
@login_required
def download():
    from .legacy_port.excel_writer import build_workbook

    today = ph_today()
    report_date = _parse_date(request.form.get('report_date'), today)

    db = get_db()
    output = build_workbook(db, report_date, _BANK_IDS)

    filename = f"{report_date} LTV Stocks.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
