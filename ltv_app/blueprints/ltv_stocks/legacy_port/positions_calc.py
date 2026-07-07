from datetime import date

from ltv_app.blueprints.transactions.extensions.trades_done_average import get_transactions

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


def _first_of_month(d):
    return f"{d.year:04d}-{d.month:02d}-01"


def _moving_average_engine(rows):
    """Per-row moving-average cost engine, mirroring
    ``ltv_app.blueprints.transactions.models.accumulate_position`` (the engine the
    golden's averages agree with) so the whole-report averages match the legacy.
    Returns [(balance, cost_to_date), ...] per row, in the given
    (transaction_basis, priority) order. A buy adds its full amount to cost; a
    sell removes a proportional slice (cost * |qty| / prior balance) and resets
    cost to 0 once the position is fully sold or oversold; a buy that covers a
    short recomputes the residual cost."""
    balance = 0
    cost = 0.0
    out = []
    for r in rows:
        q = r['quantity']
        charges = (r['brokerage'] + r['commission'] + r['foreign_charge']
                   + r['stamp_duty'] + r['misc'])
        amount = q * r['price'] + charges
        if q > 0:
            if balance >= 0:
                cost = cost + amount
            elif balance + q <= 0:
                cost = 0.0
            else:
                cost = (balance + q) / q * amount
        else:
            if balance > 0 and balance - abs(q) > 0:
                cost = cost - cost * abs(q) / balance
            else:
                cost = 0.0
        balance = balance + q
        out.append((balance, cost))
    return out


def _average(db, bank_id, code, as_of_date):
    """Port of trades_done_average + ending_balance (my_routes/transaction_list.py
    :249-432). The average is '=cost_to_date/balance', where cost/balance come from
    the moving-average engine selecting the current month's footer OR, when the
    footer is left unset, the prior-month-end beginning_balance.

    trades_done_average runs the engine over the month window [1st-of-month ..
    as_of], keyed on the bank's transaction_basis. Its footer loop breaks on the
    first current-window row whose value_date settles in a LATER month
    (value_date[:7] > as_of[:7]); if that break fires before any current row is
    recorded, the footer stays unset and the function falls through to
    beginning_balance (the moving-cost state at the last row before 1st-of-month)."""
    basis = db.execute(
        "SELECT transaction_basis FROM tbl_bank_account WHERE bank_id = ?", (bank_id,)
    ).fetchone()[0]
    rows = list(get_transactions(db, as_of_date.isoformat(), code, bank_id))
    if not rows:
        return 0
    eng = _moving_average_engine(rows)
    date_from = _first_of_month(as_of_date)
    to_month = as_of_date.isoformat()[:7]

    beginning = None   # last row with basis < 1st-of-month
    footer = None      # last processed current-window row (basis >= 1st-of-month)
    for r, (bal, cost) in zip(rows, eng):
        basis_val = str(r[basis])[:10]
        if basis_val < date_from:
            beginning = (bal, cost)
        else:
            if basis == 'value_date' and str(r['value_date'])[:7] > to_month:
                break
            footer = (bal, cost)

    sel = footer if footer is not None else beginning
    if sel is None:
        return 0
    bal, cost = sel
    if bal:
        return f"={cost}/{bal}"
    return 0


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

    NOTE (ltv_stocks2.py:927-938, analyze_position): the `average` snapshotted
    at `start_date` is only recomputed as of `report_date` for codes that have
    a report-date trade (non-empty `transactions` narrative); codes that did
    not trade today keep the `start_date`-derived average.
    """
    bank_row = db.execute(
        "SELECT indicative FROM tbl_bank_account WHERE ref_num = ?", (bank_ref,)
    ).fetchone()
    indicative = bank_row['indicative'] if bank_row else None

    wd = WorkingDay(db, ccy_id)
    if hkd_wd is None:
        hkd_wd = wd if ccy_id == 'HKD' else WorkingDay(db, 'HKD')
    start_date = position_start_date(report_date, hkd_wd)
    # BUG FIX (diverges from legacy): the beginning stock position must be the
    # on-hand balance as of the AS-OF date shown in the header -- the previous
    # week's Friday (previous_day(start_date)) -- NOT of start_date itself (the
    # walked-back Monday). The legacy labels the column "AS OF <Friday>" yet
    # snapshots the balance one working day later, wrongly folding Fri->Mon-gap
    # trades into the beginning position. `beginning_date` is that Friday.
    beginning_date = hkd_wd.previous_day(start_date)
    # Blocked-shares cutoff is unchanged: the legacy's non-indicative cutoff
    # previous_day(start_date) already equals beginning_date (the Friday), so
    # blocked was already computed as of the correct beginning date.
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
        (bank_ref, ccy_id, beginning_date.isoformat())
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

        transactions = _transactions_narrative(db, bank_ref, code_ref, report_date, balance)
        # Port of ltv_stocks2.py:analyze_position -- in principle the average
        # snapshotted at start_date is re-derived as of report_date when the
        # code has a report-date trade ('transactions' non-empty). In the
        # legacy production code this branch is actually unreachable: Gather_Info
        # calls get_ranged_transactions(self.report_date) with report_date as a
        # datetime object, so its "trade_date == '{report_date}'" filter compares
        # against a str(datetime) like '2026-07-06 00:00:00' that never matches
        # the plain-date-string trade_date column ('2026-07-06') -- confirmed by
        # the golden file's 'transactions'/column-O cells being blank throughout.
        # So 'average' always uses start_date; only the narrative column here
        # differs (it is computed from a live route, not the buggy Gather_Info
        # path), which is why _transactions_narrative may be non-empty while
        # 'average' must still use start_date to match the golden output.
        average_date = start_date

        result[code] = {
            'stock_name': r['stock_name'],
            'code': code,
            'code_ref': code_ref,
            'yahoo_ticker': r['yahoo_ticker'],
            'balance': balance,
            'blocked': blocked_v,
            'unblocked': unblocked_v,
            'average': _average(db, bank_id, code, average_date),
            'transactions': transactions,
        }

    return dict(sorted(result.items()))
