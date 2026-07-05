# LTV Stocks Active Count — Exclude KO Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ACCU/DECU section active-contract count in the downloaded LTV Stocks Excel exclude both DONE and KO contracts, written as a plain integer (not an Excel formula).

**Architecture:** Two edits. `_load_contracts` (data layer) starts reading the contract's stored `status` and exposes an `is_ko` flag. `_xl_contracts` (Excel layer) replaces the `COUNTIF` formula with a plain integer produced by a new pure helper `_active_count(contracts)` that counts contracts that are neither DONE nor KO. KO contracts keep showing their next-month date in column M and stay listed.

**Tech Stack:** Python 3, SQLite (`get_db()` / sqlite3 Row), openpyxl, pytest.

## Global Constraints

- KO is read from the stored value only: `tbl_stock_contract.status == 'KO'`. No price-based KO detection.
- DONE (`remaining == 0`) and KO are mutually exclusive per contract.
- DONE and KO contracts remain listed in the report (not hidden).
- Column M behavior is unchanged: `"DONE"` when `remaining == 0`; otherwise the next-month date (active **and** KO both show a date).
- The count cell must be a plain integer, never an Excel formula.
- Changes apply to `ltv_app/blueprints/ltv_stocks/` only. No schema/data changes. The web view and `legacy_excel_generator.py` are out of scope.

---

## File structure

- `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — `_load_contracts` reads `status`, adds `is_ko`.
- `ltv_app/blueprints/ltv_stocks/views.py` — new `_active_count` helper; `_xl_contracts` writes plain integer count.
- `tests/functional/test_ltv_stocks_active_count.py` — new test file (created in Task 1, extended in Task 2).

---

### Task 1: `_load_contracts` reads status and exposes `is_ko`

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py:50-137` (`_load_contracts`)
- Test: `tests/functional/test_ltv_stocks_active_count.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: each contract dict returned via `result[ccy][bank]['accu'|'decu']` now contains key `is_ko` (bool). Existing key `is_done` (bool) is unchanged. Task 2 relies on `is_done` and `is_ko`.

- [ ] **Step 1: Write the failing test**

Create `tests/functional/test_ltv_stocks_active_count.py`:

```python
"""Active-count / KO handling for the LTV Stocks report."""
import sqlite3

from ltv_app.blueprints.ltv_stocks.create_ltv_stocks import _load_contracts


def _add_contract(conn, ref_num, ttype, status):
    conn.execute(
        "INSERT INTO tbl_stock_contract "
        "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
        " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) "
        "VALUES (?, ?, 1, 1, '2026-01-01', '2026-01-01', ?, 1000, 'No', "
        " 100.0, 95.0, 110.0, '12m', 'monthly', '1m', 'DOC', ?)",
        (ref_num, f"REF{ref_num}", ttype, status),
    )
    # One unreceived period so the contract is not DONE (remaining > 0).
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (?, '2026-01-01', '2026-01-31', '20', '', '1m')",
        (ref_num,),
    )


