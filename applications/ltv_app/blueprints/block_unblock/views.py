import re

from flask import Blueprint, render_template, request, send_file, current_app
from datetime import timedelta
from .. transactions.models import get_balance
from ...tz import ph_today

from .. auth import login_required
from .. database import get_db
from .. term_sheet import StockContract

from .extensions import CreateFile

bp = Blueprint('block_unblock', __name__, template_folder='pages', url_prefix='/block-unblock')


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    db = get_db()
    sql = """
        SELECT tbl_stock_contract.ref_num
        FROM tbl_stock_contract
        INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_stock_contract.bank_ref
        INNER JOIN tbl_code ON tbl_code.ref_num = tbl_stock_contract.code_ref
        WHERE status="active"
            AND transaction_type="DECU"
        ORDER BY tbl_bank_account.priority, tbl_code.code
    """
    active_decu_ref = [i['ref_num'] for i in db.execute(sql).fetchall()]

    data = {}
    for contract_ref in active_decu_ref:
        ts = StockContract(db=db)
        ts.get(ref_num=contract_ref)
        ts.get_schedules()

        bank_name = ts.bank_name
        stock = f"{ts.stock_name} ({ts.code})"

        if bank_name not in data:
            data[bank_name] = {}

        if stock not in data[bank_name]:
            data[bank_name][stock] = {
                "shares_on_hand": 0,
                "cost-to-date": 0,
                "unblocked_shares": 0,
                "block_shares": 0,
                "shares_to_block": 0
            }

        if ts.leveraged == 'Yes':
            data[bank_name][stock]["shares_to_block"] += ts.daily_shares * ts.remaining_days  * 2
        else:
            data[bank_name][stock]["shares_to_block"] += ts.daily_shares * ts.remaining_days
            
    for bank_name in data:
        for stock_name in data[bank_name]:
            bank_ref = db.execute("SELECT ref_num FROM tbl_bank_account WHERE bank_name=?;", (bank_name, )).fetchone()[0]
            code = re.search(r'\((\d+)\)', stock_name).group(1)
            code_ref = db.execute("SELECT ref_num FROM tbl_code WHERE code=?;", (code, )).fetchone()[0]

            balance, cost_to_date = get_balance(db=db, bank_ref=bank_ref, code_ref=code_ref, trade_date=str(ph_today())[:10])
            data[bank_name][stock_name]["shares_on_hand"] = balance
            data[bank_name][stock_name]["cost-to-date"] = cost_to_date
            
    if request.method == "POST":
        excel_file = CreateFile(data=data, instance_path=current_app.instance_path)
        
        return send_file('{}'.format(excel_file.filename), as_attachment=True)
        
        
        

    return render_template('block_unblock/home.html', data=data)
