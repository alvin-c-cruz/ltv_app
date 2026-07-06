# LTV Stocks — Exact Legacy Replica Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ltv_app`'s `/ltv-stocks/download` produce a workbook byte-equivalent (over the printed `A1:X` area) to the legacy `localhost/modules/ltv_stocks2.py` output, by porting the legacy calculators natively and rebuilding the Excel writer. Validated against the golden file `localhost/excel_files/LTV_Stocks/2026-07-06 LTV Stocks.xlsx`.

**Architecture:** New subpackage `ltv_app/blueprints/ltv_stocks/legacy_port/` holds the ported calculators and writer. Six phases, each a TDD deliverable: (1) working-day/price helpers, (2) contract calculator, (3) positions calculator, (4) writer — contracts, (5) writer — positions + workbook, (6) route wiring + golden-file acceptance. The divergent `create_ltv_stocks.py` and truncated `extensions/legacy_excel_generator.py` are removed in Phase 6.

**Tech Stack:** Python 3, SQLite (`sqlite3.Row`), openpyxl, pytest.

## Global Constraints

- Read-only (SELECT only). No schema/data changes. **No `localhost/` import at runtime.**
- All DB access via `get_db()` (`ltv_app/blueprints/database/views.py`). Tests may use `sqlite3.connect` on `app.config['DATABASE']` (existing pattern).
- **Exact legacy parity is the acceptance bar.** The Phase 6 golden-file test compares the new output cell-by-cell (values, formulas, number formats) against `localhost/excel_files/LTV_Stocks/2026-07-06 LTV Stocks.xlsx` over each `{bank}-{ccy}` sheet's `A1:X` range. Any diff there is a bug.
- Ported algorithms must match the legacy exactly — see the per-phase specs, which transcribe `localhost/modules/term_sheet.py`, `transaction_list.py`, and `ltv_stocks2.py`.
- Out of scope (do NOT implement): AA–AJ per-day status columns; off-print helper columns (contract `Z`/`AK`, positions `Y–AC`).
- `tbl_holiday` columns: `ref_num, ccy_ref, holi_date` (ISO string). Join `ccy_ref → tbl_currency.ref_num` for `ccy_id`.
- Test seed data (`tests/functional/conftest.py`): bank `ref_num=1`="Citibank No. 1" (`bank_id='CB1'`), code `ref_num=1`=code "700" "Tencent Holdings Limited", currency HKD, plus the `_add_contract` helper in `tests/functional/test_ltv_stocks_active_count.py`.

## File structure

```
ltv_app/blueprints/ltv_stocks/legacy_port/
├── __init__.py
├── working_day.py     # WorkingDay: is_holiday / next_day / previous_day / count_days  (Phase 1)
├── stock_price.py     # get_stock_price(db, code_ref, date) over tbl_stock_price        (Phase 1)
├── term_sheet_calc.py # ContractSchedule + contract_records()  (port of term_sheet.py)  (Phase 2)
├── positions_calc.py  # position_records() (port of stock_position + blocked_shares)     (Phase 3)
└── excel_writer.py    # build_workbook() -> BytesIO (port of ltv_stocks2 writer)         (Phases 4-5)
```
Tests: `tests/functional/test_ltv_stocks_legacy_*.py` (one per phase) + `tests/functional/test_ltv_stocks_golden.py` (Phase 6).

---

### Task 1: Working-day + stock-price helpers

**Files:**
- Create: `ltv_app/blueprints/ltv_stocks/legacy_port/__init__.py` (empty), `working_day.py`, `stock_price.py`
- Test: `tests/functional/test_ltv_stocks_legacy_helpers.py`

