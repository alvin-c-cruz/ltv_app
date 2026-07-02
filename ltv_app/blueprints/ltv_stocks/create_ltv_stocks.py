from datetime import date, timedelta


def get_ltv_stocks(db, report_date: date) -> dict:
    """Web view: positions only."""
    result = {}
    price_map = _load_closing_prices(db, report_date)
    _load_positions(db, result, report_date, price_map)
    week_start = report_date - timedelta(days=report_date.weekday())
    _load_transactions(db, result, week_start, report_date)
    return result


def get_ltv_stocks_full(db, report_date: date):
    """Excel download: contracts + positions + two-week closing prices."""
    result = {}
    price_map = _load_closing_prices(db, report_date)
    _load_contracts(db, result, price_map, report_date)
    _load_positions(db, result, report_date, price_map)
    week_start = report_date - timedelta(days=report_date.weekday())
    _load_transactions(db, result, week_start, report_date)
    trading_dates = _get_two_week_dates(report_date)
    price_map_multi = _load_closing_prices_multi(db, trading_dates)
    return result, price_map_multi, trading_dates


# ---------------------------------------------------------------------------
# Closing prices
# ---------------------------------------------------------------------------

def _load_closing_prices(db, report_date: date) -> dict:
    """Returns {code_ref: closing_price} for the most recent price on or before report_date."""
    rows = db.execute("""
        SELECT p.code_ref, p.closing_price
        FROM tbl_stock_price p
        INNER JOIN (
            SELECT code_ref, MAX(trade_date) AS latest
            FROM tbl_stock_price
            WHERE trade_date <= ?
            GROUP BY code_ref
        ) m ON m.code_ref = p.code_ref AND m.latest = p.trade_date
    """, (str(report_date),)).fetchall()
    return {r['code_ref']: r['closing_price'] for r in rows}


# ---------------------------------------------------------------------------
# Contracts (ACCU / DECU)
# ---------------------------------------------------------------------------

def _parse_trade_date(value):
    """Parse a stored trade_date (ISO YYYY-MM-DD...) to a date, or None."""
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _load_contracts(db, result: dict, price_map: dict, report_date: date):
    rows = db.execute("""
        SELECT
            c.ref_num, c.transaction_type, c.bank_doc,
            c.daily_shares, c.spot, c.strike_rate, c.ko_rate,
            c.start_date, c.trade_date, c.tenor, c.frequency, c.leveraged, c.status,
            b.bank_id, b.bank_name, b.report_label, b.priority AS bank_priority,
            s.ref_num AS code_ref, s.code, s.stock_name,
            cy.ccy_id, cy.priority AS ccy_priority,
            COUNT(p.ref_num)  AS received_count,
            MAX(p.end_date)   AS last_end_date
        FROM tbl_stock_contract c
        INNER JOIN tbl_bank_account b ON b.ref_num = c.bank_ref
        INNER JOIN tbl_code s         ON s.ref_num  = c.code_ref
        INNER JOIN tbl_currency cy    ON cy.ref_num = s.ccy_ref
        LEFT JOIN tbl_stock_contract_period p ON p.contract_ref = c.ref_num
        WHERE c.status != 'inactive'
        GROUP BY c.ref_num
        ORDER BY cy.priority, b.priority, s.code
    """).fetchall()

    week_start = report_date - timedelta(days=report_date.weekday())
    week_end   = week_start + timedelta(days=4)

    for row in rows:
        ccy  = row['ccy_id']
        bank = row['bank_id']
        bank_data = result \
            .setdefault(ccy, {}) \
            .setdefault(bank, _empty_bank(row['bank_name'], row['bank_priority'], row['report_label']))

        raw_months = _parse_tenor_months(row['tenor'])
        freq_mult  = 2 if row['frequency'] and 'bi' in str(row['frequency']).lower() else 1
        total      = raw_months * freq_mult
        received   = row['received_count']
        remaining  = max(0, total - received)

        received_months  = received / freq_mult
        remaining_months = max(0.0, raw_months - received_months)

        spot_raw   = row['spot']
        strike_raw = spot_raw * row['strike_rate'] / 100 if spot_raw and row['strike_rate'] else None
        ko_raw     = spot_raw * row['ko_rate']     / 100 if spot_raw and row['ko_rate']     else None

        daily = row['daily_shares']
        shares_day = f"{daily:,.0f} / {daily*2:,.0f}" if row['leveraged'] == 'Yes' else f"{daily:,.0f}"

        # KO is a distinct terminal state from DONE: a contract flagged KO is
        # never treated as DONE, even if all its periods have been received, so
        # it keeps showing a next-month date (like an active contract).
        is_ko   = row['status'] == 'KO'
        is_done = remaining == 0 and not is_ko

        # DONE/KO contracts are listed only when traded in the current week
        # (Mon-Fri of the report date). Active contracts are always listed.
        if is_done or is_ko:
            td = _parse_trade_date(row['trade_date'])
            if td is None or not (week_start <= td <= week_end):
                continue

        next_date = 'DONE' if is_done else _next_month_date(row['last_end_date'])
        closing_raw = price_map.get(row['code_ref'])

        try:
            start_date_raw = date.fromisoformat(str(row['start_date']))
        except (TypeError, ValueError):
            start_date_raw = None
        try:
            last_end_date_raw = date.fromisoformat(str(row['last_end_date']))
        except (TypeError, ValueError):
            last_end_date_raw = None

        contract = {
            'ref_num':          row['ref_num'],
            'code_ref':         row['code_ref'],
            'code':             row['code'],
            'stock_name':       row['stock_name'],
            'bank_doc':         row['bank_doc'] or '—',
            'shares_day':       shares_day,
            'daily_shares':     daily,
            'spot':             _fmt_price(spot_raw),
            'strike':           _fmt_price(strike_raw),
            'ko':               _fmt_price(ko_raw),
            'spot_raw':         spot_raw,
            'strike_raw':       strike_raw,
            'ko_raw':           ko_raw,
            'start_date':       row['start_date'] or '—',
            'last_end_date':    row['last_end_date'] or '—',
            'start_date_raw':   start_date_raw,
            'last_end_date_raw': last_end_date_raw,
            'received':         received,
            'remaining':        remaining,
            'total':            total,
            'received_months':  received_months,
            'remaining_months': remaining_months,
            'total_months':     raw_months,
            'next_date':        next_date,
            'is_done':          is_done,
            'is_ko':            is_ko,
            'closing':          closing_raw,
            'closing_fmt':      _fmt_price(closing_raw) if closing_raw is not None else '—',
        }

        key = 'accu' if row['transaction_type'] == 'ACCU' else 'decu'
        bank_data[key].append(contract)


