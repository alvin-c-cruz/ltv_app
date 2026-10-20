from datetime import date, timedelta

from ltv_app.blueprints.transactions.extensions.trades_done_average import get_transactions
from ltv_app.blueprints.transactions.models import get_short_average

from .working_day import WorkingDay, position_start_date
from .term_sheet_calc import build_schedule

# Legacy get_ranged_transactions: transaction types that ADD to the running
# balance get a leading "+ " when they are not the first entry of the day;
# everything else gets "- ".
_ADD_TYPES = ('Buy (Accu-KO)', 'Buy (Accu)', 'Buy (Spot)', 'Stock Dividend', 'Transfer-In')

# Transaction types that name the account on the other side of the trade, and
# the word that reads correctly for each direction.
_COUNTERPARTY_PREPOSITION = {'Transfer-Out': 'to', 'Transfer-In': 'from'}


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


def narrative_week_start(report_date: date) -> date:
    """The calendar Monday of report_date's own week: the first day the trade
    narrative covers, and so also the first day of the window that decides
    whether a code earns a position row at all (see position_records). Kept in
    one place so those two windows cannot drift apart -- a code that would print
    a narrative but gets no row is exactly the bug the second caller fixes.

    position_start_date() returns this same Monday since 2026-10-20; before that
    it walked back past a holiday Monday into the previous week."""
    return report_date - timedelta(days=report_date.isoweekday() - 1)


