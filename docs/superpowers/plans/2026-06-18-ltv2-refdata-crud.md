# LTV2 Reference-Data CRUD — Stocks, Holidays, Transaction Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the master-data CRUD surface by adding list/add/edit/soft-delete UI for the remaining three reference entities — Stocks, Holidays, and Transaction Types — reusing the canonical Banks CRUD pattern.

**Architecture:** Builds on the merged master-data layer (Plan B). The models already exist (`Stock`, `Holiday`, `TransactionType`); this plan adds one CRUD blueprint per entity (`stocks`, `holidays`, `transaction_types`) with Flask-WTF forms, templates, blueprint registration, and nav links — mirroring the `banks` blueprint exactly. The two new wrinkles over Banks: (1) a **dynamic FK SelectField** for `currency` (Stocks, Holidays), whose choices are populated from active currencies in the view; (2) Holidays uses **add + toggle (no edit)** since a holiday is just a currency+date, and a constrained **behavior_category** SelectField for Transaction Types.

**Tech Stack:** Flask 3.1, Flask-SQLAlchemy 3.1, Flask-WTF 1.2 (WTForms), Flask-Login, pytest. Python 3.13. Venv `.venv-ltv2`.

## Global Constraints

- **Isolation:** v2 code only under `ltv2/`. Never modify `ltv_app/`/`localhost/`. DB `instance/ltv2.db` only; never reference `instance/LTV Stocks.db`.
- **Auth:** all routes `@login_required`, NOT admin-only.
- **Canonical pattern = `banks`:** mirror `ltv2/blueprints/banks/` (views, form, templates) including the established improvements — `priority = form.priority.data if form.priority.data is not None else 0`; a `logged_in_client` pytest fixture (unique username per test file to avoid collision); toggle-active is **POST-only** with a hidden `csrf_token` and a hidden `<input name="show">` read via `request.form`; an `edit_same_*_no_error` regression test for entities that have an edit route.
- **Soft delete:** `is_active` toggle; list defaults active-only with `?show=all`.
- **Duplicate handling:** unique fields (stock `code`, transaction-type `name`, holiday `currency_id`+`holiday_date`) → flash "already exists", no dup row, no 500; edit paths exclude self.
- **behavior_category:** Transaction-type `behavior_category` is a SelectField constrained to `BEHAVIOR_CATEGORIES` (from `ltv2/constants.py`).
- **CSRF:** forms are FlaskForm rendering `{{ form.csrf_token }}`. `TestConfig` already disables CSRF for tests.
- **Tests:** pytest, in-memory SQLite, via `.venv-ltv2/Scripts/python -m pytest`. Don't regress the 46 existing tests.

---

## File Structure

- `ltv2/blueprints/stocks/__init__.py`, `views.py`, `forms.py`; templates `ltv2/templates/stocks/list.html`, `form.html`.
- `ltv2/blueprints/holidays/__init__.py`, `views.py`, `forms.py`; templates `ltv2/templates/holidays/list.html`, `form.html`.
- `ltv2/blueprints/transaction_types/__init__.py`, `views.py`, `forms.py`; templates `ltv2/templates/transaction_types/list.html`, `form.html`.
- Modify: `ltv2/__init__.py` (register 3 blueprints), `ltv2/templates/layout.html` (add 3 nav links).
- Tests: `tests/ltv2/test_stocks_crud.py`, `test_holidays_crud.py`, `test_transaction_types_crud.py`.

---

### Task 1: Stocks CRUD

**Files:**
- Create: `ltv2/blueprints/stocks/__init__.py`, `views.py`, `forms.py`; `ltv2/templates/stocks/list.html`, `form.html`
- Modify: `ltv2/__init__.py`, `ltv2/templates/layout.html`
- Test: `tests/ltv2/test_stocks_crud.py`

