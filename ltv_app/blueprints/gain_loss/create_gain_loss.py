import io
import os
import openpyxl
from datetime import datetime, timedelta
from flask import current_app, url_for

from .. database import get_db
from .. transactions import get_balance, get_transactions


def list_currency():
    db = get_db()
    return [ccy['ccy_id'] for ccy in db.execute("SELECT * FROM tbl_currency ORDER BY priority;").fetchall()]


def list_bank_accounts():
    db = get_db()
    return [bank['bank_id'] for bank in db.execute("SELECT * FROM tbl_bank_account ORDER BY priority;").fetchall()]


def bank_ref_nums():
    db = get_db()
    return [bank['ref_num'] for bank in db.execute("SELECT * FROM tbl_bank_account ORDER BY priority;").fetchall()]


def get_bank_ref(bank_id):
    db = get_db()
    bank = db.execute("SELECT * FROM tbl_bank_account WHERE bank_id=?;", (bank_id, )).fetchone()

    return bank["ref_num"]


def get_bank_id(bank_ref):
    db = get_db()
    bank = db.execute("SELECT * FROM tbl_bank_account WHERE ref_num=?;", (bank_ref, )).fetchone()

    return bank["bank_id"]


def get_bank_name(bank_ref):
    db = get_db()
    bank = db.execute("SELECT * FROM tbl_bank_account WHERE ref_num=?;", (bank_ref, )).fetchone()

    return bank["bank_name"]


def get_code(code_ref):
    db = get_db()
    stock = db.execute("SELECT * FROM tbl_code WHERE ref_num=?;", (code_ref, )).fetchone()

    return stock["code"]


def get_stock_name(code_ref):
    db = get_db()
    stock = db.execute("SELECT * FROM tbl_code WHERE ref_num=?;", (code_ref, )).fetchone()

    return stock["stock_name"]


def get_ccy_ref(ccy_id):
    db = get_db()
    currency = db.execute("SELECT * FROM tbl_currency WHERE ccy_id=?;", (ccy_id, )).fetchone()

    return currency["ref_num"]


def get_ccy(code_ref):
    db = get_db()
    currency = db.execute("SELECT * FROM tbl_currency "
                          "INNER JOIN tbl_code on tbl_code.ccy_ref = tbl_currency.ref_num "
                          "WHERE tbl_code.ref_num=?;", (code_ref, )).fetchone()

    return currency["ccy_id"]


def get_stock_ref():
    db = get_db()
    sql = "SELECT ref_num FROM tbl_code;"
    stock_refs = [stock["ref_num"] for stock in db.execute(sql).fetchall()]

    return stock_refs


