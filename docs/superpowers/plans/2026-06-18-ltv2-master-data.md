# LTV2 Master Data — Models + Forms/CSRF + Currencies & Banks CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the reference-data layer to ltv2 — the five master-data tables, CSRF-protected forms, an authenticated layout/nav, and full CRUD UI for Currencies and Banks (establishing the reusable CRUD pattern that Plan C replicates for Stocks, Holidays, Transaction Types).

**Architecture:** Builds directly on the merged Foundation (`ltv2/` package, app factory, `db`, Flask-Login auth). Adds SQLAlchemy models for the 5 reference entities (one migration), Flask-WTF for CSRF-protected forms, an authenticated `layout.html` that CRUD pages extend, and two CRUD blueprints (`currencies`, `banks`). "Delete" is soft — a `is_active` toggle — so reference rows are never hard-removed once later tables reference them.

**Tech Stack:** Flask 3.1, Flask-SQLAlchemy 3.1, Flask-Migrate/Alembic, Flask-WTF 1.2 (CSRF + WTForms), Flask-Login, pytest. Python 3.13. Venv `.venv-ltv2`.

## Global Constraints

- **Isolation:** v2 code lives only under `ltv2/`. Never modify `ltv_app/` or `localhost/`. DB is `instance/ltv2.db`; never reference `instance/LTV Stocks.db`.
- **Auth:** all master-data routes require login (`@login_required`); they are NOT admin-only (per the 2-role model, any logged-in User does data entry; admin gates only user-management/lock/settings).
- **Table names:** unprefixed snake_case plurals — `currencies`, `banks`, `stocks`, `holidays`, `transaction_types`.
- **Soft delete:** every reference table has `is_active` (Boolean, not null, default True). The "delete" action toggles `is_active`; no hard DELETE in the UI. List views default to active-only with a `?show=all` toggle.
- **Transaction-type behavior category:** `transaction_types.behavior_category` is a string constrained to exactly: `increase`, `decrease`, `transfer_in`, `transfer_out`, `dividend`, `neutral`. (Defined now; the trading-ledger plan wires the engine to it. Plan B only creates the model + migration; its CRUD is Plan C.)
- **CSRF:** forms are Flask-WTF `FlaskForm` subclasses rendering `{{ form.csrf_token }}`. `CSRFProtect` is initialised in the factory. `TestConfig` already sets `WTF_CSRF_ENABLED = False` so tests post without tokens.
- **Tests:** pytest, isolated in-memory SQLite. Run via `.venv-ltv2/Scripts/python -m pytest`. Every task ends green; do not regress the 21 existing Foundation tests.
- **Validation:** required fields enforced by WTForms validators; unique fields (currency code, bank code) checked in the view with a flashed error (no 500 on duplicate).

---

## File Structure

- `requirements.txt` — add `Flask-WTF==1.2.2`.
- `ltv2/extensions.py` — add `csrf = CSRFProtect()`.
- `ltv2/__init__.py` — init CSRF; register `currencies` + `banks` blueprints.
- `ltv2/models/mixins.py` — `ActiveMixin` (the `is_active` column + `query_active`/`query_all` helpers).
- `ltv2/models/currency.py`, `bank.py`, `stock.py`, `holiday.py`, `transaction_type.py` — the 5 models.
- `ltv2/models/__init__.py` — import all models (Alembic discovery).
- `ltv2/constants.py` — `TRANSACTION_BASES`, `BEHAVIOR_CATEGORIES` tuples.
- `ltv2/templates/layout.html` — authenticated base (extends `base.html`, adds nav + logout).
- `ltv2/templates/index.html` — becomes a simple dashboard extending `layout.html` when logged in.
- `ltv2/blueprints/currencies/__init__.py`, `views.py`, `forms.py`; templates `ltv2/templates/currencies/list.html`, `form.html`.
- `ltv2/blueprints/banks/__init__.py`, `views.py`, `forms.py`; templates `ltv2/templates/banks/list.html`, `form.html`.
- `tests/ltv2/test_reference_models.py`, `test_currencies_crud.py`, `test_banks_crud.py`, `test_csrf_layout.py`.

