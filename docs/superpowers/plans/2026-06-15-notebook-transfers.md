# Notebook Transfer of Stocks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Append a "Transfer of Stocks" section to the daily notebook Excel output, showing each Transfer-Out / Transfer-In pair as one numbered entry with a two-column before/after balance display.

**Architecture:** Add `get_transfers()` to the data layer (`transactions.py`), add `_opening_balance()` + `write_transfers()` to `CreateNotebook` (`create_notebook.py`), then wire both into `views.py`. No schema changes, no new files, no template changes.

**Tech Stack:** Python 3, Flask, SQLite, openpyxl

---

## File Map

| File | Change |
|------|--------|
| `ltv_app/blueprints/notebook/extensions/transactions.py` | Add `TRANSFER_SQL` + `get_transfers()` |
| `ltv_app/blueprints/notebook/extensions/create_notebook.py` | Add `transfers` param to `__init__`, add `_opening_balance()` + `write_transfers()`, call in `create_file()` |
| `ltv_app/blueprints/notebook/extensions/__init__.py` | Export `get_transfers` |
| `ltv_app/blueprints/notebook/views.py` | Import + call `get_transfers`, pass to `CreateNotebook` |
| `tests/functional/test_notebook_transfers.py` | New test file for `get_transfers()` |

---

## Task 1: Data layer — `get_transfers()` in `transactions.py`

**Files:**
- Modify: `ltv_app/blueprints/notebook/extensions/transactions.py`
- Create: `tests/functional/test_notebook_transfers.py`

- [x] **Step 1: Create the test file**

```python
# tests/functional/test_notebook_transfers.py
import pytest
from ltv_app.blueprints.notebook.extensions.transactions import get_transfers


def test_get_transfers_returns_pair(db_conn):
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')

    assert len(result) == 1
    assert result[0]['out_bank']   == 'Citibank No. 1'
    assert result[0]['in_bank']    == 'Citibank No. 2'
    assert result[0]['quantity']   == 500
    assert result[0]['code']       == '700'
    assert result[0]['stock_name'] == 'Tencent Holdings Limited'
    assert result[0]['ccy_id']     == 'HKD'


def test_get_transfers_empty_when_no_transfers(db_conn):
    result = get_transfers(db_conn, '2026-05-18')
    assert result == []


def test_get_transfers_ignores_other_dates(db_conn):
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-17',NULL,'2026-05-19',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-17',NULL,'2026-05-19',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')
    assert result == []


def test_get_transfers_no_duplicate_for_identical_same_day_pairs(db_conn):
    # Two identical transfers (same stock/qty/date/banks) on one day.
    # Driving off Transfer-Out yields exactly one row per Transfer-Out (2),
    # never a fan-out from matching both Transfer-In rows (would be 4).
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(12,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(13,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')

    assert len(result) == 2
    assert {r['out_ref'] for r in result} == {10, 12}


def test_get_transfers_includes_pair_with_mismatched_partner(db_conn):
    # A Transfer-Out whose Transfer-In partner differs (here: no partner row at
    # all). It must still appear — the destination bank comes from
    # counter_bank_ref, so unmatched partners are never silently dropped.
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')

    assert len(result) == 1
    assert result[0]['out_bank'] == 'Citibank No. 1'
    assert result[0]['in_bank']  == 'Citibank No. 2'
```

- [x] **Step 2: Run tests to confirm they fail**

```
pytest tests/functional/test_notebook_transfers.py -v
```

Expected: `ImportError` or `AttributeError` — `get_transfers` does not exist yet.

- [x] **Step 3: Add `TRANSFER_SQL` and `get_transfers()` to `transactions.py`**

Append after the existing `get_transactions()` function in `ltv_app/blueprints/notebook/extensions/transactions.py`:

