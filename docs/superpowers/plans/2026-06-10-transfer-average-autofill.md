# Transfer Average Auto-fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-fill the Add Transfer Price with the From account's unrounded average as of the trade date, and warn on insufficient shares.

**Architecture:** `TradesDoneAverage` gains `self.balance`; a JSON endpoint in `transactions/views.py` wraps it; vanilla JS in `home.html` fetches on field changes and validates quantity.

**Tech Stack:** Flask, vanilla JS (fetch), pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-transfer-average-autofill-design.md`

---

### Task 1: Endpoint (TDD)

**Files:**
- Create: `tests/functional/test_average_price.py`
- Modify: `ltv_app/blueprints/transactions/extensions/trades_done_average.py` (add `self.balance`)
- Modify: `ltv_app/blueprints/transactions/views.py` (route)

- [ ] **Step 1: Failing tests**

```python
"""Functional tests for /trades/average_price/<bank_ref>/<code_ref>."""
TEST_DATE  = '2026-05-18'
PRIOR_DATE = '2026-05-01'
URL = '/trades/average_price/1/1'


def _insert(db_conn, **overrides):
    params = {
        'trade_date': TEST_DATE, 'value_date': TEST_DATE,
        'bank_ref': 1, 'code_ref': 1,
        'transaction_type': 'Buy (Spot)', 'quantity': 1000, 'price': 10.0,
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


class AveragePriceTests:

    def test_requires_login(self, client):
        response = client.get(URL)
        assert response.status_code == 302

    def test_unknown_refs_return_404(self, auth_client):
        response = auth_client.get('/trades/average_price/999/999')
        assert response.status_code == 404

    def test_unrounded_average_and_balance(self, auth_client, db_conn):
        _insert(db_conn, quantity=1000, price=10.0)
        _insert(db_conn, quantity=500, price=11.0)
        data = auth_client.get(f'{URL}?trade_date={TEST_DATE}').get_json()
        assert data['average'] == 15500 / 1500     # full precision, no rounding
        assert data['balance'] == 1500

    def test_trade_date_cutoff(self, auth_client, db_conn):
        _insert(db_conn, trade_date=PRIOR_DATE, value_date=PRIOR_DATE,
                quantity=1000, price=10.0)
        _insert(db_conn, quantity=500, price=11.0)   # after PRIOR_DATE
        data = auth_client.get(f'{URL}?trade_date={PRIOR_DATE}').get_json()
        assert data['average'] == 10.0
        assert data['balance'] == 1000

    def test_no_holdings(self, auth_client):
        data = auth_client.get(f'{URL}?trade_date={TEST_DATE}').get_json()
        assert data['average'] is None
        assert data['balance'] == 0
```

- [ ] **Step 2: Run** — expect 404s/AttributeErrors (route missing).

- [ ] **Step 3: Implement** — in `trades_done_average.py` store `self.balance = balance`. In `views.py` add:

```python
@bp.route('/average_price/<int:bank_ref>/<int:code_ref>', methods=['GET'])
@login_required
def average_price(bank_ref, code_ref):
    from ..database import get_db
    from .extensions import TradesDoneAverage
    db = get_db()
    trade_date = request.args.get('trade_date') or str(ph_today())
    code_row = db.execute("SELECT code FROM tbl_code WHERE ref_num=?", (code_ref,)).fetchone()
    bank_row = db.execute("SELECT bank_id FROM tbl_bank_account WHERE ref_num=?", (bank_ref,)).fetchone()
    if not code_row or not bank_row:
        return jsonify({'error': 'Unknown bank or stock'}), 404
    result = TradesDoneAverage(db=db, trade_date=trade_date,
                               code=code_row['code'], bank_id=bank_row['bank_id'])
    return jsonify({
        'average': result.average if result.average else None,
        'balance': result.balance,
    })
```

- [ ] **Step 4: Run tests** — all PASS; run full functional suite.

### Task 2: Modal wiring

**Files:**
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html`

- [ ] **Step 1: Warning div** after the Price form-group inside the transfer grid:

```html
<div id="transferBalanceWarning" style="grid-column:1/-1;display:none;color:#b00020;font-size:0.85rem;font-weight:600;"></div>
```

- [ ] **Step 2: JS** in the page's script block: `updateTransferAverage()` + `checkTransferQuantity()` with `change`/`input` listeners on the transfer modal fields (see spec).

- [ ] **Step 3: Run full functional suite** — all PASS.

- [ ] **Step 4: Commit.**

### Task 3: Live verification

- [ ] Reload /trades/, open + Transfer, set From = Sun Hung Kai Account No. 1, To = Account No. 2, Stock = Great Wall (2333), quantity -250000 → Price auto-fills with the unrounded SHK1 average; no warning (SHK1 holds 582,635). Set quantity -999999 → warning appears. Leave Save to the user.
