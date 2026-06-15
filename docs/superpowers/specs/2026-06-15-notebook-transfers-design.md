# Notebook Transfer of Stocks Design

## Goal

Add Transfer-Out / Transfer-In pairs to the daily notebook Excel output as a "Transfer of Stocks" section appended after all bank sections.

## Architecture

Transfer transactions are already fetched by the existing `TRADE_SQL` but silently dropped in `write_line()` because `Transfer-Out` / `Transfer-In` are not in `STOCK_TRANSACTIONS` or `DERIVATIVES`. The fix adds a dedicated `get_transfers()` data function and a `write_transfers()` rendering method, wired in at the end of `create_file()`. No schema changes, no new files, no template changes.

## Tech Stack

Python 3, Flask, SQLite, openpyxl

---

## Files Modified

| File | Change |
|------|--------|
| `ltv_app/blueprints/notebook/extensions/transactions.py` | Add `TRANSFER_SQL` constant + `get_transfers(db, trade_date)` function |
| `ltv_app/blueprints/notebook/extensions/create_notebook.py` | Add `transfers` param to `__init__`, add `write_transfers()` method, call it in `create_file()` |
| `ltv_app/blueprints/notebook/views.py` | Call `get_transfers()` and pass result to `CreateNotebook` |

---

## Section 1: Data Layer

### `transactions.py` — `TRANSFER_SQL` + `get_transfers()`

```python
TRANSFER_SQL = """
    SELECT
        out_t.ref_num     AS out_ref,
        in_t.ref_num      AS in_ref,
        out_bank.bank_name  AS out_bank,
        out_bank.bank_id    AS out_bank_id,
        in_bank.bank_name   AS in_bank,
        in_bank.bank_id     AS in_bank_id,
        C.stock_name,
        C.code,
        CY.ccy_id,
        ABS(out_t.quantity) AS quantity
    FROM tbl_transaction out_t
    INNER JOIN tbl_transaction in_t
        ON  in_t.transaction_type LIKE 'Transfer%'
        AND in_t.bank_ref   = out_t.counter_bank_ref
        AND in_t.code_ref   = out_t.code_ref
        AND in_t.trade_date = out_t.trade_date
        AND ABS(in_t.quantity) = ABS(out_t.quantity)
    INNER JOIN tbl_bank_account out_bank ON out_bank.ref_num = out_t.bank_ref
    INNER JOIN tbl_bank_account in_bank  ON in_bank.ref_num  = in_t.bank_ref
    INNER JOIN tbl_code C    ON C.ref_num  = out_t.code_ref
    INNER JOIN tbl_currency CY ON CY.ref_num = C.ccy_ref
    WHERE out_t.transaction_type = 'Transfer-Out'
      AND out_t.counter_bank_ref IS NOT NULL
      AND out_t.trade_date = ?
    ORDER BY C.code
"""

def get_transfers(db, trade_date):
    rows = db.execute(TRANSFER_SQL, (trade_date,)).fetchall()
    return [dict(r) for r in rows]
```

**Known limitation:** Two identical transfers (same stock, same banks, same quantity) on the same day will produce duplicate rows in the output due to the self-join Cartesian product. The user handles this manually.

---

## Section 2: Excel Layout

The `write_transfers()` method appends output after the last bank section.

All rows call `border_line(ws, row_num)` first (thin grey top+bottom across A–Q), then write cell-specific values on top. This matches the pattern used in `write_transactions()`.

### Opening balance helper

```python
def _opening_balance(self, bank_name, code):
    row = self.db.execute(
        "SELECT SUM(tbl_transaction.quantity) AS balance "
        "FROM tbl_transaction "
        "INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_transaction.bank_ref "
        "INNER JOIN tbl_code ON tbl_code.ref_num = tbl_transaction.code_ref "
        "WHERE tbl_bank_account.bank_name = ? AND tbl_code.code = ? AND tbl_transaction.trade_date < ?",
        (bank_name, code, self.trade_date)
    ).fetchone()
    try:
        return row[0] or 0
    except (TypeError, IndexError):
        return 0
```

### Section structure

**Section header — 1 row:**
- Merge `C{r}:P{r}`, value `"Transfer of Stocks"`, Font(sz=13, bold=True), Alignment(h=center)

**Per pair — 9 content rows + 1 blank spacing row:**

| Row offset | Col | Value | Style |
|---|---|---|---|
| +0 | B | counter int | sz=13, numfmt=`0\)`, h=right |
| +0 | C | `"Transfer {stock_name} ({code})"` | sz=13, h=left |
| +1 | C | `"from {out_bank}"` | sz=13, h=left |
| +2 | C | `"to {in_bank}"` | sz=13, h=left |
| +3 | C | `"{qty:,} shares"` | sz=13, h=left |
| +4 | C | out_bank name | sz=12 |
| +4 | K | in_bank name | sz=12 |
| +5 | E:H merged | opening balance at out bank | sz=13, h=right, `#,##0` |
| +5 | M:P merged | opening balance at in bank | sz=13, h=right, `#,##0` |
| +6 | D | `"-"` | sz=13, h=right |
| +6 | E:H merged | quantity | sz=13, h=right, `#,##0` |
| +6 | L | `"+"` | sz=13, h=right |
| +6 | M:P merged | quantity | sz=13, h=right, `#,##0` |
| +7 | D | `"shares"` | sz=13, h=right |
| +7 | E:H merged | closing out = opening_out − qty | sz=13, h=right, `#,##0` |
| +7 | L | `"shares"` | sz=13, h=right |
| +7 | M:P merged | closing in = opening_in + qty | sz=13, h=right, `#,##0` |
| +8 | K | `"Average"` | sz=13 |
| +8 | N:P merged | `TradesDoneAverage(db, trade_date, code, in_bank_id).average` | sz=13, h=center, `#,##0.0000` |
| +9 | — | blank spacing row | `border_line()` only |

`ROW_HEIGHT = 17.25` applied to all rows via `ws.row_dimensions[row_num].height`.

---

## Section 3: Integration

### `views.py`

```python
from ltv_app.blueprints.notebook.extensions.transactions import get_transactions, get_transfers

# inside the generate route:
transactions = get_transactions(db, trade_date)
transfers    = get_transfers(db, trade_date)
CreateNotebook(db=db, trade_date=trade_date, transactions=transactions, transfers=transfers)
```

### `create_notebook.py` — `__init__` and `create_file()`

```python
class CreateNotebook:
    def __init__(self, db, trade_date, transactions, transfers):
        self.db           = db
        self.trade_date   = trade_date
        self.transactions = transactions
        self.transfers    = transfers
        ...
        self.create_file()

    def create_file(self):
        wb = load_workbook(self.template_file)
        ws = wb["notebook"]
        self.write_date(ws)
        self.write_stock_card(ws)
        row_num = self.write_transactions(ws=ws, row_num=ROW_NUM_START)
        row_num = self.write_transfers(ws, row_num)   # ← new
        ws.print_area = f"A1:Q{row_num}"
        wb.save(self.filename)
        wb.close()
```

`write_transfers()` returns `row_num` unchanged when `self.transfers` is empty, so days with no transfers are unaffected.

---

## Out of Scope

- Edge case: two identical transfers (same stock, same banks, same quantity) on the same day → manual handling by user
- Charges tab in Workflow page — unchanged
- Delete of transfer pairs in Workflow page — unchanged
