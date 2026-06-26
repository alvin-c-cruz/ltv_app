# LTV v2 Trading Ledger — Plan 1: Schema + Position Engine

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `book` dimension + `transactions` table to the ltv2 schema and build a pure, exhaustively-tested position/P&L engine — with no UI yet.

**Architecture:** Two Alembic migrations extend the existing reference-data schema (a `book` column on `transaction_types` plus `server_default` backfills, then a new `transactions` table). The position engine (`ltv2/services/positions.py`) is a set of pure functions — no Flask, no SQLAlchemy session — that fold an ordered list of transaction dicts into per-`(bank, stock, book)` `PositionState` objects using a signed-delta mapping and a three-case weighted-average rule. It is unit-tested in complete isolation.

**Tech Stack:** Python 3, Flask-SQLAlchemy, Flask-Migrate/Alembic (SQLite, batch mode), WTForms, `decimal.Decimal` for all money math, pytest.

**Source spec:** `docs/superpowers/specs/2026-06-22-ltv2-trading-ledger-design.md` (§2, §3, §6, §7).

## Global Constraints

- **Isolation guardrail (hard):** Touch ONLY files under `ltv2/`, `tests/ltv2/`, and `migrations/versions/`. NEVER edit anything under `ltv_app/`, and never open, migrate, or modify the live DB `instance/LTV Stocks.db`. The v2 app uses its own DB `instance/ltv2.db`.
- **Virtualenv:** Run all Python/pytest/flask commands with the ltv2 interpreter: `.venv-ltv2/Scripts/python`. (Commands below are written for Git Bash; on PowerShell set env vars with `$env:NAME="..."` first.)
- **Migrations entry point:** `FLASK_APP=flask_app_v2.py` for every `flask db ...` command.
- **Money math:** Every quantity, price, charge, cost, and P&L value in the engine is a `decimal.Decimal`. Never use `float`.
- **Migration safety:** Never run `flask db downgrade` against the real `instance/ltv2.db`. Round-trip migration tests run against a throwaway scratch DB via the `LTV2_DATABASE_URI` env override added in Task 1.
- **Alembic chain:** The real current head is `98c3b03d0462`. New migrations chain after it (Task 2 → Task 4).
- **Test invocation:** `.venv-ltv2/Scripts/python -m pytest tests/ltv2/<file> -v`. The root `conftest.py` (legacy, live DB) defines fixtures only used by non-ltv2 tests; ltv2 tests use `tests/ltv2/conftest.py` and never touch the live DB.

---

### Task 1: Remove the stray migration and add a DB-URI env override

A leftover 2022 Alembic migration (`d185642c2439_.py`, `down_revision = None`, creating singular `currency`/`holiday` tables) sits in `migrations/versions/` as a second, isolated alembic head. With two heads, `flask db upgrade` fails ("Multiple head revisions"). It is untracked and not part of the real ltv2 chain (`3647ba05c178` → `98c3b03d0462`). Delete it. Also add an env override to `ltv2/config.py` so later migration round-trip tests can target a scratch DB instead of the real one.

**Files:**
- Delete: `migrations/versions/d185642c2439_.py`
- Modify: `ltv2/config.py:9`

**Interfaces:**
- Consumes: nothing.
- Produces: a single alembic head (`98c3b03d0462`); `Config.SQLALCHEMY_DATABASE_URI` honors the `LTV2_DATABASE_URI` env var.

- [ ] **Step 1: Confirm the two heads exist (reproduce the problem)**

Run:
```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db heads
```
Expected: TWO head lines printed, including `d185642c2439` and `98c3b03d0462`.

- [ ] **Step 2: Delete the stray migration**

```bash
git rm migrations/versions/d185642c2439_.py
```
(If git reports it was untracked, fall back to `rm migrations/versions/d185642c2439_.py`.)

- [ ] **Step 3: Verify a single head remains**

Run:
```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db heads
```
Expected: exactly ONE line: `98c3b03d0462 (head)`.

- [ ] **Step 4: Add the `LTV2_DATABASE_URI` env override**

In `ltv2/config.py`, replace the hardcoded URI line:

```python
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(_INSTANCE, "ltv2.db")
```

with:

```python
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "LTV2_DATABASE_URI", "sqlite:///" + os.path.join(_INSTANCE, "ltv2.db")
    )
```

- [ ] **Step 5: Verify a clean upgrade round-trip on a scratch DB**

Run (creates a throwaway DB, upgrades to head, downgrades to base, deletes it):
```bash
rm -f instance/_scratch_migr.db
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db upgrade
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db downgrade base
rm -f instance/_scratch_migr.db
```
Expected: upgrade runs `3647ba05c178` then `98c3b03d0462` with no "multiple heads" error; downgrade unwinds both cleanly.

- [ ] **Step 6: Commit**

```bash
git add migrations/versions/d185642c2439_.py ltv2/config.py
git commit -m "chore(ltv2): drop stray alembic head + add LTV2_DATABASE_URI override"
```

---

### Task 2: Add `book` to `transaction_types` + `server_default` backfill (model + Migration A)

Add the `book` column to the `TransactionType` model and add `server_default` to the existing NOT-NULL columns that the future v1→v2 raw-SQL data migration would otherwise trip over (`is_active` on all 5 reference tables; `priority` on the 3 tables that have it; `role` and `failed_logins` on `users`). Keep the model and the migration in lockstep so future autogenerate sees no drift.

