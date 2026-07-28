"""Presentation-agnostic data/logic helpers used by excel_writer.py.

Everything here is pure Python (dates, DB reads, classification logic) with
no dependency on openpyxl or any other rendering library -- moved out of
excel_writer.py so this logic isn't tangled up with cell/style-writing code,
and so any future second renderer could reuse it without duplicating
business logic (a PDF renderer was scoped and prototyped against this split
but was decided against -- see docs/superpowers/specs/
2026-07-28-ltv-stocks-pdf-report-design.md for that history).
"""

from datetime import date, timedelta

from .positions_calc import _average, _transactions_narrative


def week_dates(report_date: date) -> list:
    """The 10-date range: previous Mon-Fri + current Mon-Fri, built with isoweekday()."""
    start = report_date - timedelta(days=6 + report_date.isoweekday())
    offsets = (0, 1, 2, 3, 4, 7, 8, 9, 10, 11)
    return [start + timedelta(days=o) for o in offsets]


_OX_COLS = ('O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')


def _today_for_inherit():
    # Deferred import to avoid a hard dependency on ltv_app.tz at module
    # import time for callers (e.g. a future standalone test) that don't
    # need it -- matches how excel_writer.py already imports ph_today
    # lazily relative to the rest of this module's imports.
    from ....tz import ph_today
    return ph_today()


def compute_status_flags(records, first_row, date_range, report_date, wd, price_lookup):
    """Returns [(col_letter, row), ...] for every date-column cell that is in
    "D" status (strike breached, not yet knocked out) for the given contract
    records, starting at `first_row`.

    Ported unchanged from excel_writer.py's _compute_circle_cells (same
    body/behavior) -- renamed on the move since "circle cells" was specific
    to how excel_writer.py visualizes this classification (a drawn ellipse);
    the classification itself is presentation-agnostic. `col_letter` is one
    of _OX_COLS, a stable per-day-offset label inherited from the Excel
    layout.

    See _write_contracts' own O:X gating in excel_writer.py for why each
    skip condition below exists (before start/after end/holiday -> never a
    real price there):
    - before start_date / after end_date / a holiday: skipped (blank or
      "Done" placeholder, never a price).
    - report_date itself: two-part rule -- if a price is already recorded,
      classify normally; if not AND report_date is the actual current day
      (still showing a live not-yet-populated closing-price lookup),
      inherit the most recently classified real trading day's status
      instead of skipping, so report_date still shows "D" if the position
      was already "D" as of the last known close. If report_date is not
      today, a missing price there is skipped like any other gap.
    - every other date: skipped unless price_lookup returns a real, nonzero
      number.
    """
    today = _today_for_inherit()
    cells = []
    for i, rec in enumerate(records):
        r = first_row + i
        e, f, g = rec['spot'], rec['strike'], rec['ko']
        above = e > f
        last_status = None  # most recent real-priced day's status for this row
        for col, d in zip(_OX_COLS, date_range):
            if d < rec['start_date'] or d > rec['end_date'] or wd.is_holiday(d):
                continue
            px = price_lookup(rec['code_ref'], d)
            has_price = isinstance(px, (int, float)) and px != 0
            if not has_price:
                if d != report_date or report_date != today or last_status is None:
                    continue  # no data and nothing to inherit -- skip
                status = last_status  # report_date inherits the last known day
            else:
                if above:
                    status = 'KO' if g <= px else ('D' if f >= px else '.')
                else:
                    status = 'KO' if g >= px else ('D' if f <= px else '.')
                last_status = status
            if status == 'D':
                cells.append((col, r))
    return cells


def inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date):
    """Port of contract()'s side-effect on self.stock_position (ltv_stocks2.py
    ~561-563): any ACCU contract whose code has no balance-derived position
    (zero net shares as of the report's AS-OF snapshot date) gets a
    placeholder row (unblocked=0, blocked=0). DECU contracts get no such
    placeholder.

    Uses the real average cost (and attaches the week's transactions
    narrative) whenever _average() can compute one; falls back to the
    contract's strike price only when the code truly has no computable
    average as of report_date either. Returns a fresh dict re-sorted by code.
    """
    positions = dict(positions)
    for rec in accu:
        code = rec['code']
        if code not in positions:
            real_average = _average(db, bank_id, code, report_date)
            if real_average is not None:
                positions[code] = {
                    'stock_name': rec['stock_name_plain'],
                    'code': code,
                    'code_ref': rec['code_ref'],
                    'yahoo_ticker': rec['yahoo_ticker'],
                    'balance': 0,
                    'blocked': 0,
                    'unblocked': 0,
                    'average': real_average,
                    'transactions': _transactions_narrative(db, bank_ref, rec['code_ref'], report_date),
                }
            else:
                positions[code] = {
                    'stock_name': rec['stock_name_plain'],
                    'code': code,
                    'code_ref': rec['code_ref'],
                    'yahoo_ticker': rec['yahoo_ticker'],
                    'balance': 0,
                    'blocked': 0,
                    'unblocked': 0,
                    'average': rec['strike'],
                    'transactions': None,
                }
    return dict(sorted(positions.items()))


