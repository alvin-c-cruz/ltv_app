"""PDF writer -- reportlab-based renderer producing the same contract +
positions report as excel_writer.py's build_workbook(), for hosts (like
PythonAnywhere) with no Office/LibreOffice/browser available. See
docs/superpowers/specs/2026-07-28-ltv-stocks-pdf-report-design.md.

build_pdf(db, report_date, bank_ids) is the public entry point -- same
signature shape as excel_writer.build_workbook.

"D" status (strike breached, not KO'd) renders as a bordered box around the
cell, not an ellipse (see design spec's tradeoff section) -- reportlab's
per-cell TableStyle BOX command is used directly rather than a canvas
overlay.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

from .term_sheet_calc import contract_records
from .positions_calc import position_records
from .stock_price import get_stock_price
from .working_day import WorkingDay
from .report_data import (
    week_dates, inject_accu_only_positions,
    _CCYS, _BANK_NAME, _SUB_TITLE, _ACCOUNT_LABEL, _CODE_FILLS,
)

_OX_COLS = ('O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')

# Fixed columns before the 10 date columns, matching excel_writer.py's
# visible (non-hidden) A/B/D/E/F/G/H/I/J/K/L/N columns -- C (Bank Reference)
# and M (Yahoo ticker) are hidden in Excel and simply omitted here rather
# than rendered-then-hidden.
_FIXED_HEADERS = (
    'UNDERLYING', 'CODE', 'SHARES/DAY', 'SPOT', 'STRIKE', 'K/O PRICE',
    'START', 'END', 'RCVD', 'REM', 'TOTAL', 'NEXT',
)
_FIXED_COL_WIDTHS = (
    1.55 * inch, 0.35 * inch, 0.55 * inch, 0.45 * inch, 0.45 * inch,
    0.45 * inch, 0.5 * inch, 0.5 * inch, 0.3 * inch, 0.3 * inch,
    0.3 * inch, 0.55 * inch,
)
_DATE_COL_WIDTH = 0.42 * inch

_HEX_TO_COLOR_CACHE = {}


def _hex_color(argb_hex):
    """'00RRGGBB' or 'FFRRGGBB' openpyxl-style hex -> reportlab Color, caching
    by input string (small fixed palette, called often per report)."""
    if argb_hex in _HEX_TO_COLOR_CACHE:
        return _HEX_TO_COLOR_CACHE[argb_hex]
    rgb = argb_hex[-6:]
    c = colors.HexColor(f'#{rgb}')
    _HEX_TO_COLOR_CACHE[argb_hex] = c
    return c


def _fmt_date(d):
    """'m/d' with no leading zeros -- avoids strftime's %-m/%-d (Unix-only)
    vs %#m/%#d (Windows-only) platform split, since this must run
    identically on this Windows dev machine and PythonAnywhere's Linux."""
    return f"{d.month}/{d.day}"