```python
TRANSFER_SQL = """
    SELECT
        out_t.ref_num       AS out_ref,
        out_bank.bank_name  AS out_bank,
        out_bank.bank_id    AS out_bank_id,
        in_bank.bank_name   AS in_bank,
        in_bank.bank_id     AS in_bank_id,
        C.stock_name,
        C.code,
        CY.ccy_id,
        ABS(out_t.quantity) AS quantity
    FROM tbl_transaction out_t
    INNER JOIN tbl_bank_account out_bank ON out_bank.ref_num = out_t.bank_ref
    INNER JOIN tbl_bank_account in_bank  ON in_bank.ref_num  = out_t.counter_bank_ref
    INNER JOIN tbl_code C      ON C.ref_num  = out_t.code_ref
    INNER JOIN tbl_currency CY ON CY.ref_num = C.ccy_ref
    WHERE out_t.transaction_type = 'Transfer-Out'
      AND out_t.counter_bank_ref IS NOT NULL
      AND out_t.trade_date = ?
    ORDER BY C.code, out_t.ref_num
"""


def get_transfers(db, trade_date):
    rows = db.execute(TRANSFER_SQL, (trade_date,)).fetchall()
    return [dict(r) for r in rows]
```

> **Why no self-join to the Transfer-In row?** The destination bank is reachable
> directly via `out_t.counter_bank_ref → tbl_bank_account`, so each Transfer-Out
> yields exactly one row. Joining the matching `Transfer-In` row on
> `(qty, date, code, bank)` instead (1) **double-counts** when two identical
> transfers occur the same day — verified on live data: out_ref 132 (55,000 HSBC,
> same banks/date) matches two Transfer-In rows and renders twice — and
> (2) **silently drops** transfers whose partner row differs in qty/date
> (5 such rows in live history). Driving off Transfer-Out alone shows every
> transfer once. `write_transfers()` only consumes `in_bank`/`in_bank_id`, never
> the in-row's `ref_num`, so nothing downstream needs the join.

- [x] **Step 4: Run tests — all five must pass**

```
pytest tests/functional/test_notebook_transfers.py -v
```

Expected: 5 PASSED.

- [x] **Step 5: Commit**

```
git add ltv_app/blueprints/notebook/extensions/transactions.py tests/functional/test_notebook_transfers.py
git commit -m "Add get_transfers() to notebook data layer"
```

---

## Task 2: Rendering — `write_transfers()` in `create_notebook.py`

**Files:**
- Modify: `ltv_app/blueprints/notebook/extensions/create_notebook.py`

Context: `create_notebook.py` lives at `ltv_app/blueprints/notebook/extensions/create_notebook.py`. It already imports `Font`, `Alignment`, `Border`, `Side` from openpyxl. It has a module-level `border_line(ws, row_num)` function that applies thin grey (`color='00C0C0C0'`) top+bottom borders to all columns A–Q. `ROW_HEIGHT = 17.25` is a module-level constant. `TradesDoneAverage` is already imported at the top.

- [x] **Step 6: Update `__init__` to accept `transfers`, add `_opening_balance()` helper, update `create_file()`, add `write_transfers()`**

Replace the `CreateNotebook` class body entirely. The diff is:

**`__init__`** — add `transfers` parameter:
```python
def __init__(self, db, trade_date, transactions, transfers):
    self.db           = db
    self.trade_date   = trade_date
    self.transactions = transactions
    self.transfers    = transfers

    self.template_file = os.path.join(current_app.instance_path, "excel_templates", "notebook.xlsx")
    self.filename      = os.path.join(current_app.instance_path, "temp", f"{trade_date} notebook.xlsx")

    self.create_file()
```

**`create_file()`** — call `write_transfers()` between `write_transactions()` and save:
```python
def create_file(self):
    wb = load_workbook(self.template_file)
    ws = wb["notebook"]

    self.write_date(ws)
    self.write_stock_card(ws)
    row_num = self.write_transactions(ws=ws, row_num=ROW_NUM_START)
    row_num = self.write_transfers(ws, row_num)

    ws.print_area = f"A1:Q{row_num}"

    wb.save(self.filename)
    wb.close()
```

**New `_opening_balance()` method** — add before `write_line()`:
```python
def _opening_balance(self, bank_name, code):
    row = self.db.execute(
        "SELECT SUM(tbl_transaction.quantity) AS balance "
        "FROM tbl_transaction "
        "INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_transaction.bank_ref "
        "INNER JOIN tbl_code ON tbl_code.ref_num = tbl_transaction.code_ref "
        "WHERE tbl_bank_account.bank_name = ? "
        "  AND tbl_code.code = ? "
        "  AND tbl_transaction.trade_date < ?",
        (bank_name, code, self.trade_date)
    ).fetchone()
    try:
        return int(row[0]) if row and row[0] is not None else 0
    except (TypeError, IndexError):
        return 0
```