def create_file(date_from, date_to, bank_ref, code_ref):

    wb = openpyxl.load_workbook(os.path.join(current_app.instance_path, 'excel_templates', 'gain_loss.xlsx'))

    wb['SUMMARY']['A3'] = f'As of {datetime.strftime(datetime.strptime(date_to, "%Y-%m-%d"), "%B %d, %Y")}'

    head_line = {}

    if date_from[:4] == date_to[:4]:
        if date_from[5:7] == date_to[5:7]:
            if date_from[-2:] == date_to[-2:]:
                period_covered = f'=TEXT("{date_from}","mmmm  d, yyyy")'
            else:
                period_covered = f'="From "&TEXT("{date_from}","mmmm  d")&" to "&TEXT("{date_to}","d, yyyy")'
        else:
            period_covered = f'="From "&TEXT("{date_from}","mmmm  d")&" to "&TEXT("{date_to}","mmmm  d, yyyy")'
    else:
        period_covered = f'="From "&TEXT("{date_from}","mmmm  d, yyyy")&" to "&TEXT("{date_to}","mmmm  d, yyyy")'

    period_covered = '=INDIRECT("SUMMARY!A3")'

    year = int(date_from[:4])
    month = date_from[5:7]
    prev_month = {
        "01": ("December", year - 1),
        "02": ("January", year),
        "03": ("February", year),
        "04": ("March", year),
        "05": ("April", year),
        "06": ("May", year),
        "07": ("June", year),
        "08": ("July", year),
        "09": ("August", year),
        "10": ("September", year),
        "11": ("October", year),
        "12": ("November", year),
    }

    end_of = f'End of {prev_month[month][0]} {prev_month[month][1]}'

    download_name, bank_refs, code_refs = _get_refs_and_name(date_from, date_to, bank_ref, code_ref)
    dict_gain_loss = gather_gain_loss(date_from, date_to, bank_refs, code_refs)

    for ccy in list_currency():
        for bank_id in list_bank_accounts():
            if ccy in dict_gain_loss:
                if get_bank_ref(bank_id) not in dict_gain_loss[ccy]:
                    if f'{bank_id}-{ccy}' in wb.sheetnames:
                        ws = wb[f'{bank_id}-{ccy}']
                        ws.sheet_state = 'hidden'
            else:
                if f'{bank_id}-{ccy}' in wb.sheetnames:
                    ws = wb[f'{bank_id}-{ccy}']
                    ws.sheet_state = 'hidden'

    for ccy in dict_gain_loss:
        head_line[ccy] = {}

        for bank_ref in dict_gain_loss[ccy]:
            head_line[ccy][bank_ref] = {}
            bank_id = get_bank_id(bank_ref)
            bank_name = get_bank_name(bank_ref)
            sheet_name = f'{bank_id}-{ccy}'
            if sheet_name not in wb.sheetnames: wb.create_sheet(sheet_name)
            ws = wb[sheet_name]

            # Headers

            write_title(ws, 'A1', 'Avg. Price vs Selling Price', 12, 'left')
            write_title(ws, 'A2', period_covered, 12, 'left')
            write_title(ws, 'A4', bank_name, 16, 'left')

            for cell_name in ("A4", "B4", "C4"):
                fill_color(ws, cell_name, "00FFFF00")

            rate = {
                "HKD": "=hkd_per_usd",
                "JPY": "=jpy_per_usd",
                "AUD": "=aud_per_usd",
                "USD": 1,
                "SGD": "=sgd_per_usd",
            }

            write_title(ws, 'D6', 'USD RATE', 11, 'left')
            write(ws, 'E6', rate[ccy], 11, 'right', 'currency_2', True)

            write_title(ws, 'D8', end_of, 11, 'left')
            ws.merge_cells('D8:G8')
            write_title(ws, 'D9', 'Average Price', 11, 'left')
            ws.merge_cells('D9:G9')

            # Beginning Balance Headers
            write_title(ws, 'A10', '', 11, 'center', True)
            write_title(ws, 'B10', 'Stock', 11, 'center', True)
            ws.merge_cells('B10:C10')
            write_title(ws, 'D10', 'Code', 11, 'center', True)
            write_title(ws, 'E10', 'Quantity', 11, 'center', True)
            write_title(ws, 'F10', 'Avg Price', 11, 'center', True)
            write_title(ws, 'G10', 'Value', 11, 'center', True)
            write_title(ws, 'H10', 'USD  Value', 11, 'center', True)
            ws.merge_cells('H10:I10')

            write_title(ws, 'K9', 'Gain Loss', 11, 'center', True)
            ws.merge_cells('K9:M9')
            write_title(ws, 'K10', 'Net', 11, 'center', True)
            write_title(ws, 'L10', 'Stock', 11, 'center', True)
            ws.merge_cells('L10:M10')

            # Beginning Balance Details
            row_num = 11
            start_total = row_num
            for code_ref in dict_gain_loss[ccy][bank_ref]['beginning']:
                head_line[ccy][bank_ref][code_ref] = row_num

                code = get_code(code_ref)
                stock_name = get_stock_name(code_ref)
                beginning_balance = dict_gain_loss[ccy][bank_ref]['beginning'][code_ref]['quantity']
                average = dict_gain_loss[ccy][bank_ref]['beginning'][code_ref]['average']

                write_box_normal(ws, f'A{row_num}', f'=INDIRECT("A"&row()-1)+1', "integer")
                write_box_normal(ws, f'B{row_num}', stock_name)
                ws.merge_cells(f'B{row_num}:C{row_num}')
                write_box_normal(ws, f'D{row_num}', code, "code")
                write_box_normal(ws, f'E{row_num}', beginning_balance, "shares")
                write_box_normal(ws, f'F{row_num}', average, "currency_4")
                write_box_normal(ws, f'G{row_num}', f'=E{row_num}*F{row_num}', "currency_2")
                write_box_normal(ws, f'H{row_num}', f'=G{row_num}/hkd_per_usd', "currency_2")
                ws.merge_cells(f'H{row_num}:I{row_num}')
                write_box_normal(ws, f'K{row_num}', '')
                write_box_normal(ws, f'L{row_num}', f'=B{row_num}')
                ws.merge_cells(f'L{row_num}:M{row_num}')

                row_num += 1

            end_total = row_num - 1

            # Total Line
            write_box_normal(ws, f'A{row_num}', '')
            write_box_normal(ws, f'B{row_num}', '')
            ws.merge_cells(f'B{row_num}:C{row_num}')
            write_box_normal(ws, f'D{row_num}', 'TOTAL', 'string', True)
            write_box_normal(ws, f'E{row_num}', f'=SUM(E{start_total}:E{end_total})', 'shares', True)
            write_box_normal(ws, f'F{row_num}', '')
            write_box_normal(ws, f'G{row_num}', f'=SUM(G{start_total}:G{end_total})', 'currency_2', True)
            write_box_normal(ws, f'H{row_num}', f'=SUM(H{start_total}:H{end_total})', 'currency_2', True)
            ws.merge_cells(f'H{row_num}:I{row_num}')

            ws[f'G{row_num}'].number_format = f'[${ccy}] #,##0.00_);([${ccy}] #,##0.00)'
            ws[f'H{row_num}'].number_format = f'[$USD] #,##0.00_);([$USD] #,##0.00)'

            write_box_normal(ws, f'K{row_num}', f'=SUM(K{start_total}:K{end_total})', 'currency_2', True)
            write_box_normal(ws, f'L{row_num}', 'TOTAL')
            ws.merge_cells(f'L{row_num}:M{row_num}')

            ws[f'K{row_num}'].number_format = f'[${ccy}] #,##0.00_);([${ccy}] #,##0.00)'

            row_num += 2

            # Stock Transactions
            for code_ref in dict_gain_loss[ccy][bank_ref]['trades']:
                if dict_gain_loss[ccy][bank_ref]['trades'][code_ref]:
                    code = get_code(code_ref)
                    name = get_stock_name(code_ref)
                    # Stock Name
                    stock_name = f'{code}:{ccy[:2]} - {name}'
                    write_title(ws, f'A{row_num}', stock_name, 12, 'left')
                    for cell_name in (f'A{row_num}', f'B{row_num}', f'C{row_num}'):
                        fill_color(ws, cell_name, "00FFFF00")

                    head_row_num = head_line[ccy][bank_ref][code_ref]
                    write(ws, f'E{row_num}', f'=E{head_row_num}', 11, 'right', 'shares', True)
                    write(ws, f'F{row_num}', f'=F{head_row_num}', 11, 'right', 'currency_4', True)
                    start_balance = row_num

                    # For gain_loss_per_stock
                    ws[f"O{row_num}"].value = f"=E{row_num}"

                    row_num += 1

                    # Headers
                    write_title(ws, f'A{row_num}', '', 11, 'center', True)
                    write_title(ws, f'B{row_num}', 'Trade  Date', 11, 'center', True)
                    write_title(ws, f'C{row_num}', 'Settlement Date', 11, 'center', True)
                    write_title(ws, f'D{row_num}', 'Transaction', 11, 'center', True)
                    write_title(ws, f'E{row_num}', 'Shares', 11, 'center', True)
                    write_title(ws, f'F{row_num}', 'Price', 11, 'center', True)
                    write_title(ws, f'G{row_num}', 'Gross Total', 11, 'center', True)
                    write_title(ws, f'H{row_num}', 'Charges', 11, 'center', True)
                    write_title(ws, f'I{row_num}', 'Net Total', 11, 'center', True)
                    write_title(ws, f'J{row_num}', 'Avg. Price', 11, 'center', True)
                    write_title(ws, f'K{row_num}', 'Avg. Cost', 11, 'center', True)
                    write_title(ws, f'L{row_num}', 'Net Gain Loss', 11, 'center', True)
                    write_title(ws, f'M{row_num}', '%', 11, 'center', True)

                    # For gain_loss_per_stock
                    ws[f"O{row_num}"].value = f"=O{row_num-1}"

                    row_num += 1
                    i = 0
                    g_l = False

                    # Details
                    for record in dict_gain_loss[ccy][bank_ref]['trades'][code_ref]:
                        write_box_normal(ws, f'A{row_num}', f'=INDIRECT("A"&row()-1)+1', "integer")

                        write_box_normal(ws, f'B{row_num}', datetime.strptime(record['trade_date'], "%Y-%m-%d"), "date")
                        write_box_normal(ws, f'C{row_num}', datetime.strptime(record['value_date'], "%Y-%m-%d"), "date")
                        write_box_normal(ws, f'D{row_num}', record['description'])
                        write_box_normal(ws, f'E{row_num}', record['quantity'], "shares")
                        write_box_normal(ws, f'F{row_num}', record['price'], "currency_4")
                        write_box_normal(ws, f'G{row_num}', f'=E{row_num}*F{row_num}', "currency_2")
                        write_box_normal(ws, f'H{row_num}', record['charges'], "currency_2")
                        write_box_normal(ws, f'I{row_num}', f'=G{row_num}+H{row_num}', "currency_2")

                        if not i:
                            formula = f'=if(sum(E{start_balance}:E{row_num})=0,F{row_num - 2},if(left(D{row_num},4)="Sell",F{start_balance},(E{start_balance}*F{start_balance}+I{row_num})/sum(E{start_balance}:E{row_num})))'
                            i = 1
                        else:
                            # formula = f'=if(sum(E{start_balance}:E{row_num})=0,J{row_num - 1},if(left(D{row_num},4)="Sell",J{row_num - 1},(sum(E{start_balance}:E{row_num - 1})*if(isnumber(J{row_num - 1}),J{row_num - 1},0)+I{row_num})/sum(E{start_balance}:E{row_num})))'
                            formula = f'=IF(SUM(INDIRECT("E{start_balance}:E"&ROW()))=0,INDIRECT("J"&ROW()-1),IF(LEFT(D{row_num},4)="Sell",INDIRECT("J"&ROW()-1),(SUM(INDIRECT("E{start_balance}:E"&ROW()-1))*IF(ISNUMBER(INDIRECT("J"&ROW()-1)),INDIRECT("J"&ROW()-1),0)+I{row_num})/SUM(INDIRECT("E{start_balance}:E"&ROW()))))'
                        write_box_normal(ws, f'J{row_num}', formula, "currency_4")

                        if record['description'][:4] == 'Sell':
                            write_box_normal(ws, f'K{row_num}', f'=E{row_num}*J{row_num}', "currency_2")
                            write_box_normal(ws, f'L{row_num}', f'=K{row_num}-I{row_num}', "currency_2")
                            write_box_normal(ws, f'M{row_num}', f'=(I{row_num}/K{row_num})-1', "percentage")
                            g_l = True
                        else:
                            write_box_normal(ws, f'K{row_num}', '', "currency_2")
                            write_box_normal(ws, f'L{row_num}', '', "currency_2")
                            write_box_normal(ws, f'M{row_num}', '', "percentage")

                        # For gain_loss_per_stock
                        ws[f"O{row_num}"].value = f'=INDIRECT("O"&row()-1)+E{row_num}'
                        ws[f"O{row_num}"].number_format = "#,##0;[RED]-#,##0"
                        
                        # HyperLink
                        cell = ws[f"D{row_num}"]
                        if 'Accu' in record['description'] or 'Decu' in record['description']:
                            cell.hyperlink = url_for('fixings.edit', ref_num=record['ref_num'], _external=True)
                        else:
                            cell.hyperlink = url_for('transactions.edit', ref_num=record['ref_num'], _external=True)

                        row_num += 1

                    # Footer
                    write_box_normal(ws, f'A{row_num}', "")
                    write_box_normal(ws, f'B{row_num}', "")
                    write_box_normal(ws, f'C{row_num}', "")
                    write_box_normal(ws, f'D{row_num}', "TOTAL", "string", True)
                    write_box_normal(ws, f'E{row_num}', f'=SUM(E{start_balance}:E{row_num - 1})', "shares", True)
                    write_box_normal(ws, f'F{row_num}', "")

                    write_box_normal(ws, f'G{row_num}', f'=SUM(G{start_balance}:G{row_num - 1})', "currency_2", True)
                    ws[f'G{row_num}'].number_format = f'[${ccy}] #,##0.00_);([${ccy}] #,##0.00)'

                    write_box_normal(ws, f'H{row_num}', "")

                    write_box_normal(ws, f'I{row_num}', f'=SUM(I{start_balance}:I{row_num - 1})', "currency_2", True)
                    ws[f'I{row_num}'].number_format = f'[${ccy}] #,##0.00_);([${ccy}] #,##0.00)'

                    write_box_normal(ws, f'J{row_num}', "")

                    write_box_normal(ws, f'K{row_num}', f'=SUM(K{start_balance}:K{row_num - 1})', "currency_2", True)
                    ws[f'K{row_num}'].number_format = f'[${ccy}] #,##0.00_);([${ccy}] #,##0.00)'

                    write_box_normal(ws, f'L{row_num}', f'=SUM(L{start_balance}:L{row_num - 1})', "currency_2", True)
                    ws[f'L{row_num}'].number_format = f'[${ccy}] #,##0.00_);([${ccy}] #,##0.00)'

                    if g_l:
                        fill_color(ws, f'L{row_num}', "00FF9900")

                    write_box_normal(ws, f'M{row_num}', "")

                    write_box_normal(ws, f'K{head_row_num}', f'=L{row_num}', "currency_2")
                    row_num += 2

    output = io.BytesIO()
    wb.save(output)
    wb.close()
    output.seek(0)

    return output, download_name