def _contract_table(records, report_date, date_range, wd, price_lookup):
    """Builds one reportlab Table (header + data rows) for the given ACCU or
    DECU records, mirroring excel_writer._write_contracts' column layout and
    the same "D"/"KO"/"xxx" per-date classification report_data.py's
    compute_status_flags uses for Excel's circle placement (re-derived here
    directly since this renderer also needs KO cell locations, which
    compute_status_flags doesn't surface -- see the comment at its call site
    below).

    Returns None if records is empty -- a PDF has no reason to render an
    empty placeholder row the way Excel does.
    """
    if not records:
        return None

    header_row = list(_FIXED_HEADERS) + [_fmt_date(d) for d in date_range]
    data = [header_row]

    # (col_idx, row_idx) 1-indexed against `data` (row 0 is the header),
    # collected while building rows so the TableStyle pass below can style
    # them without a second data walk.
    ko_cells = []
    d_cells = []

    for i, rec in enumerate(records):
        divisor = {'monthly': 1, 'weekly': 4, 'bi-monthly': 2, 'bi-weekly': 2}.get(rec.get('frequency'), 2)
        rem_raw = rec['total'] - rec['received']
        # Matches _write_contracts' own J/K/L number_format: whole numbers for
        # monthly (divisor==1), one decimal place otherwise -- rec['total']/
        # rec['received'] are always floats (contract_records divides by
        # _FREQ_DIV), so without this, monthly contracts would show "15.0"
        # instead of "15".
        if divisor == 1:
            rcvd, rem, total = f"{rec['received']:.0f}", f"{rem_raw:.0f}", f"{rec['total']:.0f}"
        else:
            rcvd, rem, total = f"{rec['received']:.1f}", f"{rem_raw:.1f}", f"{rec['total']:.1f}"

        row = [
            rec['stock_name'],
            rec['code'],
            rec['shares'],
            f"{rec['spot']:,.4f}",
            f"{rec['strike']:,.4f}",
            f"{rec['ko']:,.4f}",
            rec['start_date'].strftime('%d-%b-%y'),
            rec['end_date'].strftime('%d-%b-%y'),
            rcvd, rem, total,
            'DONE' if rec['received'] == rec['total'] else
            (rec['next_date'].strftime('%d-%b-%y') if rec['next_date'] else ''),
        ]

        table_row_idx = len(data)  # this row's index once appended below
        # compute_status_flags (report_data.py) only surfaces "D" cells (it
        # was originally scoped for Excel's circle-placement, which never
        # needed KO locations since Excel writes "KO" via its own live
        # formula). This renderer needs both KO and D cell placement, so the
        # same per-date classification is re-derived directly here rather
        # than calling compute_status_flags and then separately figuring out
        # which dates are KO -- same rule, single pass, no redundant call.
        above = rec['spot'] > rec['strike']
        for d in date_range:
            col_idx = len(row)  # position this date column will land at
            if d < rec['start_date'] or d > rec['end_date'] or wd.is_holiday(d):
                row.append('')
                continue
            px = price_lookup(rec['code_ref'], d)
            has_price = isinstance(px, (int, float)) and px != 0
            if not has_price:
                row.append('')
                continue
            if above:
                status = 'KO' if rec['ko'] <= px else ('D' if rec['strike'] >= px else '.')
            else:
                status = 'KO' if rec['ko'] >= px else ('D' if rec['strike'] <= px else '.')
            if status == 'KO':
                row.append('KO')
                ko_cells.append((col_idx, table_row_idx))
            elif status == 'D':
                row.append(f"{px:,.2f}")
                d_cells.append((col_idx, table_row_idx))
            else:
                row.append(f"{px:,.2f}")

        data.append(row)

    col_widths = list(_FIXED_COL_WIDTHS) + [_DATE_COL_WIDTH] * 10
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style = [
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]
    for i, rec in enumerate(records):
        r = i + 1
        fill = _CODE_FILLS.get(rec['code'])
        if fill:
            style.append(('BACKGROUND', (0, r), (0, r), _hex_color(fill)))
    for col_idx, row_idx in ko_cells:
        style.append(('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), colors.red))
        style.append(('FONTNAME', (col_idx, row_idx), (col_idx, row_idx), 'Helvetica-Bold'))
    for col_idx, row_idx in d_cells:
        style.append(('BOX', (col_idx, row_idx), (col_idx, row_idx), 1.2, colors.black))

    table.setStyle(TableStyle(style))
    return table


def _positions_table(positions, report_date, wd, price_lookup, bank_id, ccy):
    if not positions:
        return None

    account_label = _ACCOUNT_LABEL.get(bank_id)
    if isinstance(account_label, dict):
        account_label = account_label.get(ccy, bank_id)
    elif account_label is None:
        account_label = bank_id or ''

    header = ['ACCOUNT', 'CODE', 'UNBLOCKED', 'BLOCKED', 'TOTAL', 'AVE. PRICE', 'CLOSING', '% INC/DEC', 'TRANSACTIONS']
    data = [header]
    for code, pos in positions.items():
        total = (pos['unblocked'] or 0) + (pos['blocked'] or 0)
        if ccy == 'USD':
            trade_date = wd.previous_day(report_date)
            closing = price_lookup(pos['code_ref'], trade_date)
        else:
            # Excel resolves this via a live =INDEX(closing_price!...) formula
            # that only evaluates once opened in Excel -- a PDF has no
            # equivalent "resolve on open" concept, so this is left blank
            # rather than baking in a value Excel itself wouldn't show as of
            # generation time either. See design spec's "no live formulas"
            # section and the implementation plan's Self-Review for the
            # disclosed scope gap.
            closing = None
        pct = None
        if closing and pos['average']:
            pct = (closing / pos['average']) - 1
        data.append([
            pos['stock_name'], code,
            f"{pos['unblocked']:,.0f}" if pos['unblocked'] else '',
            f"{pos['blocked']:,.0f}" if pos['blocked'] else '',
            f"{total:,.0f}" if total else '',
            f"{pos['average']:,.4f}" if pos['average'] is not None else '',
            f"{closing:,.2f}" if closing else '',
            f"{pct:.2%}" if pct is not None else '',
            Paragraph(pos.get('transactions') or '', ParagraphStyle('cell', fontSize=6, leading=7)),
        ])

    col_widths = [1.6 * inch, 0.45 * inch, 0.6 * inch, 0.55 * inch, 0.55 * inch,
                  0.6 * inch, 0.55 * inch, 0.6 * inch, 2.3 * inch]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    return table


def build_pdf(db, report_date, bank_ids):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=0.2 * inch, rightMargin=0.2 * inch,
        topMargin=0.2 * inch, bottomMargin=0.2 * inch,
    )

    date_range = week_dates(report_date)
    hkd_wd = WorkingDay(db, 'HKD')
    title_style = ParagraphStyle('title', fontSize=14, spaceAfter=4, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('subtitle', fontSize=10, spaceAfter=8)

    story = []
    first_sheet = True

    for ccy in _CCYS:
        for bank_id in bank_ids:
            bank_row = db.execute(
                "SELECT ref_num FROM tbl_bank_account WHERE bank_id = ?", (bank_id,)
            ).fetchone()
            if bank_row is None:
                continue
            bank_ref = bank_row[0]

            accu = [r for r in contract_records(db, bank_ref, 'ACCU') if r['ccy_id'] == ccy]
            decu = [r for r in contract_records(db, bank_ref, 'DECU') if r['ccy_id'] == ccy]
            positions = position_records(db, bank_ref, bank_id, ccy, report_date, hkd_wd=hkd_wd)
            positions = inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date)

            if not (accu or decu or positions):
                continue

            wd = WorkingDay(db, ccy)
            price_lookup = lambda code_ref, d: get_stock_price(db, code_ref, d)

            if not first_sheet:
                story.append(PageBreak())
            first_sheet = False

            title = f"{_BANK_NAME.get(bank_id, bank_id)} as of {report_date.strftime('%B %d, %Y')}"
            story.append(Paragraph(title, title_style))
            if bank_id in _SUB_TITLE:
                story.append(Paragraph(_SUB_TITLE[bank_id]['title'], subtitle_style))
            if ccy != 'HKD':
                story.append(Paragraph(f"{ccy} STOCKS", subtitle_style))

            accu_table = _contract_table(accu, report_date, date_range, wd, price_lookup)
            if accu_table:
                story.append(Paragraph("ACCUMULATOR", subtitle_style))
                story.append(accu_table)
                story.append(Spacer(1, 12))

            decu_table = _contract_table(decu, report_date, date_range, wd, price_lookup)
            if decu_table:
                story.append(Paragraph("DECUMULATOR", subtitle_style))
                story.append(decu_table)
                story.append(Spacer(1, 12))

            pos_table = _positions_table(positions, report_date, wd, price_lookup, bank_id, ccy)
            if pos_table:
                story.append(Paragraph("POSITIONS", subtitle_style))
                story.append(pos_table)

    doc.build(story)
    buf.seek(0)
    return buf