**Files:**
- Modify: `ltv2/models/mixins.py:5`
- Modify: `ltv2/models/transaction_type.py`
- Modify: `ltv2/models/currency.py:10`
- Modify: `ltv2/models/bank.py:12`
- Modify: `ltv2/models/user.py:16-17`
- Create: `migrations/versions/a1b2c3d4e5f6_book_and_server_defaults.py`
- Test: `tests/ltv2/test_reference_models.py` (append)

**Interfaces:**
- Consumes: single alembic head `98c3b03d0462` (Task 1).
- Produces: `TransactionType.book` (str, `"long"`/`"short"`, default `"long"`); alembic head `a1b2c3d4e5f6`.

- [ ] **Step 1: Write the failing test**

Append to `tests/ltv2/test_reference_models.py`:

```python
def test_transaction_type_book_defaults_to_long(app):
    from ltv2.extensions import db
    from ltv2.models.transaction_type import TransactionType
    with app.app_context():
        t = TransactionType(name="Buy (Spot)", behavior_category="increase")
        db.session.add(t)
        db.session.commit()
        assert t.book == "long"


def test_transaction_type_book_can_be_short(app):
    from ltv2.extensions import db
    from ltv2.models.transaction_type import TransactionType
    with app.app_context():
        t = TransactionType(name="Sell (Short)", behavior_category="increase", book="short")
        db.session.add(t)
        db.session.commit()
        assert t.book == "short"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_reference_models.py -k book -v
```
Expected: FAIL — `TypeError: 'book' is an invalid keyword argument` (column does not exist yet).

- [ ] **Step 3: Add the `book` column to the model**

In `ltv2/models/transaction_type.py`, add the `book` column after `priority`:

```python
class TransactionType(ActiveMixin, db.Model):
    __tablename__ = "transaction_types"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    behavior_category = db.Column(db.String(20), nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    book = db.Column(db.String(10), nullable=False, default="long", server_default="long")
```

- [ ] **Step 4: Add `server_default` to the other model columns**

In `ltv2/models/mixins.py`, update `is_active`:

```python
class ActiveMixin:
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("1"))
```

In `ltv2/models/currency.py`, update `priority`:

```python
    priority = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

In `ltv2/models/bank.py`, update `priority`:

```python
    priority = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

In `ltv2/models/user.py`, update `role` and `failed_logins`:

```python
    role = db.Column(db.String(20), nullable=False, default="user", server_default="user")
    failed_logins = db.Column(db.Integer, nullable=False, default=0, server_default="0")
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_reference_models.py -v
```
Expected: PASS (new book tests pass; pre-existing reference-model tests still pass).

- [ ] **Step 6: Write Migration A**

Create `migrations/versions/a1b2c3d4e5f6_book_and_server_defaults.py`:

```python
"""add book to transaction_types + server_default backfill

Revision ID: a1b2c3d4e5f6
Revises: 98c3b03d0462
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '98c3b03d0462'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transaction_types") as batch:
        batch.add_column(sa.Column("book", sa.String(length=10), nullable=False, server_default="long"))
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default="0")
    with op.batch_alter_table("currencies") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default="0")
    with op.batch_alter_table("banks") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default="0")
    with op.batch_alter_table("holidays") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
    with op.batch_alter_table("stocks") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(length=20), existing_nullable=False, server_default="user")
        batch.alter_column("failed_logins", existing_type=sa.Integer(), existing_nullable=False, server_default="0")


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("failed_logins", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("role", existing_type=sa.String(length=20), existing_nullable=False, server_default=None)
    with op.batch_alter_table("stocks") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("holidays") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("banks") as batch:
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("currencies") as batch:
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("transaction_types") as batch:
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
        batch.drop_column("book")
```

- [ ] **Step 7: Verify the migration upgrades and downgrades on a scratch DB**

Run:
```bash
rm -f instance/_scratch_migr.db
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db upgrade
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db current
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db downgrade base
rm -f instance/_scratch_migr.db
```
Expected: `db current` reports `a1b2c3d4e5f6 (head)`; upgrade and full downgrade both complete without error.

- [ ] **Step 8: Apply the migration to the real ltv2 DB**

Run:
```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db upgrade
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db current
```
Expected: `db current` reports `a1b2c3d4e5f6 (head)`. (Upgrade only — never downgrade the real DB.)

- [ ] **Step 9: Commit**

```bash
git add ltv2/models/mixins.py ltv2/models/transaction_type.py ltv2/models/currency.py ltv2/models/bank.py ltv2/models/user.py migrations/versions/a1b2c3d4e5f6_book_and_server_defaults.py tests/ltv2/test_reference_models.py
git commit -m "feat(ltv2): add book to transaction_types + server_default backfill"
```

---

### Task 3: Surface `book` in the transaction_types CRUD form, view, and templates

The new NOT-NULL `book` column must be settable in the UI. Add a `BOOKS` constant, a `book` select to `TransactionTypeForm` (default `"long"` so existing callers that omit it stay valid), wire the view to persist it, and show it in the form and list templates. Update the existing CRUD tests and add a book-persistence test (spec §6).

