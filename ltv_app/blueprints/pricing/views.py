import io
import os

from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash, make_response, send_file

from .. auth import login_required
from .. database import get_db
from ...tz import ph_today

from .extensions import transform_email, BANKS, parse_pasted_data, generate_pricing_excel


bp = Blueprint('pricing', __name__, template_folder="pages", url_prefix="/pricing")


@bp.route("/", methods=['GET', 'POST'])
@login_required
def home():
    form = {}
    banks = [(key, value) for key, value in BANKS.items()]
    today_str = ph_today().strftime('%Y-%m-%d')

    if request.method == "POST":
        bank_code      = request.form.get("bank_code", "")
        textarea_data  = request.form.get("textarea_data", "")
        stock_name     = request.form.get("stock_name", "")
        spot_price     = request.form.get("spot_price", "")
        date_str       = request.form.get("date_str", today_str)
        cmd_button     = request.form.get("cmd_button", "")

        form.update({
            "bank_code":     bank_code,
            "textarea_data": textarea_data,
            "stock_name":    stock_name,
            "spot_price":    spot_price,
            "date_str":      date_str,
        })

        if cmd_button == "Generate Excel":
            if not bank_code:
                flash("Please select a bank / issuer.", "warning")
            elif not textarea_data.strip():
                flash("Please paste pricing data.", "warning")
            elif not spot_price:
                flash("Please enter a spot price.", "warning")
            else:
                rows = parse_pasted_data(textarea_data, bank_code)
                if not rows:
                    flash("Could not parse any rows — check that the correct bank is selected and the header row matches.", "danger")
                else:
                    excel_bytes = generate_pricing_excel(rows, stock_name or "Pricing", float(spot_price), date_str)
                    safe_name = (stock_name or "pricing").replace(" ", "_")
                    return send_file(
                        io.BytesIO(excel_bytes),
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        as_attachment=True,
                        download_name=f"pricing_{safe_name}_{date_str}.xlsx"
                    )

        elif cmd_button == "Preview":
            if bank_code and textarea_data.strip():
                list_data = transform_email(textarea_data, bank_code, form)
                form['list_data'] = list_data

        elif cmd_button == "Yes":
            headers = [i.strip() for i in textarea_data.split("\n")[0].replace("\r", "").split("\t")]
            return redirect(url_for('pricing.add_header') + f"?data={[bank_code, headers]}")

        elif cmd_button == "No":
            return redirect(url_for("pricing.home"))

    context = {
        "banks":     banks,
        "form":      form,
        "today":     today_str,
    }
    return render_template("pricing/home.html", **context)


@bp.route("/add_header", methods=["GET", "POST"])
@login_required
def add_header():
    if request.method == "POST":
        dict_data = dict(request.form)
        bank_code = dict_data["bank_code"]
        dict_data.pop("bank_code")

        with open(os.path.join(current_app.instance_path, "pricing_columns.txt"), "w") as f:
            f.writelines([str(dict_data)])

        from flask import jsonify
        response = make_response(jsonify(dict_data))
        response.headers["Target"] = "_blank"
        return response

    else:
        data = request.args.get("data")
        data_types = [
            ("product",   "AQ/DQ"),
            ("code",      "Stock Code"),
            ("strike",    "Strike"),
            ("ko",        "KO"),
            ("tenor",     "Tenor"),
            ("leverage",  "Single/Double"),
            ("gtd",       "Guarantee"),
            ("frequency", "Frequency"),
        ]

        bank_code, headers = eval(data)
        context = {
            "bank_code":   bank_code,
            "headers":     enumerate(headers, start=1),
            "data_types":  data_types,
        }

    return render_template("pricing/add_header.html", **context)
