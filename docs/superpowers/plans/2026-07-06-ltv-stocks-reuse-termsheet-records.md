# LTV Stocks — Reuse Term-Sheet Records Implementation Plan

> ⚠️ **SUPERSEDED** — the target is now an exact native replica of the legacy `create_LTV_Stocks.py`
> Excel (porting `summary_ts_raw` + `blocked_shares`, minus AA–AJ per-day markers). Do not execute this plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the LTV Stocks Excel ACCU/DECU sections list every non-inactive contract, computed by reusing term-sheet's `StockContract` model, with term-sheet columns (Received/Remaining/Total months, DONE/KO Next Date, Contract No., Reference) and correct Positions blocked shares.

**Architecture:** The data layer `create_ltv_stocks.py` stops re-implementing period math and instead builds each Excel record from a `StockContract` instance (as the term-sheet page does). The Excel renderer `views.py:_xl_contracts` gets the term-sheet column set. `_get_blocked_map` uses the model's `remaining_shares`. `term_sheet/models.py` is imported, never modified.

**Tech Stack:** Python 3, SQLite (`sqlite3.Row`), openpyxl, pytest.

## Global Constraints

- Read-only: SELECT only. No schema/data changes. No `localhost/` impact.
- Reuse `ltv_app.blueprints.term_sheet.models.StockContract` (imported lazily inside functions to avoid any import-order coupling). Do **not** edit `term_sheet/`.
- "Received" months, `next_date`, and `remaining_shares` come from the `StockContract` instance after `.get(ref_num=…)` + a call that triggers `__post_init__` (`as_dict()`). A period-less contract leaves `next_date` unset → `as_dict()` raises `AttributeError`; the loaders catch it and skip that contract.
- Contract record dict shape (produced by `_load_contracts`, consumed by `_xl_contracts` and tests):
  `stock_name` (GTD-suffixed str), `code` (str), `code_ref` (int), `bank_doc` (str), `reference` (str), `shares_day` (str), `spot_raw`/`strike_raw`/`ko_raw` (float|None), `start_date_raw`/`last_end_date_raw` (date|None), `received`/`remaining`/`total` (float months), `next_date_display` (`'DONE'` | `'KO'` | ISO date str), `is_done`/`is_ko` (bool), `closing` (float|None).
- Test seed data (`tests/functional/conftest.py`): bank `ref_num=1` = "Citibank No. 1" (`bank_id='CB1'`), code `ref_num=1` = code "700" "Tencent Holdings Limited", currency HKD. `_load_contracts` results land at `result['HKD']['CB1']['accu'|'decu']`.
- The `_add_contract` helper (top of the test file) inserts a contract + one period `received='1000', days='20', gtd='1m'`, with `daily_shares=1000, leveraged='No', frequency='monthly'`.

---

## File structure

- **Modify:** `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — new `_stock_name_with_gtd`; rewrite `_load_contracts` and `_get_blocked_map`; `get_ltv_stocks_full` caller; delete `_parse_trade_date`.
- **Modify:** `ltv_app/blueprints/ltv_stocks/views.py` — rewrite `_xl_contracts` (columns) and the column-width block in `_generate_excel`.
- **Modify:** `tests/functional/test_ltv_stocks_active_count.py` — rework tests to the new record shape and behavior.

Note: the rewrite intentionally drops two legacy-only extras from `_xl_contracts` that term-sheet does not have — the per-stock name colors (`STOCK_COLORS`) and the KO-closing-rate / in-contract "Average" annotations. KO rows instead get a light-red fill, matching term-sheet.

---

### Task 1: `_stock_name_with_gtd` helper

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Produces: module-level `_stock_name_with_gtd(stock_name: str, gtd) -> str`, consumed by `_load_contracts` in Task 2.

- [ ] **Step 1: Write the failing test**

Replace the top import line of `tests/functional/test_ltv_stocks_active_count.py`:
```python
from ltv_app.blueprints.ltv_stocks.create_ltv_stocks import _load_contracts
from ltv_app.blueprints.ltv_stocks.views import _active_count, _generate_excel
```
with:
```python
from ltv_app.blueprints.ltv_stocks.create_ltv_stocks import (
    _load_contracts, _get_blocked_map, _stock_name_with_gtd,
)
from ltv_app.blueprints.ltv_stocks.views import _active_count, _generate_excel
```

Append:
```python
def test_stock_name_gtd_suffix():
    assert _stock_name_with_gtd('Alibaba', 'No')  == 'Alibaba No GTD'
    assert _stock_name_with_gtd('Alibaba', 'Yes') == 'Alibaba GTD 1m'
    assert _stock_name_with_gtd('Alibaba', '3m')  == 'Alibaba GTD 3m'
    assert _stock_name_with_gtd('Alibaba', '')    == 'Alibaba'
    assert _stock_name_with_gtd('Alibaba', None)  == 'Alibaba'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py::test_stock_name_gtd_suffix -v`
Expected: FAIL — `ImportError: cannot import name '_stock_name_with_gtd'`.

- [ ] **Step 3: Add the helper**

In `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`, add near the other helpers (e.g. above `_fmt_price`):
```python
def _stock_name_with_gtd(stock_name, gtd):
    """Append the GTD term to the stock name, mirroring term_sheet's summary()."""
    if not gtd:
        return stock_name
    if gtd == "No":
        return f"{stock_name} No GTD"
    if gtd == "Yes":
        return f"{stock_name} GTD 1m"
    return f"{stock_name} GTD {gtd}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py::test_stock_name_gtd_suffix -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): add _stock_name_with_gtd helper"