---

### Task 1: Flask-WTF / CSRF wiring + authenticated layout

**Files:**
- Modify: `requirements.txt`, `ltv2/extensions.py`, `ltv2/__init__.py`
- Create: `ltv2/templates/layout.html`; Modify: `ltv2/templates/index.html`, `ltv2/blueprints/main/views.py`
- Test: `tests/ltv2/test_csrf_layout.py`

**Interfaces:**
- Produces: `ltv2.extensions.csrf` (`CSRFProtect`), initialised on the app. `layout.html` template providing `{% block content %}` and a nav with a Logout link (only the authenticated dashboard for now). `main.index` renders the dashboard.

- [ ] **Step 1: Add Flask-WTF to requirements and install**

Edit `requirements.txt` — add line `Flask-WTF==1.2.2`. Then run:
```bash
.venv-ltv2/Scripts/python -m pip install Flask-WTF==1.2.2
```
Expected: installs Flask-WTF + WTForms.

- [ ] **Step 2: Add CSRF to extensions**

In `ltv2/extensions.py` add:
```python
from flask_wtf import CSRFProtect

csrf = CSRFProtect()
```

- [ ] **Step 3: Write the failing test**

`tests/ltv2/test_csrf_layout.py`:
```python
from ltv2.extensions import db
from ltv2.models.user import User


def _login(client, app):
    u = User(username="alice", email="a@x.com", role="user")
    u.set_password("password123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice", "password": "password123"})


def test_csrf_enabled_in_default_config():
    from ltv2 import create_app
    app = create_app("ltv2.config.DevConfig")
    assert app.config.get("WTF_CSRF_ENABLED", True) is True


def test_dashboard_requires_login(client):
    resp = client.get("/")
    # anonymous → redirected to login
    assert resp.status_code in (301, 302)


def test_dashboard_renders_for_logged_in_user(client, app):
    _login(client, app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Logout" in resp.data
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_csrf_layout.py -v`
Expected: FAIL — index is public and has no Logout link.

- [ ] **Step 5: Init CSRF and make the dashboard auth-gated**

In `ltv2/__init__.py` factory, after `login_manager.init_app(app)` add:
```python
    from ltv2.extensions import csrf
    csrf.init_app(app)
```

`ltv2/templates/layout.html`:
```html
{% extends "base.html" %}
{% block content %}
<nav>
  <a href="{{ url_for('main.index') }}">Dashboard</a>
  {% block nav %}{% endblock %}
  <a href="{{ url_for('auth.logout') }}">Logout</a>
</nav>
<main>{% block main %}{% endblock %}</main>
{% endblock %}
```

`ltv2/templates/index.html`:
```html
{% extends "layout.html" %}
{% block main %}<h1>LTV2 Dashboard</h1>{% endblock %}
```