# ---------------------------------------------------------------------------
# Stock positions
# ---------------------------------------------------------------------------

def _load_positions(db, result: dict, report_date: date, price_map: dict):
    blocked_map = _get_blocked_map(db)

    rows = db.execute("""
        SELECT
            b.bank_id, b.bank_name, b.report_label, b.priority AS bank_priority,
            s.ref_num AS code_ref, s.code, s.stock_name,
            cy.ccy_id, cy.priority AS ccy_priority,
            SUM(t.quantity) AS balance,
            SUM(CASE WHEN t.quantity > 0
                THEN t.quantity * t.price
                     + t.brokerage + t.commission
                     + t.foreign_charge + t.stamp_duty + t.misc
                ELSE 0 END) AS total_buy_cost,
            SUM(CASE WHEN t.quantity > 0 THEN t.quantity ELSE 0 END) AS total_bought
        FROM tbl_transaction t
        INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref
        INNER JOIN tbl_code s         ON s.ref_num  = t.code_ref
        INNER JOIN tbl_currency cy    ON cy.ref_num = s.ccy_ref
        WHERE t.trade_date <= ?
        GROUP BY b.bank_id, b.bank_name, b.priority,
                 s.code, s.stock_name, cy.ccy_id, cy.priority
        HAVING SUM(t.quantity) != 0
        ORDER BY cy.priority, b.priority, s.code
    """, (str(report_date),)).fetchall()

    for row in rows:
        ccy     = row['ccy_id']
        bank    = row['bank_id']
        code    = row['code']
        balance = row['balance']

        blocked   = blocked_map.get((bank, code), 0)
        unblocked = max(0, balance - blocked)
        avg_cost  = row['total_buy_cost'] / row['total_bought'] if row['total_bought'] else 0

        closing = price_map.get(row['code_ref'])
        pct_chg = (closing / avg_cost - 1) if closing and avg_cost else None

        bank_data = result \
            .setdefault(ccy, {}) \
            .setdefault(bank, _empty_bank(row['bank_name'], row['bank_priority'], row['report_label']))

        bank_data['positions'][code] = {
            'stock_name':   row['stock_name'],
            'code_ref':     row['code_ref'],
            'balance':      balance,
            'unblocked':    unblocked,
            'blocked':      blocked,
            'average':      avg_cost,
            'closing':      closing,
            'pct_chg':      pct_chg,
            'transactions': '',
        }


def _get_blocked_map(db) -> dict:
    """Returns {(bank_id, code): shares_blocked} for active DECU with remaining periods."""
    rows = db.execute("""
        SELECT b.bank_id, s.code, c.leveraged, c.daily_shares,
               c.tenor, c.frequency,
               COUNT(p.ref_num) AS received_count
        FROM tbl_stock_contract c
        INNER JOIN tbl_bank_account b ON b.ref_num = c.bank_ref
        INNER JOIN tbl_code s         ON s.ref_num  = c.code_ref
        LEFT JOIN tbl_stock_contract_period p ON p.contract_ref = c.ref_num
        WHERE c.transaction_type = 'DECU'
          AND c.status != 'inactive'
        GROUP BY c.ref_num
    """).fetchall()

    result = {}
    for row in rows:
        total     = _parse_tenor_periods(row['tenor'], row['frequency'])
        remaining = max(0, total - row['received_count'])
        if remaining == 0:
            continue
        key    = (row['bank_id'], row['code'])
        shares = row['daily_shares'] * 2 if row['leveraged'] == 'Yes' else row['daily_shares']
        result[key] = result.get(key, 0) + (remaining * shares)
    return result


