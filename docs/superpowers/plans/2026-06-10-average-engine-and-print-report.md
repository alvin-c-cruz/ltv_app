# Average Engine + Printable Trades Done Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract one shared cost/average engine, use it in the New Trades Done averages, and add a printable HTML popup equivalent of that report. Excel downloads unchanged.

**Architecture:** Pure function `accumulate_position` in `transactions/models.py`; `TradesDoneAverage` becomes a thin SQL + filter wrapper around it. A new `TradesDoneReport` extension builds plain dicts from `TransactionSummary`, rendered by a standalone print template at `GET /trades/print_with_gain_loss/<trade_date>`.

**Tech Stack:** Flask, Jinja2, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-average-engine-and-print-report-design.md`

---

### Task 1: Engine + unit tests + TradesDoneAverage refactor

**Files:**
- Modify: `ltv_app/blueprints/transactions/models.py`
- Modify: `ltv_app/blueprints/transactions/extensions/trades_done_average.py`
- Create: `tests/unit/__init__.py` (empty, if missing)
- Create: `tests/unit/test_accumulate_position.py`

- [ ] **Step 1: Write failing unit tests**

`tests/unit/test_accumulate_position.py`:

```python
"""Unit tests for the shared weighted-average cost engine."""
from ltv_app.blueprints.transactions.models import accumulate_position


def _t(quantity, price, charges=0.0):
    return {
        'quantity': quantity, 'price': price,
        'brokerage': charges, 'commission': 0, 'foreign_charge': 0,
        'stamp_duty': 0, 'misc': 0,
    }


def test_single_buy():
    balance, cost, last_avg = accumulate_position([_t(1000, 10.0)])
    assert balance == 1000
    assert cost == 10000.0
    assert last_avg == 10.0


def test_buys_weighted_average_includes_charges():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0, charges=100.0),
        _t(1000, 12.0),
    ])
    assert balance == 2000
    assert cost == 22100.0
    assert last_avg == 11.05


def test_sell_keeps_average_unchanged():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0),
        _t(1000, 12.0),
        _t(-500, 15.0),
    ])
    assert balance == 1500
    assert cost == 16500.0          # 22000 - 22000*500/2000
    assert last_avg == 11.0


def test_sold_out_keeps_last_average():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0),
        _t(-1000, 15.0),
    ])
    assert balance == 0
    assert cost == 0
    assert last_avg == 10.0


def test_short_position_has_zero_cost():
    balance, cost, last_avg = accumulate_position([_t(-1000, 10.0)])
    assert balance == -1000
    assert cost == 0


def test_rebuy_after_flat_restarts_average():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0),
        _t(-1000, 15.0),
        _t(500, 20.0),
    ])
    assert balance == 500
    assert cost == 10000.0
    assert last_avg == 20.0
```

- [ ] **Step 2: Run** `pytest tests/unit/ -v` — Expected: ImportError (function missing).

- [ ] **Step 3: Add the engine** to `ltv_app/blueprints/transactions/models.py` (above `get_balance`), the loop copied from `get_balance`/`get_average` plus the last-average tracking:

```python
def accumulate_position(transactions):
    """Weighted-average cost engine shared by position/average calculations.

    `transactions` is an ordered iterable of rows exposing quantity, price,
    brokerage, commission, foreign_charge, stamp_duty, misc.
    Returns (balance, cost_to_date, last_average) where last_average is the
    most recent non-zero average — the cost basis when a position closes.
    """
    balance = 0
    cost_to_date = 0.0
    last_average = 0.0

    for row in transactions:
        quantity = row['quantity']
        price = row['price']
        charges = row['brokerage'] + row['commission'] + row['foreign_charge'] + row['stamp_duty'] + row['misc']
        amount = quantity * price + charges

        if quantity > 0:
            if balance > 0:
                cost_to_date += amount
            elif balance == 0:
                cost_to_date += amount
            elif balance < 0:
                if balance + quantity == 0:
                    cost_to_date = 0
                elif balance + quantity < 0:
                    cost_to_date = 0
                else:
                    cost_to_date = (balance + quantity) / quantity * amount
        else:
            if balance > 0:
                if balance - abs(quantity) > 0:
                    cost_to_date -= cost_to_date * abs(quantity) / balance
                else:
                    cost_to_date = 0
            else:
                cost_to_date = 0

        balance += quantity
        if balance > 0:
            average = cost_to_date / balance
            if average != 0:
                last_average = average

    return balance, cost_to_date, last_average
```

- [ ] **Step 4: Run** `pytest tests/unit/ -v` — Expected: all PASS.

- [ ] **Step 5: Refactor `trades_done_average.py`** — replace `get_average` usage with the engine; keep SQL and same-day-Transfer skip as a pre-filter:

```python
from ..models import accumulate_position


class TradesDoneAverage:
    def __init__(self, db, trade_date, code, bank_id):
        transactions = get_transactions(db, trade_date, code, bank_id)
        rows = [
            r for r in transactions
            if not (r['trade_date'] == trade_date and "Transfer" in r['transaction_type'])
        ]
        balance, cost_to_date, last_average = accumulate_position(rows)
        average = cost_to_date / balance if balance > 0 else 0
        self.average = average if average else last_average
