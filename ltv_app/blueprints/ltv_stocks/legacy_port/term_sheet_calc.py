from datetime import date, datetime
from .working_day import WorkingDay

_FREQ_DIV = {'monthly': 1, 'weekly': 4, 'bi-monthly': 2, 'bi-weekly': 2}
_FREQ_STEP = {'monthly': 1, 'weekly': 0.25, 'bi-monthly': 0.5, 'bi-weekly': 0.5}


def _to_date(v):
    return date.fromisoformat(str(v)[:10])


def _to_int(v):
    if v is None or v == '':
        return 0
    if isinstance(v, str):
        v = v.replace(',', '').strip()
        if v == '':
            return 0
    return int(float(v))


def _stock_name_gtd(name, gtd):
    if gtd in ('Yes', '1m'):
        return f'{name} GTD 1m'
    if gtd == 'No':
        return f'{name} NO GTD'
    digits = ''.join(ch for ch in str(gtd) if ch.isdigit())
    n = int(digits) if digits else 0
    return f'{name} GTD {n}m'


def _header(db, contract_ref):
    return db.execute("""
        SELECT c.reference, c.trade_date, c.start_date, b.bank_id, s.code,
               s.stock_name, s.yahoo_ticker, c.transaction_type, c.daily_shares,
               c.leveraged, c.spot,
               ROUND(c.strike_rate*c.spot/100, 4) AS strike, c.strike_rate,
               ROUND(c.ko_rate*c.spot/100, 4) AS ko, c.ko_rate,
               c.tenor, c.frequency, c.gtd, c.status, c.bank_doc,
               cy.ccy_id, b.indicative, s.ref_num AS code_ref
        FROM tbl_stock_contract c
        INNER JOIN tbl_bank_account b ON b.ref_num = c.bank_ref
        INNER JOIN tbl_code s         ON s.ref_num = c.code_ref
        INNER JOIN tbl_currency cy    ON cy.ref_num = s.ccy_ref
        WHERE c.ref_num = ?
    """, (contract_ref,)).fetchone()


def contract_records(db, bank_ref, transaction_type):
    ref_rows = db.execute(
        "SELECT c.ref_num FROM tbl_stock_contract c "
        "INNER JOIN tbl_bank_account b ON c.bank_ref = b.ref_num "
        "WHERE c.transaction_type = ? AND b.ref_num = ? AND c.status != 'inactive'",
        (transaction_type, bank_ref)
    ).fetchall()

    records = []
    for rr in ref_rows:
        contract_ref = rr['ref_num']
        h = _header(db, contract_ref)
        wd = WorkingDay(db, h['ccy_id'])

        periods = db.execute(
            "SELECT start_date, end_date, days, received, gtd "
            "FROM tbl_stock_contract_period WHERE contract_ref = ?", (contract_ref,)
        ).fetchall()
        if not periods:
            continue  # no schedule -> not displayable (legacy would KeyError)

        leveraged = h['leveraged'] == 'Yes'
        daily = h['daily_shares']
        freq = h['frequency']

        # Build schedule with per-period start_date/days/total_shares (period 1 start = contract start)
        sched = []
        prev_end = None
        for i, p in enumerate(periods):
            end_d = _to_date(p['end_date'])
            if i == 0:
                start_d = _to_date(h['start_date'])
            else:
                start_d = wd.next_day(prev_end)
            days = _to_int(p['days']) or wd.count_days(start_d, end_d)
            total_shares = days * daily * (2 if leveraged else 1)
            sched.append({'end_date': end_d, 'received': p['received'],
                          'days': days, 'total_shares': total_shares})
            prev_end = end_d

        last = len(sched)
        total = last / _FREQ_DIV.get(freq, 2)

        received = 0
        next_date = None
        for p in sched:
            if p['received'] == '' or p['received'] is None:
                next_date = wd.next_day(p['end_date'])
                break
            received += _FREQ_STEP.get(freq, 0.5)

        single = daily
        double = single * 2 if leveraged else single
        shares = f"{single:,.0f} / {double:,.0f}" if leveraged else f"{single:,.0f}"

        records.append({
            'ref_num': contract_ref,
            'reference': h['reference'],
            'bank_doc': h['bank_doc'],
            'frequency': freq,
            'stock_name': _stock_name_gtd(h['stock_name'], h['gtd']),
            'code': h['code'],
            'code_ref': h['code_ref'],
            'yahoo_ticker': h['yahoo_ticker'],
            'shares': shares,
            'spot': h['spot'],
            'strike': h['strike'],
            'ko': h['ko'],
            'start_date': _to_date(h['start_date']),
            'end_date': sched[last - 1]['end_date'],
            'total': total,
            'received': received,
            'next_date': next_date,
            'remaining': total - received,
            'ccy_id': h['ccy_id'],
            'daily_shares': daily,
            'leveraged': h['leveraged'],
            'indicative': h['indicative'],
            'status': h['status'],
        })
    return records