```

---

### Task 2: Rebuild `_load_contracts` on `StockContract` and rewrite the Excel columns

Data layer and renderer change together — they share the record dict shape, so this is one deliverable.

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (`_load_contracts`, `get_ltv_stocks_full`, delete `_parse_trade_date`)
- Modify: `ltv_app/blueprints/ltv_stocks/views.py` (`_xl_contracts`, `_generate_excel` widths)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Consumes: `_stock_name_with_gtd` (Task 1).
- Produces: `_load_contracts(db, result: dict, price_map: dict)` (3-arg) filling `result[ccy][bank]['accu'|'decu']` with the record dict shape from Global Constraints. `_xl_contracts` renders that shape.

- [ ] **Step 1: Rework the tests (write the failing tests)**

In `tests/functional/test_ltv_stocks_active_count.py`:

Delete `test_current_week_filters_done_and_ko`, `test_missing_trade_date_done_ko_omitted`, `test_load_contracts_sets_is_ko`, and `test_ko_overrides_done_when_all_periods_received` (the mechanism they asserted is replaced).

Replace the `_contract(**overrides)` builder and `test_generate_excel_count_is_plain_integer` with the new record shape:
```python
def _contract(**overrides):
    base = {
        'stock_name': 'Tencent GTD 1m', 'code': '700', 'code_ref': 1,
        'bank_doc': 'DOC', 'reference': 'Tencent - 1', 'shares_day': '1,000',
        'spot_raw': 100.0, 'strike_raw': 95.0, 'ko_raw': 110.0,
        'start_date_raw': date(2026, 1, 1), 'last_end_date_raw': date(2026, 1, 31),
        'received': 1.0, 'remaining': 11.0, 'total': 12.0,
        'next_date_display': '2026-08-01', 'is_done': False, 'is_ko': False,
    }
    base.update(overrides)
    return base


def test_generate_excel_count_is_plain_integer():
    accu = [
        _contract(),                                          # active
        _contract(is_ko=True, next_date_display='KO'),        # ko
        _contract(is_done=True, next_date_display='DONE'),    # done
    ]
    data = {'HKD': {'CB1': {
        'bank_name': 'Citibank No. 1', 'bank_priority': 1, 'report_label': None,
        'accu': accu, 'decu': [], 'positions': {},
    }}}
    output = _generate_excel(data, date(2026, 7, 2), {}, [])
    wb = load_workbook(output)
    ws = wb['CB1-HKD']
    # find the ACCU count cell: the first cell in column A that is an int
    ints = [ws.cell(r, 1).value for r in range(1, 12)
            if isinstance(ws.cell(r, 1).value, int)]
    assert ints and ints[0] == 1