def create_file_name(date_from, date_to, bank_ref, code_ref):
    if bank_ref == 0:
        bank_refs = bank_ref_nums()
        if code_ref == 0:
            code_refs = get_stock_ref()
            filename = os.path.join(current_app.instance_path, 'temp', f'{date_from}-to-{date_to}-gain_loss.xlsx')
        else:
            code_refs = [code_ref]
            code = get_code(code_ref)
            filename = os.path.join(current_app.instance_path, 'temp', f'{date_from}-to-{date_to}-gain_loss-{code}.xlsx')
    else:
        bank_refs = [bank_ref]
        bank_id = get_bank_id(bank_ref)

        if code_ref == 0:
            code_refs = get_stock_ref()
            filename = os.path.join(current_app.instance_path, 'temp',
                                    f'{date_from}-to-{date_to}-gain_loss-{bank_id}.xlsx')
        else:
            code_refs = [code_ref]
            code = get_code(code_ref)
            filename = os.path.join(current_app.instance_path, 'temp',
                                    f'{date_from}-to-{date_to}-gain_loss-{bank_id}-{code}.xlsx')

    return filename, bank_refs, code_refs


def _get_refs_and_name(date_from, date_to, bank_ref, code_ref):
    if bank_ref == 0:
        bank_refs = bank_ref_nums()
        if code_ref == 0:
            code_refs = get_stock_ref()
            name = f'{date_from}-to-{date_to}-gain_loss.xlsx'
        else:
            code_refs = [code_ref]
            name = f'{date_from}-to-{date_to}-gain_loss-{get_code(code_ref)}.xlsx'
    else:
        bank_refs = [bank_ref]
        bank_id = get_bank_id(bank_ref)
        if code_ref == 0:
            code_refs = get_stock_ref()
            name = f'{date_from}-to-{date_to}-gain_loss-{bank_id}.xlsx'
        else:
            code_refs = [code_ref]
            name = f'{date_from}-to-{date_to}-gain_loss-{bank_id}-{get_code(code_ref)}.xlsx'
    return name, bank_refs, code_refs


