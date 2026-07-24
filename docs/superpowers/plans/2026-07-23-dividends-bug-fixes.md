# Dividends Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four open `dividends` bugs — a hardcoded-2022 date filter, missing
Record/Declaration Date columns, no Excel export, and no visual cue for
overdue Estimate rows — per the approved spec at
`docs/superpowers/specs/2026-07-23-dividends-bug-fixes-design.md`.

**Architecture:** Follow existing codebase patterns exactly: `workflow`'s
GET-query-param date filter, `portfolio`'s one-sheet-per-bank Excel export
structure. Add two nullable columns to `tbl_cash_dividends` via a one-time
manual `ALTER TABLE` (no migration tooling exists in this app).

**Tech Stack:** Flask, Flask-WTF (WTForms 3.2.1), raw `sqlite3` via `get_db()`
(no ORM in use here), Jinja2, openpyxl 3.1.5.

## Global Constraints

- No test suite exists in this repo (`tests/` removed, `pytest` unused per
  `CLAUDE.md`). Verification is scripted, ad-hoc: `ast.parse` for syntax,
  Jinja `Environment().parse()` for template syntax, Flask's test client with
  a simulated superuser session for end-to-end checks, direct `sqlite3` for
  schema checks. This is the same technique already used and proven earlier
  in this session for the `term_sheet`/`workflow` work.
- `server/instance/LTV Stocks.db` is **real client data** — treat every
  schema/data change as destructive-until-proven-safe. No destructive SQL,
  no bulk deletes.
- Superuser test-session pattern (verified working this session): in a
  `test_request_context`, `client.session_transaction()` setting
  `sess['_user_id'] = '2'; sess['_fresh'] = True` (user id 2 = `admin`,
  `role='superuser'`, already exists in the DB) logs in the Flask test
  client without touching real credentials.
- Pushing to git `main` and touching the **production** DB/webapp
  (PythonAnywhere) requires explicit user confirmation before Task 5's
  production sub-steps run — do not push, `ALTER TABLE` production, or
  reload the production webapp without that confirmation, even though the
  design is already approved.

---

### Task 1: Schema — add `declaration_date` / `record_date` columns

**Files:**
- Modify: `ltv_app/blueprints/dividends/models.py` (whole file — `CashDividends` dataclass)
- Modify: `ltv_app/blueprints/dividends/views.py:157-176` (`create_table()`)
- Local DB: `instance/LTV Stocks.db` (one-time `ALTER TABLE`, run from `server/`)

**Interfaces:**
- Produces: `CashDividends.declaration_date: str = None`,
  `CashDividends.record_date: str = None` — both `str` in `YYYY-MM-DD` form
  or `None`, consumed by Tasks 2–4.

- [ ] **Step 1: Add the two columns to the local DB**

Run from `server/`:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('instance/LTV Stocks.db')
conn.execute('ALTER TABLE tbl_cash_dividends ADD COLUMN declaration_date TIMESTAMP;')
conn.execute('ALTER TABLE tbl_cash_dividends ADD COLUMN record_date TIMESTAMP;')
conn.commit()
print('done')
"
```

Expected output: `done` (SQLite raises `OperationalError: duplicate column
name` if run twice — if you see that, the columns already exist, move on).

- [ ] **Step 2: Verify the columns exist**

```bash
python -c "
import sqlite3
conn = sqlite3.connect('instance/LTV Stocks.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(tbl_cash_dividends)').fetchall()]
assert 'declaration_date' in cols, cols
assert 'record_date' in cols, cols
print('columns present:', cols)
"
```

Expected: prints the column list including both new names, no `AssertionError`.

- [ ] **Step 3: Update `CashDividends` dataclass**

Replace the full contents of `ltv_app/blueprints/dividends/models.py` with:

```python
from dataclasses import dataclass
from ..data_model import Model


@dataclass
class CashDividends(Model):
    ref_num: int = None
    bank_id: int = None
    stock_id: int = None
    declaration_date: str = None
    ex_date: str = None
    record_date: str = None
    pay_out: str = None
    nominal: float = None
    ccy_id: int = None
    dividends_per_share: float = None
    tax: float = None
    charges: float = None
    status: str = None

    def __post_init__(self):
        self.table_name = "tbl_cash_dividends"

# class DividendsDeclaration(db.Model):
#     id = db.Column(db.Integer(), primary_key=True)
#     ex_date = db.Column(db.DateTime(), nullable=True)
#     pay_out_date = db.Column(db.DateTime(), nullable=True)
#     ccy_ref = db.Column(db.Integer())
#     dividends_per_share = db.Column(db.Float())
#     comment = db.Column(db.String(), nullable=True)
```

- [ ] **Step 4: Update `create_table()`**

In `ltv_app/blueprints/dividends/views.py`, find:

```python
def create_table():
    db = get_db()
    sql = """
    CREATE TABLE tbl_cash_dividends 
        (
        ref_num INTEGER PRIMARY KEY AUTOINCREMENT, 
        bank_id INT,
        stock_id INT,
        ex_date TIMESTAMP,
        pay_out TIMESTAMP,
        nominal REAL,
        ccy_id INT,
        dividends_per_share REAL,
        tax REAL,
        charges REAL,
        status TEXT        
        )
    ;"""
    db.execute(sql)