```

Delete the now-unused `get_average` function; keep `get_transactions`.

- [ ] **Step 6: Regression** — `pytest tests/functional/test_download_trades_done.py -q` then `pytest -q` (full suite). Expected: all PASS (identical numbers).

- [ ] **Step 7: Commit** — `feat: extract shared accumulate_position engine, use in TradesDoneAverage`

---

### Task 2: Printable report (builder + route + template + button + tests)

**Files:**
- Create: `tests/functional/test_print_trades_done.py`
- Create: `ltv_app/blueprints/transactions/extensions/trades_done_report.py`
- Modify: `ltv_app/blueprints/transactions/views.py` (new route)
- Create: `ltv_app/blueprints/transactions/pages/transactions/print_trades_done.html`
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html` (toolbar button)

- [ ] **Step 1: Failing functional tests** (`tests/functional/test_print_trades_done.py`):

```python
"""Functional tests for the printable Trades Done report."""
TEST_DATE  = '2026-05-18'
PRIOR_DATE = '2026-05-01'
PRINT_URL  = f'/trades/print_with_gain_loss/{TEST_DATE}'


def _insert_transaction(db_conn, **overrides):
    params = {
        'trade_date': TEST_DATE, 'value_date': '2026-05-20',
        'bank_ref': 1, 'code_ref': 1,
        'transaction_type': 'Buy (Spot)', 'quantity': 1000, 'price': 320.50,
        'brokerage': 0, 'commission': 0, 'foreign_charge': 0,
        'stamp_duty': 0, 'misc': 0, 'locked': 0,
    }
    params.update(overrides)
    db_conn.execute(
        """INSERT INTO tbl_transaction
           (trade_date, value_date, bank_ref, code_ref, transaction_type,
            quantity, price, brokerage, commission, foreign_charge,
            stamp_duty, misc, locked)
           VALUES (:trade_date, :value_date, :bank_ref, :code_ref,
                   :transaction_type, :quantity, :price, :brokerage,
                   :commission, :foreign_charge, :stamp_duty, :misc, :locked)""",
        params,
    )
    db_conn.commit()


class PrintTradesDoneTests:

    def test_requires_login(self, client):
        response = client.get(PRINT_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_no_data_redirects_with_flash(self, auth_client):
        response = auth_client.get(PRINT_URL, follow_redirects=True)
        assert b'No data to print' in response.data

    def test_buy_shows_average_without_gain_loss(self, auth_client, db_conn):
        _insert_transaction(db_conn)
        response = auth_client.get(PRINT_URL)
        assert response.status_code == 200
        assert b'BUY' in response.data
        assert b'320.5000' in response.data          # average on last buy row
        assert b'Cost HKD' not in response.data

    def test_sell_spot_shows_gain_loss(self, auth_client, db_conn):
        _insert_transaction(db_conn, trade_date=PRIOR_DATE, value_date='2026-05-03',
                            quantity=1000, price=300.00)
        _insert_transaction(db_conn, transaction_type='Sell (Spot)',
                            quantity=-500, price=350.00)
        response = auth_client.get(PRINT_URL)
        assert response.status_code == 200
        assert b'Cost HKD' in response.data
        assert b'150,000.00' in response.data        # 500 x 300 cost
        assert b'25,000.00' in response.data         # 175,000 - 150,000 gain
        assert b'Gain HKD' in response.data

    def test_sell_short_has_no_gain_loss(self, auth_client, db_conn):
        _insert_transaction(db_conn, transaction_type='Sell (Short)',
                            quantity=-500, price=310.00)
        response = auth_client.get(PRINT_URL)
        assert response.status_code == 200
        assert b'Cost HKD' not in response.data
```

- [ ] **Step 2: Run** `pytest tests/functional/test_print_trades_done.py -v` — Expected: all FAIL with 404.

- [ ] **Step 3: Report builder** (`trades_done_report.py`): per-currency/type blocks mirroring the Excel writer — Transfers skipped, Average on the last buy row of each stock per bank, Cost/Gain-Loss/% only for Sell (Spot) (via `TradesDoneAverage`), per-bank Sell (Spot) subtotals, block TOTAL when multiple banks or repeated trades, Gain/Loss header from the signs of the block's gains. (Full code in implementation — mirrors `write_transactions` structure.)

- [ ] **Step 4: Route** in `views.py` (next to `download_with_gain_loss`):

```python
@bp.route('/print_with_gain_loss/<trade_date>', methods=['GET'])
@login_required
def print_with_gain_loss(trade_date):
    from ..database import get_db
    db = get_db()
    summary = TransactionSummary(db, trade_date)
    if summary.is_empty():
        flash("No data to print.", category="error")
        return redirect(url_for("transactions.home"))
    report = TradesDoneReport(db=db, trade_date=trade_date, trade_summary=summary)
    return render_template('transactions/print_trades_done.html', report=report)
```

- [ ] **Step 5: Standalone template** `print_trades_done.html` — no base.html, inline print CSS, `no-print` Print button (`window.print()`), ACCU/DECU tables then transaction blocks.

- [ ] **Step 6: Toolbar button** in `home.html` after "New Trades Done":

```html
<a href="{{ url_for('transactions.print_with_gain_loss', trade_date=trade_date) }}" target="_blank" class="btn btn-outline">Print Trades Done</a>
```

- [ ] **Step 7: Run** print tests, then the full functional suite. Expected: all PASS.

- [ ] **Step 8: Commit** — `feat: printable Trades Done report popup`

---

### Task 3: Live verification

- [ ] Open `/trades/print_with_gain_loss/2026-06-10` in the browser, screenshot, confirm parity with the Excel content (BUY block, average 10.0973, no gain/loss columns).