# ---------------------------------------------------------------------------
# Weekly transactions
# ---------------------------------------------------------------------------

def _load_transactions(db, result: dict, start_date: date, end_date: date):
    rows = db.execute("""
        SELECT
            b.bank_id, s.code, cy.ccy_id,
            t.trade_date, t.transaction_type, t.quantity, t.price
        FROM tbl_transaction t
        INNER JOIN tbl_bank_account b      ON b.ref_num = t.bank_ref
        INNER JOIN tbl_code s              ON s.ref_num  = t.code_ref
        INNER JOIN tbl_currency cy         ON cy.ref_num = s.ccy_ref
        INNER JOIN tbl_transaction_type tt ON tt.transaction_type = t.transaction_type
        WHERE t.trade_date >= ? AND t.trade_date <= ?
        ORDER BY cy.priority, b.priority, s.code, t.trade_date, tt.priority
    """, (str(start_date), str(end_date))).fetchall()

    parts_map: dict[tuple, list] = {}
    for row in rows:
        key   = (row['bank_id'], row['code'])
        qty   = row['quantity']
        td    = row['trade_date']
        d_fmt = f"({int(td[5:7])}/{int(td[8:10])})"
        p_fmt = _fmt_price(row['price'])
        q_fmt = f"{abs(qty):,.0f}"
        parts_map.setdefault(key, []).append((qty, f"{d_fmt} {row['transaction_type']} {q_fmt} @ {p_fmt}"))

    for (bank_id, code), parts in parts_map.items():
        txn_str = _join_parts(parts)
        for ccy_data in result.values():
            if bank_id in ccy_data:
                pos = ccy_data[bank_id]['positions']
                if code in pos:
                    pos[code]['transactions'] = txn_str
                    break


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_two_week_dates(report_date: date) -> list:
    """
    Legacy-style date range: previous full week (Mon-Fri) + current week to report_date.

    Example: report_date = Tuesday, June 2, 2026
    Returns: [May 25 (Mon), May 26 (Tue), May 27 (Wed), May 28 (Thu), May 29 (Fri),
              June 1 (Mon), June 2 (Tue), ...up to 10 dates total]
    """
    # Go back to previous Monday (6 days + weekday offset)
    start = report_date - timedelta(days=6 + report_date.weekday())

    # Return exactly 10 dates as legacy does
    return [
        start,
        start + timedelta(days=1),
        start + timedelta(days=2),
        start + timedelta(days=3),
        start + timedelta(days=4),
        start + timedelta(days=7),
        start + timedelta(days=8),
        start + timedelta(days=9),
        start + timedelta(days=10),
        start + timedelta(days=11),
    ]


def _load_closing_prices_multi(db, dates: list) -> dict:
    """Returns {code_ref: {date_str: price}} for the given list of dates."""
    if not dates:
        return {}
    ph = ','.join('?' * len(dates))
    rows = db.execute(
        f"SELECT code_ref, trade_date, closing_price FROM tbl_stock_price WHERE trade_date IN ({ph})",
        [str(d) for d in dates]
    ).fetchall()
    result: dict = {}
    for r in rows:
        result.setdefault(r['code_ref'], {})[r['trade_date']] = r['closing_price']
    return result


def _parse_tenor_months(tenor: str) -> int:
    """Return the numeric month count from tenor string (e.g. '12m' → 12)."""
    try:
        return int(str(tenor).lower().replace('m', '').strip())
    except (ValueError, AttributeError):
        return 0


def _parse_tenor_periods(tenor: str, frequency: str) -> int:
    """Convert tenor (e.g. '12m') + frequency to expected period count."""
    multiplier = 2 if frequency and 'bi' in str(frequency).lower() else 1
    return _parse_tenor_months(tenor) * multiplier


def _next_month_date(date_str: str) -> str:
    """Estimate next delivery date as last_end_date + ~30 days."""
    try:
        d = date.fromisoformat(date_str)
        return str(d + timedelta(days=30))
    except Exception:
        return '—'


def _empty_bank(bank_name: str, priority: int, report_label: str = None) -> dict:
    return {'bank_name': bank_name, 'bank_priority': priority,
            'report_label': report_label,
            'accu': [], 'decu': [], 'positions': {}}


def _fmt_price(value) -> str:
    if value is None:
        return '—'
    return f"{value:,.4f}" if _decimal_places(value) > 2 else f"{value:,.2f}"


def _join_parts(parts: list) -> str:
    segments = []
    for qty, part in parts:
        if segments:
            segments.append(' + ' if qty >= 0 else ' - ')
        segments.append(part)
    return ''.join(segments)


def _decimal_places(value: float) -> int:
    s = f"{value:.10f}".rstrip('0')
    return len(s) - s.index('.') - 1 if '.' in s else 0
