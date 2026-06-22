# LTV v2 — Trading Ledger Design

**Date:** 2026-06-22
**Scope:** Transaction data model, manual entry CRUD, and the core position/P&L engine.
**Deferred:** Rich report views (own plan), workflow/review pipeline (own plan), derivatives/fixings (own plan), v1→v2 data migration (own plan).

---

## 1. Context

The reference-data layer (Plans A–C) is complete on `main`: `currencies`, `banks`, `stocks`, `holidays`, and `transaction_types` (with `behavior_category` enum). The trading ledger builds directly on these.

`TransactionType.behavior_category` is the engine's only branching hook:

| value | meaning |
|---|---|
| `increase` | adds shares and cost to the position |
| `decrease` | removes shares and realizes P&L |
| `transfer_in` | receives shares from another account; cost-basis neutral |
| `transfer_out` | sends shares to another account; cost-basis neutral |
| `dividend` | adds shares at zero cost (stock dividend) |
| `neutral` | recorded event with no position effect |

---

## 2. Data Model Changes

### 2a. Add `book` to `TransactionType`

A new `book` column (`"long"` or `"short"`) on the existing `transaction_types` table determines which position book a transaction affects. This means the *type* drives everything — the user just picks a type and both `behavior_category` and `book` are implied.

**Migration:** add a `book` column, non-nullable, default `"long"` for all existing rows.

**CRUD:** add a `<select long/short>` field to the existing transaction-types Add/Edit form and to `TransactionTypeForm`.

**Effect:** a `Sell (Short)` type has `book="short"` and `behavior_category="increase"` (opening a short position *adds* to the short balance). A `Buy (Pay Short)` has `book="short"` and `behavior_category="decrease"` (closing the short).

### 2b. `Transaction` model (new table `transactions`)

| column | type | notes |
|---|---|---|
| `id` | Integer PK | |
| `trade_date` | Date | |
| `value_date` | Date | |
| `bank_id` | FK → `banks.id` | |
| `stock_id` | FK → `stocks.id` | |
| `transaction_type_id` | FK → `transaction_types.id` | supplies `book` + `behavior_category` |
| `quantity` | Numeric | **positive magnitude always**; direction inferred from `behavior_category` |
| `price` | Numeric | per share |
| `brokerage` | Numeric, default 0 | |
| `commission` | Numeric, default 0 | |
| `foreign_charge` | Numeric, default 0 | |
| `stamp_duty` | Numeric, default 0 | |
| `misc` | Numeric, default 0 | |
| `counter_bank_id` | FK → `banks.id`, nullable | set on both legs of a transfer |
| `comments` | Text, nullable | |
| `locked` | Boolean, default False | reserved for the review pipeline; engine treats locked rows as read-only |
| `created_at`, `updated_at` | DateTime | auto-managed |

`total_charges` is a Python property: `brokerage + commission + foreign_charge + stamp_duty + misc`.

---

## 3. Position Engine (`ltv2/services/positions.py`)

### Design principle

Pure functions — no Flask, no SQLAlchemy session, no side effects. Takes an ordered list of transaction dicts and returns position state. Fully unit-testable without a running app.

### Position key

`(bank_id, stock_id, book)` — long and short books are **always independent balances**, even on the same (bank, stock). An explicit short book and a long book that has crossed zero (oversell) are separate.

### State per position

```python
@dataclass
class PositionState:
    balance: Decimal      # signed; positive = long shares held, negative = synthetic short within book
    cost_basis: Decimal   # signed; tracks the weighted-average entry cost
    realized_pnl: Decimal

    @property
    def average(self) -> Decimal:
        return cost_basis / balance if balance != 0 else Decimal(0)
```

### Signed delta mapping

The engine first converts each transaction into a **signed quantity delta** before applying the averaging rule:

| book | behavior_category | signed delta |
|---|---|---|
| long | increase | `+qty` |
| long | decrease | `−qty` |
| long | dividend | `+qty` (zero-cost; handled separately — see §3.2) |
| long | transfer_in | `+qty` |
| long | transfer_out | `−qty` |
| short | increase | `−qty` (opening/adding to short) |
| short | decrease | `+qty` (closing short) |
| either | neutral | no position effect |

**Transfers only apply to the long book.** A short-book position represents borrowed shares and cannot be physically transferred between accounts. If a `transfer_in`/`transfer_out` type is associated with a short book, it is rejected at the entry-form validation layer.