**Interfaces:**
- Produces: `WorkingDay(db, ccy_id)` with `.is_holiday(d: date) -> bool`, `.next_day(d) -> date`, `.previous_day(d) -> date`, `.count_days(start: date, end: date) -> int` (inclusive weekday/non-holiday count); `get_stock_price(db, code_ref, d) -> float | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/functional/test_ltv_stocks_legacy_helpers.py`:
```python
import sqlite3
from datetime import date
from ltv_app.blueprints.ltv_stocks.legacy_port.working_day import WorkingDay
from ltv_app.blueprints.ltv_stocks.legacy_port.stock_price import get_stock_price


def test_next_and_previous_skip_weekends(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    wd = WorkingDay(conn, 'HKD')
    # 2026-07-03 is a Friday -> next working day is Monday 2026-07-06
    assert wd.next_day(date(2026, 7, 3)) == date(2026, 7, 6)
    # previous working day before Monday 2026-07-06 is Friday 2026-07-03
    assert wd.previous_day(date(2026, 7, 6)) == date(2026, 7, 3)
    conn.close()


def test_next_day_skips_holiday(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    # seed HKD (ccy_ref=1) holiday on Monday 2026-07-06
    conn.execute("INSERT INTO tbl_holiday (ccy_ref, holi_date) VALUES (1, '2026-07-06')")
    conn.commit()
    wd = WorkingDay(conn, 'HKD')
    assert wd.next_day(date(2026, 7, 3)) == date(2026, 7, 7)   # skips Fri->Mon(holiday)->Tue
    conn.close()


def test_count_days_inclusive_weekdays(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    wd = WorkingDay(conn, 'HKD')
    # Mon 2026-07-06 .. Fri 2026-07-10 inclusive = 5 weekdays
    assert wd.count_days(date(2026, 7, 6), date(2026, 7, 10)) == 5
    conn.close()


def test_get_stock_price_returns_close_or_none(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO tbl_stock_price (code_ref, trade_date, closing_price) "
                 "VALUES (1, '2026-07-06', 431.2)")
    conn.commit()
    assert get_stock_price(conn, 1, date(2026, 7, 6)) == 431.2
    assert get_stock_price(conn, 1, date(2026, 7, 7)) is None
    conn.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/functional/test_ltv_stocks_legacy_helpers.py -q`
Expected: FAIL — `ModuleNotFoundError: ...legacy_port.working_day`.

- [ ] **Step 3: Implement the helpers**

Create `ltv_app/blueprints/ltv_stocks/legacy_port/__init__.py` (empty file).

Create `ltv_app/blueprints/ltv_stocks/legacy_port/working_day.py`:
```python
from datetime import date, timedelta


class WorkingDay:
    """Holiday-aware working-day helper for one currency, backed by tbl_holiday.
    Ports localhost/modules/working_day.py against get_db()-style connections."""

    def __init__(self, db, ccy_id):
        rows = db.execute(
            "SELECT h.holi_date FROM tbl_holiday h "
            "INNER JOIN tbl_currency c ON c.ref_num = h.ccy_ref "
            "WHERE c.ccy_id = ?", (ccy_id,)
        ).fetchall()
        self._holidays = {str(r[0])[:10] for r in rows}

    def is_holiday(self, d: date) -> bool:
        return d.weekday() >= 5 or d.isoformat() in self._holidays

    def next_day(self, d: date) -> date:
        d = d + timedelta(days=1)
        while self.is_holiday(d):
            d = d + timedelta(days=1)
        return d

    def previous_day(self, d: date) -> date:
        d = d - timedelta(days=1)
        while self.is_holiday(d):
            d = d - timedelta(days=1)
        return d

    def count_days(self, start: date, end: date) -> int:
        """Inclusive count of weekday, non-holiday dates from start to end."""
        n, d = 0, start
        while d <= end:
            if not self.is_holiday(d):
                n += 1
            d = d + timedelta(days=1)
        return n
```

Create `ltv_app/blueprints/ltv_stocks/legacy_port/stock_price.py`:
```python
from datetime import date


def get_stock_price(db, code_ref, d):
    """Closing price for (code_ref, date), or None. Ports get_stock_price."""
    ds = d.isoformat() if isinstance(d, date) else str(d)[:10]
    row = db.execute(
        "SELECT closing_price FROM tbl_stock_price WHERE code_ref = ? AND trade_date = ?",
        (code_ref, ds)
    ).fetchone()
    return row[0] if row else None
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_legacy_helpers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/legacy_port/ tests/functional/test_ltv_stocks_legacy_helpers.py
git commit -m "feat(ltv-stocks): working-day + stock-price helpers for legacy port"
```

---

### Task 2: Contract calculator (`term_sheet_calc.py`)

Port of `term_sheet` (schedule) + `summary_ts_raw` (record). Reference: `localhost/modules/term_sheet.py` lines 33–162 (header/schedule/footer) and 338–447 (`summary_ts_raw`).