def _transactions_narrative(db, bank_ref, code_ref, report_date):
    """Current-week trade narrative for one (bank, code): every trade from the
    calendar Monday of report_date's own week through report_date, grouped by day.

    Enhancement over the legacy get_ranged_transactions and the original port, both
    of which showed only report_date's trades (`WHERE trade_date == report_date`).
    The window starts at the *calendar* Monday of report_date's week, so it begins
    the day after the AS-OF date of the balance beside it. When the week's only
    trades fall on report_date, output is identical to the old single-date narrative.

    Format: the first trade is `(m/d) Type qty @ price`; every later trade is
    prefixed with `+ ` / `- ` (add- vs subtract-type) and, when the trade day
    changes, its own `(m/d)` comes right after that sign -- e.g.
    `(7/6) Buy (Spot) 5,000 @ 112.20 - (7/8) Sell 2,000 @ 118.00 + (7/10) Buy (Spot)
    5,000 @ 112.20  = 70,960`. The trailing total is the TRUE ending balance as of
    report_date (self-computed here, not the caller's beginning-of-week snapshot --
    that snapshot is the wrong figure to show as the running total after these
    trades)."""
    week_monday = narrative_week_start(report_date)
    rows = db.execute(
        "SELECT t.trade_date, t.transaction_type, t.quantity, t.price, "
        "ba.bank_name AS counter_name "
        "FROM tbl_transaction t "
        "INNER JOIN tbl_transaction_type tt ON tt.transaction_type = t.transaction_type "
        "LEFT JOIN tbl_bank_account ba ON ba.ref_num = t.counter_bank_ref "
        "WHERE t.bank_ref = ? AND t.code_ref = ? "
        "AND t.trade_date >= ? AND t.trade_date <= ? "
        "ORDER BY t.trade_date, tt.priority, t.ref_num",
        (bank_ref, code_ref, week_monday.isoformat(), report_date.isoformat())
    ).fetchall()
    if not rows:
        return ''

    entry = ""
    current_day = None
    for i, r in enumerate(rows):
        day = str(r['trade_date'])[:10]
        ttype = r['transaction_type']
        qty_str = "{:,.0f}".format(abs(r['quantity']))
        price_str = _format_price(r['price'])
        sign = "" if i == 0 else ("+ " if ttype in _ADD_TYPES else "- ")
        # Both legs of a transfer name the account on the other side, inline and
        # in the same shape -- "Transfer-Out (to <bank>)" on the paying page,
        # "Transfer-In (from <bank>)" on the receiving one -- using the
        # counterparty bank on the transaction (tbl_transaction.counter_bank_ref).
        # Only the Out leg was labelled until 2026-09-06, so a receiving page
        # announced an arrival from nowhere and the two legs could not be tied
        # together by eye (see server/BUGS.md).
        type_part = ttype
        preposition = _COUNTERPARTY_PREPOSITION.get(ttype)
        if preposition and r['counter_name']:
            type_part = f"{ttype} ({preposition} {r['counter_name']})"
        if day != current_day:
            d = date.fromisoformat(day)
            date_part = f"({d.month}/{d.day}) "
            current_day = day
        else:
            date_part = ""
        entry += f"{sign}{date_part}{type_part} {qty_str} @ {price_str} "

    ending_balance = db.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM tbl_transaction "
        "WHERE bank_ref = ? AND code_ref = ? AND trade_date <= ?",
        (bank_ref, code_ref, report_date.isoformat())
    ).fetchone()[0]
    entry = entry.rstrip() + " = " + "{:,.0f}".format(ending_balance)
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
    :249-432). The average is cost_to_date/balance (a plain float), where cost/balance come from
    the moving-average engine selecting the current month's footer OR, when the
    footer is left unset, the prior-month-end beginning_balance.

    trades_done_average runs the engine over the month window [1st-of-month ..
    as_of], keyed on the bank's transaction_basis.

    BUG FIX (diverges from legacy, 2026-09-30): the legacy footer loop broke on the
    first current-window row whose value_date settles in a LATER month, so on a
    month-end report date a row traded that day but settling next month moved the
    narrative's share total and not the average printed beside it (found on a
    2026-09-30 accumulator fixing; see BUGS.md). Alvin: "/ltv-stocks should always show
    the most updated average." Every row traded up to as_of now counts -- the same
    running average the bank ledger page and /trades/average_price show. Pinned by
    scripts/verify_average_latest.py."""
    basis = db.execute(
        "SELECT transaction_basis FROM tbl_bank_account WHERE bank_id = ?", (bank_id,)
    ).fetchone()[0]
    rows = list(get_transactions(db, as_of_date.isoformat(), code, bank_id))
    if not rows:
        return None
    eng = _moving_average_engine(rows)
    date_from = _first_of_month(as_of_date)

    beginning = None   # last row with basis < 1st-of-month
    footer = None      # last processed current-window row (basis >= 1st-of-month)
    last_nonzero = None  # most recent (bal, cost) with bal != 0, as of each candidate row
    for r, (bal, cost) in zip(rows, eng):
        if bal:
            last_nonzero = (bal, cost)
        basis_val = str(r[basis])[:10]
        if basis_val < date_from:
            beginning = (bal, cost, last_nonzero)
        else:
            footer = (bal, cost, last_nonzero)

    sel = footer if footer is not None else beginning
    if sel is None:
        return None
    bal, cost, last_nz = sel
    if bal:
        return cost / bal
    # BUG FIX: a position that sold/transferred out to exactly zero has no
    # meaningful cost/balance ratio (0/0) -- showing a bare 0 there reads as "no
    # cost basis" rather than "fully closed out". Show the last average on record
    # (the cost/balance ratio from the last row where balance was still nonzero)
    # instead, so the figure still reflects what the position was carried at.
    if last_nz:
        lbal, lcost = last_nz
        return lcost / lbal
    return None


def position_records(db, bank_ref, bank_id, ccy_id, report_date: date, hkd_wd=None) -> dict:
    """Port of stock_balance.stock_position + blocked_shares for one bank/currency.

    Returns positions keyed by code, sorted by code, for every code of `ccy_id`
    that either carried a non-zero long-leg share balance at `bank_ref` on the
    AS-OF date or traded there during the reported week (see the query below).

    NOTE (ltv_stocks2.py:33): Gather_Info snapshots the balance/blocked/average as
    of `start_date` -- the current week's Monday (`position_start_date`) -- not
    `report_date` itself. Only the
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

    # BUG FIX (2026-09-06, server/BUGS.md): a code is emitted when it held a
    # balance on the AS-OF date OR traded during the reported week. It used to be
    # the balance alone (`HAVING SUM(quantity) != 0` as of beginning_date), which
    # silently dropped any code that started the week flat -- so the week's trades
    # in it had nowhere to print and the shares vanished from the report. A code
    # that arrives during the week is emitted with a zero beginning balance, which
    # is what the AS-OF column is asking for and is already how
    # inject_accu_only_positions renders an ACCU-only code.
    #
    # The two CASE windows cannot overlap: beginning_date < start_date ==
    # week_start for every report_date. No HKD working day falls between them:
    # beginning_date is the last HKD working day before week_start.
    # HAVING spells both aggregates out again rather than reusing the SELECT
    # aliases: `tbl_transaction` has its own `balance` column, and a bare name in
    # HAVING binds to the table column in preference to a result alias -- so
    # `HAVING balance != 0` silently filters on the stored per-row balance
    # instead of the computed one. Named parameters keep the repeated dates from
    # drifting out of order.
    week_start = narrative_week_start(report_date)
    rows = db.execute(
        "SELECT s.ref_num AS code_ref, s.code, s.stock_name, s.yahoo_ticker, "
        "       COALESCE(SUM(CASE WHEN t.trade_date <= :as_of THEN t.quantity END), 0) "
        "           AS beginning_balance "
        "FROM tbl_transaction t "
        "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
        "INNER JOIN tbl_currency cy ON cy.ref_num = s.ccy_ref "
        "WHERE t.bank_ref = :bank_ref AND cy.ccy_id = :ccy_id "
        "AND t.trade_date <= :report_date "
        "GROUP BY s.ref_num "
        "HAVING COALESCE(SUM(CASE WHEN t.trade_date <= :as_of THEN t.quantity END), 0) != 0 "
        "    OR COUNT(CASE WHEN t.trade_date >= :week_start THEN 1 END) > 0",
        {'as_of': beginning_date.isoformat(), 'week_start': week_start.isoformat(),
         'bank_ref': bank_ref, 'ccy_id': ccy_id,
         'report_date': report_date.isoformat()}
    ).fetchall()

    result = {}
    for r in rows:
        code_ref = r['code_ref']
        code = r['code']
        balance = r['beginning_balance']

        blocked = _blocked_shares(db, bank_ref, code_ref, cutoff, wd)
        if blocked >= balance:
            blocked_v, unblocked_v = balance, 0
        else:
            blocked_v, unblocked_v = blocked, balance - blocked

        transactions = _transactions_narrative(db, bank_ref, code_ref, report_date)
        # BUG FIX (diverges from legacy): the Ave. Price column is priced as of
        # the REPORT date (its header reads the report date, e.g. "06-Jul"), so
        # the average cost basis is computed as of report_date -- not the
        # walked-back start_date the legacy used. (The legacy's analyze_position
        # only re-derived it as of report_date for codes with a report-date
        # trade, and even that branch was effectively unreachable, so it always
        # showed the stale start_date average.)
        average_date = report_date

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