In `ltv2/blueprints/main/views.py`, gate the index:
```python
from flask_login import login_required

@bp.route("/")
@login_required
def index():
    return render_template("index.html")
```
(Keep `/healthz` public and unchanged.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_csrf_layout.py -v`
Expected: PASS (3 tests). Then run the full suite — fix the one Foundation test that assumed a public `/`:

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/ -q`
If `tests/ltv2/test_app_factory.py::test_index_renders` now fails (index requires login), update it to log in first OR assert the redirect — change it to:
```python
def test_index_redirects_anonymous(client):
    resp = client.get("/")
    assert resp.status_code in (301, 302)
```
Re-run the full suite; expected all green.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt ltv2/extensions.py ltv2/__init__.py ltv2/templates tests/ltv2/test_csrf_layout.py tests/ltv2/test_app_factory.py ltv2/blueprints/main/views.py
git commit -m "feat(ltv2): CSRF + authenticated layout/dashboard"
```

---

### Task 2: Reference-data models + migration

**Files:**
- Create: `ltv2/models/mixins.py`, `ltv2/constants.py`, `ltv2/models/currency.py`, `ltv2/models/bank.py`, `ltv2/models/stock.py`, `ltv2/models/holiday.py`, `ltv2/models/transaction_type.py`
- Modify: `ltv2/models/__init__.py`
- Migration: new Alembic revision creating all 5 tables
- Test: `tests/ltv2/test_reference_models.py`

**Interfaces:**
- Produces these models (all with `id` PK and `is_active` Boolean default True):
  - `Currency(code unique not-null, name, priority int default 0)`
  - `Bank(bank_code unique not-null, name not-null, report_label, transaction_basis in TRANSACTION_BASES default "trade_date", priority int default 0)`
  - `Stock(code unique not-null, company_name, stock_name, yahoo_ticker, security_code, currency_id FK→currencies.id)`
  - `Holiday(currency_id FK→currencies.id not-null, holiday_date Date not-null, UniqueConstraint(currency_id, holiday_date))`
  - `TransactionType(name unique not-null, behavior_category in BEHAVIOR_CATEGORIES not-null, priority int default 0)`
- `ltv2/constants.py`: `TRANSACTION_BASES = ("trade_date", "value_date")`, `BEHAVIOR_CATEGORIES = ("increase","decrease","transfer_in","transfer_out","dividend","neutral")`.

- [ ] **Step 1: Write the failing test**

`tests/ltv2/test_reference_models.py`:
```python
import datetime as dt
import pytest
from ltv2.extensions import db
from ltv2.models.currency import Currency
from ltv2.models.bank import Bank
from ltv2.models.stock import Stock
from ltv2.models.holiday import Holiday
from ltv2.models.transaction_type import TransactionType


def test_currency_create_and_defaults(app):
    c = Currency(code="HKD", name="Hong Kong Dollar")
    db.session.add(c); db.session.commit()
    assert c.id is not None
    assert c.is_active is True
    assert c.priority == 0


def test_currency_code_unique(app):
    db.session.add(Currency(code="HKD", name="x")); db.session.commit()
    db.session.add(Currency(code="HKD", name="y"))
    with pytest.raises(Exception):
        db.session.commit()


def test_bank_transaction_basis_default(app):
    b = Bank(bank_code="CB1", name="Citibank 1")
    db.session.add(b); db.session.commit()
    assert b.transaction_basis == "trade_date"
    assert b.is_active is True


def test_stock_currency_fk(app):
    c = Currency(code="HKD", name="x"); db.session.add(c); db.session.commit()
    s = Stock(code="700", stock_name="Tencent", currency_id=c.id)
    db.session.add(s); db.session.commit()
    assert s.currency_id == c.id


def test_holiday_unique_per_currency_date(app):
    c = Currency(code="HKD", name="x"); db.session.add(c); db.session.commit()
    d = dt.date(2026, 1, 1)
    db.session.add(Holiday(currency_id=c.id, holiday_date=d)); db.session.commit()
    db.session.add(Holiday(currency_id=c.id, holiday_date=d))
    with pytest.raises(Exception):
        db.session.commit()


def test_transaction_type_create(app):
    t = TransactionType(name="Buy (Spot)", behavior_category="increase")
    db.session.add(t); db.session.commit()
    assert t.id is not None
    assert t.behavior_category == "increase"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_reference_models.py -v`
Expected: FAIL — model modules do not exist.

- [ ] **Step 3: Write constants and the ActiveMixin**

`ltv2/constants.py`:
```python
TRANSACTION_BASES = ("trade_date", "value_date")
BEHAVIOR_CATEGORIES = ("increase", "decrease", "transfer_in", "transfer_out", "dividend", "neutral")
```

`ltv2/models/mixins.py`:
```python
from ltv2.extensions import db


class ActiveMixin:
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    @classmethod
    def query_active(cls):
        return cls.query.filter_by(is_active=True)
```

- [ ] **Step 4: Write the five models**

`ltv2/models/currency.py`:
```python
from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Currency(ActiveMixin, db.Model):
    __tablename__ = "currencies"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100))
    priority = db.Column(db.Integer, nullable=False, default=0)
```

`ltv2/models/bank.py`:
```python
from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Bank(ActiveMixin, db.Model):
    __tablename__ = "banks"
    id = db.Column(db.Integer, primary_key=True)
    bank_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    report_label = db.Column(db.String(150))
    transaction_basis = db.Column(db.String(20), nullable=False, default="trade_date")
    priority = db.Column(db.Integer, nullable=False, default=0)
