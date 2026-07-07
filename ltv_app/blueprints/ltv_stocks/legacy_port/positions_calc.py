from datetime import date

from ltv_app.blueprints.transactions.extensions.trades_done_average import get_transactions
from ltv_app.blueprints.transactions.models import accumulate_position

from .working_day import WorkingDay, position_start_date
from .term_sheet_calc import build_schedule

# Legacy get_ranged_transactions: transaction types that ADD to the running
# balance get a leading "+ " when they are not the first entry of the day;
# everything else gets "- ".
_ADD_TYPES = ('Buy (Accu-KO)', 'Buy (Accu)', 'Buy (Spot)', 'Stock Dividend', 'Transfer-In')


def _blocked_shares(db, bank_ref, code_ref, cutoff, wd):
    """Port of blocked_shares: sum total_shares of active-DECU periods ending after cutoff."""
    total = 0
    contract_rows = db.execute(
        "SELECT ref_num FROM tbl_stock_contract "
        "WHERE bank_ref = ? AND code_ref = ? AND transaction_type = 'DECU' AND status = 'active'",
        (bank_ref, code_ref)
    ).fetchall()
    for cr in contract_rows:
        sched = build_schedule(db, cr['ref_num'], wd)
        for p in sched:
            if p['end_date'] > cutoff:
                total += p['total_shares']
    return total


def _format_price(price):
    """Port of the legacy decimal-place heuristic: 2dp unless str(price) carries
    more than 2 fractional digits, in which case use 4dp."""
    s = str(float(price))
    loc = s.find('.')
    decimal_digits = len(s) - loc - 1
    decimals = 2 if decimal_digits <= 2 else 4
    return "{:,.{}f}".format(price, decimals)


def _transactions_narrative(db, bank_ref, code_ref, report_date, balance):
    """Port of get_ranged_transactions: the report-date trade narrative for one (bank, code)."""
    rows = db.execute(
        "SELECT t.transaction_type, t.quantity, t.price "
        "FROM tbl_transaction t "
        "INNER JOIN tbl_transaction_type tt ON tt.transaction_type = t.transaction_type "
        "WHERE t.bank_ref = ? AND t.code_ref = ? AND t.trade_date = ? "
        "ORDER BY tt.priority, t.ref_num",
        (bank_ref, code_ref, report_date.isoformat())
    ).fetchall()
    if not rows:
        return ''

    entry = f"({report_date.month}/{report_date.day}) "
    for i, r in enumerate(rows):
        ttype = r['transaction_type']
        qty_str = "{:,.0f}".format(abs(r['quantity']))
        price_str = _format_price(r['price'])
        if i == 0:
            entry += f"{ttype} {qty_str} @ {price_str} "
        else:
            sign = "+ " if ttype in _ADD_TYPES else "- "
            entry += f"{sign}{ttype} {qty_str} @ {price_str} "
    entry += " = " + "{:,.0f}".format(balance)
    return entry


def _average(db, bank_id, code, as_of_date):
    """Port of trades_done_average: '=cost_to_date/balance' formula, else running-average fallback."""
    rows = get_transactions(db, as_of_date.isoformat(), code, bank_id)
    balance, cost_to_date, last_average = accumulate_position(rows)
    if balance:
        return f"={cost_to_date}/{balance}"
    return last_average


def position_records(db, bank_ref, bank_id, ccy_id, report_date: date, hkd_wd=None) -> dict:
    """Port of stock_balance.stock_position + blocked_shares for one bank/currency.

    Returns positions keyed by code, sorted by code, for every code of `ccy_id`
    held at `bank_ref` with a non-zero long-leg share balance.

    NOTE (ltv_stocks2.py:33): Gather_Info snapshots the balance/blocked/average as
    of `start_date` -- the **HKD**-working-day walk-back to the current-week's
    Monday (`position_start_date`) -- not `report_date` itself. Only the
    `transactions` narrative column is computed as of the literal `report_date`
    (`get_ranged_transactions`). `hkd_wd` lets the caller reuse one HKD
    `WorkingDay` across sheets; defaults to a fresh one scoped to this call.
    """
    bank_row = db.execute(
        "SELECT indicative FROM tbl_bank_account WHERE ref_num = ?", (bank_ref,)
    ).fetchone()
    indicative = bank_row['indicative'] if bank_row else None

    wd = WorkingDay(db, ccy_id)
    if hkd_wd is None:
        hkd_wd = wd if ccy_id == 'HKD' else WorkingDay(db, 'HKD')
    start_date = position_start_date(report_date, hkd_wd)
    cutoff = start_date if indicative == 'YES' else wd.previous_day(start_date)

    rows = db.execute(
        "SELECT s.ref_num AS code_ref, s.code, s.stock_name, s.yahoo_ticker, "
        "       SUM(t.quantity) AS balance "
        "FROM tbl_transaction t "
        "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
        "INNER JOIN tbl_currency cy ON cy.ref_num = s.ccy_ref "
        "WHERE t.bank_ref = ? AND cy.ccy_id = ? AND t.trade_date <= ? "
        "GROUP BY s.ref_num "
        "HAVING SUM(t.quantity) != 0",
        (bank_ref, ccy_id, start_date.isoformat())
    ).fetchall()

    result = {}
    for r in rows:
        code_ref = r['code_ref']
        code = r['code']
        balance = r['balance']

        blocked = _blocked_shares(db, bank_ref, code_ref, cutoff, wd)
        if blocked >= balance:
            blocked_v, unblocked_v = balance, 0
        else:
            blocked_v, unblocked_v = blocked, balance - blocked

        result[code] = {
            'stock_name': r['stock_name'],
            'code': code,
            'code_ref': code_ref,
            'yahoo_ticker': r['yahoo_ticker'],
            'balance': balance,
            'blocked': blocked_v,
            'unblocked': unblocked_v,
            'average': _average(db, bank_id, code, start_date),
            'transactions': _transactions_narrative(db, bank_ref, code_ref, report_date, balance),
        }

    return dict(sorted(result.items()))