# _dict = {
#     "ccy": {
#         "int(bank_ref)": {
#             "beginning": {
#                 "int(code_ref)": {
#                     "quantity": 0,
#                     "cost_to_date": 0,
#                     "average": 0
#                 }
#             },
#             "trades": {
#                 "int(code_ref)": [
#                     {"SELECT * FROM tbl_transaction"}
#                 ]
#             }
#         }
#     }
# }
def gather_gain_loss(date_from, date_to, bank_refs, code_refs):
    db = get_db()
    dict_gain_loss = {}

    beginning_date = str(datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=1))[:10]

    for bank_ref in bank_refs:
        for code_ref in code_refs:
            #  1. Get balances
            quantity, cost_to_date = get_balance(db=db, bank_ref=bank_ref, code_ref=code_ref, trade_date=beginning_date)
            if quantity:
                ccy = get_ccy(code_ref)
                if ccy not in dict_gain_loss:
                    dict_gain_loss[ccy] = {}

                if bank_ref not in dict_gain_loss[ccy]:
                    dict_gain_loss[ccy][bank_ref] = {"beginning": {}, "trades": {}}

                dict_gain_loss[ccy][bank_ref]["beginning"][code_ref] = {
                    "quantity": quantity,
                    "cost_to_date": cost_to_date,
                    "average": cost_to_date / quantity,
                }

            #  2. Get Transactions
            transactions = get_transactions(db=db, bank_ref=bank_ref, code_ref=code_ref,
                                            date_from=date_from, date_to=date_to)
            if transactions:
                ccy = get_ccy(code_ref)
                if ccy not in dict_gain_loss:
                    dict_gain_loss[ccy] = {}

                if bank_ref not in dict_gain_loss[ccy]:
                    dict_gain_loss[ccy][bank_ref] = {"beginning": {}, "trades": {}}

                if code_ref not in dict_gain_loss[ccy][bank_ref]["beginning"]:
                    dict_gain_loss[ccy][bank_ref]["beginning"][code_ref] = {
                        "quantity": 0,
                        "cost_to_date": 0,
                        "average": 0,
                    }

                dict_gain_loss[ccy][bank_ref]["trades"][code_ref] = transactions

    return dict_gain_loss


