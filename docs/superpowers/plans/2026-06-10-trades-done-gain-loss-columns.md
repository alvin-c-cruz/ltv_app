# Trades Done Gain/Loss Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the New Trades Done export, write the gain/loss columns (L/M/N, plus O average, M/N headers, and bank subtotals) only for Sell (Spot) blocks.

**Architecture:** All changes inside `write_transactions` in `ltv_app/blueprints/transactions/extensions/download_trades_done_with_gain_loss.py`. TDD via the existing functional download tests, parsing the returned xlsx with openpyxl.

**Tech Stack:** Flask, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-trades-done-gain-loss-columns-design.md`

---

### Task 1: Failing tests — column emptiness/presence

**Files:**
- Modify: `tests/functional/test_download_trades_done.py`

- [ ] **Step 1: Add xlsx-parsing tests**

Add at the top of the file (after existing imports):

```python
import io
from openpyxl import load_workbook
```

Append a new test class:

```python
def _first_sheet(response):
    wb = load_workbook(io.BytesIO(response.data))
    return wb[wb.sheetnames[0]]


def _column_values(ws, letters):
    values = {}
    for letter in letters:
        values[letter] = [
            cell.value for cell in ws[letter] if cell.value is not None
        ]
    return values


class GainLossColumnTests:
    """Columns L/M/N belong to Sell (Spot) blocks only."""

    def test_buy_only_has_no_gain_loss_columns(self, auth_client, db_conn):
        _insert_transaction(db_conn)  # Buy (Spot)
        response = auth_client.get(NEW_URL)
        ws = _first_sheet(response)
        values = _column_values(ws, 'LMN')
        assert values == {'L': [], 'M': [], 'N': []}

    def test_sell_short_has_no_gain_loss_columns(self, auth_client, db_conn):
        _insert_transaction(db_conn, transaction_type='Sell (Short)',
                            quantity=-500, price=310.00)
        response = auth_client.get(NEW_URL)
        ws = _first_sheet(response)
        values = _column_values(ws, 'LMN')
        assert values == {'L': [], 'M': [], 'N': []}

    def test_sell_spot_has_gain_loss_columns(self, auth_client, db_conn):
        _insert_buy_and_sell(db_conn)  # prior buy + Sell (Spot) on TEST_DATE
        response = auth_client.get(NEW_URL)
        ws = _first_sheet(response)
        values = _column_values(ws, 'LMN')
        assert values['L'], "expected cost formulas in column L"
        assert values['M'], "expected gain/loss formulas in column M"
        assert values['N'], "expected % formulas in column N"
```

- [ ] **Step 2: Run to verify the two emptiness tests fail**

Run: `pytest tests/functional/test_download_trades_done.py -k GainLoss -v`
Expected: `test_buy_only_has_no_gain_loss_columns` and `test_sell_short_has_no_gain_loss_columns` FAIL (L/M/N contain formulas today); `test_sell_spot_has_gain_loss_columns` PASSES.

### Task 2: Fix `write_transactions`

**Files:**
- Modify: `ltv_app/blueprints/transactions/extensions/download_trades_done_with_gain_loss.py`

- [ ] **Step 1: Gate header labels** — replace

```python
                if "Buy" in transaction_type:
                    cols["J"] = "Average"
                else:
                    cols["L"] = f"Cost {ccy}"
                    cols["M"] = f"Lost {ccy}"
                    cols["N"] = "% Lost"
```

with

```python
                if "Buy" in transaction_type:
                    cols["J"] = "Average"
                elif transaction_type == "Sell (Spot)":
                    cols["L"] = f"Cost {ccy}"
                    cols["M"] = f"Lost {ccy}"
                    cols["N"] = "% Lost"
```

- [ ] **Step 2: Gate detail formulas** — remove `"L"`, `"M"`, `"N"` from the base `cols` dict and move them (with `O`) into a Sell (Spot)-only branch:

```python
                            cols = {
                                "A": bank_name,
                                "B": f'=A{row_num}&D{row_num}&MID(C{row_num},FIND("(",C{row_num})+1,4)',
                                "C": stock_name,
                                "D": transaction_type,
                                "E": price,
                                "G": quantity,
                                "H": f'=E{row_num}*G{row_num}',
                            }

                            if "Buy" in transaction_type:
                                if i_trade + 1 == trade_count:
                                    average = TradesDoneAverage(db=self.db, trade_date=self.trade_date,
                                                                code=code, bank_id=bank_id).average
                                else:
                                    average = None

                                cols["J"] = average
                            elif transaction_type == "Sell (Spot)":
                                cols["L"] = f'=G{row_num}*O{row_num}'
                                cols["M"] = f'=H{row_num}-L{row_num}'
                                cols["N"] = f'=M{row_num}/L{row_num}'
                                cols["O"] = TradesDoneAverage(db=self.db, trade_date=self.trade_date,
                                                              code=code, bank_id=bank_id).average
```

- [ ] **Step 3: Gate bank subtotals and header fix-up** — change `if "Sell" in transaction_type:` (cost totals) to `if transaction_type == "Sell (Spot)":`, and wrap the M/N "Fix the Gain/Loss Ccy Header" block in the same condition.

- [ ] **Step 4: Run the download test file**

Run: `pytest tests/functional/test_download_trades_done.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Full functional suite**

Run: `pytest tests/functional/ -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/functional/test_download_trades_done.py ltv_app/blueprints/transactions/extensions/download_trades_done_with_gain_loss.py
git commit -m "New Trades Done: gain/loss columns only for Sell (Spot)"
```

### Task 3: Live verification

- [ ] Re-download the same trade date from the running app and confirm columns L/M/N are gone for the Buy-only sheet.