def test_load_contracts_sets_is_ko(app):
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 10, 'ACCU', 'active')
    _add_contract(conn, 11, 'ACCU', 'KO')
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    accu = result['HKD']['CB1']['accu']
    by_ref = {c['ref_num']: c for c in accu}

    assert by_ref[10]['is_ko'] is False
    assert by_ref[11]['is_ko'] is True
    # KO contract is not DONE and keeps a date in the next-month column.
    assert by_ref[11]['is_done'] is False
    assert by_ref[11]['next_date'] != 'DONE'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/functional/test_ltv_stocks_active_count.py::test_load_contracts_sets_is_ko -v`
Expected: FAIL with `KeyError: 'is_ko'`.

- [ ] **Step 3: Add `c.status` to the SELECT**

In `_load_contracts`, add `c.status` to the selected columns. The SELECT head becomes:

```python
    rows = db.execute("""
        SELECT
            c.ref_num, c.transaction_type, c.bank_doc,
            c.daily_shares, c.spot, c.strike_rate, c.ko_rate,
            c.start_date, c.tenor, c.frequency, c.leveraged, c.status,
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
```

- [ ] **Step 4: Add the `is_ko` flag to the contract dict**

In the `for row in rows:` loop, add this line just before the `contract = { ... }` dict literal (near the other derived values such as `next_date`):

```python
        is_ko = row['status'] == 'KO'
```

Then add one entry inside the `contract = {` dict, next to the existing `'is_done'` entry:

```python
            'is_done':          remaining == 0,
            'is_ko':            is_ko,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/functional/test_ltv_stocks_active_count.py::test_load_contracts_sets_is_ko -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): expose is_ko flag on report contracts"
```

---

### Task 2: Plain-integer active count excluding DONE and KO

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/views.py:156-167` (count block in `_xl_contracts`) and add a module-level helper `_active_count`.
- Test: `tests/functional/test_ltv_stocks_active_count.py` (extend)

**Interfaces:**
- Consumes: contract dicts with keys `is_done` (bool) and `is_ko` (bool) from Task 1.
- Produces: `_active_count(contracts: list[dict]) -> int` — count of contracts where `not is_done and not is_ko`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/functional/test_ltv_stocks_active_count.py`:

```python
from openpyxl import load_workbook

from ltv_app.blueprints.ltv_stocks.views import _active_count, _generate_excel
from datetime import date


def test_active_count_excludes_done_and_ko():
    contracts = [
        {'is_done': False, 'is_ko': False},  # active   -> counted
        {'is_done': True,  'is_ko': False},  # done     -> excluded
        {'is_done': False, 'is_ko': True},   # ko       -> excluded
        {'is_done': False, 'is_ko': False},  # active   -> counted
    ]
    assert _active_count(contracts) == 2
    assert _active_count([]) == 0


def _contract(**overrides):
    base = {
        'stock_name': 'Tencent', 'code': '700', 'code_ref': 1, 'bank_doc': 'DOC',
        'shares_day': '1,000', 'spot_raw': 100.0, 'strike_raw': 95.0, 'ko_raw': 110.0,
        'start_date_raw': date(2026, 1, 1), 'last_end_date_raw': date(2026, 1, 31),
        'received_months': 1.0, 'remaining_months': 11.0, 'total_months': 12,
        'next_date': '2026-08-01', 'is_done': False, 'is_ko': False,
    }
    base.update(overrides)
    return base


def test_generate_excel_count_is_plain_integer():
    accu = [
        _contract(),                    # active
        _contract(is_ko=True),          # ko
        _contract(is_done=True, next_date='DONE'),  # done
    ]
    data = {'HKD': {'CB1': {
        'bank_name': 'Citibank No. 1', 'bank_priority': 1, 'report_label': None,
        'accu': accu, 'decu': [], 'positions': {},
    }}}

    output = _generate_excel(data, date(2026, 7, 2), {}, [])
    wb = load_workbook(output)
    ws = wb['CB1-HKD']

    # ACCU count cell is column A of the section's first row (A3).
    value = ws['A3'].value
    assert value == 1
    assert isinstance(value, int)
    assert not (isinstance(value, str) and str(value).startswith('='))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/functional/test_ltv_stocks_active_count.py -k "active_count or plain_integer" -v`
Expected: FAIL — `ImportError: cannot import name '_active_count'`.

- [ ] **Step 3: Add the `_active_count` helper**

In `ltv_app/blueprints/ltv_stocks/views.py`, add this module-level function just above `_xl_contracts`:

```python
def _active_count(contracts) -> int:
    """Number of contracts that are neither DONE nor KO."""
    return sum(1 for ct in contracts if not ct['is_done'] and not ct['is_ko'])
```

- [ ] **Step 4: Replace the COUNTIF formula with the plain integer**

In `_xl_contracts`, replace the count block (currently lines 156-167):

```python
    # ── Row 1: Active contract count formula (legacy feature) ────────
    if contracts:
        count_row = row
        next_col_start = count_row + 4
        next_col_end = next_col_start + len(contracts) - 1
        formula = f'={len(contracts)}-COUNTIF(M{next_col_start}:M{next_col_end},"*DONE*")'
        c = ws.cell(row, 1, formula)
        c.font = Font(name='Arial', size=7, bold=False)
        c.number_format = '0'
        c.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[row].height = 10.5
        row += 1
```

with:

```python
    # ── Row 1: Active contract count (excludes DONE and KO) ──────────
    if contracts:
        c = ws.cell(row, 1, _active_count(contracts))
        c.font = Font(name='Arial', size=7, bold=False)
        c.number_format = '0'
        c.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[row].height = 10.5
        row += 1
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/functional/test_ltv_stocks_active_count.py -v`
Expected: PASS (all tests, including Task 1's).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/views.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): count active contracts excluding DONE and KO as plain integer"
```

---

## Manual verification (after both tasks)

1. Start the app: `! python flask_app.py`
2. Log in, open `/ltv-stocks/`, pick a report date, click **Download Excel**.
3. On a bank sheet with contracts, confirm:
   - The ACCU count cell (A3) and the DECU count cell are plain integers equal to the number of contracts that are neither DONE nor KO.
   - A `status='KO'` contract still shows its next-month **date** in column M and remains listed.
   - A DONE contract still shows `"DONE"` and remains listed.

## Self-review

- **Spec coverage:** Req 1 (exclude DONE+KO) → Task 2 `_active_count`. Req 2 (plain integer, no formula) → Task 2 Step 4 + `test_generate_excel_count_is_plain_integer`. Req 3 (DONE/KO stay listed) → unchanged listing logic; asserted indirectly (contracts remain in `accu`). Req 4 (column M unchanged, KO shows date) → Task 1 test asserts `next_date != 'DONE'` for KO; no change to M rendering. Both ACCU+DECU → shared `_xl_contracts`.
- **Placeholder scan:** none.
- **Type consistency:** `is_ko` (bool) produced in Task 1, consumed in Task 2; `_active_count(list[dict]) -> int` consistent across helper, call site, and tests.
