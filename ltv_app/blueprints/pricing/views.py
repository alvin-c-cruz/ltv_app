from flask import Blueprint, render_template, request, current_app, redirect, url_for, jsonify, flash, make_response
import os

from .. auth import login_required
from .. database import get_db

from .extensions import transform_email, BANKS


bp = Blueprint('pricing', __name__, template_folder="pages", url_prefix="/pricing")


@bp.route("/", methods=['GET', 'POST'])
@login_required
def home():
    form = {}
    cmd_button = ""
    banks = [(key, value) for key, value in BANKS.items()]

    if request.method == "POST":
        bank_code = request.form["bank_code"]
        form["bank_code"] = bank_code

        textarea_data = request.form["textarea_data"]
        form["textarea_data"] = textarea_data

        cmd_button = request.form.get("cmd_button")

        if cmd_button == "Submit":
            list_data = transform_email(textarea_data, bank_code, form)

            form['list_data'] = list_data
        elif cmd_button == "Yes":
            headers = [i.strip() for i in textarea_data.split("\n")[0].replace("\r", "").split("\t")]
            return redirect(url_for('pricing.add_header') + f"?data={[bank_code, headers]}")

        elif cmd_button == "No":
            return redirect(url_for("pricing.home"))

    context = {
        "banks": banks,
        "form": form,
        "cmd_button": cmd_button
    }
    return render_template("pricing/home.html", **context)


@bp.route("/add_header", methods=["GET", "POST"])
@login_required
def add_header():
    if request.method == "POST":
        dict_data = dict(request.form)
        bank_code = dict_data["bank_code"]
        dict_data.pop("bank_code")  # Delete bank_code from data because it is not part of header

        with open(os.path.join(current_app.instance_path, "pricing_columns.txt"), "w") as f:
            f.writelines([str(dict_data)])

        # flash(f"{bank_code} columns saved.")
        # return redirect(url_for('pricing.home'))

        response = make_response(jsonify(dict_data))
        response.headers["Target"] = "_blank"
        return response

    else:
        data = request.args.get("data")
        data_types = [
            ("product", "AQ/DQ"),
            ("code", "Stock Code"),
            ("strike", "Strike"),
            ("ko", "KO"),
            ("tenor", "Tenor"),
            ("leverage", "Single/Double"),
            ("gtd", "Guarantee"),
            ("frequency", "Frequency"),
        ]

        bank_code, headers = eval(data)
        context = {
            "bank_code": bank_code,
            "headers": enumerate(headers, start=1),
            "data_types": data_types,
        }

    return render_template("pricing/add_header.html", **context)