### Cash-flow conventions (used throughout)

Two values are defined per trade before applying any case:

**`opening_cost`** — the signed cost added when *entering* shares:
- Long increase (buy): `+qty × price + charges` (cash paid out, positive)
- Short increase (sell short): `−(qty × price − charges)` (proceeds received, stored as negative obligation)

**`closing_cash`** — the signed cash received/paid when *exiting* shares:
- Long decrease (sell): `+qty × price − charges` (positive — you receive)
- Short decrease (cover): `−(qty × price + charges)` (negative — you pay)

`cost_basis` inherits the sign of the position it represents: positive for long, negative for short.

### Three-case averaging rule

**Case 1 — Opening or adding** (`d` same sign as `balance`, or `balance == 0`)

No P&L. Weighted average absorbs the new shares.

```
cost_basis += opening_cost
balance    += d
```

Verified:
- Long buy 100 @ 10, charges 5: `cost_basis = 1005`, `balance = 100`, `avg = 10.05` ✓
- Short sell 50 @ 15, charges 2: `cost_basis = −748`, `balance = −50`, `avg = 14.96` ✓

**Case 2 — Reducing, no zero-cross** (`d` opposite sign to `balance`, `|d| ≤ |balance|`)

Release the proportional cost basis; realize P&L.

```
released     = (close_qty / |balance|) × cost_basis   # signed: positive for long, negative for short
realized_pnl += closing_cash − released
cost_basis   -= released
balance      += d
```

`released` is proportional and **inherits the sign of `cost_basis`**, so the formula `closing_cash − released` works identically for long-decrease and short-decrease.

Verified:
- Long sell 40 @ 12, charges 3 (from 100-share long @ avg 10.05):
  `released = (40/100)×1005 = 402`, `closing_cash = 40×12−3 = 477`
  P&L = `477 − 402 = +75`, `cost_basis = 1005 − 402 = 603`, avg stays `10.05` ✓
- Short cover 20 @ 14, charges 1 (from 50-share short @ avg 14.96):
  `released = (20/50)×(−748) = −299.2`, `closing_cash = −(20×14+1) = −281`
  P&L = `−281 − (−299.2) = +18.2`, `cost_basis = −748 − (−299.2) = −448.8`, avg stays `14.96` ✓

Note: when `balance` reaches exactly 0, `cost_basis` also reaches 0 (proportional release of the whole thing).

**Case 3 — Zero-crossing** (`d` opposite sign to `balance`, `|d| > |balance|`)

Split the trade at the crossing: close the full existing position (Case 2 on `close_qty`), then open the remainder in the new direction (Case 1 on `open_qty`). Charges are pro-rated by quantity.

```
close_qty = |balance|
open_qty  = |d| − close_qty

# Pro-rate price and charges
price_per_share  = trade.price
charges_close    = charges × (close_qty / |d|)
charges_open     = charges × (open_qty  / |d|)

# Step A: close existing position (full Case 2)
released     = cost_basis            # full remaining cost (proportional with close_qty = |balance|)
closing_cash = sign(balance) × (close_qty × price_per_share − charges_close)
realized_pnl += closing_cash − released
cost_basis    = 0
balance       = 0

# Step B: open new position in the opposite direction (Case 1)
new_d            = sign(d) × open_qty   # sign follows the trade direction
opening_cost_new = sign(new_d) × (open_qty × price_per_share) + sign(new_d) × charges_open
  # long open: +(open_qty×price + charges_open)
  # short open: −(open_qty×price − charges_open)
cost_basis = opening_cost_new
balance    = new_d
```

A long oversell is Case 3 on the long book — the long closes, and the remainder carries a negative `balance` and negative `cost_basis` as a synthetic short within the long book. No special branches.
A short over-cover is the mirror: the short closes, remainder opens as a synthetic long within the short book.

### Dividend handling (stock dividend)

Dividends (`behavior_category = "dividend"`) add shares at zero cost: `balance += qty`, `cost_basis` unchanged. The per-share average drops automatically. No Case rule needed — it's a direct adjustment before any case logic.

### Transfer handling

`transfer_in` / `transfer_out` legs move shares between banks **at the source account's current average cost**, so the cost basis is preserved across accounts. The entry view stamps the price on both legs at save time (source bank's `state.average`). The engine then treats each leg as a normal increase/decrease at that stamped price — no special case in the engine itself.