def write_box_normal(ws, cell_name, cell_value, value_format="string", bold=False):
    cell = ws[cell_name]
    cell.value = cell_value
    if bold:
        cell.font = openpyxl.styles.Font(size="12", name='Arial', bold=True)
    else:
        cell.font = openpyxl.styles.Font(size="12", name='Arial')
    cell.border = openpyxl.styles.borders.Border(
        left=openpyxl.styles.borders.Side(style='thin'),
        right=openpyxl.styles.borders.Side(style='thin'),
        top=openpyxl.styles.borders.Side(style='thin'),
        bottom=openpyxl.styles.borders.Side(style='thin')
    )

    if value_format == "integer":
        cell.number_format = '#,##0_);(#,##0)'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "date":
        cell.number_format = 'd-mmm-yyyy'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "shares":
        cell.number_format = '#,##0_);(#,##0)'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='right',
            vertical='center',
            indent=0)
    elif value_format == "currency_4":
        cell.number_format = '#,##0.0000'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "currency_2":
        cell.number_format = '#,##0.00_);(#,##0.00)'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='right',
            vertical='center',
            indent=0)
    elif value_format == "percentage":
        cell.number_format = '0.00%;( 0.00% )'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "code":
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "string":
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='left',
            vertical='center',
            indent=0)