**Files:**
- Modify: `ltv2/constants.py`
- Modify: `ltv2/blueprints/transaction_types/forms.py`
- Modify: `ltv2/blueprints/transaction_types/views.py:27-29,46-48`
- Modify: `ltv2/templates/transaction_types/form.html`
- Modify: `ltv2/templates/transaction_types/list.html`
- Test: `tests/ltv2/test_transaction_types_crud.py` (append)

**Interfaces:**
- Consumes: `TransactionType.book` (Task 2).
- Produces: `BOOKS = ("long", "short")` in `ltv2/constants.py`; `TransactionTypeForm.book` select field.

- [ ] **Step 1: Write the failing test**

Append to `tests/ltv2/test_transaction_types_crud.py`:

```python
def test_add_saves_book(logged_in_client, app):
    logged_in_client.post("/transaction-types/add", data={
        "name": "Sell (Short)", "behavior_category": "increase",
        "priority": "0", "book": "short"})
    with app.app_context():
        t = TransactionType.query.filter_by(name="Sell (Short)").first()
        assert t is not None and t.book == "short"


def test_add_defaults_book_to_long(logged_in_client, app):
    logged_in_client.post("/transaction-types/add", data={
        "name": "Buy (Spot)", "behavior_category": "increase", "priority": "0"})
    with app.app_context():
        t = TransactionType.query.filter_by(name="Buy (Spot)").first()
        assert t is not None and t.book == "long"


def test_edit_updates_book(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Flip", behavior_category="increase", book="long")
        db.session.add(t); db.session.commit()
        tid = t.id
    logged_in_client.post(f"/transaction-types/{tid}/edit", data={
        "name": "Flip", "behavior_category": "increase", "priority": "0", "book": "short"})
    with app.app_context():
        assert db.session.get(TransactionType, tid).book == "short"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_transaction_types_crud.py -k book -v
```
Expected: FAIL — `book` is not persisted (form ignores it), so assertions on `t.book == "short"` fail.

- [ ] **Step 3: Add the `BOOKS` constant**

In `ltv2/constants.py`, add:

```python
BOOKS = ("long", "short")
```

- [ ] **Step 4: Add the `book` field to the form**

In `ltv2/blueprints/transaction_types/forms.py`:

```python
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional
from ltv2.constants import BEHAVIOR_CATEGORIES, BOOKS


class TransactionTypeForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    behavior_category = SelectField("Behavior Category",
                                    choices=[(b, b) for b in BEHAVIOR_CATEGORIES],
                                    validators=[DataRequired()])
    book = SelectField("Book", choices=[(b, b) for b in BOOKS], default="long")
    priority = IntegerField("Priority", validators=[Optional()], default=0)
```

- [ ] **Step 5: Persist `book` in the view**

In `ltv2/blueprints/transaction_types/views.py`, in `add_type`, set `book` when constructing the record:

```python
        t = TransactionType(name=form.name.data,
                            behavior_category=form.behavior_category.data,
                            book=form.book.data,
                            priority=form.priority.data if form.priority.data is not None else 0)
```

In `edit_type`, set `book` alongside the other fields:

```python
        t.name = form.name.data
        t.behavior_category = form.behavior_category.data
        t.book = form.book.data
        t.priority = form.priority.data if form.priority.data is not None else 0
```

- [ ] **Step 6: Show `book` in the templates**

In `ltv2/templates/transaction_types/form.html`, add a row after `behavior_category`:

```html
  <p>{{ form.behavior_category.label }} {{ form.behavior_category() }}</p>
  <p>{{ form.book.label }} {{ form.book() }}</p>
```

In `ltv2/templates/transaction_types/list.html`, add a `Book` header and cell:

```html
  <tr><th>Name</th><th>Behavior</th><th>Book</th><th>Priority</th><th>Active</th><th></th></tr>
```
```html
    <td>{{ t.name }}</td><td>{{ t.behavior_category }}</td><td>{{ t.book }}</td><td>{{ t.priority }}</td>
```

- [ ] **Step 7: Run the full transaction_types test file**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_transaction_types_crud.py -v
```
Expected: PASS — the three new book tests pass and all pre-existing tests (add/edit/duplicate/toggle) still pass.

- [ ] **Step 8: Commit**

```bash
git add ltv2/constants.py ltv2/blueprints/transaction_types/forms.py ltv2/blueprints/transaction_types/views.py ltv2/templates/transaction_types/form.html ltv2/templates/transaction_types/list.html tests/ltv2/test_transaction_types_crud.py
git commit -m "feat(ltv2): add book select to transaction-types CRUD"
```

---

### Task 4: `Transaction` model + Migration B (`transactions` table)

Create the `Transaction` SQLAlchemy model per spec §2b with a `total_charges` property, register it, and write the migration that creates the `transactions` table.

**Files:**
- Create: `ltv2/models/transaction.py`
- Modify: `ltv2/models/__init__.py`
- Create: `migrations/versions/b2c3d4e5f6a1_create_transactions_table.py`
- Test: `tests/ltv2/test_transaction_model.py`

**Interfaces:**
- Consumes: `banks.id`, `stocks.id`, `transaction_types.id` (existing); alembic head `a1b2c3d4e5f6` (Task 2).
- Produces: `Transaction` model with columns per §2b and `total_charges` property; alembic head `b2c3d4e5f6a1`.

- [ ] **Step 1: Write the failing test**

Create `tests/ltv2/test_transaction_model.py`:

```python
from datetime import date
from decimal import Decimal
from ltv2.extensions import db
from ltv2.models.currency import Currency
from ltv2.models.bank import Bank
from ltv2.models.stock import Stock
from ltv2.models.transaction_type import TransactionType
from ltv2.models.transaction import Transaction