```

Replace with:

```python
def create_table():
    db = get_db()
    sql = """
    CREATE TABLE tbl_cash_dividends 
        (
        ref_num INTEGER PRIMARY KEY AUTOINCREMENT, 
        bank_id INT,
        stock_id INT,
        declaration_date TIMESTAMP,
        ex_date TIMESTAMP,
        record_date TIMESTAMP,
        pay_out TIMESTAMP,
        nominal REAL,
        ccy_id INT,
        dividends_per_share REAL,
        tax REAL,
        charges REAL,
        status TEXT        
        )
    ;"""
    db.execute(sql)
```

- [ ] **Step 5: Verify the dataclass matches the schema**

Run from `server/`:

```bash
python -c "
import ast
ast.parse(open('ltv_app/blueprints/dividends/models.py', encoding='utf-8').read())
ast.parse(open('ltv_app/blueprints/dividends/views.py', encoding='utf-8').read())
print('syntax OK')
"
python -c "
import sys; sys.path.insert(0, '.')
from ltv_app import create_app
from ltv_app.blueprints.dividends.models import CashDividends
app = create_app()
with app.test_request_context('/'):
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    cd = CashDividends(db=db)
    field_names = {f['name'] for f in cd.fields()}
    assert 'declaration_date' in field_names, field_names
    assert 'record_date' in field_names, field_names
    print('model fields OK:', sorted(field_names))
"
```

Expected: `syntax OK`, then `model fields OK: [...]` including both new
names, no `AssertionError`/traceback.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/dividends/models.py ltv_app/blueprints/dividends/views.py
git commit -m "feat(dividends): add declaration_date/record_date columns to tbl_cash_dividends"
```

---

### Task 2: Optional Declaration Date / Record Date on Add/Edit

**Files:**
- Modify: `ltv_app/blueprints/dividends/forms.py` (whole file)
- Modify: `ltv_app/blueprints/dividends/views.py` (`add()`, `edit()`, plus two new helpers)
- Modify: `ltv_app/blueprints/dividends/pages/dividends/add.html`
- Modify: `ltv_app/blueprints/dividends/pages/dividends/edit.html`

**Interfaces:**
- Consumes: `CashDividends.declaration_date`/`record_date` (Task 1).
- Produces: `Form.declaration_date`, `Form.record_date` (WTForms `DateField`,
  optional) — used by no later task, but their presence/behavior is what
  Task 2's verification checks.

- [ ] **Step 1: Add the two optional fields to the form**

Replace the full contents of `ltv_app/blueprints/dividends/forms.py` with:

```python
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, DecimalField, FloatField
from wtforms.validators import DataRequired, NumberRange, Optional


class Form(FlaskForm):
    bank_id = SelectField(
        validators=[DataRequired()],
        label="Bank Account",
        render_kw={
            "class": "form-control",
            "autofocus": "autofocus",
        }
    )

    stock_id = SelectField(
        validators=[DataRequired()],
        label="Stock",
        render_kw={
            "class": "form-control",
        }
    )

    declaration_date = DateField(
        validators=[Optional()],
        label="Declaration Date",
        render_kw={
            "class": "form-control"
        }
    )

    ex_date = DateField(
        validators=[DataRequired()],
        label="Ex-Date",
        render_kw={
            "class": "form-control"
        }
    )

    record_date = DateField(
        validators=[Optional()],
        label="Record Date",
        render_kw={
            "class": "form-control"
        }
    )

    pay_out = DateField(
        validators=[DataRequired()],
        label="Pay Out Date",
        render_kw={
            "class": "form-control"
        }
    )

    nominal = FloatField(
        validators=[DataRequired()],
        label="Nominal",
        render_kw={
            "class": "form-control"
        }
    )

    ccy_id = SelectField(
        validators=[DataRequired()],
        label="Ccy",
        render_kw={
            "class": "form-control",
        }
    )

    dividends_per_share = FloatField(
        validators=[DataRequired()],
        label="Dividends per share",
        render_kw={
            "class": "form-control"
        }
    )
    tax = FloatField(
        label="Tax",
        render_kw={
            "class": "form-control"
        }
    )

    charges = FloatField(
        label="Charges",
        render_kw={
            "class": "form-control"
        }
    )

    status = SelectField(
        validators=[DataRequired()],
        label="Status",
        choices=["Actual", "Estimate"],
        render_kw={
            "class": "form-control",
        }
    )
```

(Only change from the original: `Optional` added to the validators import,
and the two new `declaration_date`/`record_date` fields inserted in
chronological position — before `ex_date` and between `ex_date`/`pay_out`
respectively.)

- [ ] **Step 2: Add date-conversion helpers to `views.py`**

In `ltv_app/blueprints/dividends/views.py`, directly above `def select_fields(db, form):`, add:

```python
def _optional_date(value):
    """WTForms DateField -> 'YYYY-MM-DD' string for storage, or None if blank."""
    return str(value)[:10] if value else None


def _parse_date(value):
    """Stored 'YYYY-MM-DD' string -> datetime for populating a DateField, or None."""
    if not value:
        return None
    return datetime(int(value[:4]), int(value[5:7]), int(value[-2:]))
```

- [ ] **Step 3: Wire the fields into `add()`**

In `ltv_app/blueprints/dividends/views.py`, find:

```python
    if request.method == "POST" or form.validate_on_submit():
        dividend = CashDividends(
            db=db,
            bank_id=int(form.bank_id.data),
            stock_id=int(form.stock_id.data),
            ex_date=str(form.ex_date.data)[:10],
            pay_out=str(form.pay_out.data)[:10],
            nominal=float(form.nominal.data),
            ccy_id=int(form.ccy_id.data),
            dividends_per_share=float(form.dividends_per_share.data),
            tax=float(form.tax.data),
            charges=float(form.charges.data),
            status=form.status.data
        )
```

Replace with:

```python
    if request.method == "POST" or form.validate_on_submit():
        dividend = CashDividends(
            db=db,
            bank_id=int(form.bank_id.data),
            stock_id=int(form.stock_id.data),
            declaration_date=_optional_date(form.declaration_date.data),
            ex_date=str(form.ex_date.data)[:10],
            record_date=_optional_date(form.record_date.data),
            pay_out=str(form.pay_out.data)[:10],
            nominal=float(form.nominal.data),
            ccy_id=int(form.ccy_id.data),
            dividends_per_share=float(form.dividends_per_share.data),
            tax=float(form.tax.data),
            charges=float(form.charges.data),
            status=form.status.data
        )
```

- [ ] **Step 4: Wire the fields into `edit()` (POST branch)**

In the same file, find:

```python
    if request.method == "POST" or form.validate_on_submit():
        dividend.bank_id = int(form.bank_id.data)
        dividend.stock_id = int(form.stock_id.data)
        dividend.ex_date = str(form.ex_date.data)[:10]
        dividend.pay_out = str(form.pay_out.data)[:10]
        dividend.nominal = float(form.nominal.data)
```

Replace with:

```python
    if request.method == "POST" or form.validate_on_submit():
        dividend.bank_id = int(form.bank_id.data)
        dividend.stock_id = int(form.stock_id.data)
        dividend.declaration_date = _optional_date(form.declaration_date.data)
        dividend.ex_date = str(form.ex_date.data)[:10]
        dividend.record_date = _optional_date(form.record_date.data)
        dividend.pay_out = str(form.pay_out.data)[:10]
        dividend.nominal = float(form.nominal.data)
```

- [ ] **Step 5: Wire the fields into `edit()` (GET branch — populate the form)**

In the same file, find:

```python
    else:
        form.bank_id.data = str(dividend.bank_id)
        form.stock_id.data = str(dividend.stock_id)
        form.ex_date.data = datetime(int(dividend.ex_date[:4]), int(dividend.ex_date[5:7]), int(dividend.ex_date[-2:]))
        form.pay_out.data = datetime(int(dividend.pay_out[:4]), int(dividend.pay_out[5:7]), int(dividend.pay_out[-2:]))
        form.nominal.data = dividend.nominal
```

Replace with:

```python
    else:
        form.bank_id.data = str(dividend.bank_id)
        form.stock_id.data = str(dividend.stock_id)
        form.declaration_date.data = _parse_date(dividend.declaration_date)
        form.ex_date.data = datetime(int(dividend.ex_date[:4]), int(dividend.ex_date[5:7]), int(dividend.ex_date[-2:]))
        form.record_date.data = _parse_date(dividend.record_date)
        form.pay_out.data = datetime(int(dividend.pay_out[:4]), int(dividend.pay_out[5:7]), int(dividend.pay_out[-2:]))
        form.nominal.data = dividend.nominal
```

- [ ] **Step 6: Add the fields to `add.html`**

In `ltv_app/blueprints/dividends/pages/dividends/add.html`, find:

```html
  {{ form_control(form.bank_id) }}
  {{ form_control(form.stock_id) }}
  {{ form_control(form.ex_date) }}
  {{ form_control(form.pay_out) }}
```

Replace with:

```html
  {{ form_control(form.bank_id) }}
  {{ form_control(form.stock_id) }}
  {{ form_control(form.declaration_date) }}
  {{ form_control(form.ex_date) }}
  {{ form_control(form.record_date) }}
  {{ form_control(form.pay_out) }}
```

- [ ] **Step 7: Add the fields to `edit.html`**

In `ltv_app/blueprints/dividends/pages/dividends/edit.html`, apply the same
change as Step 6 (identical block, same find/replace).

- [ ] **Step 8: Verify — syntax and template parse**

```bash
cd server
python -c "
import ast
ast.parse(open('ltv_app/blueprints/dividends/forms.py', encoding='utf-8').read())
ast.parse(open('ltv_app/blueprints/dividends/views.py', encoding='utf-8').read())
print('py OK')
"
python -c "
import jinja2
for f in ('add.html', 'edit.html'):
    src = open(f'ltv_app/blueprints/dividends/pages/dividends/{f}', encoding='utf-8').read()
    jinja2.Environment().parse(src)
print('templates OK')
"
```

Expected: `py OK`, `templates OK`, no tracebacks.

- [ ] **Step 9: Verify — blank/filled optional-date round trip via the real form**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from ltv_app import create_app
app = create_app()
client = app.test_client()
with client.session_transaction() as sess:
    sess['_user_id'] = '2'
    sess['_fresh'] = True