**New `write_transfers()` method** — add before `write_line()`:
```python
def write_transfers(self, ws, row_num):
    if not self.transfers:
        return row_num

    # Section header: C:P merged
    border_line(ws, row_num)
    cell = ws[f"C{row_num}"]
    cell.value     = "Transfer of Stocks"
    cell.font      = Font(size=13, bold=True)
    cell.alignment = Alignment(horizontal="center")
    ws.merge_cells(f"C{row_num}:P{row_num}")
    ws.row_dimensions[row_num].height = ROW_HEIGHT
    row_num += 1

    counter = 1
    for pair in self.transfers:
        out_bank   = pair['out_bank']
        in_bank    = pair['in_bank']
        in_bank_id = pair['in_bank_id']
        stock_name = pair['stock_name']
        code       = pair['code']
        qty        = int(pair['quantity'])

        opening_out = self._opening_balance(out_bank, code)
        opening_in  = self._opening_balance(in_bank,  code)
        closing_out = opening_out - qty
        closing_in  = opening_in  + qty

        # Row 1: counter + title
        border_line(ws, row_num)
        ws[f"B{row_num}"].value         = counter
        ws[f"B{row_num}"].font          = Font(size=13)
        ws[f"B{row_num}"].number_format = "0\\)"
        ws[f"C{row_num}"].value         = f"Transfer {stock_name} ({code})"
        ws[f"C{row_num}"].font          = Font(size=13)
        ws[f"C{row_num}"].alignment     = Alignment(horizontal="left")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 2: from
        border_line(ws, row_num)
        ws[f"C{row_num}"].value     = f"from {out_bank}"
        ws[f"C{row_num}"].font      = Font(size=13)
        ws[f"C{row_num}"].alignment = Alignment(horizontal="left")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 3: to
        border_line(ws, row_num)
        ws[f"C{row_num}"].value     = f"to {in_bank}"
        ws[f"C{row_num}"].font      = Font(size=13)
        ws[f"C{row_num}"].alignment = Alignment(horizontal="left")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 4: quantity in shares
        border_line(ws, row_num)
        ws[f"C{row_num}"].value     = f"{qty:,} shares"
        ws[f"C{row_num}"].font      = Font(size=13)
        ws[f"C{row_num}"].alignment = Alignment(horizontal="left")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 5: bank name headers
        border_line(ws, row_num)
        ws[f"C{row_num}"].value = out_bank
        ws[f"C{row_num}"].font  = Font(size=12)
        ws[f"K{row_num}"].value = in_bank
        ws[f"K{row_num}"].font  = Font(size=12)
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 6: opening balances
        border_line(ws, row_num)
        cell = ws[f"E{row_num}"]
        cell.value         = opening_out
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="right")
        cell.number_format = "#,##0"
        ws.merge_cells(f"E{row_num}:H{row_num}")
        cell = ws[f"M{row_num}"]
        cell.value         = opening_in
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="right")
        cell.number_format = "#,##0"
        ws.merge_cells(f"M{row_num}:P{row_num}")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 7: movement (− out, + in)
        border_line(ws, row_num)
        ws[f"D{row_num}"].value     = "-"
        ws[f"D{row_num}"].font      = Font(size=13)
        ws[f"D{row_num}"].alignment = Alignment(horizontal="right")
        cell = ws[f"E{row_num}"]
        cell.value         = qty
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="right")
        cell.number_format = "#,##0"
        ws.merge_cells(f"E{row_num}:H{row_num}")
        ws[f"L{row_num}"].value     = "+"
        ws[f"L{row_num}"].font      = Font(size=13)
        ws[f"L{row_num}"].alignment = Alignment(horizontal="right")
        cell = ws[f"M{row_num}"]
        cell.value         = qty
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="right")
        cell.number_format = "#,##0"
        ws.merge_cells(f"M{row_num}:P{row_num}")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 8: closing balances
        border_line(ws, row_num)
        ws[f"D{row_num}"].value     = "shares"
        ws[f"D{row_num}"].font      = Font(size=13)
        ws[f"D{row_num}"].alignment = Alignment(horizontal="right")
        cell = ws[f"E{row_num}"]
        cell.value         = closing_out
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="right")
        cell.number_format = "#,##0"
        ws.merge_cells(f"E{row_num}:H{row_num}")
        ws[f"L{row_num}"].value     = "shares"
        ws[f"L{row_num}"].font      = Font(size=13)
        ws[f"L{row_num}"].alignment = Alignment(horizontal="right")
        cell = ws[f"M{row_num}"]
        cell.value         = closing_in
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="right")
        cell.number_format = "#,##0"
        ws.merge_cells(f"M{row_num}:P{row_num}")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Row 9: average at destination bank
        border_line(ws, row_num)
        ws[f"K{row_num}"].value = "Average"
        ws[f"K{row_num}"].font  = Font(size=13)
        average = TradesDoneAverage(
            db=self.db, trade_date=self.trade_date,
            code=code, bank_id=in_bank_id
        ).average
        cell = ws[f"N{row_num}"]
        cell.value         = average
        cell.font          = Font(size=13)
        cell.alignment     = Alignment(horizontal="center")
        cell.number_format = "#,##0.0000"
        ws.merge_cells(f"N{row_num}:P{row_num}")
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        # Blank spacing row
        border_line(ws, row_num)
        ws.row_dimensions[row_num].height = ROW_HEIGHT
        row_num += 1

        counter += 1

    return row_num
```