def _seed(app):
    with app.app_context():
        ccy = Currency(code="HKD")
        bank = Bank(bank_code="B1", name="Bank One")
        stock = Stock(code="700")
        tt = TransactionType(name="Buy (Spot)", behavior_category="increase", book="long")
        db.session.add_all([ccy, bank, stock, tt])
        db.session.commit()
        return bank.id, stock.id, tt.id


def test_total_charges_sums_all_charge_fields(app):
    bank_id, stock_id, tt_id = _seed(app)
    with app.app_context():
        t = Transaction(
            trade_date=date(2026, 6, 1), value_date=date(2026, 6, 3),
            bank_id=bank_id, stock_id=stock_id, transaction_type_id=tt_id,
            quantity=Decimal("100"), price=Decimal("10"),
            brokerage=Decimal("1"), commission=Decimal("2"),
            foreign_charge=Decimal("3"), stamp_duty=Decimal("4"), misc=Decimal("5"),
        )
        db.session.add(t); db.session.commit()
        assert t.total_charges == Decimal("15")


def test_charge_fields_default_to_zero(app):
    bank_id, stock_id, tt_id = _seed(app)
    with app.app_context():
        t = Transaction(
            trade_date=date(2026, 6, 1), value_date=date(2026, 6, 3),
            bank_id=bank_id, stock_id=stock_id, transaction_type_id=tt_id,
            quantity=Decimal("50"), price=Decimal("20"),
        )
        db.session.add(t); db.session.commit()
        assert t.total_charges == Decimal("0")
        assert t.locked is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_transaction_model.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ltv2.models.transaction'`.

- [ ] **Step 3: Create the `Transaction` model**

Create `ltv2/models/transaction.py`:

```python
from datetime import datetime
from decimal import Decimal
from ltv2.extensions import db


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    trade_date = db.Column(db.Date, nullable=False)
    value_date = db.Column(db.Date, nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey("banks.id"), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey("stocks.id"), nullable=False)
    transaction_type_id = db.Column(db.Integer, db.ForeignKey("transaction_types.id"), nullable=False)
    quantity = db.Column(db.Numeric, nullable=False)
    price = db.Column(db.Numeric, nullable=False)
    brokerage = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    commission = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    foreign_charge = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    stamp_duty = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    misc = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    counter_bank_id = db.Column(db.Integer, db.ForeignKey("banks.id"), nullable=True)
    comments = db.Column(db.Text, nullable=True)
    locked = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    bank = db.relationship("Bank", foreign_keys=[bank_id])
    counter_bank = db.relationship("Bank", foreign_keys=[counter_bank_id])
    stock = db.relationship("Stock")
    transaction_type = db.relationship("TransactionType")

    @property
    def total_charges(self) -> Decimal:
        zero = Decimal(0)
        return ((self.brokerage or zero) + (self.commission or zero)
                + (self.foreign_charge or zero) + (self.stamp_duty or zero)
                + (self.misc or zero))
```

- [ ] **Step 4: Register the model**

In `ltv2/models/__init__.py`, add at the end:

```python
from ltv2.models.transaction import Transaction  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_transaction_model.py -v
```
Expected: PASS.

- [ ] **Step 6: Write Migration B**

Create `migrations/versions/b2c3d4e5f6a1_create_transactions_table.py`:

```python
"""create transactions table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column("bank_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("brokerage", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("commission", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("foreign_charge", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("stamp_duty", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("misc", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("counter_bank_id", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"]),
        sa.ForeignKeyConstraint(["counter_bank_id"], ["banks.id"]),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.ForeignKeyConstraint(["transaction_type_id"], ["transaction_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("transactions")
```

- [ ] **Step 7: Verify migration round-trip on a scratch DB**

Run:
```bash
rm -f instance/_scratch_migr.db
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db upgrade
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db current
FLASK_APP=flask_app_v2.py LTV2_DATABASE_URI="sqlite:///instance/_scratch_migr.db" .venv-ltv2/Scripts/python -m flask db downgrade base
rm -f instance/_scratch_migr.db
```
Expected: `db current` reports `b2c3d4e5f6a1 (head)`; clean full downgrade.

- [ ] **Step 8: Apply to the real ltv2 DB**

Run:
```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db upgrade
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db current
```
Expected: `db current` reports `b2c3d4e5f6a1 (head)`.

- [ ] **Step 9: Commit**

```bash
git add ltv2/models/transaction.py ltv2/models/__init__.py migrations/versions/b2c3d4e5f6a1_create_transactions_table.py tests/ltv2/test_transaction_model.py
git commit -m "feat(ltv2): add Transaction model + transactions table migration"
```

---

### Task 5: Position engine — `PositionState`, signed-delta mapping, Case 1 (opening/adding)

Start the pure engine. Define `PositionState`, the `(book, behavior_category) → sign` mapping, the unified `opening_cost` helper, the `_apply` dispatcher handling **only** Case 1 (open or add — `balance == 0` or same-sign delta), and `compute_position` (sort + fold). No Flask, no DB.