**Files:**
- Create: `ltv_app/blueprints/ltv_stocks/legacy_port/term_sheet_calc.py`
- Test: `tests/functional/test_ltv_stocks_legacy_contracts.py`

**Interfaces:**
- Consumes: `WorkingDay` (Task 1).
- Produces: `contract_records(db, bank_ref, transaction_type) -> list[dict]` — one dict per non-inactive contract of that type for the bank, DB-insertion order, with keys: `ref_num, reference, bank_doc, frequency, stock_name, code, code_ref, yahoo_ticker, shares, spot, strike, ko, start_date` (date), `end_date` (date), `total` (float), `received` (float), `next_date` (date|None), `remaining` (float), `ccy_id`, `daily_shares`, `leveraged`, `indicative`, `status`.

- [ ] **Step 1: Write the failing tests**

Create `tests/functional/test_ltv_stocks_legacy_contracts.py`:
```python
import sqlite3
from datetime import date
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records


def _contract(conn, ref, ttype, *, frequency='monthly', gtd='1m', leveraged='No',
              daily=1000, spot=100.0, strike_rate=95.0, ko_rate=110.0, status='active',
              start='2026-01-01'):
    conn.execute(
        "INSERT INTO tbl_stock_contract (ref_num, reference, bank_ref, code_ref, trade_date, "
        " start_date, transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) VALUES (?,?,1,1,?,?,?,?,?,?,?,?, '12m',?,?, 'DOC',?)",
        (ref, f'REF{ref}', start, start, ttype, daily, leveraged, spot, strike_rate, ko_rate,
         frequency, gtd, status))


def _period(conn, ref, end_date, received, days='20'):
    conn.execute("INSERT INTO tbl_stock_contract_period "
                 "(contract_ref, start_date, end_date, days, received, gtd) "
                 "VALUES (?, '2026-01-01', ?, ?, ?, '1m')", (ref, end_date, days, received))


def test_received_breaks_on_first_empty(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 10, 'ACCU', frequency='monthly')
    _period(conn, 10, '2026-01-31', '1000')   # filled
    _period(conn, 10, '2026-02-28', '1000')   # filled
    _period(conn, 10, '2026-03-31', '')       # EMPTY -> break here
    _period(conn, 10, '2026-04-30', '1000')   # filled but AFTER the gap -> not counted
    conn.commit()
    rec = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}[10]
    conn.close()
    assert rec['total'] == 4          # monthly: 4 period rows
    assert rec['received'] == 2       # consecutive filled before first empty
    assert rec['remaining'] == 2
    assert rec['next_date'] is not None   # next working day after 2026-03-31


def test_total_divides_by_frequency(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 11, 'ACCU', frequency='bi-monthly')
    _period(conn, 11, '2026-01-15', '1000'); _period(conn, 11, '2026-01-31', '1000')
    _period(conn, 11, '2026-02-15', '')
    conn.commit()
    rec = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}[11]
    conn.close()
    assert rec['total'] == 1.5        # 3 periods / 2
    assert rec['received'] == 1.0     # 2 filled * 0.5


def test_all_filled_is_done(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 12, 'ACCU', frequency='monthly')
    _period(conn, 12, '2026-01-31', '1000')
    conn.commit()
    rec = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}[12]
    conn.close()
    assert rec['received'] == rec['total'] == 1
    assert rec['next_date'] is None    # never hit an empty period


def test_gtd_suffix(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 13, 'ACCU', gtd='No');  _period(conn, 13, '2026-01-31', '')
    _contract(conn, 14, 'ACCU', gtd='Yes'); _period(conn, 14, '2026-01-31', '')
    _contract(conn, 15, 'ACCU', gtd='3m');  _period(conn, 15, '2026-01-31', '')
    conn.commit()
    recs = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}
    conn.close()
    assert recs[13]['stock_name'].endswith('NO GTD')
    assert recs[14]['stock_name'].endswith('GTD 1m')
    assert recs[15]['stock_name'].endswith('GTD 3m')


def test_no_periods_skipped(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 16, 'ACCU'); conn.commit()   # no periods
    recs = {r['ref_num'] for r in contract_records(conn, 1, 'ACCU')}
    conn.close()
    assert 16 not in recs
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/functional/test_ltv_stocks_legacy_contracts.py -q`
Expected: FAIL — module/function missing.