```

Append these new tests:
```python
def test_load_contracts_matches_stockcontract(app):
    """The loaded record's period figures equal StockContract's own values."""
    from ltv_app.blueprints.term_sheet.models import StockContract
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 50, 'ACCU', 'active', tenor='2m', trade_date='2026-07-06')
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (50, '2026-02-01', '2026-02-28', '20', '', '1m')"
    )
    conn.commit()

    sc = StockContract(db=conn); sc.get(ref_num=50); ref = sc.as_dict()
    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    ct = {c['ref_num']: c for c in result['HKD']['CB1']['accu']}[50]
    assert ct['received'] == ref['received']
    assert ct['remaining'] == ref['remaining']
    assert ct['total'] == ref['total']
    assert ct['remaining'] > 0
    assert ct['is_done'] is False
    assert ct['is_ko'] is False


def test_active_and_ko_and_done_all_listed(app):
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 60, 'ACCU', 'active', tenor='2m', trade_date='2026-07-06')  # active
    conn.execute("INSERT INTO tbl_stock_contract_period "
                 "(contract_ref, start_date, end_date, days, received, gtd) "
                 "VALUES (60, '2026-02-01', '2026-02-28', '20', '', '1m')")
    _add_contract(conn, 61, 'ACCU', 'active', tenor='1m', trade_date='2020-01-01')  # DONE (1 period, received)
    _add_contract(conn, 62, 'ACCU', 'KO', tenor='2m', trade_date='2020-01-01')      # KO
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    by_ref = {c['ref_num']: c for c in result['HKD']['CB1']['accu']}
    assert set(by_ref) == {60, 61, 62}
    assert by_ref[61]['is_done'] is True
    assert by_ref[62]['is_ko'] is True


def test_next_date_done_ko_date(app):
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 70, 'ACCU', 'active', tenor='1m')                 # DONE
    _add_contract(conn, 71, 'ACCU', 'KO', tenor='2m')                     # KO
    _add_contract(conn, 72, 'ACCU', 'active', tenor='2m')                 # active, 1 received + implicit unreceived
    conn.execute("INSERT INTO tbl_stock_contract_period "
                 "(contract_ref, start_date, end_date, days, received, gtd) "
                 "VALUES (72, '2026-02-01', '2026-02-28', '20', '', '1m')")
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    by_ref = {c['ref_num']: c for c in result['HKD']['CB1']['accu']}
    assert by_ref[70]['next_date_display'] == 'DONE'
    assert by_ref[71]['next_date_display'] == 'KO'
    assert by_ref[72]['next_date_display'] not in ('DONE', 'KO')  # a date string


def test_generate_excel_has_reference_and_contract_no_columns():
    accu = [_contract(), _contract(is_ko=True, next_date_display='KO', reference='Tencent - 2')]
    data = {'HKD': {'CB1': {
        'bank_name': 'Citibank No. 1', 'bank_priority': 1, 'report_label': None,
        'accu': accu, 'decu': [], 'positions': {},
    }}}
    output = _generate_excel(data, date(2026, 7, 2), {}, [])
    wb = load_workbook(output)
    ws = wb['CB1-HKD']
    seen = set()
    for r in range(1, 15):
        for ccol in range(1, 15):
            v = ws.cell(r, ccol).value
            if isinstance(v, str):
                seen.add(v)
    assert 'Reference' in seen
    assert 'Contract No.' in seen
    assert 'Tencent - 1' in seen  # reference value rendered
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: FAIL — the old 4-arg `_load_contracts` call/keys are gone and the renderer still uses old columns, so the new record-shape tests and the header tests fail (e.g. `'Reference' in seen` is False; `_load_contracts(conn, result, {})` may still take `report_date`).

- [ ] **Step 3: Rewrite `_load_contracts`**