**Interfaces:**
- Consumes: `Stock`, `Currency`, `db`, `login_required`.
- Produces routes (all `@login_required`): `GET /stocks/?show=active|all`, `GET/POST /stocks/add`, `GET/POST /stocks/<int:sid>/edit`, `POST /stocks/<int:sid>/toggle-active`. `StockForm(FlaskForm)` with `code`, `company_name`, `stock_name`, `yahoo_ticker`, `security_code`, `currency_id` (SelectField, coerce=int, choices set in view from active currencies).

- [ ] **Step 1: Write the failing test**

`tests/ltv2/test_stocks_crud.py`:
```python
import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency
from ltv2.models.stock import Stock


@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_stk", email="s@x.com", role="user")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"username": "alice_stk", "password": "password123"})
    return client


def _currency(app, code="HKD"):
    with app.app_context():
        c = Currency(code=code, name=code)
        db.session.add(c)
        db.session.commit()
        return c.id


def test_list_requires_login(client):
    assert client.get("/stocks/").status_code in (301, 302)


def test_add_stock(logged_in_client, app):
    cid = _currency(app)
    resp = logged_in_client.post("/stocks/add", data={
        "code": "700", "company_name": "Tencent Holdings", "stock_name": "Tencent",
        "yahoo_ticker": "0700.HK", "security_code": "", "currency_id": str(cid),
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        s = Stock.query.filter_by(code="700").first()
        assert s is not None and s.currency_id == cid


def test_add_duplicate_code_flashes(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Stock(code="700", stock_name="x", currency_id=cid))
        db.session.commit()
    resp = logged_in_client.post("/stocks/add", data={
        "code": "700", "company_name": "", "stock_name": "dup",
        "yahoo_ticker": "", "security_code": "", "currency_id": str(cid),
    }, follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert Stock.query.filter_by(code="700").count() == 1


def test_edit_stock(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        s = Stock(code="5", stock_name="old", currency_id=cid)
        db.session.add(s); db.session.commit()
        sid = s.id
    logged_in_client.post(f"/stocks/{sid}/edit", data={
        "code": "5", "company_name": "HSBC Holdings", "stock_name": "HSBC",
        "yahoo_ticker": "0005.HK", "security_code": "", "currency_id": str(cid),
    })
    with app.app_context():
        s = db.session.get(Stock, sid)
        assert s.stock_name == "HSBC"


def test_edit_same_code_no_error(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        s = Stock(code="9", stock_name="orig", currency_id=cid)
        db.session.add(s); db.session.commit()
        sid = s.id
    resp = logged_in_client.post(f"/stocks/{sid}/edit", data={
        "code": "9", "company_name": "", "stock_name": "renamed",
        "yahoo_ticker": "", "security_code": "", "currency_id": str(cid),
    }, follow_redirects=True)
    assert b"already exists" not in resp.data
    with app.app_context():
        assert db.session.get(Stock, sid).stock_name == "renamed"


def test_toggle_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        s = Stock(code="1", stock_name="CKH", currency_id=cid)
        db.session.add(s); db.session.commit()
        sid = s.id
    resp = logged_in_client.post(f"/stocks/{sid}/toggle-active", data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(Stock, sid).is_active is False


def test_list_filters_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Stock(code="700", stock_name="a", currency_id=cid, is_active=True))
        db.session.add(Stock(code="5", stock_name="b", currency_id=cid, is_active=False))
        db.session.commit()
    active = logged_in_client.get("/stocks/").data
    assert b"700" in active and b">5<" not in active
    allrows = logged_in_client.get("/stocks/?show=all").data
    assert b"700" in allrows and b">5<" in allrows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_stocks_crud.py -v`
Expected: FAIL — `/stocks/` 404.

- [ ] **Step 3: Write the form**