- [ ] **Step 3: Implement `term_sheet_calc.py`**

Create the module. Transcribe the legacy exactly:
```python
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


def _schedule(db, header, wd):
    """1-indexed dict of period dicts (end_date str, days int, received raw, total_shares int)."""
    rows = db.execute(
        "SELECT start_date, end_date, days, received, gtd FROM tbl_stock_contract_period "
        "WHERE contract_ref = ?", (header['ref_num'] if 'ref_num' in header.keys() else None,)
    ).fetchall()
    # NOTE: header has no ref_num; caller passes contract_ref separately (see contract_records).
    return rows


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
```
(Delete the unused `_schedule` stub above — it was a scratch note; the real schedule build is inline in `contract_records`.)

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_legacy_contracts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/legacy_port/term_sheet_calc.py tests/functional/test_ltv_stocks_legacy_contracts.py
git commit -m "feat(ltv-stocks): port contract calculator (summary_ts_raw)"
```

---

### Task 3: Positions calculator (`positions_calc.py`)

Port of `stock_balance.stock_position` + `blocked_shares` (`transaction_list.py` 176–283) and the day's transaction narrative. Reference the exact blocking rules in the spec §3.

**Files:**
- Create: `ltv_app/blueprints/ltv_stocks/legacy_port/positions_calc.py`
- Test: `tests/functional/test_ltv_stocks_legacy_positions.py`

**Interfaces:**
- Consumes: `WorkingDay` (Task 1), `contract_records`/`_schedule` building logic (reuse the period-schedule builder from Task 2 — extract a shared `build_schedule(db, contract_ref, wd)` helper in `term_sheet_calc.py` and import it here).
- Produces: `position_records(db, bank_ref, bank_id, ccy_id, report_date) -> dict[code] = {stock_name, code, code_ref, yahoo_ticker, balance, blocked, unblocked, average, transactions}` sorted by code.

- [ ] **Step 1: Write the failing test** — covers: balance from transactions, blocked = future-period total_shares of active DECUs, `end_date > cutoff` (cutoff = previous working day unless indicative), cap at balance, unblocked = balance − blocked. (Seed a code with a share balance and an active DECU with one future period; assert blocked equals that period's `total_shares`, capped at balance.)

```python
import sqlite3
from datetime import date
from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import position_records
# ... seed tbl_transaction (balance), an active DECU contract + a future-dated period,
#     then assert blocked == days*daily_shares (x2 if leveraged), capped at balance,
#     and unblocked == max(0, balance - blocked). (Full seeding mirrors the _contract/_period
#     helpers from Task 2; assert the cutoff excludes past periods.)
```
*(The implementer writes the concrete seeding following the Task 2 helpers; assertions per spec §3.)*

- [ ] **Step 2-5:** Run→fail, implement `position_records` (DECU-only, `status='active'` contracts for the code+bank via a `status='active'` SELECT; cutoff = `report_date` if `indicative=='YES'` else `wd.previous_day(report_date)`, compared as ISO strings; sum `total_shares` for periods with `end_date > cutoff`; cap at balance; average via `cost_to_date/balance` formula string), run→pass, commit `feat(ltv-stocks): port positions + blocked-shares calculator`.

---

### Task 4: Excel writer — contract tables (`excel_writer.py`)

Transcribe `ltv_stocks2.contract()` (`localhost/modules/ltv_stocks2.py` lines 410–709) cell-for-cell, **excluding AA–AJ and the `Z`/`AK` helper columns**. Use the exact cell map in the design spec's "Excel writer" section (headers, `K=L−J`, `N`=next_date/"DONE", O–X grid with grey-fill/'Done'/INDEX-MATCH, count-cell `COUNTIF` formula, code fills, hidden C/M).

**Files:**
- Create: `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`
- Test: `tests/functional/test_ltv_stocks_legacy_writer.py`

**Interfaces:**
- Consumes: `contract_records` (Task 2), `get_stock_price`, `WorkingDay`.
- Produces: `_write_contracts(ws, records, product, row, report_date, date_range, price_map, wd) -> int` (next row), plus module constants (fonts/fills/borders) and the 10-date range builder `week_dates(report_date)` using **`isoweekday()`**: `start = report_date - timedelta(days=6+report_date.isoweekday())`, dates `[start, +1..+4, +7..+11]`.

- [ ] **Step 1: Write the failing test** — build a worksheet in-memory, feed 2 contract records (one active, one all-filled→DONE), assert: header labels present (`ACCUMULATOR`, `RCVD mos.`, `NEXT MO.`), `K{r}` == `=L{r}-J{r}`, the DONE row's `N` == `'DONE'`, the active row's `N` is a date, the count cell == `=2-COUNTIF(N..,"*DONE*")`, and column C/M are hidden (`ws.column_dimensions['C'].hidden`).

- [ ] **Step 2-5:** Run→fail, implement `_write_contracts` + `week_dates` + style constants transcribing the legacy cell map (dropping AA–AJ/`Z`/`AK`), run→pass, commit `feat(ltv-stocks): port Excel writer — contract tables`.

*Note to implementer:* keep `start_date`/`end_date` as `date` objects so the O–X `date_range[k] < start_date` / `> end_date` comparisons and the grey-fill/'Done' boundary logic (spec §"O–X closing grid") work. The report-date cell (ccy≠USD) is the `INDEX/MATCH` formula; other dates use `get_stock_price` literals.

---

### Task 5: Excel writer — positions, workbook assembly, cross-sheet totals

Transcribe `ltv_stocks2.position()` (712–914, excluding `Y–AC`), `create()` (211–295), `report_header()` (342–407), `column_width()` (298–339). Reference spec §"Excel writer".

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`
- Test: `tests/functional/test_ltv_stocks_legacy_writer.py` (extend)