def format_short_shares(quantity):
    """A short balance the way the home page and the SHORT POSITION column show it: (1,000)."""
    text = "{:,.0f}".format(abs(quantity))
    return f"({text})" if quantity < 0 else text


def _short_transactions_narrative(db, bank_ref, code_ref, report_date):
    """_transactions_narrative for the short book (tbl_transaction_short): the week's
    short sales and covers, e.g. `(10/13) Sell (Short) 2,500 @ 894.50 = (2,500)`. A
    sale deepens the short and a cover reduces it, so the sign follows the quantity."""
    week_monday = narrative_week_start(report_date)
    rows = db.execute(
        "SELECT trade_date, transaction_type, quantity, price FROM tbl_transaction_short "
        "WHERE bank_ref = ? AND code_ref = ? AND trade_date >= ? AND trade_date <= ? "
        "ORDER BY trade_date, ref_num",
        (bank_ref, code_ref, week_monday.isoformat(), report_date.isoformat())
    ).fetchall()
    if not rows:
        return ''

    entry = ""
    current_day = None
    for i, r in enumerate(rows):
        day = str(r['trade_date'])[:10]
        sign = "" if i == 0 else ("+ " if r['quantity'] > 0 else "- ")
        if day != current_day:
            d = date.fromisoformat(day)
            date_part = f"({d.month}/{d.day}) "
            current_day = day
        else:
            date_part = ""
        entry += (f"{sign}{date_part}{r['transaction_type']} "
                  f"{'{:,.0f}'.format(abs(r['quantity']))} @ {_format_price(r['price'])} ")

    ending_balance = db.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM tbl_transaction_short "
        "WHERE bank_ref = ? AND code_ref = ? AND trade_date <= ?",
        (bank_ref, code_ref, report_date.isoformat())
    ).fetchone()[0]
    return entry.rstrip() + " = " + format_short_shares(ending_balance)


