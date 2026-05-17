from flask import Blueprint, render_template, send_file, request, flash
from datetime import timedelta, date

from .create_gain_loss import create_file
from .. auth import login_required

bp = Blueprint('gain_loss', __name__, template_folder='pages', url_prefix='/gain-loss')


@bp.route("/", methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        date_from = request.form['date_from']
        date_to = request.form['date_to']
        bank_ref = int(request.form['bank_ref'])
        code_ref = int(request.form['code_ref'])

        try:
            output, download_name = create_file(
                date_from=date_from, date_to=date_to,
                bank_ref=bank_ref, code_ref=code_ref
            )
            return send_file(
                output,
                download_name=download_name,
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        except FileNotFoundError as e:
            flash(f'Template file not found: {e}. Ensure gain_loss.xlsx is deployed to instance/excel_templates/.')
        except Exception as e:
            flash(f'Error generating report: {e}')

        form = {
            "date_from": date_from,
            "date_to": date_to,
            "bank_ref": bank_ref,
            "code_ref": code_ref,
        }
        return render_template('gain_loss/home.html', form=form)
    else:
        date_now = date.today()

        date_from = date(date_now.year, date_now.month, 1)

        # Date To
        year = date_now.year if date_now.month != 12 else date_now.year + 1
        month = date_now.month + 1 if date_now.month != 12 else 1
        date_to = date(year, month, 1) - timedelta(days=1)

        bank_ref = 0
        code_ref = 0

    form = {
        "date_from": date_from,
        "date_to": date_to,
        "bank_ref": bank_ref,
        "code_ref": code_ref
    }

    return render_template('gain_loss/home.html', form=form)

# TODO: Program Top page