**Interfaces:**
- Consumes: `position_records` (Task 3), `_write_contracts` (Task 4).
- Produces: `build_workbook(db, report_date, bank_ids) -> io.BytesIO` — the full multi-sheet workbook: empty `closing_price`/`record` sheets first; one `{bank}-{ccy}` sheet per bank×ccy in `['HKD','SGD']` skipped when it has no ACCU/DECU/position; `report_header`; ACCU then DECU via `_write_contracts`; positions via `_write_positions`; hidden C/M; `print_area='A1:X{n}'`; then the cross-sheet `=SUM('{bank}-HKD'!{cell}, …)` ACCU/DECU totals written into the `DBPe-HKD` sheet.

- [ ] **Step 1: Write the failing test** — `build_workbook` for a seeded bank produces a workbook whose sheet names include `closing_price`, `record`, and `CB1-HKD`; the positions block has `G{r}` == `=D{r}+E{r}` and `J{r}` == `=(L{r}/I{r})-1` and `L{r}` an INDEX/MATCH formula; hidden C.

- [ ] **Step 2-5:** Run→fail, implement `_write_positions` + `build_workbook` + `report_header`/`column_width`, run→pass, commit `feat(ltv-stocks): port Excel writer — positions + workbook assembly`.

---

### Task 6: Wire the route, remove divergent code, golden-file acceptance

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/views.py` (`download` route)
- Delete: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`, `ltv_app/blueprints/ltv_stocks/extensions/legacy_excel_generator.py`
- Modify/Delete: `tests/functional/test_ltv_stocks_active_count.py` (asserts the removed divergent `_load_contracts`; delete it — its behavior is replaced by the legacy_port tests)
- Test: `tests/functional/test_ltv_stocks_golden.py`

**Interfaces:**
- Consumes: `build_workbook` (Task 5).
- Produces: `download` returns the `build_workbook` BytesIO.

- [ ] **Step 1: Write the golden-file acceptance test**