def short_position_records(db, bank_ref, ccy_id, report_date: date, hkd_wd=None) -> dict:
    """Short-book counterpart of position_records, for the SHORT POSITION table.

    Short sales are kept in tbl_transaction_short, not in the long book, so
    position_records never sees them. Same selection rule: a code is emitted when it
    carried a short balance on the AS-OF date (the previous week's Friday) or had a
    short-book trade during the reported week. Shares are the AS-OF balance (negative),
    as the long table's are; the average and the narrative run to report_date."""
    wd = WorkingDay(db, ccy_id)
    if hkd_wd is None:
        hkd_wd = wd if ccy_id == 'HKD' else WorkingDay(db, 'HKD')
    beginning_date = hkd_wd.previous_day(position_start_date(report_date, hkd_wd))
    week_start = narrative_week_start(report_date)

    rows = db.execute(
        "SELECT s.ref_num AS code_ref, s.code, s.stock_name, s.yahoo_ticker, "
        "       COALESCE(SUM(CASE WHEN t.trade_date <= :as_of THEN t.quantity END), 0) "
        "           AS beginning_balance "
        "FROM tbl_transaction_short t "
        "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
        "INNER JOIN tbl_currency cy ON cy.ref_num = s.ccy_ref "
        "WHERE t.bank_ref = :bank_ref AND cy.ccy_id = :ccy_id "
        "AND t.trade_date <= :report_date "
        "GROUP BY s.ref_num "
        "HAVING COALESCE(SUM(CASE WHEN t.trade_date <= :as_of THEN t.quantity END), 0) != 0 "
        "    OR COUNT(CASE WHEN t.trade_date >= :week_start THEN 1 END) > 0",
        {'as_of': beginning_date.isoformat(), 'week_start': week_start.isoformat(),
         'bank_ref': bank_ref, 'ccy_id': ccy_id,
         'report_date': report_date.isoformat()}
    ).fetchall()

    result = {}
    for r in rows:
        # The borrow fee the bank quoted with the latest short sale that carries one
        rate_row = db.execute(
            "SELECT interest_rate FROM tbl_transaction_short "
            "WHERE bank_ref = ? AND code_ref = ? AND trade_date <= ? AND interest_rate IS NOT NULL "
            "ORDER BY trade_date DESC, ref_num DESC LIMIT 1",
            (bank_ref, r['code_ref'], report_date.isoformat())
        ).fetchone()
        result[r['code']] = {
            'stock_name': r['stock_name'],
            'code': r['code'],
            'code_ref': r['code_ref'],
            'yahoo_ticker': r['yahoo_ticker'],
            'shares': r['beginning_balance'],
            'interest_rate': rate_row['interest_rate'] if rate_row else None,
            'average': get_short_average(db, bank_ref, r['code_ref'], report_date.isoformat()),
            'transactions': _short_transactions_narrative(db, bank_ref, r['code_ref'], report_date),
        }

    return dict(sorted(result.items()))