- [x] **Step 7: Run the full test suite to confirm nothing broke**

```
pytest tests/functional/ -v
```

Expected: all existing tests PASS, 5 notebook transfer tests PASS.

- [x] **Step 8: Commit**

```
git add ltv_app/blueprints/notebook/extensions/create_notebook.py
git commit -m "Add write_transfers() and _opening_balance() to CreateNotebook"
```

---

## Task 3: Wiring — `views.py` + `__init__.py`

**Files:**
- Modify: `ltv_app/blueprints/notebook/extensions/__init__.py`
- Modify: `ltv_app/blueprints/notebook/views.py`

- [x] **Step 9: Export `get_transfers` from `extensions/__init__.py`**

Current content of `ltv_app/blueprints/notebook/extensions/__init__.py`:
```python
from .transactions import get_transactions
from .create_notebook import CreateNotebook
```

Replace with:
```python
from .transactions import get_transactions, get_transfers
from .create_notebook import CreateNotebook
```

- [x] **Step 10: Update `views.py` to fetch transfers and pass to `CreateNotebook`**

Current `generate` route in `ltv_app/blueprints/notebook/views.py`:
```python
from .extensions import get_transactions, CreateNotebook

@bp.route("/generate/<trade_date>")
@login_required
def generate(trade_date):
    db = get_db()
    transactions = get_transactions(db=db, trade_date=trade_date)
    notebook = CreateNotebook(db=db, trade_date=trade_date, transactions=transactions)
    return send_file('{}'.format(notebook.filename), as_attachment=True)
```

Replace with:
```python
from .extensions import get_transactions, get_transfers, CreateNotebook

@bp.route("/generate/<trade_date>")
@login_required
def generate(trade_date):
    db = get_db()
    transactions = get_transactions(db=db, trade_date=trade_date)
    transfers    = get_transfers(db=db, trade_date=trade_date)
    notebook = CreateNotebook(
        db=db, trade_date=trade_date,
        transactions=transactions, transfers=transfers
    )
    return send_file('{}'.format(notebook.filename), as_attachment=True)
```

- [x] **Step 11: Run full test suite**

```
pytest tests/functional/ -v
```

Expected: all tests PASS.

- [x] **Step 12: Manual smoke test**

1. Start the app: `! python flask_app.py`
2. Navigate to `/notebook/`
3. Pick a date that has Transfer-Out / Transfer-In transactions in the database
4. Click generate — download the notebook Excel
5. Open the file and verify:
   - All existing bank sections render as before
   - A "Transfer of Stocks" section appears after the last bank section
   - Each pair shows: counter, "Transfer [Stock] ([Code])", "from [bank]", "to [bank]", "[qty] shares", two-column balance table, Average at destination bank

- [x] **Step 13: Commit**

```
git add ltv_app/blueprints/notebook/extensions/__init__.py ltv_app/blueprints/notebook/views.py
git commit -m "Wire get_transfers into notebook generate route"
```