**Engine math reference (authoritative — derived from spec §2/§3 worked examples):**
- Signed delta `d`: long {increase +, decrease −, dividend +, transfer_in +, transfer_out −}; short {increase −, decrease +}; neutral → 0. Any other `(book, behavior)` raises `ValueError`.
- `opening_cost = sign_of_new_shares * (qty * price) + charges` — charges always add to basis. (Long buy 100@10 chg5 → 1005; short sell 50@15 chg2 → −748.)
- `closing_cash = sign_of_existing_balance * (qty * price) − charges` — charges always reduce cash. (Used in Tasks 6–7.)
- Note: this corrects a sign typo in the spec §3 Case-3 Step-B inline formula; the spec's worked examples and §2 definitions are the oracle and the tests below encode them.

**Files:**
- Create: `ltv2/services/__init__.py`
- Create: `ltv2/services/positions.py`
- Test: `tests/ltv2/test_position_engine.py`

**Interfaces:**
- Consumes: nothing (pure module).
- Produces:
  - `PositionState(balance: Decimal, cost_basis: Decimal, realized_pnl: Decimal)` dataclass with `.average` property.
  - `compute_position(transactions: list[dict]) -> dict[tuple[int, int, str], PositionState]`.
  - Transaction dict contract (keys): `bank_id: int`, `stock_id: int`, `book: str`, `behavior_category: str`, `quantity: Decimal` (positive magnitude), `price: Decimal`, `charges: Decimal`, `sort_date: datetime.date` (effective date already resolved from the bank's basis by the caller), `priority: int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/ltv2/test_position_engine.py`:

```python
from datetime import date
from decimal import Decimal
import pytest
from ltv2.services.positions import PositionState, compute_position

D = Decimal


def txn(book="long", behavior="increase", qty="100", price="10", charges="0",
        bank_id=1, stock_id=1, sort_date=date(2026, 1, 1), priority=0):
    return {
        "bank_id": bank_id, "stock_id": stock_id, "book": book,
        "behavior_category": behavior, "quantity": D(qty), "price": D(price),
        "charges": D(charges), "sort_date": sort_date, "priority": priority,
    }


def only(positions):
    assert len(positions) == 1
    return next(iter(positions.values()))


def test_single_long_buy():
    s = only(compute_position([txn(qty="100", price="10", charges="5")]))
    assert s.balance == D("100")
    assert s.cost_basis == D("1005")
    assert s.average == D("10.05")
    assert s.realized_pnl == D("0")


def test_single_short_open():
    s = only(compute_position([txn(book="short", behavior="increase",
                                   qty="50", price="15", charges="2")]))
    assert s.balance == D("-50")
    assert s.cost_basis == D("-748")
    assert s.average == D("14.96")
    assert s.realized_pnl == D("0")


def test_two_long_buys_weighted_average():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(qty="100", price="20", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    assert s.balance == D("200")
    assert s.cost_basis == D("3000")
    assert s.average == D("15")


def test_separate_keys_for_each_bank_stock_book():
    positions = compute_position([
        txn(bank_id=1, stock_id=1, book="long"),
        txn(bank_id=2, stock_id=1, book="long"),
        txn(bank_id=1, stock_id=1, book="short", behavior="increase"),
    ])
    assert set(positions.keys()) == {(1, 1, "long"), (2, 1, "long"), (1, 1, "short")}


def test_unsupported_book_behavior_raises():
    with pytest.raises(ValueError):
        compute_position([txn(book="short", behavior="transfer_in")])


def test_neutral_has_no_effect():
    positions = compute_position([txn(behavior="neutral", qty="100")])
    # neutral creates the key but leaves a zero position
    s = only(positions)
    assert s.balance == D("0") and s.cost_basis == D("0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ltv2.services'`.

- [ ] **Step 3: Create the services package**

Create `ltv2/services/__init__.py` as an empty file:

```python
```

- [ ] **Step 4: Implement the engine (Case 1 only)**

Create `ltv2/services/positions.py`:

```python
"""Pure position/P&L engine for the ltv2 trading ledger.

No Flask, no SQLAlchemy session. Folds an ordered list of transaction dicts
into per-(bank_id, stock_id, book) PositionState objects.

Transaction dict keys:
    bank_id: int
    stock_id: int
    book: str                 # "long" | "short"
    behavior_category: str    # increase|decrease|transfer_in|transfer_out|dividend|neutral
    quantity: Decimal         # positive magnitude; direction inferred
    price: Decimal            # per share
    charges: Decimal          # total charges
    sort_date: datetime.date  # effective date (caller resolves trade vs value)
    priority: int             # transaction_type.priority, tiebreaker
"""
from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal(0)

_DELTA_SIGN = {
    ("long", "increase"): 1,
    ("long", "decrease"): -1,
    ("long", "dividend"): 1,
    ("long", "transfer_in"): 1,
    ("long", "transfer_out"): -1,
    ("short", "increase"): -1,
    ("short", "decrease"): 1,
}


@dataclass
class PositionState:
    balance: Decimal = ZERO
    cost_basis: Decimal = ZERO
    realized_pnl: Decimal = ZERO

    @property
    def average(self) -> Decimal:
        return self.cost_basis / self.balance if self.balance != ZERO else ZERO


def _signed_delta(book, behavior, qty):
    if behavior == "neutral":
        return ZERO
    try:
        sign = _DELTA_SIGN[(book, behavior)]
    except KeyError:
        raise ValueError(f"unsupported (book, behavior): ({book!r}, {behavior!r})")
    return Decimal(sign) * qty


def _sign(value):
    return Decimal(1) if value > ZERO else Decimal(-1)


def _apply(state, txn):
    behavior = txn["behavior_category"]
    qty = txn["quantity"]
    price = txn["price"]
    charges = txn["charges"]

    d = _signed_delta(txn["book"], behavior, qty)
    if d == ZERO:
        return

    bal = state.balance
    # Case 1: opening or adding (flat, or delta same sign as balance)
    if bal == ZERO or (d > ZERO) == (bal > ZERO):
        sign_new = _sign(d)
        opening_cost = sign_new * (qty * price) + charges
        state.cost_basis += opening_cost
        state.balance += d
        return

    raise NotImplementedError("reducing/zero-cross cases added in later tasks")


def compute_position(transactions):
    ordered = sorted(transactions, key=lambda t: (t["sort_date"], t["priority"]))
    positions = {}
    for txn in ordered:
        key = (txn["bank_id"], txn["stock_id"], txn["book"])
        state = positions.setdefault(key, PositionState())
        _apply(state, txn)
    return positions
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -v
```
Expected: PASS (all 6 tests). The `NotImplementedError` path is not hit by any Case-1/neutral test.

- [ ] **Step 6: Commit**

```bash
git add ltv2/services/__init__.py ltv2/services/positions.py tests/ltv2/test_position_engine.py
git commit -m "feat(ltv2): position engine — PositionState + Case 1 (open/add)"
```

---

### Task 6: Position engine — Case 2 (reduce without zero-cross)

Add the reduce branch: delta opposite in sign to balance, magnitude `≤ |balance|`. Release proportional cost basis and realize P&L. Covers partial sell, full sell (balance→0), and short partial cover.

**Files:**
- Modify: `ltv2/services/positions.py` (in `_apply`)
- Test: `tests/ltv2/test_position_engine.py` (append)

**Interfaces:**
- Consumes: `PositionState`, `_apply`, `compute_position` (Task 5).
- Produces: no new public names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ltv2/test_position_engine.py`:

```python
def test_long_partial_sell_realizes_pnl():
    s = only(compute_position([
        txn(qty="100", price="10", charges="5", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="40", price="12", charges="3", sort_date=date(2026, 1, 2)),
    ]))
    # released = 40/100 * 1005 = 402 ; closing_cash = 40*12 - 3 = 477
    assert s.realized_pnl == D("75")
    assert s.cost_basis == D("603")
    assert s.balance == D("60")
    assert s.average == D("10.05")


def test_long_full_sell_zeroes_position():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="100", price="12", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    assert s.balance == D("0")
    assert s.cost_basis == D("0")
    assert s.realized_pnl == D("200")  # 1200 - 1000


def test_short_partial_cover_realizes_pnl():
    s = only(compute_position([
        txn(book="short", behavior="increase", qty="50", price="15", charges="2",
            sort_date=date(2026, 1, 1)),
        txn(book="short", behavior="decrease", qty="20", price="14", charges="1",
            sort_date=date(2026, 1, 2)),
    ]))
    # released = 20/50 * -748 = -299.2 ; closing_cash = -(20*14 + 1) = -281
    assert s.realized_pnl == D("18.2")
    assert s.cost_basis == D("-448.8")
    assert s.balance == D("-30")
    assert s.average == D("14.96")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -k "sell or cover" -v
```
Expected: FAIL — `NotImplementedError: reducing/zero-cross cases added in later tasks`.

- [ ] **Step 3: Implement Case 2**

In `ltv2/services/positions.py`, replace the `raise NotImplementedError(...)` line in `_apply` with:

```python
    abs_bal = -bal if bal < ZERO else bal
    # Case 2: reduce without crossing zero
    if qty <= abs_bal:
        sign_bal = _sign(bal)
        closing_cash = sign_bal * (qty * price) - charges
        released = (qty / abs_bal) * state.cost_basis
        state.realized_pnl += closing_cash - released
        state.cost_basis -= released
        state.balance += d
        return

    raise NotImplementedError("zero-cross case added in the next task")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -v
```
Expected: PASS (all Task-5 and Task-6 tests).

- [ ] **Step 5: Commit**

```bash
git add ltv2/services/positions.py tests/ltv2/test_position_engine.py
git commit -m "feat(ltv2): position engine — Case 2 (reduce, no zero-cross)"
```

---

### Task 7: Position engine — Case 3 (zero-crossing)

Add the zero-cross branch: delta opposite in sign to balance, magnitude `> |balance|`. Close the existing position fully (Case-2 math on `close_qty = |balance|`), then open the remainder in the new direction (Case-1 math on `open_qty`), pro-rating charges by quantity. Covers long oversell, oversell→buy-back, and short over-cover.

**Files:**
- Modify: `ltv2/services/positions.py` (in `_apply`)
- Test: `tests/ltv2/test_position_engine.py` (append)

**Interfaces:**
- Consumes: `_apply` (Tasks 5–6).
- Produces: no new public names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ltv2/test_position_engine.py`:

```python
def test_long_oversell_flips_to_short():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="150", price="12", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    # Step A: close 100 @12 -> closing_cash 1200, released 1000, pnl +200
    # Step B: open 50 short within long book @12 -> cost_basis -(50*12) = -600
    assert s.realized_pnl == D("200")
    assert s.balance == D("-50")
    assert s.cost_basis == D("-600")
    assert s.average == D("12")


def test_oversell_then_buyback_crosses_again():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="150", price="12", charges="0", sort_date=date(2026, 1, 2)),
        txn(behavior="increase", qty="80", price="11", charges="0", sort_date=date(2026, 1, 3)),
    ]))
    # After step 2: balance -50, cost_basis -600 (avg 12)
    # Buy 80 (long) vs balance -50: Case 3. Close 50 short @11:
    #   closing_cash = -(50*11) = -550 ; released = -600 ; pnl += -550 -(-600)= +50
    # Open 30 long @11 -> cost_basis +330
    assert s.realized_pnl == D("250")  # 200 + 50
    assert s.balance == D("30")
    assert s.cost_basis == D("330")
    assert s.average == D("11")


def test_short_over_cover_flips_to_long():
    s = only(compute_position([
        txn(book="short", behavior="increase", qty="50", price="15", charges="0",
            sort_date=date(2026, 1, 1)),
        txn(book="short", behavior="decrease", qty="80", price="14", charges="0",
            sort_date=date(2026, 1, 2)),
    ]))
    # Step A: close 50 short @14 -> closing_cash -(50*14) = -700 ; released -750 ; pnl +50
    # Step B: open 30 long within short book @14 -> cost_basis +420
    assert s.realized_pnl == D("50")
    assert s.balance == D("30")
    assert s.cost_basis == D("420")
    assert s.average == D("14")


def test_zero_cross_prorates_charges():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="200", price="12", charges="10", sort_date=date(2026, 1, 2)),
    ]))
    # close_qty 100, open_qty 100 -> charges split 5 / 5
    # Step A: closing_cash = 100*12 - 5 = 1195 ; released 1000 ; pnl +195
    # Step B: open 100 short @12 charges_open 5 -> cost_basis = -(100*12) + 5 = -1195
    assert s.realized_pnl == D("195")
    assert s.balance == D("-100")
    assert s.cost_basis == D("-1195")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -k "oversell or over_cover or prorates" -v
```
Expected: FAIL — `NotImplementedError: zero-cross case added in the next task`.

- [ ] **Step 3: Implement Case 3**

In `ltv2/services/positions.py`, replace the `raise NotImplementedError("zero-cross case added in the next task")` line with:

```python
    # Case 3: zero-crossing (close fully, then open the remainder)
    close_qty = abs_bal
    open_qty = qty - close_qty
    charges_close = charges * (close_qty / qty)
    charges_open = charges * (open_qty / qty)

    # Step A: close the existing position fully
    sign_bal = _sign(bal)
    closing_cash = sign_bal * (close_qty * price) - charges_close
    released = state.cost_basis
    state.realized_pnl += closing_cash - released
    state.cost_basis = ZERO
    state.balance = ZERO

    # Step B: open the remainder in the new direction
    sign_new = _sign(d)
    state.cost_basis = sign_new * (open_qty * price) + charges_open
    state.balance = sign_new * open_qty
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -v
```
Expected: PASS (all engine tests through Task 7).

- [ ] **Step 5: Commit**

```bash
git add ltv2/services/positions.py tests/ltv2/test_position_engine.py
git commit -m "feat(ltv2): position engine — Case 3 (zero-cross)"
```

---

### Task 8: Position engine — dividend, transfer, and ordering

Finish the engine's behaviors: stock dividends add zero-cost shares (lowering the average), transfers move shares between banks at the source average (cost-basis neutral combined), and `compute_position` honors `(sort_date, priority)` ordering so trade-date vs value-date sequencing changes intermediate state.

**Files:**
- Modify: `ltv2/services/positions.py` (dividend branch in `_apply`)
- Test: `tests/ltv2/test_position_engine.py` (append)

**Interfaces:**
- Consumes: `_apply`, `compute_position` (Tasks 5–7).
- Produces: no new public names.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ltv2/test_position_engine.py`:

```python
def test_dividend_lowers_average_without_changing_cost_basis():
    # Non-zero price proves the dividend branch ignores price (no cost added).
    # Without the branch, Case 1 would wrongly add 10*10 = 100 to cost_basis.
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="dividend", qty="10", price="10", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    assert s.balance == D("110")
    assert s.cost_basis == D("1000")
    assert s.realized_pnl == D("0")
    assert s.average == D("1000") / D("110")


def test_transfer_is_cost_basis_neutral_across_banks():
    # Source bank 1 holds 100 @ avg 10 (cost 1000). Transfer 40 out at avg 10;
    # destination bank 2 receives 40 in at the same stamped price 10.
    positions = compute_position([
        txn(bank_id=1, qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(bank_id=1, behavior="transfer_out", qty="40", price="10", charges="0",
            sort_date=date(2026, 1, 2)),
        txn(bank_id=2, behavior="transfer_in", qty="40", price="10", charges="0",
            sort_date=date(2026, 1, 2), priority=1),
    ])
    src = positions[(1, 1, "long")]
    dst = positions[(2, 1, "long")]
    assert src.balance == D("60") and src.cost_basis == D("600")
    assert dst.balance == D("40") and dst.cost_basis == D("400")
    assert src.realized_pnl == D("0")  # transfer at average realizes nothing
    assert src.cost_basis + dst.cost_basis == D("1000")  # combined neutral


def test_ordering_by_sort_date_changes_intermediate_state():
    # Same three trades; only the sell's sort_date differs.
    # Variant A: sell occurs BEFORE the second buy (avg at sell = 10).
    buy1 = txn(qty="100", price="10", sort_date=date(2026, 1, 1), priority=0)
    buy2 = txn(qty="100", price="20", sort_date=date(2026, 1, 3), priority=0)
    sell_early = txn(behavior="decrease", qty="50", price="30",
                     sort_date=date(2026, 1, 2), priority=0)
    a = only(compute_position([buy1, buy2, sell_early]))
    # sell vs 100 @10: released 500, closing_cash 1500, pnl +1000
    assert a.realized_pnl == D("1000")

    # Variant B: sell occurs AFTER the second buy (avg at sell = 15).
    sell_late = txn(behavior="decrease", qty="50", price="30",
                    sort_date=date(2026, 1, 4), priority=0)
    b = only(compute_position([buy1, buy2, sell_late]))
    # sell vs 200 @15: released 750, closing_cash 1500, pnl +750
    assert b.realized_pnl == D("750")
    assert a.realized_pnl != b.realized_pnl


def test_priority_breaks_ties_within_same_date():
    # Same date: a buy (priority 0) must apply before a sell (priority 1).
    s = only(compute_position([
        txn(behavior="decrease", qty="50", price="12", sort_date=date(2026, 1, 1), priority=1),
        txn(qty="100", price="10", sort_date=date(2026, 1, 1), priority=0),
    ]))
    # If ordered correctly: buy 100@10 then sell 50@12 -> balance 50, pnl = 600-500 = 100
    assert s.balance == D("50")
    assert s.realized_pnl == D("100")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -k "dividend or transfer or ordering or priority" -v
```
Expected: FAIL — `test_dividend_lowers_average_without_changing_cost_basis` fails because dividend currently flows through Case 1 and adds `10*10 = 100` to `cost_basis` (asserts 1000, gets 1100). The transfer/ordering/priority tests already pass (Cases 1–3 from Tasks 5–7); the dividend test is the red test driving Step 3.

- [ ] **Step 3: Add the dividend branch**

In `ltv2/services/positions.py`, inside `_apply`, immediately after the `d = _signed_delta(...)` and `if d == ZERO: return` lines and BEFORE the `bal = state.balance` line, insert:

```python
    if behavior == "dividend":
        # Zero-cost shares: add to balance, leave cost_basis untouched.
        state.balance += d
        return
```

- [ ] **Step 4: Run the full engine test file**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_position_engine.py -v
```
Expected: PASS (every engine scenario across Tasks 5–8).

- [ ] **Step 5: Run the entire ltv2 suite to confirm no regressions**

Run:
```bash
.venv-ltv2/Scripts/python -m pytest tests/ltv2/ -v
```
Expected: PASS — all ltv2 tests green (reference models, transaction_types CRUD incl. book, transaction model, engine).

- [ ] **Step 6: Commit**

```bash
git add ltv2/services/positions.py tests/ltv2/test_position_engine.py
git commit -m "feat(ltv2): position engine — dividend, transfer, ordering"
```

---

## Self-Review

**1. Spec coverage (§7 Plan 1 items):**
- Migration A (`book` + `server_default` backfill) → Task 2 ✓
- transaction_types CRUD form `book` field + test update → Task 3 ✓
- Migration B (`transactions` table) + `Transaction` model + `total_charges` → Task 4 ✓
- Engine `ltv2/services/positions.py` (signed delta, 3-case averaging, dividend, transfer) → Tasks 5–8 ✓
- Exhaustive unit tests (spec §6 list: single buy; partial/full sell; oversell; oversell→buyback cross; dividend; short open; short cover; short over-cover; transfer neutral; value vs trade ordering; priority tie-break) → Tasks 5–8 ✓
- Prereq not in spec but required to run migrations (stray alembic head) → Task 1 ✓
- "Definition of done: pre-existing ltv2 suite stays green" → Task 8 Step 5 ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step contains complete code; the engine is built incrementally with explicit `NotImplementedError` guards that each later task removes (intentional, not a placeholder). ✓

**3. Type/name consistency:** `PositionState`, `compute_position`, `_apply`, `_signed_delta`, `_sign`, `_DELTA_SIGN`, `ZERO` consistent across Tasks 5–8. Transaction dict keys (`bank_id`, `stock_id`, `book`, `behavior_category`, `quantity`, `price`, `charges`, `sort_date`, `priority`) consistent between the engine contract and the `txn()` test helper. Revision ids chain `98c3b03d0462` → `a1b2c3d4e5f6` → `b2c3d4e5f6a1`. Model column names match migration column names. ✓

**Note for reviewers:** The engine's `opening_cost`/`closing_cash` formulas were unified to `sign*(qty*price) ± charges` (charges always cost money). This matches every worked example in spec §2/§3 and corrects a charge-sign typo in the spec's §3 Case-3 Step-B inline formula. The tests encode the spec's verified numeric examples as the oracle.