In `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`, replace the whole `_load_contracts` function with:
```python
def _load_contracts(db, result: dict, price_map: dict):
    from ltv_app.blueprints.term_sheet.models import StockContract

    rows = db.execute("""
        SELECT c.ref_num, c.transaction_type,
               b.bank_id, b.bank_name, b.report_label, b.priority AS bank_priority,
               cy.ccy_id, cy.priority AS ccy_priority, s.code
        FROM tbl_stock_contract c
        INNER JOIN tbl_bank_account b ON b.ref_num = c.bank_ref
        INNER JOIN tbl_code s         ON s.ref_num = c.code_ref
        INNER JOIN tbl_currency cy    ON cy.ref_num = s.ccy_ref
        WHERE c.status != 'inactive'
        ORDER BY cy.priority, b.priority, s.code
    """).fetchall()

    for row in rows:
        sc = StockContract(db=db)
        sc.get(ref_num=row['ref_num'])
        try:
            sc.as_dict()   # triggers __post_init__; AttributeError if no periods
        except AttributeError:
            continue

        is_ko   = sc.status == 'KO'
        is_done = sc.next_date == 'DONE'
        if is_done:
            next_date_display = 'DONE'
        elif is_ko:
            next_date_display = 'KO'
        else:
            next_date_display = sc.next_date

        spot_raw   = sc.spot
        strike_raw = sc.spot * sc.strike_rate / 100 if sc.spot and sc.strike_rate else None
        ko_raw     = sc.spot * sc.ko_rate / 100 if sc.spot and sc.ko_rate else None

        daily = sc.daily_shares
        shares_day = f"{daily:,.0f} / {daily*2:,.0f}" if sc.leveraged == 'Yes' else f"{daily:,.0f}"

        try:
            start_date_raw = date.fromisoformat(str(sc.start_date)[:10])
        except (TypeError, ValueError):
            start_date_raw = None
        try:
            last_end_date_raw = date.fromisoformat(str(sc.end_date)[:10])
        except (TypeError, ValueError):
            last_end_date_raw = None

        contract = {
            'ref_num':           sc.ref_num,
            'code_ref':          sc.code_ref,
            'code':              sc.code,
            'stock_name':        _stock_name_with_gtd(sc.stock_name, sc.gtd),
            'bank_doc':          sc.bank_doc or '-',
            'reference':         sc.reference or '-',
            'shares_day':        shares_day,
            'spot_raw':          spot_raw,
            'strike_raw':        strike_raw,
            'ko_raw':            ko_raw,
            'start_date_raw':    start_date_raw,
            'last_end_date_raw': last_end_date_raw,
            'received':          sc.received_periods,
            'remaining':         sc.remaining_periods,
            'total':             sc.total_periods,
            'next_date_display': next_date_display,
            'is_done':           is_done,
            'is_ko':             is_ko,
            'closing':           price_map.get(sc.code_ref),
        }

        bank_data = result \
            .setdefault(row['ccy_id'], {}) \
            .setdefault(row['bank_id'],
                        _empty_bank(row['bank_name'], row['bank_priority'], row['report_label']))
        key = 'accu' if sc.transaction_type == 'ACCU' else 'decu'
        bank_data[key].append(contract)
```

Then delete the `_parse_trade_date` helper (it is no longer referenced), and in `get_ltv_stocks_full` change `_load_contracts(db, result, price_map, report_date)` to `_load_contracts(db, result, price_map)`.

- [ ] **Step 4: Rewrite `_xl_contracts` (new columns)**