def write_title(ws, cell_name, cell_value, font_size, h_align, border=False):
    cell = ws[cell_name]
    cell.value = cell_value
    cell.font = openpyxl.styles.Font(size=font_size, bold=True, name='Arial')
    cell.alignment = openpyxl.styles.Alignment(
        horizontal=h_align,
        vertical='center')

    if border:
        cell.border = openpyxl.styles.borders.Border(
            left=openpyxl.styles.borders.Side(style='thin'),
            right=openpyxl.styles.borders.Side(style='thin'),
            top=openpyxl.styles.borders.Side(style='thin'),
            bottom=openpyxl.styles.borders.Side(style='thin')
        )


def write(ws, cell_name, cell_value, font_size, h_align, value_format, bold=False):
    cell = ws[cell_name]
    cell.value = cell_value
    if bold:
        cell.font = openpyxl.styles.Font(size=font_size, bold=True, name='Arial')
    else:
        cell.font = openpyxl.styles.Font(size=font_size)

    if value_format == "integer":
        cell.number_format = '#,##0_);(#,##0)'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "date":
        cell.number_format = 'd-mmm-yyyy'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "shares":
        cell.number_format = '#,##0_);(#,##0)'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='right',
            vertical='center',
            indent=0)
    elif value_format == "currency_4":
        cell.number_format = '#,##0.0000'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "currency_2":
        cell.number_format = '#,##0.00_);(#,##0.00)'
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='right',
            vertical='center',
            indent=0)
    elif value_format == "code":
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='center',
            vertical='center')
    elif value_format == "string":
        cell.alignment = openpyxl.styles.Alignment(
            horizontal='left',
            vertical='center',
            indent=0)


def fill_color(ws, cell_name, cell_color):
    cell = ws[cell_name]
    cell.fill = openpyxl.styles.fills.PatternFill(
        patternType='solid',
        fgColor=cell_color
    )