```

`ltv2/models/stock.py`:
```python
from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Stock(ActiveMixin, db.Model):
    __tablename__ = "stocks"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    company_name = db.Column(db.String(150))
    stock_name = db.Column(db.String(150))
    yahoo_ticker = db.Column(db.String(30))
    security_code = db.Column(db.String(30))
    currency_id = db.Column(db.Integer, db.ForeignKey("currencies.id"))
    currency = db.relationship("Currency")
```

`ltv2/models/holiday.py`:
```python
from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Holiday(ActiveMixin, db.Model):
    __tablename__ = "holidays"
    __table_args__ = (db.UniqueConstraint("currency_id", "holiday_date", name="uq_holiday_ccy_date"),)
    id = db.Column(db.Integer, primary_key=True)
    currency_id = db.Column(db.Integer, db.ForeignKey("currencies.id"), nullable=False)
    holiday_date = db.Column(db.Date, nullable=False)
    currency = db.relationship("Currency")
```

`ltv2/models/transaction_type.py`:
```python
from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class TransactionType(ActiveMixin, db.Model):
    __tablename__ = "transaction_types"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    behavior_category = db.Column(db.String(20), nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=0)
```

In `ltv2/models/__init__.py` add imports:
```python
from ltv2.models.user import User  # noqa: F401
from ltv2.models.currency import Currency  # noqa: F401
from ltv2.models.bank import Bank  # noqa: F401
from ltv2.models.stock import Stock  # noqa: F401
from ltv2.models.holiday import Holiday  # noqa: F401
from ltv2.models.transaction_type import TransactionType  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_reference_models.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Generate and apply the migration**

Run:
```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db migrate -m "create reference data tables"
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db upgrade
```
Verify the new revision's `upgrade()` creates all 5 tables with the FKs and the holiday unique constraint, and that `down_revision` points at the users-table revision (`3647ba05c178`). Run the isolation grep:
```bash
grep -rn "LTV Stocks" ltv2/ migrations/versions/ && echo "FOUND — FIX" || echo "clean"
```
Expected: `clean`.

- [ ] **Step 7: Commit**

```bash
git add ltv2/models ltv2/constants.py migrations/versions tests/ltv2/test_reference_models.py
git commit -m "feat(ltv2): reference-data models + migration"
```

---

### Task 3: Currencies CRUD

**Files:**
- Create: `ltv2/blueprints/currencies/__init__.py`, `views.py`, `forms.py`; `ltv2/templates/currencies/list.html`, `form.html`
- Modify: `ltv2/__init__.py` (register blueprint), `ltv2/templates/layout.html` (add nav link)
- Test: `tests/ltv2/test_currencies_crud.py`

**Interfaces:**
- Consumes: `Currency`, `db`, `login_required`.
- Produces routes (all `@login_required`): `GET /currencies/?show=active|all` (list), `GET/POST /currencies/add`, `GET/POST /currencies/<int:cid>/edit`, `POST /currencies/<int:cid>/toggle-active`. `CurrencyForm(FlaskForm)` with `code`, `name`, `priority`.

- [ ] **Step 1: Write the failing test**