`ltv2/blueprints/stocks/forms.py`:
```python
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired, Length, Optional


class StockForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(max=20)])
    company_name = StringField("Company Name", validators=[Optional(), Length(max=150)])
    stock_name = StringField("Stock Name", validators=[Optional(), Length(max=150)])
    yahoo_ticker = StringField("Yahoo Ticker", validators=[Optional(), Length(max=30)])
    security_code = StringField("Security Code", validators=[Optional(), Length(max=30)])
    currency_id = SelectField("Currency", coerce=int, validators=[DataRequired()])
```

- [ ] **Step 4: Write the views**

`ltv2/blueprints/stocks/views.py`:
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.stock import Stock
from ltv2.models.currency import Currency
from ltv2.blueprints.stocks.forms import StockForm

bp = Blueprint("stocks", __name__, url_prefix="/stocks")


def _currency_choices():
    return [(c.id, c.code) for c in Currency.query_active().order_by(Currency.code).all()]


@bp.route("/")
@login_required
def list_stocks():
    show = request.args.get("show", "active")
    q = Stock.query if show == "all" else Stock.query_active()
    rows = q.order_by(Stock.code).all()
    return render_template("stocks/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_stock():
    form = StockForm()
    form.currency_id.choices = _currency_choices()
    if form.validate_on_submit():
        if Stock.query.filter_by(code=form.code.data).first():
            flash(f"Stock {form.code.data!r} already exists", "error")
            return redirect(url_for("stocks.add_stock"))
        s = Stock(code=form.code.data, company_name=form.company_name.data,
                  stock_name=form.stock_name.data, yahoo_ticker=form.yahoo_ticker.data,
                  security_code=form.security_code.data, currency_id=form.currency_id.data)
        db.session.add(s); db.session.commit()
        flash("Stock added", "success")
        return redirect(url_for("stocks.list_stocks"))
    return render_template("stocks/form.html", form=form, mode="add")


@bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit_stock(sid):
    s = db.get_or_404(Stock, sid)
    form = StockForm(obj=s)
    form.currency_id.choices = _currency_choices()
    if form.validate_on_submit():
        existing = Stock.query.filter_by(code=form.code.data).first()
        if existing and existing.id != s.id:
            flash(f"Stock {form.code.data!r} already exists", "error")
            return redirect(url_for("stocks.edit_stock", sid=sid))
        s.code = form.code.data
        s.company_name = form.company_name.data
        s.stock_name = form.stock_name.data
        s.yahoo_ticker = form.yahoo_ticker.data
        s.security_code = form.security_code.data
        s.currency_id = form.currency_id.data
        db.session.commit()
        flash("Stock updated", "success")
        return redirect(url_for("stocks.list_stocks"))
    return render_template("stocks/form.html", form=form, mode="edit")


@bp.route("/<int:sid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(sid):
    s = db.get_or_404(Stock, sid)
    s.is_active = not s.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("stocks.list_stocks", show=request.form.get("show", "active")))
```

`ltv2/blueprints/stocks/__init__.py`:
```python
from ltv2.blueprints.stocks.views import bp  # noqa: F401
```

- [ ] **Step 5: Write the templates**

`ltv2/templates/stocks/list.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>Stocks</h1>
<a href="{{ url_for('stocks.add_stock') }}">+ Add</a>
<a href="{{ url_for('stocks.list_stocks', show='all' if show!='all' else 'active') }}">
  {{ 'Show active' if show=='all' else 'Show all' }}</a>
<table>
  <tr><th>Code</th><th>Company</th><th>Stock</th><th>Yahoo</th><th>Currency</th><th>Active</th><th></th></tr>
  {% for s in rows %}
  <tr>
    <td>{{ s.code }}</td><td>{{ s.company_name }}</td><td>{{ s.stock_name }}</td>
    <td>{{ s.yahoo_ticker }}</td><td>{{ s.currency.code if s.currency }}</td>
    <td>{{ 'Yes' if s.is_active else 'No' }}</td>
    <td>
      <a href="{{ url_for('stocks.edit_stock', sid=s.id) }}">Edit</a>
      <form method="post" action="{{ url_for('stocks.toggle_active', sid=s.id) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="show" value="{{ show }}">
        <button type="submit">{{ 'Deactivate' if s.is_active else 'Activate' }}</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`ltv2/templates/stocks/form.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>{{ 'Add' if mode=='add' else 'Edit' }} Stock</h1>
<form method="post">
  {{ form.csrf_token }}
  <p>{{ form.code.label }} {{ form.code() }}</p>
  <p>{{ form.company_name.label }} {{ form.company_name() }}</p>
  <p>{{ form.stock_name.label }} {{ form.stock_name() }}</p>
  <p>{{ form.yahoo_ticker.label }} {{ form.yahoo_ticker() }}</p>
  <p>{{ form.security_code.label }} {{ form.security_code() }}</p>
  <p>{{ form.currency_id.label }} {{ form.currency_id() }}</p>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Register blueprint and add nav link**

In `ltv2/__init__.py`:
```python
    from ltv2.blueprints.stocks import bp as stocks_bp
    app.register_blueprint(stocks_bp)
```

In `ltv2/templates/layout.html`, add inside the `{% block nav %}` (after Banks):
```html
<a href="{{ url_for('stocks.list_stocks') }}">Stocks</a>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_stocks_crud.py -v`
Expected: PASS (7 tests). Then full suite green.

- [ ] **Step 8: Commit**

```bash
git add ltv2/blueprints/stocks ltv2/templates/stocks ltv2/__init__.py ltv2/templates/layout.html tests/ltv2/test_stocks_crud.py
git commit -m "feat(ltv2): stocks CRUD"
```

---

### Task 2: Holidays CRUD (add + toggle, no edit)

**Files:**
- Create: `ltv2/blueprints/holidays/__init__.py`, `views.py`, `forms.py`; `ltv2/templates/holidays/list.html`, `form.html`
- Modify: `ltv2/__init__.py`, `ltv2/templates/layout.html`
- Test: `tests/ltv2/test_holidays_crud.py`

**Interfaces:**
- Consumes: `Holiday`, `Currency`, `db`, `login_required`.
- Produces routes (all `@login_required`): `GET /holidays/?show=active|all`, `GET/POST /holidays/add`, `POST /holidays/<int:hid>/toggle-active`. `HolidayForm(FlaskForm)` with `currency_id` (SelectField coerce=int, required, active currencies) and `holiday_date` (DateField, required). **No edit route** — a holiday is a (currency, date) pair; changing it is a deactivate + add. The unique constraint `(currency_id, holiday_date)` is enforced with a flashed "already exists".

- [ ] **Step 1: Write the failing test**

`tests/ltv2/test_holidays_crud.py`:
```python
import datetime as dt
import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency
from ltv2.models.holiday import Holiday


@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_hol", email="h@x.com", role="user")
        u.set_password("password123")
        db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice_hol", "password": "password123"})
    return client


def _currency(app, code="HKD"):
    with app.app_context():
        c = Currency(code=code, name=code); db.session.add(c); db.session.commit()
        return c.id


def test_list_requires_login(client):
    assert client.get("/holidays/").status_code in (301, 302)


def test_add_holiday(logged_in_client, app):
    cid = _currency(app)
    resp = logged_in_client.post("/holidays/add", data={
        "currency_id": str(cid), "holiday_date": "2026-01-01"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        h = Holiday.query.filter_by(currency_id=cid).first()
        assert h is not None and h.holiday_date == dt.date(2026, 1, 1)


def test_add_duplicate_flashes(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Holiday(currency_id=cid, holiday_date=dt.date(2026, 1, 1)))
        db.session.commit()
    resp = logged_in_client.post("/holidays/add", data={
        "currency_id": str(cid), "holiday_date": "2026-01-01"}, follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert Holiday.query.filter_by(currency_id=cid).count() == 1


def test_toggle_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        h = Holiday(currency_id=cid, holiday_date=dt.date(2026, 5, 1))
        db.session.add(h); db.session.commit()
        hid = h.id
    resp = logged_in_client.post(f"/holidays/{hid}/toggle-active", data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(Holiday, hid).is_active is False


def test_list_filters_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Holiday(currency_id=cid, holiday_date=dt.date(2026, 1, 1), is_active=True))
        db.session.add(Holiday(currency_id=cid, holiday_date=dt.date(2026, 2, 2), is_active=False))
        db.session.commit()
    active = logged_in_client.get("/holidays/").data
    assert b"2026-01-01" in active and b"2026-02-02" not in active
    allrows = logged_in_client.get("/holidays/?show=all").data
    assert b"2026-01-01" in allrows and b"2026-02-02" in allrows
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_holidays_crud.py -v`
Expected: FAIL — `/holidays/` 404.

- [ ] **Step 3: Write the form**

`ltv2/blueprints/holidays/forms.py`:
```python
from flask_wtf import FlaskForm
from wtforms import SelectField, DateField
from wtforms.validators import DataRequired


class HolidayForm(FlaskForm):
    currency_id = SelectField("Currency", coerce=int, validators=[DataRequired()])
    holiday_date = DateField("Holiday Date", validators=[DataRequired()])
```

- [ ] **Step 4: Write the views**

`ltv2/blueprints/holidays/views.py`:
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.holiday import Holiday
from ltv2.models.currency import Currency
from ltv2.blueprints.holidays.forms import HolidayForm

bp = Blueprint("holidays", __name__, url_prefix="/holidays")


def _currency_choices():
    return [(c.id, c.code) for c in Currency.query_active().order_by(Currency.code).all()]


@bp.route("/")
@login_required
def list_holidays():
    show = request.args.get("show", "active")
    q = Holiday.query if show == "all" else Holiday.query_active()
    rows = q.order_by(Holiday.holiday_date).all()
    return render_template("holidays/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_holiday():
    form = HolidayForm()
    form.currency_id.choices = _currency_choices()
    if form.validate_on_submit():
        dup = Holiday.query.filter_by(currency_id=form.currency_id.data,
                                      holiday_date=form.holiday_date.data).first()
        if dup:
            flash("Holiday already exists for that currency and date", "error")
            return redirect(url_for("holidays.add_holiday"))
        h = Holiday(currency_id=form.currency_id.data, holiday_date=form.holiday_date.data)
        db.session.add(h); db.session.commit()
        flash("Holiday added", "success")
        return redirect(url_for("holidays.list_holidays"))
    return render_template("holidays/form.html", form=form)


@bp.route("/<int:hid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(hid):
    h = db.get_or_404(Holiday, hid)
    h.is_active = not h.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("holidays.list_holidays", show=request.form.get("show", "active")))
```

`ltv2/blueprints/holidays/__init__.py`:
```python
from ltv2.blueprints.holidays.views import bp  # noqa: F401
```

- [ ] **Step 5: Write the templates**

`ltv2/templates/holidays/list.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>Holidays</h1>
<a href="{{ url_for('holidays.add_holiday') }}">+ Add</a>
<a href="{{ url_for('holidays.list_holidays', show='all' if show!='all' else 'active') }}">
  {{ 'Show active' if show=='all' else 'Show all' }}</a>
<table>
  <tr><th>Currency</th><th>Date</th><th>Active</th><th></th></tr>
  {% for h in rows %}
  <tr>
    <td>{{ h.currency.code if h.currency }}</td>
    <td>{{ h.holiday_date.isoformat() }}</td>
    <td>{{ 'Yes' if h.is_active else 'No' }}</td>
    <td>
      <form method="post" action="{{ url_for('holidays.toggle_active', hid=h.id) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="show" value="{{ show }}">
        <button type="submit">{{ 'Deactivate' if h.is_active else 'Activate' }}</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`ltv2/templates/holidays/form.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>Add Holiday</h1>
<form method="post">
  {{ form.csrf_token }}
  <p>{{ form.currency_id.label }} {{ form.currency_id() }}</p>
  <p>{{ form.holiday_date.label }} {{ form.holiday_date() }}</p>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Register blueprint and add nav link**

In `ltv2/__init__.py`:
```python
    from ltv2.blueprints.holidays import bp as holidays_bp
    app.register_blueprint(holidays_bp)
```

In `ltv2/templates/layout.html`, add inside `{% block nav %}` (after Stocks):
```html
<a href="{{ url_for('holidays.list_holidays') }}">Holidays</a>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_holidays_crud.py -v`
Expected: PASS (5 tests). Then full suite green.

- [ ] **Step 8: Commit**

```bash
git add ltv2/blueprints/holidays ltv2/templates/holidays ltv2/__init__.py ltv2/templates/layout.html tests/ltv2/test_holidays_crud.py
git commit -m "feat(ltv2): holidays CRUD (add/toggle)"
```

---

### Task 3: Transaction Types CRUD

**Files:**
- Create: `ltv2/blueprints/transaction_types/__init__.py`, `views.py`, `forms.py`; `ltv2/templates/transaction_types/list.html`, `form.html`
- Modify: `ltv2/__init__.py`, `ltv2/templates/layout.html`
- Test: `tests/ltv2/test_transaction_types_crud.py`

**Interfaces:**
- Consumes: `TransactionType`, `db`, `login_required`, `BEHAVIOR_CATEGORIES`.
- Produces routes (all `@login_required`): `GET /transaction-types/?show=active|all`, `GET/POST /transaction-types/add`, `GET/POST /transaction-types/<int:tid>/edit`, `POST /transaction-types/<int:tid>/toggle-active`. `TransactionTypeForm(FlaskForm)` with `name`, `behavior_category` (SelectField from BEHAVIOR_CATEGORIES), `priority`.

- [ ] **Step 1: Write the failing test**

`tests/ltv2/test_transaction_types_crud.py`:
```python
import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.transaction_type import TransactionType


@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_tt", email="t@x.com", role="user")
        u.set_password("password123")
        db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice_tt", "password": "password123"})
    return client


def test_list_requires_login(client):
    assert client.get("/transaction-types/").status_code in (301, 302)


def test_add_transaction_type(logged_in_client, app):
    resp = logged_in_client.post("/transaction-types/add", data={
        "name": "Buy (Spot)", "behavior_category": "increase", "priority": "1"},
        follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        t = TransactionType.query.filter_by(name="Buy (Spot)").first()
        assert t is not None and t.behavior_category == "increase"


def test_invalid_behavior_category_rejected(logged_in_client, app):
    logged_in_client.post("/transaction-types/add", data={
        "name": "Bogus", "behavior_category": "explode", "priority": "0"})
    with app.app_context():
        assert TransactionType.query.filter_by(name="Bogus").first() is None


def test_add_duplicate_name_flashes(logged_in_client, app):
    with app.app_context():
        db.session.add(TransactionType(name="Sell (Spot)", behavior_category="decrease"))
        db.session.commit()
    resp = logged_in_client.post("/transaction-types/add", data={
        "name": "Sell (Spot)", "behavior_category": "decrease", "priority": "0"},
        follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert TransactionType.query.filter_by(name="Sell (Spot)").count() == 1


def test_edit_transaction_type(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Transfer-Out", behavior_category="transfer_out")
        db.session.add(t); db.session.commit()
        tid = t.id
    logged_in_client.post(f"/transaction-types/{tid}/edit", data={
        "name": "Transfer-Out", "behavior_category": "transfer_out", "priority": "5"})
    with app.app_context():
        assert db.session.get(TransactionType, tid).priority == 5


def test_edit_same_name_no_error(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Dividend", behavior_category="dividend")
        db.session.add(t); db.session.commit()
        tid = t.id
    resp = logged_in_client.post(f"/transaction-types/{tid}/edit", data={
        "name": "Dividend", "behavior_category": "dividend", "priority": "2"},
        follow_redirects=True)
    assert b"already exists" not in resp.data
    with app.app_context():
        assert db.session.get(TransactionType, tid).priority == 2


def test_toggle_active(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Neutral Adj", behavior_category="neutral")
        db.session.add(t); db.session.commit()
        tid = t.id
    resp = logged_in_client.post(f"/transaction-types/{tid}/toggle-active", data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(TransactionType, tid).is_active is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_transaction_types_crud.py -v`
Expected: FAIL — `/transaction-types/` 404.

- [ ] **Step 3: Write the form**

`ltv2/blueprints/transaction_types/forms.py`:
```python
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional
from ltv2.constants import BEHAVIOR_CATEGORIES


class TransactionTypeForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=50)])
    behavior_category = SelectField("Behavior Category",
                                    choices=[(b, b) for b in BEHAVIOR_CATEGORIES],
                                    validators=[DataRequired()])
    priority = IntegerField("Priority", validators=[Optional()], default=0)
```

- [ ] **Step 4: Write the views**

`ltv2/blueprints/transaction_types/views.py`:
```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.transaction_type import TransactionType
from ltv2.blueprints.transaction_types.forms import TransactionTypeForm

bp = Blueprint("transaction_types", __name__, url_prefix="/transaction-types")


@bp.route("/")
@login_required
def list_types():
    show = request.args.get("show", "active")
    q = TransactionType.query if show == "all" else TransactionType.query_active()
    rows = q.order_by(TransactionType.priority, TransactionType.name).all()
    return render_template("transaction_types/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_type():
    form = TransactionTypeForm()
    if form.validate_on_submit():
        if TransactionType.query.filter_by(name=form.name.data).first():
            flash(f"Transaction type {form.name.data!r} already exists", "error")
            return redirect(url_for("transaction_types.add_type"))
        t = TransactionType(name=form.name.data,
                            behavior_category=form.behavior_category.data,
                            priority=form.priority.data if form.priority.data is not None else 0)
        db.session.add(t); db.session.commit()
        flash("Transaction type added", "success")
        return redirect(url_for("transaction_types.list_types"))
    return render_template("transaction_types/form.html", form=form, mode="add")


@bp.route("/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def edit_type(tid):
    t = db.get_or_404(TransactionType, tid)
    form = TransactionTypeForm(obj=t)
    if form.validate_on_submit():
        existing = TransactionType.query.filter_by(name=form.name.data).first()
        if existing and existing.id != t.id:
            flash(f"Transaction type {form.name.data!r} already exists", "error")
            return redirect(url_for("transaction_types.edit_type", tid=tid))
        t.name = form.name.data
        t.behavior_category = form.behavior_category.data
        t.priority = form.priority.data if form.priority.data is not None else 0
        db.session.commit()
        flash("Transaction type updated", "success")
        return redirect(url_for("transaction_types.list_types"))
    return render_template("transaction_types/form.html", form=form, mode="edit")


@bp.route("/<int:tid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(tid):
    t = db.get_or_404(TransactionType, tid)
    t.is_active = not t.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("transaction_types.list_types", show=request.form.get("show", "active")))
```

`ltv2/blueprints/transaction_types/__init__.py`:
```python
from ltv2.blueprints.transaction_types.views import bp  # noqa: F401
```

- [ ] **Step 5: Write the templates**

`ltv2/templates/transaction_types/list.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>Transaction Types</h1>
<a href="{{ url_for('transaction_types.add_type') }}">+ Add</a>
<a href="{{ url_for('transaction_types.list_types', show='all' if show!='all' else 'active') }}">
  {{ 'Show active' if show=='all' else 'Show all' }}</a>
<table>
  <tr><th>Name</th><th>Behavior</th><th>Priority</th><th>Active</th><th></th></tr>
  {% for t in rows %}
  <tr>
    <td>{{ t.name }}</td><td>{{ t.behavior_category }}</td><td>{{ t.priority }}</td>
    <td>{{ 'Yes' if t.is_active else 'No' }}</td>
    <td>
      <a href="{{ url_for('transaction_types.edit_type', tid=t.id) }}">Edit</a>
      <form method="post" action="{{ url_for('transaction_types.toggle_active', tid=t.id) }}" style="display:inline">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="hidden" name="show" value="{{ show }}">
        <button type="submit">{{ 'Deactivate' if t.is_active else 'Activate' }}</button>
      </form>
    </td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`ltv2/templates/transaction_types/form.html`:
```html
{% extends "layout.html" %}
{% block main %}
<h1>{{ 'Add' if mode=='add' else 'Edit' }} Transaction Type</h1>
<form method="post">
  {{ form.csrf_token }}
  <p>{{ form.name.label }} {{ form.name() }}</p>
  <p>{{ form.behavior_category.label }} {{ form.behavior_category() }}</p>
  <p>{{ form.priority.label }} {{ form.priority() }}</p>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

- [ ] **Step 6: Register blueprint and add nav link**

In `ltv2/__init__.py`:
```python
    from ltv2.blueprints.transaction_types import bp as transaction_types_bp
    app.register_blueprint(transaction_types_bp)
```

In `ltv2/templates/layout.html`, add inside `{% block nav %}` (after Holidays):
```html
<a href="{{ url_for('transaction_types.list_types') }}">Transaction Types</a>
```

- [ ] **Step 7: Run tests + full suite**

Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/test_transaction_types_crud.py -v`
Expected: PASS (7 tests).
Run: `.venv-ltv2/Scripts/python -m pytest tests/ltv2/ -q`
Expected: all green (46 prior + Stocks 7 + Holidays 5 + Transaction Types 7).

- [ ] **Step 8: Commit**

```bash
git add ltv2/blueprints/transaction_types ltv2/templates/transaction_types ltv2/__init__.py ltv2/templates/layout.html tests/ltv2/test_transaction_types_crud.py
git commit -m "feat(ltv2): transaction types CRUD"
```

---

## Self-Review (author checklist — completed)

- **Spec coverage:** full CRUD for the remaining 3 reference entities ✅; Stocks + Holidays use a dynamic currency SelectField populated from active currencies ✅; Transaction Types use a behavior_category SelectField constrained to `BEHAVIOR_CATEGORIES` (invalid value rejected — `test_invalid_behavior_category_rejected`) ✅; soft-delete toggle + active/all filter on all three ✅; duplicate guards with edit-excludes-self on Stocks/Transaction-Types, and the holiday composite-uniqueness guard ✅; nav links for all three ✅. All follow the canonical Banks pattern (is-not-None priority, fixture login, hidden show field, edit-same regression tests).
- **Justified deviation:** Holidays has no edit route (a holiday is a currency+date identity; "edit" = deactivate + add). Documented in Task 2 interfaces.
- **Placeholder scan:** none — every step has complete code.
- **Type consistency:** `_currency_choices()` returns `(id, code)` with `coerce=int` matching the SelectField; `db.get_or_404`/`db.session.get` used consistently; endpoint names (`stocks.list_stocks`, `holidays.list_holidays`, `transaction_types.list_types`) consistent across views, templates, nav, and tests. List-filter tests use `b">5<"`/`b"2026-02-02"` markers to avoid substring false-positives.

## Verification (end-to-end, manual)

```bash
FLASK_APP=flask_app_v2.py .venv-ltv2/Scripts/python -m flask db upgrade   # no new migration; models already exist
.venv-ltv2/Scripts/python flask_app_v2.py   # http://<lan-ip>:5002
```
Log in; under the nav, open Stocks (add one with a currency, edit, deactivate), Holidays (add a date for a currency, confirm a duplicate flashes, deactivate), Transaction Types (add with each behavior category, confirm an out-of-range category can't be submitted, edit priority, deactivate).