# GET the add page — confirm the two new fields render
resp = client.get('/dividends/add')
assert resp.status_code == 200, resp.status_code
html = resp.data.decode('utf-8')
assert 'declaration_date' in html, 'declaration_date field missing from add.html'
assert 'record_date' in html, 'record_date field missing from add.html'
print('add page renders both new fields: OK')
"
```

Expected: `add page renders both new fields: OK`. (This checks rendering
only — it does not submit the form, since doing so would insert a real
row into local `instance/LTV Stocks.db`. Full add/edit submission with
these fields is covered by Task 3's end-to-end check, which cleans up
after itself.)

- [ ] **Step 10: Commit**

```bash
git add ltv_app/blueprints/dividends/forms.py ltv_app/blueprints/dividends/views.py \
        ltv_app/blueprints/dividends/pages/dividends/add.html \
        ltv_app/blueprints/dividends/pages/dividends/edit.html
git commit -m "feat(dividends): add optional Declaration Date / Record Date fields to Add/Edit"
```

---

### Task 3: Home page — date-range filter, new columns, pending-Actual indicator

**Files:**
- Modify: `ltv_app/blueprints/dividends/views.py` (`home()` route)
- Modify: `ltv_app/blueprints/dividends/pages/dividends/home.html` (whole file)

**Interfaces:**
- Consumes: `ph_today()` from `ltv_app/tz.py` (already used elsewhere in the
  app, e.g. `workflow`/`notebook` views — signature: `ph_today() -> date`).
- Produces: `home()` now accepts `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  query args (both optional, default to current calendar year); template
  context gains `today: str` — consumed by nothing later in this plan, but
  is the anchor Task 4's export route reuses for its own defaulting.

- [ ] **Step 1: Rewrite `home()`**

In `ltv_app/blueprints/dividends/views.py`, find the imports at the top:

```python
from flask import Blueprint, render_template, flash, redirect, url_for, request
from datetime import datetime

from ..auth import login_required
from ..database import get_db

from .models import CashDividends
from .forms import Form
```

Replace with:

```python
from flask import Blueprint, render_template, flash, redirect, url_for, request
from datetime import datetime

from ..auth import login_required
from ..database import get_db
from ...tz import ph_today

from .models import CashDividends
from .forms import Form
```

Then find:

```python
@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    try:
        create_table()
    except:
        pass
    db = get_db()
    year = "2022"
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    sql = """
    SELECT 
        tbl_cash_dividends.ref_num,
        tbl_bank_account.bank_name,
        tbl_code.stock_name,
        tbl_code.code AS stock_code,
        tbl_cash_dividends.nominal,
        tbl_cash_dividends.ex_date,
        tbl_cash_dividends.pay_out,
        tbl_currency.ccy_id AS ccy_code,
        tbl_cash_dividends.dividends_per_share,
        tbl_cash_dividends.tax,
        tbl_cash_dividends.charges,
        tbl_cash_dividends.status
    FROM tbl_cash_dividends 
    INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_cash_dividends.bank_id
    INNER JOIN tbl_code ON tbl_code.ref_num = tbl_cash_dividends.stock_id
    INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_cash_dividends.ccy_id
    WHERE tbl_cash_dividends.ex_date >= ? AND tbl_cash_dividends.ex_date <= ?
    ORDER BY tbl_cash_dividends.ref_num desc
    ;
    """
    dividends = db.execute(sql, (start_date, end_date)).fetchall()
    context = {
        "dividends": dividends,
        "start_date": start_date,
        "end_date": end_date
    }
    return render_template("dividends/home.html", **context)
```

Replace with:

```python
@bp.route("/", methods=["GET"])
@login_required
def home():
    try:
        create_table()
    except:
        pass
    db = get_db()
    today = ph_today()
    start_date = request.args.get('start_date') or f"{today.year}-01-01"
    end_date = request.args.get('end_date') or f"{today.year}-12-31"
    sql = """
    SELECT 
        tbl_cash_dividends.ref_num,
        tbl_bank_account.bank_name,
        tbl_code.stock_name,
        tbl_code.code AS stock_code,
        tbl_cash_dividends.nominal,
        tbl_cash_dividends.declaration_date,
        tbl_cash_dividends.ex_date,
        tbl_cash_dividends.record_date,
        tbl_cash_dividends.pay_out,
        tbl_currency.ccy_id AS ccy_code,
        tbl_cash_dividends.dividends_per_share,
        tbl_cash_dividends.tax,
        tbl_cash_dividends.charges,
        tbl_cash_dividends.status
    FROM tbl_cash_dividends 
    INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_cash_dividends.bank_id
    INNER JOIN tbl_code ON tbl_code.ref_num = tbl_cash_dividends.stock_id
    INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_cash_dividends.ccy_id
    WHERE tbl_cash_dividends.ex_date >= ? AND tbl_cash_dividends.ex_date <= ?
    ORDER BY tbl_cash_dividends.ref_num desc
    ;
    """
    dividends = db.execute(sql, (start_date, end_date)).fetchall()
    context = {
        "dividends": dividends,
        "start_date": start_date,
        "end_date": end_date,
        "today": str(today),
    }
    return render_template("dividends/home.html", **context)
```

- [ ] **Step 2: Rewrite `home.html`**

Replace the full contents of
`ltv_app/blueprints/dividends/pages/dividends/home.html` with:

```html
{% extends "base.html" %}

{% block content %}
<h1>Cash Dividends</h1>
<form action="{{ url_for('dividends.home') }}" method="get">
  <label for="start_date">From</label>
  <input type="date" name="start_date" value="{{ start_date }}">
  <label for="end_date">To</label>
  <input type="date" name="end_date" value="{{ end_date }}">
  <input type="submit" value="Go" class="btn btn-success">
</form>
<a href="{{ url_for('dividends.add') }}" class="btn btn-success" autofocus>Add dividend</a>
{% if dividends %}
  <table class="table table-striped table-dark">
    <tr>
      <th>Bank / Account</th>
      <th> Stock Name</th>
      <th>Code</th>
      <th>Quantity</th>
      <th>Declaration Date</th>
      <th>Ex Date</th>
      <th>Record Date</th>
      <th>Pay-Out Date</th>
      <th>Ccy</th>
      <th>Div per Share</th>
      <th>Gross Amount</th>
      <th>Tax/charges</th>
      <th>Net Amount</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
    {% for dividend in dividends%}
    <tr>
      <td>{{ dividend.bank_name }}</td>
      <td>{{ dividend.stock_name }}</td>
      <td>{{ dividend.stock_code }}</td>
      <td>{{ '{:,.0f}'.format(dividend.nominal) }}</td>
      <td>{{ dividend.declaration_date or '' }}</td>
      <td>{{ dividend.ex_date }}</td>
      <td>{{ dividend.record_date or '' }}</td>
      <td>{{ dividend.pay_out }}</td>
      <td>{{ dividend.ccy_code }}</td>
      <td>{{ '{:,.4f}'.format(dividend.dividends_per_share) }}</td>
      <td>{{ '{:,.2f}'.format(dividend.nominal * dividend.dividends_per_share) }}</td>
      <td>{{ '{:,.2f}'.format(dividend.tax + dividend.charges) }}</td>
      <td>{{ '{:,.2f}'.format(dividend.nominal * dividend.dividends_per_share - dividend.tax - dividend.charges) }}</td>
      <td>
        {% if dividend.status == 'Estimate' and dividend.pay_out < today %}
        <span style="background:rgba(217,119,6,0.18); color:#92400e; padding:2px 8px; border-radius:4px; font-weight:600;">Estimate (overdue)</span>
        {% else %}
        {{ dividend.status }}
        {% endif %}
      </td>
      <td>
        <a href="{{ url_for('dividends.edit', ref_num=dividend.ref_num) }}" class="btn btn-success">Edit</a>
        <button type="button" class="btn btn-danger" onclick="showConfirmModal('Delete this dividend?', function(){
            window.location.href = '{{ url_for('dividends.delete', ref_num=dividend.ref_num) }}';
        }, {requireTyped: 'YES'})">Delete</button>
      </td>
    </tr>
    {% endfor %}
  </table>
{% else %}
  <p>No data</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Verify — syntax and template parse**

```bash
cd server
python -c "
import ast
ast.parse(open('ltv_app/blueprints/dividends/views.py', encoding='utf-8').read())
print('py OK')
"
python -c "
import jinja2
src = open('ltv_app/blueprints/dividends/pages/dividends/home.html', encoding='utf-8').read()
jinja2.Environment().parse(src)
print('template OK')
"
```

Expected: `py OK`, `template OK`.

- [ ] **Step 4: Verify — default range, explicit range, both via GET**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from ltv_app import create_app
app = create_app()
client = app.test_client()
with client.session_transaction() as sess:
    sess['_user_id'] = '2'
    sess['_fresh'] = True

# Default (no params) -> current-year window
resp = client.get('/dividends/')
assert resp.status_code == 200, resp.status_code
html = resp.data.decode('utf-8')
assert 'value=\"2026-01-01\"' in html, 'default start_date not current-year Jan 1'
assert 'value=\"2026-12-31\"' in html, 'default end_date not current-year Dec 31'
print('default range OK')

# Explicit range -> honored, and old 2022 hardcode is gone
resp = client.get('/dividends/?start_date=2020-01-01&end_date=2020-12-31')
assert resp.status_code == 200, resp.status_code
html = resp.data.decode('utf-8')
assert 'value=\"2020-01-01\"' in html
assert 'value=\"2020-12-31\"' in html
print('explicit range OK')
"
```