Create `tests/functional/test_ltv_stocks_golden.py`. It compares the new output against the legacy golden file over `A1:X` of each shared sheet. Because the golden file was generated against the **live** DB, this test runs against the live DB (guarded to skip if the golden file or live DB is absent):
```python
import os
from datetime import date
import pytest
from openpyxl import load_workbook

GOLDEN = r"localhost/excel_files/LTV_Stocks/2026-07-06 LTV Stocks.xlsx"
LIVE_DB = r"instance/LTV Stocks.db"

pytestmark = pytest.mark.skipif(
    not (os.path.exists(GOLDEN) and os.path.exists(LIVE_DB)),
    reason="golden file or live DB not present")


def _cells(ws, max_col=24, max_row=None):
    out = {}
    for r in range(1, (max_row or ws.max_row) + 1):
        for c in range(1, max_col + 1):
            v = ws.cell(r, c).value
            if v is not None:
                out[(r, c)] = v
    return out


def test_dbpe_hkd_matches_golden():
    import sqlite3
    from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import build_workbook
    db = sqlite3.connect(LIVE_DB); db.row_factory = sqlite3.Row
    out = build_workbook(db, date(2026, 7, 6),
                         ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG'])
    db.close()
    got = load_workbook(out)
    exp = load_workbook(GOLDEN)
    gws, ews = got['DBPe-HKD'], exp['DBPe-HKD']
    diffs = []
    for (r, c), ev in _cells(ews).items():
        gv = gws.cell(r, c).value
        if str(gv) != str(ev):
            diffs.append((gws.cell(r, c).coordinate, gv, ev))
    assert not diffs, f"{len(diffs)} cell diffs, first 10: {diffs[:10]}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/functional/test_ltv_stocks_golden.py -q`
Expected: FAIL — the `download` route / `build_workbook` output differs from the golden file (or `build_workbook` not yet wired). Use the diff list to close remaining gaps (holidays, price literals, ordering) until zero diffs over `A1:X`.

- [ ] **Step 3: Iterate `build_workbook` to zero diffs**

Fix each reported cell diff (common causes: `isoweekday` week range, price literals from `tbl_stock_price`, insertion-order of contracts, number formats). The empty `closing_price` sheet means the report-date price cell is a formula on both sides — compare formula strings, not resolved values.

- [ ] **Step 4: Wire the route and remove divergent code**

In `ltv_app/blueprints/ltv_stocks/views.py`, change `download` to:
```python
    from .legacy_port.excel_writer import build_workbook
    output = build_workbook(get_db(), report_date,
                            ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG'])
```
Remove `get_ltv_stocks_full`/`_generate_excel` usage. Delete `create_ltv_stocks.py` and `extensions/legacy_excel_generator.py` and delete `tests/functional/test_ltv_stocks_active_count.py`. Fix any imports left dangling in `views.py` (the web `home` route uses `get_ltv_stocks` for positions — replace its data source with `position_records` or leave the web page's `data` empty, since the page only toggles the Download button).

- [ ] **Step 5: Full suite + live spot check**

Run: `python -m pytest tests/functional/ -q` → the legacy_port suites pass; golden test passes; no import errors.
Then live: `/ltv-stocks/`, report date `2026-07-06`, Download — open and confirm it visually matches the legacy `2026-07-06 LTV Stocks.xlsx` (7 ACCU with GTD names + RCVD/REM/Total, DECU, positions with blocked shares).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(ltv-stocks): serve exact legacy replica; remove divergent generator"
```

---

## Self-review

- **Spec coverage:** Calculators §1–2 → Task 2; §3 → Task 3; helpers → Task 1; writer (contracts) → Task 4; writer (positions/workbook/totals) → Task 5; route + removal + golden acceptance → Task 6. Dropped AA–AJ / off-print helpers honored in Tasks 4–5. Golden-file verification → Task 6.
- **Placeholder scan:** Tasks 1, 2, 4, 5, 6 have complete code or exact cell-map references + concrete tests. Task 3's seeding is described against the Task 2 helpers (kept prose to avoid duplicating a large fixture) — the implementer writes it from spec §3; acceptable because the golden test (Task 6) is the hard gate.
- **Type consistency:** `WorkingDay`/`get_stock_price` (Task 1) used in Tasks 2–5; `contract_records(db, bank_ref, ttype) -> list[dict]` (Task 2) consumed by Task 4 and Task 6; `position_records(...) -> dict` (Task 3) consumed by Task 5; `build_workbook(db, report_date, bank_ids) -> BytesIO` (Task 5) consumed by Task 6. `start_date`/`end_date` are `date` objects throughout (required by the O–X comparisons).
- **Risk note:** the exactness bar lives in Task 6's golden diff; Tasks 2–5 unit tests catch algorithm errors early, but the byte-parity gate is the golden test. Expect an iterate loop in Task 6 Step 3.