`tests/ltv2/test_currencies_crud.py`:
```python
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency


def _login(client, app):
    u = User(username="alice", email="a@x.com", role="user")
    u.set_password("password123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice", "password": "password123"})


def test_list_requires_login(client):
    assert client.get("/currencies/").status_code in (301, 302)


def test_add_currency(client, app):
    _login(client, app)
    resp = client.post("/currencies/add",
                       data={"code": "HKD", "name": "HK Dollar", "priority": "1"},
                       follow_redirects=True)
    assert resp.status_code == 200
    c = Currency.query.filter_by(code="HKD").first()
    assert c is not None and c.name == "HK Dollar"


def test_add_duplicate_code_flashes_error(client, app):
    _login(client, app)
    db.session.add(Currency(code="HKD", name="x")); db.session.commit()
    resp = client.post("/currencies/add",
                       data={"code": "HKD", "name": "dup", "priority": "0"},
                       follow_redirects=True)
    assert b"already exists" in resp.data
    assert Currency.query.filter_by(code="HKD").count() == 1


def test_edit_currency(client, app):
    _login(client, app)
    c = Currency(code="USD", name="old"); db.session.add(c); db.session.commit()
    client.post(f"/currencies/{c.id}/edit",
                data={"code": "USD", "name": "US Dollar", "priority": "2"})
    db.session.refresh(c)
    assert c.name == "US Dollar" and c.priority == 2


def test_toggle_active(client, app):
    _login(client, app)
    c = Currency(code="JPY", name="Yen"); db.session.add(c); db.session.commit()
    client.post(f"/currencies/{c.id}/toggle-active")
    db.session.refresh(c)
    assert c.is_active is False


def test_list_filters_active(client, app):
    _login(client, app)
    db.session.add(Currency(code="HKD", name="a", is_active=True))
    db.session.add(Currency(code="USD", name="b", is_active=False))
    db.session.commit()
    active_only = client.get("/currencies/").data
    assert b"HKD" in active_only and b"USD" not in active_only
    all_rows = client.get("/currencies/?show=all").data
    assert b"HKD" in all_rows and b"USD" in all_rows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_currencies_crud.py -v`
Expected: FAIL — `/currencies/` 404.

- [ ] **Step 3: Write the form**

`ltv2/blueprints/currencies/forms.py`:
```python
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, Length, Optional


class CurrencyForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=10)])
    name = StringField("Name", validators=[Optional(), Length(max=100)])
    priority = IntegerField("Priority", validators=[Optional()], default=0)
```

- [ ] **Step 4: Write the views**

`ltv2/blueprints/currencies/views.py`:
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.currency import Currency
from ltv2.blueprints.currencies.forms import CurrencyForm

bp = Blueprint("currencies", __name__, url_prefix="/currencies")


