from flask import Blueprint, render_template, g

from .. auth import login_required
from .. database import get_db
from .. bank import gather_position_bulk

bp = Blueprint('home_page', __name__, template_folder="pages")


@bp.route("/")
@login_required
def home():
    db = get_db()
    banks = []
    for account in g.bank_accounts:
        position = gather_position_bulk(db=db, bank_ref=account['ref_num'])
        if position:
            banks.append({
                "bank_ref": account['ref_num'],
                "bank_id": account['bank_id'],
                "bank_name": account['bank_name'],
                "position": position,
            })

    return render_template('home_page/home.html', banks=banks)
