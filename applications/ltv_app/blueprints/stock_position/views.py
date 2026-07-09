from flask import Blueprint, send_file, render_template
from flask_login import login_required
import datetime
import openpyxl
import os
import tempfile

from ..database import get_db

bp = Blueprint("stock_position", __name__, template_folder="pages", url_prefix="/stock-position")


@bp.route("/", methods=["GET"])
@login_required
def home():
    return render_template('stock_position/home.html')


@bp.route("/download", methods=["GET"])
@login_required
def download():
    """Generate and download stock balance report"""
    db = get_db()

    # Get stock positions for all bank accounts
    stock_positions = get_stock_positions(db)

    # Create Excel file
    excel_file = create_excel_report(stock_positions, db)

    # Send file
    return send_file(
        excel_file,
        as_attachment=True,
        download_name=f'stock_balance_{datetime.datetime.now().strftime("%Y%m%d")}.xlsx'
    )


def get_stock_positions(db):
    """
    Calculate stock positions for all bank accounts
    Returns dict: {bank_id: {code: {shares, average_cost, total}}}
    """
    sql = """
        SELECT
            b.bank_id,
            c.code,
            SUM(t.quantity) as total_shares,
            SUM(t.quantity * t.price) as total_cost
        FROM tbl_transaction t
        INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref
        INNER JOIN tbl_code c ON c.ref_num = t.code_ref
        WHERE t.transaction_type IN ('Buy (Spot)', 'Sell (Spot)', 'Buy (Accu)', 'Buy (Accu-KO)',
                                      'Sell (Decu)', 'Sell (Decu-KO)', 'Buy (Pay Short)',
                                      'Sell (Short)', 'Transfer-In', 'Transfer-Out')
        GROUP BY b.bank_id, c.code
        HAVING total_shares != 0
        ORDER BY b.priority, c.code
    """

    results = db.execute(sql).fetchall()

    positions = {}
    for row in results:
        bank_id = row['bank_id']
        code = row['code']
        shares = row['total_shares']
        cost = row['total_cost']

        if bank_id not in positions:
            positions[bank_id] = {}

        if shares != 0:
            avg_cost = abs(cost / shares) if shares != 0 else 0
            positions[bank_id][code] = {
                'shares': shares,
                'average_cost': avg_cost,
                'total_cost': abs(cost)
            }

    return positions


def get_currency_from_code(code):
    """Determine currency from stock code"""
    if code.endswith('JP'):
        return 'JPY'
    elif ':' in code:
        suffix = code.split(':')[1]
        return suffix + 'D'  # e.g., HK -> HKD, SG -> SGD
    return 'HKD'  # Default


def create_excel_report(positions, db):
    """Create Excel file with stock positions using template"""

    # Load the template
    template_path = os.path.join(os.path.dirname(__file__), '..', '..', 'excel_templates', 'stock_summary.xlsx')
    wb = openpyxl.load_workbook(template_path)

    # Update date in ALL sheet
    wb["ALL"]["A1"].value = f'As of {datetime.datetime.now().strftime("%B %d, %Y")}'

    # Populate Download sheet with data
    ws_download = wb['Download']
    download_row = 2

    for bank_id in sorted(positions.keys()):
        for code in sorted(positions[bank_id].keys()):
            pos = positions[bank_id][code]
            ccy = get_currency_from_code(code)

            # Write to Download sheet - this feeds the formulas in ALL sheet
            ws_download[f'A{download_row}'] = bank_id
            ws_download[f'B{download_row}'].value = f'=A{download_row}&C{download_row}'
            ws_download[f'C{download_row}'] = code
            ws_download[f'D{download_row}'] = f'{int(pos["shares"]):,} shares'
            ws_download[f'E{download_row}'] = f'{ccy} ={pos["total_cost"]}/{pos["shares"]}'
            ws_download[f'G{download_row}'] = pos['shares']
            ws_download[f'H{download_row}'] = round(pos['average_cost'], 4)

            download_row += 1

        download_row += 1  # Add spacing between banks

    # Update Stocks sheet with stock names
    ws_stocks = wb['Stocks']
    stocks_row = 1

    # Get all unique stock codes
    all_codes = set()
    for bank_id in positions:
        all_codes.update(positions[bank_id].keys())

    # Write stock code to name mapping
    for code in sorted(all_codes):
        stock_name_row = db.execute(
            "SELECT stock_name FROM tbl_code WHERE code = ?", (code,)
        ).fetchone()
        stock_name = stock_name_row['stock_name'] if stock_name_row else code

        ws_stocks[f'A{stocks_row}'] = code
        ws_stocks[f'B{stocks_row}'] = stock_name
        stocks_row += 1

    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False)
    wb.save(temp_file.name)
    wb.close()

    return temp_file.name