@bp.route("/")
@login_required
def list_currencies():
    show = request.args.get("show", "active")
    q = Currency.query if show == "all" else Currency.query_active()
    rows = q.order_by(Currency.priority, Currency.code).all()
    return render_template("currencies/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_currency():
    form = CurrencyForm()
    if form.validate_on_submit():
        if Currency.query.filter_by(code=form.code.data).first():
            flash(f"Currency {form.code.data!r} already exists", "error")
            return redirect(url_for("currencies.add_currency"))
        c = Currency(code=form.code.data, name=form.name.data,
                     priority=form.priority.data or 0)
        db.session.add(c); db.session.commit()
        flash("Currency added", "success")
        return redirect(url_for("currencies.list_currencies"))
    return render_template("currencies/form.html", form=form, mode="add")


@bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def edit_currency(cid):
    c = db.get_or_404(Currency, cid)
    form = CurrencyForm(obj=c)
    if form.validate_on_submit():
        existing = Currency.query.filter_by(code=form.code.data).first()
        if existing and existing.id != c.id:
            flash(f"Currency {form.code.data!r} already exists", "error")
            return redirect(url_for("currencies.edit_currency", cid=cid))
        c.code = form.code.data
        c.name = form.name.data
        c.priority = form.priority.data or 0
        db.session.commit()
        flash("Currency updated", "success")
        return redirect(url_for("currencies.list_currencies"))
    return render_template("currencies/form.html", form=form, mode="edit")


@bp.route("/<int:cid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(cid):
    c = db.get_or_404(Currency, cid)
    c.is_active = not c.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("currencies.list_currencies", show=request.args.get("show", "active")))
```

`ltv2/blueprints/currencies/__init__.py`:
```python
from ltv2.blueprints.currencies.views import bp  # noqa: F401
```

- [ ] **Step 5: Write the templates**

`ltv2/templates/currencies/list.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>Currencies</h1>
<a href="{{ url_for('currencies.add_currency') }}">+ Add</a>
<a href="{{ url_for('currencies.list_currencies', show='all' if show!='all' else 'active') }}">
  {{ 'Show active' if show=='all' else 'Show all' }}</a>
<table>
  <tr><th>Code</th><th>Name</th><th>Priority</th><th>Active</th><th></th></tr>
  {% for c in rows %}
  <tr>
    <td>{{ c.code }}</td><td>{{ c.name }}</td><td>{{ c.priority }}</td>
    <td>{{ 'Yes' if c.is_active else 'No' }}</td>
    <td>
      <a href="{{ url_for('currencies.edit_currency', cid=c.id) }}">Edit</a>
      <form method="post" action="{{ url_for('currencies.toggle_active', cid=c.id, show=show) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit">{{ 'Deactivate' if c.is_active else 'Activate' }}</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`ltv2/templates/currencies/form.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>{{ 'Add' if mode=='add' else 'Edit' }} Currency</h1>
<form method="post">
  {{ form.csrf_token }}
  <p>{{ form.code.label }} {{ form.code() }}</p>
  <p>{{ form.name.label }} {{ form.name() }}</p>
  <p>{{ form.priority.label }} {{ form.priority() }}</p>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Register blueprint and add nav link**

In `ltv2/__init__.py` factory, with the other blueprint registrations:
```python
    from ltv2.blueprints.currencies import bp as currencies_bp
    app.register_blueprint(currencies_bp)
```

In `ltv2/templates/layout.html`, inside `{% block nav %}{% endblock %}` replace with:
```html
{% block nav %}<a href="{{ url_for('currencies.list_currencies') }}">Currencies</a>{% endblock %}
```
(Note: keep it as a default that section templates may override; the dashboard shows it too.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_currencies_crud.py -v`
Expected: PASS (6 tests). Then full suite green.

- [ ] **Step 8: Commit**

```bash
git add ltv2/blueprints/currencies ltv2/templates/currencies ltv2/__init__.py ltv2/templates/layout.html tests/ltv2/test_currencies_crud.py
git commit -m "feat(ltv2): currencies CRUD"
```

---

### Task 4: Banks CRUD

**Files:**
- Create: `ltv2/blueprints/banks/__init__.py`, `views.py`, `forms.py`; `ltv2/templates/banks/list.html`, `form.html`
- Modify: `ltv2/__init__.py` (register blueprint), `ltv2/templates/layout.html` (add nav link)
- Test: `tests/ltv2/test_banks_crud.py`

**Interfaces:**
- Consumes: `Bank`, `db`, `login_required`, `TRANSACTION_BASES`.
- Produces routes (all `@login_required`): `GET /banks/?show=active|all`, `GET/POST /banks/add`, `GET/POST /banks/<int:bid>/edit`, `POST /banks/<int:bid>/toggle-active`. `BankForm(FlaskForm)` with `bank_code`, `name`, `report_label`, `transaction_basis` (SelectField from TRANSACTION_BASES), `priority`.

- [ ] **Step 1: Write the failing test**

`tests/ltv2/test_banks_crud.py`:
```python
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.bank import Bank


def _login(client, app):
    u = User(username="alice", email="a@x.com", role="user")
    u.set_password("password123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice", "password": "password123"})


def test_list_requires_login(client):
    assert client.get("/banks/").status_code in (301, 302)


def test_add_bank(client, app):
    _login(client, app)
    resp = client.post("/banks/add", data={
        "bank_code": "CB1", "name": "Citibank 1", "report_label": "Citi 1",
        "transaction_basis": "value_date", "priority": "1"}, follow_redirects=True)
    assert resp.status_code == 200
    b = Bank.query.filter_by(bank_code="CB1").first()
    assert b is not None and b.transaction_basis == "value_date"


def test_add_duplicate_bank_code_flashes(client, app):
    _login(client, app)
    db.session.add(Bank(bank_code="CB1", name="x")); db.session.commit()
    resp = client.post("/banks/add", data={
        "bank_code": "CB1", "name": "dup", "transaction_basis": "trade_date",
        "priority": "0"}, follow_redirects=True)
    assert b"already exists" in resp.data
    assert Bank.query.filter_by(bank_code="CB1").count() == 1


def test_invalid_transaction_basis_rejected(client, app):
    _login(client, app)
    client.post("/banks/add", data={
        "bank_code": "CB9", "name": "x", "transaction_basis": "bogus",
        "priority": "0"})
    assert Bank.query.filter_by(bank_code="CB9").first() is None


def test_edit_bank(client, app):
    _login(client, app)
    b = Bank(bank_code="DB1", name="old"); db.session.add(b); db.session.commit()
    client.post(f"/banks/{b.id}/edit", data={
        "bank_code": "DB1", "name": "Deutsche 1", "report_label": "",
        "transaction_basis": "trade_date", "priority": "3"})
    db.session.refresh(b)
    assert b.name == "Deutsche 1" and b.priority == 3


def test_toggle_active(client, app):
    _login(client, app)
    b = Bank(bank_code="MS1", name="Morgan"); db.session.add(b); db.session.commit()
    client.post(f"/banks/{b.id}/toggle-active")
    db.session.refresh(b)
    assert b.is_active is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_banks_crud.py -v`
Expected: FAIL — `/banks/` 404.

- [ ] **Step 3: Write the form**

`ltv2/blueprints/banks/forms.py`:
```python
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, Optional
from ltv2.constants import TRANSACTION_BASES


class BankForm(FlaskForm):
    bank_code = StringField("Bank Code", validators=[DataRequired(), Length(max=20)])
    name = StringField("Name", validators=[DataRequired(), Length(max=150)])
    report_label = StringField("Report Label", validators=[Optional(), Length(max=150)])
    transaction_basis = SelectField("Transaction Basis",
                                    choices=[(b, b) for b in TRANSACTION_BASES])
    priority = IntegerField("Priority", validators=[Optional()], default=0)
```

- [ ] **Step 4: Write the views**

`ltv2/blueprints/banks/views.py`:
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.bank import Bank
from ltv2.blueprints.banks.forms import BankForm

bp = Blueprint("banks", __name__, url_prefix="/banks")


@bp.route("/")
@login_required
def list_banks():
    show = request.args.get("show", "active")
    q = Bank.query if show == "all" else Bank.query_active()
    rows = q.order_by(Bank.priority, Bank.bank_code).all()
    return render_template("banks/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_bank():
    form = BankForm()
    if form.validate_on_submit():
        if Bank.query.filter_by(bank_code=form.bank_code.data).first():
            flash(f"Bank {form.bank_code.data!r} already exists", "error")
            return redirect(url_for("banks.add_bank"))
        b = Bank(bank_code=form.bank_code.data, name=form.name.data,
                 report_label=form.report_label.data,
                 transaction_basis=form.transaction_basis.data,
                 priority=form.priority.data or 0)
        db.session.add(b); db.session.commit()
        flash("Bank added", "success")
        return redirect(url_for("banks.list_banks"))
    return render_template("banks/form.html", form=form, mode="add")


@bp.route("/<int:bid>/edit", methods=["GET", "POST"])
@login_required
def edit_bank(bid):
    b = db.get_or_404(Bank, bid)
    form = BankForm(obj=b)
    if form.validate_on_submit():
        existing = Bank.query.filter_by(bank_code=form.bank_code.data).first()
        if existing and existing.id != b.id:
            flash(f"Bank {form.bank_code.data!r} already exists", "error")
            return redirect(url_for("banks.edit_bank", bid=bid))
        b.bank_code = form.bank_code.data
        b.name = form.name.data
        b.report_label = form.report_label.data
        b.transaction_basis = form.transaction_basis.data
        b.priority = form.priority.data or 0
        db.session.commit()
        flash("Bank updated", "success")
        return redirect(url_for("banks.list_banks"))
    return render_template("banks/form.html", form=form, mode="edit")


@bp.route("/<int:bid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(bid):
    b = db.get_or_404(Bank, bid)
    b.is_active = not b.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("banks.list_banks", show=request.args.get("show", "active")))
```

`ltv2/blueprints/banks/__init__.py`:
```python
from ltv2.blueprints.banks.views import bp  # noqa: F401
```

- [ ] **Step 5: Write the templates**

`ltv2/templates/banks/list.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>Banks</h1>
<a href="{{ url_for('banks.add_bank') }}">+ Add</a>
<a href="{{ url_for('banks.list_banks', show='all' if show!='all' else 'active') }}">
  {{ 'Show active' if show=='all' else 'Show all' }}</a>
<table>
  <tr><th>Code</th><th>Name</th><th>Label</th><th>Basis</th><th>Priority</th><th>Active</th><th></th></tr>
  {% for b in rows %}
  <tr>
    <td>{{ b.bank_code }}</td><td>{{ b.name }}</td><td>{{ b.report_label }}</td>
    <td>{{ b.transaction_basis }}</td><td>{{ b.priority }}</td>
    <td>{{ 'Yes' if b.is_active else 'No' }}</td>
    <td>
      <a href="{{ url_for('banks.edit_bank', bid=b.id) }}">Edit</a>
      <form method="post" action="{{ url_for('banks.toggle_active', bid=b.id, show=show) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit">{{ 'Deactivate' if b.is_active else 'Activate' }}</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`ltv2/templates/banks/form.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>{{ 'Add' if mode=='add' else 'Edit' }} Bank</h1>
<form method="post">
  {{ form.csrf_token }}
  <p>{{ form.bank_code.label }} {{ form.bank_code() }}</p>
  <p>{{ form.name.label }} {{ form.name() }}</p>
  <p>{{ form.report_label.label }} {{ form.report_label() }}</p>
  <p>{{ form.transaction_basis.label }} {{ form.transaction_basis() }}</p>
  <p>{{ form.priority.label }} {{ form.priority() }}</p>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Register blueprint and add nav link**

In `ltv2/__init__.py`:
```python
    from ltv2.blueprints.banks import bp as banks_bp
    app.register_blueprint(banks_bp)
```

In `ltv2/templates/layout.html`, extend the nav block to include both links:
```html
{% block nav %}
<a href="{{ url_for('currencies.list_currencies') }}">Currencies</a>
<a href="{{ url_for('banks.list_banks') }}">Banks</a>
{% endblock %}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_banks_crud.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Run the FULL suite**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/ -q`
Expected: all green (21 Foundation + new reference/CRUD/CSRF tests).

- [ ] **Step 9: Commit**

```bash
git add ltv2/blueprints/banks ltv2/templates/banks ltv2/__init__.py ltv2/templates/layout.html tests/ltv2/test_banks_crud.py
git commit -m "feat(ltv2): banks CRUD"
```

---

## Self-Review (author checklist — completed)

- **Spec coverage:** full-CRUD master data — models for all 5 entities ✅ (Task 2); CSRF on forms ✅ (Task 1 + form templates render `csrf_token`); soft-delete via `is_active` toggle ✅ (Tasks 3–4); collapse of v1's duplicate bank/bank_accounts into one `banks` table ✅ (Task 2); transaction-type behavior_category constrained set defined ✅ (Task 2 + constants); login-gated, not admin-only ✅.
- **Deferred to Plan C:** CRUD UI for Stocks (FK to currency), Holidays (FK + unique date), Transaction Types (behavior_category select) — the models already exist after Task 2, so Plan C is pure CRUD-pattern replication.
- **Placeholder scan:** no placeholders — every step has complete code. (The earlier dead `csrf_token_field() if false` expression in currencies list.html was removed during self-review; toggle forms post a plain hidden `csrf_token` input.)
- **Type consistency:** `Currency`/`Bank` model fields, `query_active()` classmethod, `TRANSACTION_BASES`/`BEHAVIOR_CATEGORIES`, blueprint endpoint names (`currencies.list_currencies`, `banks.list_banks`, etc.), and `db.get_or_404` used consistently. SelectField validates `transaction_basis` against `TRANSACTION_BASES` (WTForms rejects out-of-choices values → covered by `test_invalid_transaction_basis_rejected`).

## Verification (end-to-end, manual)

```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db upgrade
.venv-ltv2/Scripts/python flask_app_v2.py   # http://<lan-ip>:5002
```
Log in, open `/currencies/` → add HKD/USD, edit one, deactivate one, toggle "Show all". Open `/banks/` → add a bank with each transaction_basis, edit, deactivate. Confirm a duplicate code flashes "already exists" rather than 500.