# --- Reference data ported verbatim from ltv_stocks2.py's LTV_Stocks.__init__ / position() ---

PRIMARY_BANK_ACCOUNT = 'DBPe'
PRIMARY_SHEET_NAME = f'{PRIMARY_BANK_ACCOUNT}-HKD'

_CCYS = ('HKD', 'SGD')

_BANK_NAME = {
    "CB1": "CITIBANK",
    "CB2": "CITIBANK",
    "CB3": "CITIBANK",
    "CBBH": "CITIBANK",
    "CBBH2": "CITIBANK",
    "CBSG": "CITIBANK",
    "BOS": "Bank of Singapore",
    "DBPe": "DEUTSCHE BANK",
    "DBPL": "DEUTSCHE BANK",
    "SC": "STANDARD CHARTERED",
    "SHK": "SUN HUNG KAI Account No. 1",
    "SHK2": "SUN HUNG KAI Account No. 2",
    "MST1": "MORGAN STANLEY",
    "MST2": "MORGAN STANLEY",
    "MSPL": "MORGAN STANLEY",
    "NSG": "NOMURA SINGAPORE",
}

_SUB_TITLE = {
    'CB2': {'title': 'ACCOUNT # 2 (REALGOLD)', 'color': 'FF7030A0'},
    'CB3': {'title': 'ACCOUNT # 3', 'color': 'FF0070C0'},
    'CBBH': {'title': 'BERRY HILL Account', 'color': '00FF6600'},
    'CBBH2': {'title': 'BERRY HILL Account 2', 'color': '00FF6600'},
    'CBSG': {'title': 'Singapore Account No. 1', 'color': 'FF7030A0'},
    'DBPL': {'title': 'PERFECT LEGEND HOLDINGS w/ Lucio Yan', 'color': '00000000'},
    'MST1': {'title': 'Titan Account No. 1', 'color': '00000000'},
    'MST2': {'title': 'ACCOUNT NO. 2 (Titan) - PERSONAL', 'color': '00000000'},
    'MSPL': {'title': '(Perfect Legend)', 'color': '00000000'},
}

_POSITION_COLOR = {
    'CB1': 'FF7030A0', 'CB2': 'FF7030A0', 'CB3': 'FF0070C0',
    'CBBH': '00FF6600', 'CBBH2': '00FF6600', 'CBSG': 'FF7030A0',
    'BOS': '00000000', 'DBPe': '00000000', 'DBPL': '00000000',
    'SC': '00000000', 'SHK': '00000000', 'SHK2': '00000000',
    'MST1': '00000000', 'MST2': '00000000', 'MSPL': '00000000', 'NSG': '00000000',
}

_ACCOUNT_LABEL = {
    "CB1": {
        "HKD": "Citibank Account No. 1 Stocks",
        "JPY": "Citibank Account No. 1 Stocks",
        "AUD": "Citibank Account No. 1 Stocks",
        "USD": "Citibank Account No. 1 Stocks",
        "SGD": "Citibank Account No. 1 Stocks",
    },
    "CB2": "Citibank Account No. 2 Stocks",
    "CB3": "Citibank Account No. 3 Stocks",
    "CBBH": "Citibank Berry Hill  Stocks",
    "CBBH2": "Citibank Berry Hill No. 2 Stocks",
    "CBSG": "Citibank Singapore Account No. 1 Stocks",
    "BOS": "Bank of Singapore Stocks",
    "DBPe": "DEUTSCHE PERSONAL Stocks",
    "DBPL": "DEUTSCHE PERFECT LEGEND Stocks",
    "SC": "Standard Chartered Stocks",
    "SHK": "Sun Hung Kai Account No. 1 Stocks",
    "SHK2": "Sun Hung Kai Account No. 2 Stocks",
    "MST1": "MORGAN TITAN No. 1 Stocks",
    "MST2": "MORGAN TITAN No. 2 Stocks",
    "MSPL": "MORGAN PERFECT LEGEND Stocks",
    "NSG": "NOMURA SINGAPORE",
}

_CODE_FILLS = {
    '2333': 'FFE5E39F',
    '0700': '00FFFFCC',
    '1024': '009999FF',
    '0388': '00CC99FF',
    '3993': '00FFCC99',
    '0175': '00CCFFFF',
    '9988': '00008080',
}
_SMALL_FONT_CODES = ('0981', '2196')