Expected: `default range OK`, `explicit range OK`. (2026 is hardcoded in this
check as today's actual date per this session — if run on a different date,
adjust the expected year accordingly; the check's intent is "the default
matches the *current* calendar year," not literally 2026.)

- [ ] **Step 5: Verify — full add/edit round trip with the new optional dates, self-cleaning**

This is also the deferred full-submission check from Task 2 Step 9.

```bash
python -c "
import sys; sys.path.insert(0, '.')
from ltv_app import create_app
from ltv_app.blueprints.dividends.models import CashDividends
app = create_app()
client = app.test_client()
with client.session_transaction() as sess:
    sess['_user_id'] = '2'
    sess['_fresh'] = True

with app.test_request_context('/'):
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    bank_ref = db.execute('SELECT ref_num FROM tbl_bank_account LIMIT 1').fetchone()[0]
    stock_ref = db.execute('SELECT ref_num FROM tbl_code LIMIT 1').fetchone()[0]
    ccy_ref = db.execute('SELECT ref_num FROM tbl_currency LIMIT 1').fetchone()[0]

# 1. Add with declaration_date/record_date BLANK
resp = client.post('/dividends/add', data={
    'bank_id': bank_ref, 'stock_id': stock_ref, 'ccy_id': ccy_ref,
    'ex_date': '2026-01-05', 'pay_out': '2026-02-05',
    'nominal': '100', 'dividends_per_share': '0.5',
    'tax': '0', 'charges': '0', 'status': 'Estimate',
    'declaration_date': '', 'record_date': '',
}, follow_redirects=False)
assert resp.status_code == 302, (resp.status_code, resp.data[:500])

with app.test_request_context('/'):
    db = get_db()
    row = db.execute(
        'SELECT ref_num, declaration_date, record_date FROM tbl_cash_dividends '
        \"WHERE ex_date='2026-01-05' AND nominal=100 ORDER BY ref_num DESC LIMIT 1\"
    ).fetchone()
    assert row is not None, 'row not inserted'
    assert row['declaration_date'] is None, row['declaration_date']
    assert row['record_date'] is None, row['record_date']
    ref_num = row['ref_num']
    print('blank optional dates stored as NULL: OK, ref_num=', ref_num)

# 2. Edit it, filling in both dates
resp = client.post(f'/dividends/edit/{ref_num}', data={
    'bank_id': bank_ref, 'stock_id': stock_ref, 'ccy_id': ccy_ref,
    'ex_date': '2026-01-05', 'pay_out': '2026-02-05',
    'nominal': '100', 'dividends_per_share': '0.5',
    'tax': '0', 'charges': '0', 'status': 'Estimate',
    'declaration_date': '2025-12-20', 'record_date': '2026-01-04',
}, follow_redirects=False)
assert resp.status_code == 302, (resp.status_code, resp.data[:500])

with app.test_request_context('/'):
    db = get_db()
    row = db.execute(
        'SELECT declaration_date, record_date FROM tbl_cash_dividends WHERE ref_num=?',
        (ref_num,)
    ).fetchone()
    assert row['declaration_date'] == '2025-12-20', row['declaration_date']
    assert row['record_date'] == '2026-01-04', row['record_date']
    print('filled optional dates stored correctly: OK')

    # 3. Clean up — this was a synthetic test row, not real client data
    db.execute('DELETE FROM tbl_cash_dividends WHERE ref_num=?', (ref_num,))
    db.commit()
    still_there = db.execute(
        'SELECT 1 FROM tbl_cash_dividends WHERE ref_num=?', (ref_num,)
    ).fetchone()
    assert still_there is None
    print('test row cleaned up: OK')
"
```

Expected: `blank optional dates stored as NULL: OK, ref_num= <n>`,
`filled optional dates stored correctly: OK`, `test row cleaned up: OK` —
no assertion errors, and the DB ends in the same state it started in.

- [ ] **Step 6: Verify — pending-Actual indicator renders (isolated template check, no DB writes)**

```bash
python -c "
import jinja2
env = jinja2.Environment()
src = open('ltv_app/blueprints/dividends/pages/dividends/home.html', encoding='utf-8').read()
# Extract just the status-cell logic into a minimal standalone template to
# check both branches without needing a full render_template() context.
snippet = '''
{% if status == 'Estimate' and pay_out < today %}OVERDUE{% else %}{{ status }}{% endif %}
'''
tmpl = env.from_string(snippet)
overdue = tmpl.render(status='Estimate', pay_out='2026-01-01', today='2026-07-23').strip()
not_overdue_future = tmpl.render(status='Estimate', pay_out='2026-12-31', today='2026-07-23').strip()
actual = tmpl.render(status='Actual', pay_out='2026-01-01', today='2026-07-23').strip()
assert overdue == 'OVERDUE', overdue
assert not_overdue_future == '', not_overdue_future
assert actual == 'Actual', actual
print('indicator logic OK: overdue=%r future=%r actual=%r' % (overdue, not_overdue_future, actual))
"
```

Expected: `indicator logic OK: overdue='OVERDUE' future='' actual='Actual'`.

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/dividends/views.py ltv_app/blueprints/dividends/pages/dividends/home.html
git commit -m "feat(dividends): GET-based date-range filter (was hardcoded to 2022), new date columns, pending-Actual indicator"
```

---

### Task 4: Excel export

**Files:**
- Create: `ltv_app/blueprints/dividends/extensions/__init__.py`
- Create: `ltv_app/blueprints/dividends/extensions/create_excel.py`
- Modify: `ltv_app/blueprints/dividends/views.py` (imports + new `export()` route)
- Modify: `ltv_app/blueprints/dividends/pages/dividends/home.html` (Download Excel button)

**Interfaces:**
- Consumes: `start_date`/`end_date` string format and defaulting logic from
  Task 3's `home()`.
- Produces: `dividends.export` route (GET, same query args as `home()`).

- [ ] **Step 1: Create `extensions/__init__.py`**

```python
from .create_excel import CreateExcel
```

- [ ] **Step 2: Create `extensions/create_excel.py`**

```python
from openpyxl import Workbook
import os


class CreateExcel:
    def __init__(self, path: str, start_date: str, end_date: str, db):
        self.filename = os.path.join(path, f"{start_date}_to_{end_date} dividends.xlsx")
        self.wb = Workbook()
        self.wb.remove(self.wb.active)  # drop the default blank sheet

        self.start_date = start_date
        self.end_date = end_date
        self.db = db

        self.create()

        self.wb.save(self.filename)
        self.wb.close()

    def bank_accounts(self):
        sql = "SELECT ref_num, bank_id, bank_name FROM tbl_bank_account ORDER BY priority;"
        return self.db.execute(sql).fetchall()

    def dividends_for_bank(self, bank_ref):
        sql = """
        SELECT
            tbl_code.stock_name,
            tbl_code.code AS stock_code,
            tbl_cash_dividends.nominal,
            tbl_cash_dividends.declaration_date,
            tbl_cash_dividends.ex_date,
            tbl_cash_dividends.record_date,
            tbl_cash_dividends.pay_out,
            tbl_currency.ccy_id AS ccy_code,
            tbl_cash_dividends.dividends_per_share,
            tbl_cash_dividends.tax,
            tbl_cash_dividends.charges,
            tbl_cash_dividends.status
        FROM tbl_cash_dividends
        INNER JOIN tbl_code ON tbl_code.ref_num = tbl_cash_dividends.stock_id
        INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_cash_dividends.ccy_id
        WHERE tbl_cash_dividends.bank_id = ?
          AND tbl_cash_dividends.ex_date >= ? AND tbl_cash_dividends.ex_date <= ?
        ORDER BY tbl_cash_dividends.ex_date;
        """
        return self.db.execute(sql, (bank_ref, self.start_date, self.end_date)).fetchall()

    def create(self):
        headers = [
            "Stock Name", "Code", "Quantity", "Declaration Date", "Ex Date",
            "Record Date", "Pay-Out Date", "Ccy", "Div/Share", "Gross Amount",
            "Tax/Charges", "Net Amount", "Status",
        ]
        for account in self.bank_accounts():
            ws = self.wb.create_sheet(account["bank_id"])
            ws.append(headers)

            for row in self.dividends_for_bank(account["ref_num"]):
                gross = row["nominal"] * row["dividends_per_share"]
                net = gross - row["tax"] - row["charges"]
                ws.append([
                    row["stock_name"],
                    row["stock_code"],
                    row["nominal"],
                    row["declaration_date"] or "",
                    row["ex_date"],
                    row["record_date"] or "",
                    row["pay_out"],
                    row["ccy_code"],
                    row["dividends_per_share"],
                    round(gross, 2),
                    round(row["tax"] + row["charges"], 2),
                    round(net, 2),
                    row["status"],
                ])
```

Note: `self.wb.remove(self.wb.active)` is one intentional line of divergence
from `portfolio/extensions/create_excel.py`, which leaves openpyxl's default
blank "Sheet" in the output alongside the real per-bank sheets. That's a
minor existing papercut in the reference pattern, not a deliberate design
choice worth propagating — this export skips it so downloaded files don't
contain a pointless empty sheet.

- [ ] **Step 3: Add the `export()` route**

In `ltv_app/blueprints/dividends/views.py`, find the imports:

```python
from flask import Blueprint, render_template, flash, redirect, url_for, request
from datetime import datetime

from ..auth import login_required
from ..database import get_db
from ...tz import ph_today

from .models import CashDividends
from .forms import Form
```

Replace with:

```python
from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, send_file
from datetime import datetime
import os

from ..auth import login_required
from ..database import get_db
from ...tz import ph_today

from .models import CashDividends
from .forms import Form
from .extensions import CreateExcel
```

Then, directly below the `home()` function (before `@bp.route("/add", ...)`),
add:

```python
@bp.route("/export", methods=["GET"])
@login_required
def export():
    db = get_db()
    today = ph_today()
    start_date = request.args.get('start_date') or f"{today.year}-01-01"
    end_date = request.args.get('end_date') or f"{today.year}-12-31"

    excel_file = CreateExcel(
        path=os.path.join(current_app.instance_path, "temp"),
        start_date=start_date,
        end_date=end_date,
        db=db
    )
    return send_file(excel_file.filename, as_attachment=True)
```

- [ ] **Step 4: Add the Download Excel button**

In `ltv_app/blueprints/dividends/pages/dividends/home.html`, find:

```html
<a href="{{ url_for('dividends.add') }}" class="btn btn-success" autofocus>Add dividend</a>
```

Replace with:

```html
<a href="{{ url_for('dividends.add') }}" class="btn btn-success" autofocus>Add dividend</a>
<a href="{{ url_for('dividends.export', start_date=start_date, end_date=end_date) }}" class="btn btn-primary">Download Excel</a>
```

- [ ] **Step 5: Verify — syntax and template parse**

```bash
cd server
python -c "
import ast
for f in ('views.py', 'extensions/__init__.py', 'extensions/create_excel.py'):
    ast.parse(open(f'ltv_app/blueprints/dividends/{f}', encoding='utf-8').read())
print('py OK')
"
python -c "
import jinja2
src = open('ltv_app/blueprints/dividends/pages/dividends/home.html', encoding='utf-8').read()
jinja2.Environment().parse(src)
print('template OK')
"
```

Expected: `py OK`, `template OK`.

- [ ] **Step 6: Verify — export produces a valid workbook with the right shape**

```bash
python -c "
import sys, io; sys.path.insert(0, '.')
from ltv_app import create_app
from openpyxl import load_workbook

app = create_app()
client = app.test_client()
with client.session_transaction() as sess:
    sess['_user_id'] = '2'
    sess['_fresh'] = True

resp = client.get('/dividends/export?start_date=2020-01-01&end_date=2020-12-31')
assert resp.status_code == 200, resp.status_code
assert resp.headers['Content-Type'].startswith(
    'application/vnd.openxmlformats-officedocument.spreadsheetml'
), resp.headers['Content-Type']

wb = load_workbook(io.BytesIO(resp.data))
assert len(wb.sheetnames) > 0, 'no sheets created'
first_sheet = wb[wb.sheetnames[0]]
header_row = [c.value for c in next(first_sheet.iter_rows(min_row=1, max_row=1))]
assert header_row == [
    'Stock Name', 'Code', 'Quantity', 'Declaration Date', 'Ex Date',
    'Record Date', 'Pay-Out Date', 'Ccy', 'Div/Share', 'Gross Amount',
    'Tax/Charges', 'Net Amount', 'Status',
], header_row
print('export OK, sheets:', wb.sheetnames)
"
```

Expected: `export OK, sheets: [...]` listing bank_id-keyed sheet names, no
assertion errors.

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/dividends/extensions/ ltv_app/blueprints/dividends/views.py \
        ltv_app/blueprints/dividends/pages/dividends/home.html
git commit -m "feat(dividends): add Excel export (one sheet per bank, matching portfolio's pattern)"
```

---

### Task 5: Production rollout

**Files:** none (operational task — schema + deploy on PythonAnywhere)

**Interfaces:** none — this task ships what Tasks 1–4 already built and verified locally.

> **STOP before Step 1.** Everything below touches the production DB, the
> production webapp, or pushes to the shared `main` branch. Confirm with the
> user before running any step in this task, even though the design was
> already approved — per this plan's Global Constraints.

- [ ] **Step 1: Confirm production is clean and fast-forward**

Using the PythonAnywhere console (open `/user/larrylilia/consoles/<id>/` in
a browser once if the API returns 412 "Console not yet started", per
`reference_pa_deploy_procedure`), run on PA:

```bash
cd /home/larrylilia/ltv_app && git status --short && git log origin/main..HEAD --oneline && git log HEAD..origin/main --oneline
```

Expected: no output from `git status --short` (clean working tree), no
output from either `log` diff command (not diverged either direction). If
any of those print something, stop and report back — don't proceed.

- [ ] **Step 2: `ALTER TABLE` on production — before the code deploy**

On PA:

```bash
sqlite3 "/home/larrylilia/ltv_app/instance/LTV Stocks.db" \
  "ALTER TABLE tbl_cash_dividends ADD COLUMN declaration_date TIMESTAMP; \
   ALTER TABLE tbl_cash_dividends ADD COLUMN record_date TIMESTAMP;"
sqlite3 "/home/larrylilia/ltv_app/instance/LTV Stocks.db" \
  "PRAGMA table_info(tbl_cash_dividends);" | grep -E "declaration_date|record_date"
```

Expected: the `PRAGMA` grep prints both new column names. This is safe
against the currently-running old code — it doesn't know about the columns
and won't touch them.

- [ ] **Step 3: Push and deploy**

Locally, from `server/`:

```bash
git push origin main
```

On PA:

```bash
cd /home/larrylilia/ltv_app && git pull origin main
```

Then reload via the PythonAnywhere API:

```bash
curl -X POST \
  -H "Authorization: Token $(python -c "import json; print(json.load(open('credentials/pythonanywhere.json'))['pythonanywhere']['api_token'])")" \
  https://www.pythonanywhere.com/api/v0/user/larrylilia/webapps/larrylilia.pythonanywhere.com/reload/
```

Expected: `{"status":"OK"}`.

- [ ] **Step 4: Verify live**

```bash
curl -s -o /dev/null -w "%{http_code}" https://larrylilia.pythonanywhere.com/
```

Expected: `200` or `302` (redirect to login) — not `500`. Then, with the
user (since it needs a real login), confirm on the live site:
- `/dividends/` loads with no server error, defaults to the current year,
  and the From/To filter actually changes what's shown.
- The Download Excel button produces a file.
- An Estimate row with a past Pay Out date shows the amber "Estimate
  (overdue)" indicator.
- Add/Edit dividend forms show Declaration Date / Record Date fields and
  save them correctly.

- [ ] **Step 5: Update BUGS.md**

Follow the `bug-tracker` skill: move all four dividends entries (year
hardcode, missing Record/Declaration Date columns, no Excel export,
Estimate→Actual manual step) from their current sections to `## Fixed`,
each with `**Status:** Fixed (<today's date>)` and a short note referencing
this plan and the spec at
`docs/superpowers/specs/2026-07-23-dividends-bug-fixes-design.md`. For the
Estimate→Actual entry specifically, note that only the "pending Actual"
indicator half was fixed — the auto-create-from-fetch half is still open,
so either leave that part flagged in the Fixed entry's note, or split it
into a fresh, narrower Open entry for the deferred integration work.