In `ltv_app/blueprints/ltv_stocks/views.py`, replace the whole `_xl_contracts` function with:
```python
def _xl_contracts(ws, contracts, title, row,
                  price_map_multi, trading_dates,
                  BOLD, BOLD_SM, NORM, NORM_SM, FILL_TITLE, FILL_HDR, FILL_CLOSE,
                  FONT_WHITE, BOX, CTR, LFT):
    from openpyxl.styles import Font, PatternFill, Alignment
    from datetime import date as _date

    N_dates = len(trading_dates)
    FIXED = 14
    TOTAL_COLS = FIXED + N_dates
    KO_FILL = PatternFill('solid', fgColor='FECACA')  # light red, like term-sheet

    # ── Active contract count (excludes DONE and KO) ──
    if contracts:
        c = ws.cell(row, 1, _active_count(contracts))
        c.font = Font(name='Arial', size=7, bold=False)
        c.number_format = '0'
        c.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[row].height = 10.5
        row += 1

    # ── Section title ──
    c = ws.cell(row, 1, title)
    c.font = FONT_WHITE; c.fill = FILL_TITLE; c.alignment = LFT
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=TOTAL_COLS)
    row += 1

    # ── Header row (term-sheet columns) ──
    headers = ['Stock Name', 'Code', 'Shares / Day', 'Spot Price', 'Strike Price',
               'K/O Price', 'Start Date', 'End Date', 'Received', 'Remaining',
               'Total', 'Next Date', 'Contract No.', 'Reference']
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row, i, h)
        c.font = BOLD_SM; c.fill = FILL_HDR; c.alignment = CTR; c.border = BOX
    for i, d in enumerate(trading_dates):
        c = ws.cell(row, FIXED + 1 + i, d)
        c.font = BOLD_SM; c.fill = FILL_CLOSE; c.alignment = CTR; c.border = BOX
        c.number_format = 'd-mmm'
    row += 1

    # ── Data rows ──
    if not contracts:
        c = ws.cell(row, 1, 'No contracts.')
        c.font = NORM; c.alignment = LFT
        row += 1
        return row

    STRIKE_FONT = Font(name='Arial', bold=True, size=10)

    for ct in contracts:
        nd = ct['next_date_display']
        if nd in ('DONE', 'KO'):
            next_val, next_fmt = nd, None
        else:
            try:
                next_val = _date.fromisoformat(str(nd)[:10]); next_fmt = 'd-mmm-yy'
            except (ValueError, TypeError):
                next_val, next_fmt = nd, None

        entries = [
            (1,  ct['stock_name'],        NORM,        LFT, None),
            (2,  ct['code'],              NORM,        CTR, '@'),
            (3,  ct['shares_day'],        NORM,        CTR, None),
            (4,  ct['spot_raw'],          NORM,        CTR, '#,##0.0000'),
            (5,  ct['strike_raw'],        STRIKE_FONT, CTR, '#,##0.0000'),
            (6,  ct['ko_raw'],            NORM,        CTR, '#,##0.0000'),
            (7,  ct['start_date_raw'],    NORM,        CTR, 'd-mmm-yy'),
            (8,  ct['last_end_date_raw'], NORM,        CTR, 'd-mmm-yy'),
            (9,  ct['received'],          NORM,        CTR, '0.0'),
            (10, ct['remaining'],         NORM,        CTR, '0.0'),
            (11, ct['total'],             NORM,        CTR, '0.0'),
            (12, next_val,                NORM,        CTR, next_fmt),
            (13, ct['bank_doc'],          NORM,        CTR, None),
            (14, ct['reference'],         NORM,        LFT, None),
        ]
        for col, val, fnt, aln, fmt in entries:
            c = ws.cell(row, col, val)
            c.font = fnt; c.alignment = aln; c.border = BOX
            if fmt:
                c.number_format = fmt
            if ct['is_ko']:
                c.fill = KO_FILL

        code_prices = price_map_multi.get(ct['code_ref'], {})
        for i, d in enumerate(trading_dates):
            price = code_prices.get(str(d))
            c = ws.cell(row, FIXED + 1 + i, price)
            c.font = NORM; c.alignment = CTR; c.border = BOX
            if price is not None:
                c.number_format = '#,##0.00'
            if ct['is_ko']:
                c.fill = KO_FILL
        row += 1

    return row
```

- [ ] **Step 5: Update the column widths in `_generate_excel`**

In `ltv_app/blueprints/ltv_stocks/views.py`, in `_generate_excel`, replace the width block:
```python
            base_widths = {'A': 26, 'B': 7, 'C': 12, 'D': 10, 'E': 10,
                           'F': 10, 'G': 10, 'H': 11, 'I': 11, 'J': 8, 'K': 8, 'L': 8, 'M': 12}
            for col, w in base_widths.items():
                ws.column_dimensions[col].width = w
            for i in range(len(trading_dates)):
                ws.column_dimensions[get_column_letter(14 + i)].width = 8
```
with:
```python
            base_widths = {'A': 26, 'B': 7, 'C': 12, 'D': 10, 'E': 10, 'F': 10,
                           'G': 11, 'H': 11, 'I': 9, 'J': 9, 'K': 8, 'L': 12, 'M': 12, 'N': 16}
            for col, w in base_widths.items():
                ws.column_dimensions[col].width = w
            for i in range(len(trading_dates)):
                ws.column_dimensions[get_column_letter(15 + i)].width = 8
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: PASS (all tests: the GTD test from Task 1, the reworked count/excel tests, and the new StockContract-parity / listing / next-date / columns tests).

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py ltv_app/blueprints/ltv_stocks/views.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): build Excel ACCU/DECU records from term-sheet StockContract"
```

---

### Task 3: Blocked shares from `StockContract.remaining_shares`

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (`_get_blocked_map`)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Produces: `_get_blocked_map(db) -> {(bank_id, code): blocked_shares}` from the model's `remaining_shares`, excluding KO/zero contracts.