If the source account has no current position (`balance = 0`, `average = 0`), the transfer price defaults to the user-entered price on the form rather than a zero-cost stamp.

### Transaction ordering

Transactions are fed to the engine sorted by the **bank's `transaction_basis`** (`trade_date` or `value_date`), then by `transaction_type.priority` as tiebreaker — identical to v1's ordering guarantee.

---

## 4. Entry CRUD (`ltv2/blueprints/transactions/`)

Follows the `banks` blueprint pattern exactly: `list`, `add`, `edit`, `delete`, all behind `@login_required`, WTForms + CSRF, flash messages.

### List view

Filterable by bank, stock, and date range. Shows: date, bank, stock, type, qty, price, total charges, locked indicator. Defaults to current month.

### Add / Edit form

Fields: trade_date, value_date, bank, stock, transaction_type, quantity, price, brokerage, commission, foreign_charge, stamp_duty, misc, counter_bank (visible only when type is transfer), comments.

**No sell-qty validation against balance** — oversell is allowed.

**Transfer auto-pair:** when the selected type has `behavior_category` in `(transfer_in, transfer_out)`:
- The form requires `counter_bank`.
- On save, the view creates **both** legs in one `db.session.commit()`: the entered leg and its paired opposite (`transfer_out` ↔ `transfer_in`, quantities equal, price stamped at source average, `counter_bank_id` set on both).
- Edit of one leg updates both; delete of one leg deletes both.

**Locked rows:** locked transactions render a disabled edit form with an explanation flash. The delete route rejects them. (Locking itself is the workflow plan's concern.)

### Simple position snapshot view

One read-only page: current `(bank, stock, book)` balances and average cost, driven by the engine. No date filter, no Excel export — those belong to the reports plan. This view exists solely to confirm live data is correct during development.

---

## 5. File Layout

```
ltv2/
  models/
    transaction.py          # Transaction SQLAlchemy model
  services/
    positions.py            # pure engine: PositionState, compute_position(transactions)
  blueprints/
    transactions/
      __init__.py
      forms.py              # TransactionForm
      views.py              # list/add/edit/delete/position-snapshot routes
  templates/
    transactions/
      list.html
      form.html
      position_snapshot.html
migrations/versions/
  <hash>_add_book_to_transaction_types.py
  <hash>_create_transactions_table.py
tests/ltv2/
  test_position_engine.py   # pure unit tests, no DB
  test_transactions_crud.py # functional blueprint tests
```

---

## 6. Testing

### Unit — `test_position_engine.py`

No fixtures, no DB, no Flask. Pure function calls.

Scenarios to cover exhaustively:
- Single buy → correct balance and average
- Buy then partial sell (Case 2) → correct P&L and remaining basis
- Buy then full sell (Case 2, balance → 0) → P&L correct, cost_basis = 0
- Buy then **oversell** (Case 3) → long closes, remainder opens as negative balance; correct P&L on close, correct new average
- Oversell then buy-back partial (Case 2 on negative balance)
- Oversell then buy-back crossing zero again (Case 3 back to positive)
- Dividend lowers average without changing cost_basis
- Short open (increase, short book) → negative balance, correct basis
- Short partial cover (Case 2, short book) → P&L correct
- Short over-cover crossing zero (Case 3, short book)
- Transfer: source loses shares at average, destination gains at same average → combined cost-basis neutral
- `value_date` vs `trade_date` ordering produces different intermediate states
- Mixed types in priority order within same date

### Functional — `test_transactions_crud.py`

Uses `auth_client` + `db_conn` from `tests/ltv2/conftest.py`. Covers:
- Add a transaction → row in DB
- Edit a transaction → row updated
- Delete a transaction → row removed
- Transfer add → two rows in DB with paired `counter_bank_id`
- Transfer delete → both rows removed
- Locked row → edit returns 403 / form disabled
- Unauthenticated → redirect to login
- Position snapshot view → 200, correct balance displayed
- `book` field on TransactionType add/edit form → saved to DB

---

## 7. Out of Scope (deferred)

- Excel / PDF reports
- Date-range P&L reports and gain/loss sheets
- Review / approval workflow (draft → entered → reviewed → locked state machine)
- Derivatives / term-sheets / fixings
- v1 → v2 data migration
- Pricing / market-data feed