- [ ] **Step 1: Write the failing test**

Append:
```python
def test_blocked_map_uses_remaining_shares(app):
    from ltv_app.blueprints.term_sheet.models import StockContract
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 90, 'DECU', 'active', tenor='2m')   # 1 received period (days 20)
    conn.execute("INSERT INTO tbl_stock_contract_period "
                 "(contract_ref, start_date, end_date, days, received, gtd) "
                 "VALUES (90, '2026-02-01', '2026-02-28', '20', '', '1m')")   # 1 unreceived (days 20)
    conn.commit()

    sc = StockContract(db=conn); sc.get(ref_num=90); sc.as_dict()
    expected = sc.remaining_shares            # remaining_days(20) * daily_shares(1000), not leveraged
    blocked = _get_blocked_map(conn)
    conn.close()

    assert expected > 0
    assert blocked.get(('CB1', '700')) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py::test_blocked_map_uses_remaining_shares -v`
Expected: FAIL — the old `_get_blocked_map` uses `COUNT(p.ref_num)` so `remaining` is 0 and the key is absent (`.get(...)` is `None`).

- [ ] **Step 3: Rewrite `_get_blocked_map`**

Replace the whole `_get_blocked_map` function with:
```python
def _get_blocked_map(db) -> dict:
    """{(bank_id, code): blocked_shares} for active DECUs, from the model's
    remaining_shares (remaining_days * daily_shares * leverage)."""
    from ltv_app.blueprints.term_sheet.models import StockContract

    rows = db.execute(
        "SELECT ref_num FROM tbl_stock_contract "
        "WHERE transaction_type = 'DECU' AND status != 'inactive'"
    ).fetchall()

    result = {}
    for row in rows:
        sc = StockContract(db=db)
        sc.get(ref_num=row['ref_num'])
        try:
            sc.as_dict()
        except AttributeError:
            continue
        if sc.status == 'KO':
            continue
        if not sc.remaining_shares or sc.remaining_shares <= 0:
            continue
        key = (sc.bank_id, sc.code)
        result[key] = result.get(key, 0) + sc.remaining_shares
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "fix(ltv-stocks): blocked shares from StockContract.remaining_shares"
```

---

## Final verification (after all tasks)

- [ ] `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q` → all PASS.
- [ ] Live spot check (server auto-reloads): `/ltv-stocks/`, report date `2026-07-06`, **Download Excel**. On the DBPe sheet confirm the ACCU table lists Alibaba-6/7, China Molybdenum-19, Geely-14, HK Exchange-18, Tencent-8/10 with GTD names; Received/Remaining/Total and Next Date **match `/term-sheet/DBPe`** (Alibaba-6 = 9.5 / 3.5 / 13.0); Contract No. and Reference columns populated; any KO row is red-filled; and the Positions section shows non-zero Blocked shares for active DECUs.

## Self-review

- **Spec coverage:** Req 1 (reuse model) → Task 2 `_load_contracts` + Task 3 `_get_blocked_map`. Req 2 (one table, all non-inactive) → Task 2 SELECT `status != 'inactive'`, single header + rows; `test_active_and_ko_and_done_all_listed`. Req 3 (term-sheet columns) → Task 2 `_xl_contracts` headers + `test_generate_excel_has_reference_and_contract_no_columns`. Req 4 (Next Date DONE/KO/date) → Task 2 `next_date_display`; `test_next_date_done_ko_date`. Req 5 (blocked shares) → Task 3; `test_blocked_map_uses_remaining_shares`. Req 6 (GTD) → Task 1; `test_stock_name_gtd_suffix`. Req 7 (KO fill) → Task 2 `KO_FILL`; asserted structurally via the columns test seeding a KO row.
- **Placeholder scan:** none — every code step shows the full function/edit.
- **Type consistency:** `_load_contracts(db, result, price_map)` (3-arg) defined in Task 2 and used in `get_ltv_stocks_full`; record dict shape (Global Constraints) is produced by `_load_contracts`, consumed by `_xl_contracts`, and mirrored by the `_contract()` test builder. `_stock_name_with_gtd(stock_name, gtd) -> str` defined Task 1, consumed Task 2. `_get_blocked_map(db) -> {(bank_id, code): shares}` matches `_load_positions`' `blocked_map.get((bank, code), 0)` lookup.
