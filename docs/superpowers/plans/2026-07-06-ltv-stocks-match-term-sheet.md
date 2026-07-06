# LTV Stocks — Match Term-Sheet Contract Listing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the downloaded LTV Stocks Excel list the same non-inactive ACCU/DECU contracts the term-sheet page shows, with correct DONE/active classification, correct blocked shares, and GTD-suffixed stock names.

**Architecture:** Four focused edits to the data layer `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (the Excel renderer in `views.py` is untouched — it already renders `contract['stock_name']`). (1) Remove the current-week DONE/KO filter so all `status != 'inactive'` contracts appear; (2) fix the received-period miscount in `_load_contracts`; (3) fix the same miscount in `_get_blocked_map`; (4) append the GTD suffix to stock names. Each is TDD with its own commit.

**Tech Stack:** Python 3, SQLite (`sqlite3.Row`), openpyxl (indirectly), pytest.

## Global Constraints

- Read-only feature: SELECT only. No schema/data changes. No `localhost/` impact.
- All DB access goes through the connection passed in (from `get_db()`); no direct `sqlite3.connect()` in application code (tests may use it, per existing pattern).
- "Received" period = a `tbl_stock_contract_period` row where `received IS NOT NULL AND received != ''` — never `COUNT(*)` of all period rows.
- Changes are confined to `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` and `tests/functional/test_ltv_stocks_active_count.py`. `views.py` and `legacy_excel_generator.py` are not modified.
- GTD suffix rule (verbatim from `ltv_app/blueprints/term_sheet/models.py:summary`, lines 143–149): `"No"` → `"{stock} No GTD"`; `"Yes"` → `"{stock} GTD 1m"`; otherwise → `"{stock} GTD {gtd}"`; empty/None → plain stock name.
- Test seed data (from `tests/functional/conftest.py`): bank `ref_num=1` = "Citibank No. 1" (`bank_id='CB1'`), code `ref_num=1` = code "700" "Tencent Holdings Limited", currency HKD. So `_load_contracts` results land at `result['HKD']['CB1']['accu'|'decu']`.

---

## File structure

- **Modify:** `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`
  - `_load_contracts` (def at line ~58) — signature, SELECT, remove filter, GTD.
  - `_get_blocked_map` (def at line ~225) — SELECT received count.
  - `get_ltv_stocks_full` (def at line ~14) — caller update.
  - `_parse_trade_date` (def at line ~50) — delete (only the removed filter used it).
  - New module-level helper `_stock_name_with_gtd`.
- **Modify:** `tests/functional/test_ltv_stocks_active_count.py` — update call signatures, remove two obsolete filter tests, add three new tests.

The existing `_add_contract` test helper (top of the test file) inserts a contract plus **one** period with `received='1000'`, columns:
`(ref_num, reference, bank_ref=1, code_ref=1, trade_date, start_date, transaction_type, daily_shares=1000, leveraged='No', spot=100.0, strike_rate=95.0, ko_rate=110.0, tenor, frequency='monthly', gtd='1m', bank_doc='DOC', status)`.

---

### Task 1: Remove the current-week DONE/KO filter

Makes the Excel list all non-inactive contracts (active + DONE + KO), matching term-sheet, and drops the now-unused `report_date` param from `_load_contracts`.

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (`_load_contracts`, `get_ltv_stocks_full`, delete `_parse_trade_date`)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `_load_contracts(db, result: dict, price_map: dict)` — **3 positional args** (was 4; `report_date` removed). Tasks 2 and 4 also edit `_load_contracts` but keep this signature.

- [ ] **Step 1: Update existing test calls and remove obsolete filter tests (write the failing test)**

In `tests/functional/test_ltv_stocks_active_count.py`:

Change the two existing 4-arg calls to 3-arg:
- In `test_load_contracts_sets_is_ko`: `_load_contracts(conn, result, {}, date(2026, 1, 1))` → `_load_contracts(conn, result, {})`
- In `test_ko_overrides_done_when_all_periods_received`: `_load_contracts(conn, result, {}, date(2026, 1, 1))` → `_load_contracts(conn, result, {})`

Delete the entire tests `test_current_week_filters_done_and_ko` and `test_missing_trade_date_done_ko_omitted`.

Append this new test:

```python
def test_done_and_ko_listed_regardless_of_trade_date(app):
    """After removing the week filter, DONE and KO contracts appear no matter
    how old their trade_date is (parity with the term-sheet page)."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 60, 'ACCU', 'active', tenor='1m', trade_date='2020-01-01')  # completes -> DONE
    _add_contract(conn, 61, 'ACCU', 'KO', trade_date='2020-01-01')                  # KO
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    refs = {c['ref_num'] for c in result['HKD']['CB1']['accu']}
    assert 60 in refs   # DONE listed regardless of trade_date
    assert 61 in refs   # KO listed regardless of trade_date
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: FAIL — the two updated existing tests now pass 3 args to a 4-arg function (`TypeError: _load_contracts() missing 1 required positional argument: 'report_date'`), and `test_done_and_ko_listed_regardless_of_trade_date` also raises `TypeError`.

- [ ] **Step 3: Change the signature and remove the filter in `_load_contracts`**

In `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`:

Change the signature:
```python
def _load_contracts(db, result: dict, price_map: dict, report_date: date):
```
to:
```python
def _load_contracts(db, result: dict, price_map: dict):
```

Remove `c.trade_date` from the SELECT — change:
```python
            c.start_date, c.trade_date, c.tenor, c.frequency, c.leveraged, c.status,
```
to:
```python
            c.start_date, c.tenor, c.frequency, c.leveraged, c.status,
```

Delete the current-week window lines that sit between the `rows = db.execute(...).fetchall()` block and the `for row in rows:` loop:
```python
    week_start = report_date - timedelta(days=report_date.weekday())
    week_end   = week_start + timedelta(days=4)
```

Delete the filter block inside the loop (right after the `is_ko` / `is_done` lines):
```python
        # DONE/KO contracts are listed only when traded in the current week
        # (Mon-Fri of the report date). Active contracts are always listed.
        if is_done or is_ko:
            td = _parse_trade_date(row['trade_date'])
            if td is None or not (week_start <= td <= week_end):
                continue
```

The `is_ko` and `is_done` assignments stay (used by `next_date`, the `is_ko` flag, and the active count).

- [ ] **Step 4: Delete the now-unused `_parse_trade_date` helper**

Remove this function (nothing else references it after Step 3):
```python
def _parse_trade_date(value):
    """Parse a stored trade_date (ISO YYYY-MM-DD...) to a date, or None."""
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 5: Update the caller `get_ltv_stocks_full`**

Change:
```python
    _load_contracts(db, result, price_map, report_date)
```
to:
```python
    _load_contracts(db, result, price_map)
```
(`report_date` is still used later in `get_ltv_stocks_full` for prices, positions, and the weekly `week_start` — leave those untouched.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: PASS (all tests, including the new `test_done_and_ko_listed_regardless_of_trade_date`).

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): list all non-inactive contracts (drop current-week DONE/KO filter)"
```

---

### Task 2: Count received periods correctly in `_load_contracts`

Fixes the root-cause miscount so active contracts stop being flagged DONE.

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (`_load_contracts` SELECT)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Consumes: `_load_contracts(db, result, price_map)` (3-arg) from Task 1.
- Produces: no signature change; `received_count` now reflects received-only periods.

- [ ] **Step 1: Write the failing test**

Append to `tests/functional/test_ltv_stocks_active_count.py`:

```python
def test_received_count_uses_received_flag_not_all_periods(app):
    """A contract whose schedule is fully generated but only partly received is
    still active. Counting ALL period rows (the old bug) wrongly marks it DONE."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    # tenor 2m, monthly -> 2 periods expected. _add_contract inserts one RECEIVED
    # period ('1000'); add one UNreceived period ('') so total=2, received=1.
    _add_contract(conn, 50, 'ACCU', 'active', tenor='2m', trade_date='2026-07-06')
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (50, '2026-02-01', '2026-02-28', '20', '', '1m')"
    )
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    ct = {c['ref_num']: c for c in result['HKD']['CB1']['accu']}[50]
    assert ct['is_done'] is False
    assert ct['remaining'] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py::test_received_count_uses_received_flag_not_all_periods -v`
Expected: FAIL — with the old `COUNT(p.ref_num)`, `received_count=2`, `total=2`, `remaining=0`, so `is_done` is `True` (assertion `ct['is_done'] is False` fails).

- [ ] **Step 3: Fix the received count**

In `_load_contracts`, change the SELECT line:
```python
            COUNT(p.ref_num)  AS received_count,
```
to:
```python
            COALESCE(SUM(CASE WHEN p.received IS NOT NULL AND p.received != '' THEN 1 ELSE 0 END), 0) AS received_count,
```
(The `LEFT JOIN tbl_stock_contract_period p` and `GROUP BY c.ref_num` are unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: PASS — the new test passes (`received=1`, `total=2`, `remaining=1`, `is_done False`), and the existing `test_load_contracts_sets_is_ko` / `test_ko_overrides_done_when_all_periods_received` stay green (their single period has `received='1000'`, so tenor `1m` still completes to DONE and tenor `12m` stays active).

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "fix(ltv-stocks): count only received periods when computing remaining/DONE"
```

---

### Task 3: Count received periods correctly in `_get_blocked_map`

Fixes the same miscount so the Positions section shows real blocked shares for active DECUs (currently always 0).

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (`_get_blocked_map` SELECT)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Consumes: nothing from other tasks (`_get_blocked_map(db)` signature unchanged).
- Produces: `_get_blocked_map(db)` returns `{(bank_id, code): blocked_shares}` with correct blocked shares for DECUs that have unreceived periods.

- [ ] **Step 1: Write the failing test**

Add the import at the top of `tests/functional/test_ltv_stocks_active_count.py` (extend the existing import line):

```python
from ltv_app.blueprints.ltv_stocks.create_ltv_stocks import _load_contracts, _get_blocked_map
```

Append this test:

```python
def test_blocked_map_counts_received_periods(app):
    """A DECU with unreceived periods blocks shares. The old COUNT(*) made
    every DECU's remaining 0, so blocked shares were always 0."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    # tenor 2m monthly -> total 2 periods; _add_contract adds one received ('1000').
    _add_contract(conn, 70, 'DECU', 'active', tenor='2m')
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (70, '2026-02-01', '2026-02-28', '20', '', '1m')"
    )
    conn.commit()

    blocked = _get_blocked_map(conn)
    conn.close()

    # daily_shares=1000, leveraged='No', remaining=1 period -> 1000 blocked shares
    # keyed by (bank_id, code) = ('CB1', '700')
    assert blocked.get(('CB1', '700')) == 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py::test_blocked_map_counts_received_periods -v`
Expected: FAIL — with the old `COUNT(p.ref_num)`, `received_count=2`, `total=2`, `remaining=0`, so `_get_blocked_map` hits `if remaining == 0: continue` and the key is absent (`blocked.get(...)` is `None`, not `1000`).

- [ ] **Step 3: Fix the received count**

In `_get_blocked_map`, change the SELECT line:
```python
               COUNT(p.ref_num) AS received_count
```
to:
```python
               COALESCE(SUM(CASE WHEN p.received IS NOT NULL AND p.received != '' THEN 1 ELSE 0 END), 0) AS received_count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "fix(ltv-stocks): count received periods for DECU blocked shares"
```

---

### Task 4: Append the GTD suffix to contract stock names

Makes the Excel Stock Name column read like term-sheet (e.g. "Tencent Holdings Limited GTD 1m").

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (new helper, `_load_contracts` SELECT + contract dict)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Consumes: `_load_contracts(db, result, price_map)` (3-arg) from Task 1.
- Produces: module-level `_stock_name_with_gtd(stock_name: str, gtd) -> str`; contract dicts' `stock_name` now carries the GTD suffix.

- [ ] **Step 1: Write the failing tests**

Extend the import to include the helper:

```python
from ltv_app.blueprints.ltv_stocks.create_ltv_stocks import (
    _load_contracts, _get_blocked_map, _stock_name_with_gtd,
)
```

Append these tests:

```python
def test_stock_name_gtd_suffix():
    assert _stock_name_with_gtd('Alibaba', 'No')  == 'Alibaba No GTD'
    assert _stock_name_with_gtd('Alibaba', 'Yes') == 'Alibaba GTD 1m'
    assert _stock_name_with_gtd('Alibaba', '3m')  == 'Alibaba GTD 3m'
    assert _stock_name_with_gtd('Alibaba', '')    == 'Alibaba'
    assert _stock_name_with_gtd('Alibaba', None)  == 'Alibaba'


def test_load_contracts_applies_gtd_suffix(app):
    """The stock name in a loaded contract carries the GTD suffix."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 80, 'ACCU', 'active')  # helper sets gtd='1m'
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    ct = {c['ref_num']: c for c in result['HKD']['CB1']['accu']}[80]
    assert ct['stock_name'] == 'Tencent Holdings Limited GTD 1m'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -k "gtd" -v`
Expected: FAIL — `ImportError: cannot import name '_stock_name_with_gtd'`.

- [ ] **Step 3: Add the `_stock_name_with_gtd` helper**

In `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`, add this module-level function (place it in the "Helpers" section near the bottom, e.g. just above `_fmt_price`):

```python
def _stock_name_with_gtd(stock_name, gtd):
    """Append the GTD term to the stock name, mirroring term_sheet's summary()."""
    if not gtd:
        return stock_name
    if gtd == "No":
        return f"{stock_name} No GTD"
    if gtd == "Yes":
        return f"{stock_name} GTD 1m"
    return f"{stock_name} GTD {gtd}"
```

- [ ] **Step 4: Select `c.gtd` and apply the suffix in `_load_contracts`**

Add `c.gtd` to the SELECT — change:
```python
            c.start_date, c.tenor, c.frequency, c.leveraged, c.status,
```
to:
```python
            c.start_date, c.tenor, c.frequency, c.leveraged, c.status, c.gtd,
```

In the `contract = { ... }` dict, change:
```python
            'stock_name':       row['stock_name'],
```
to:
```python
            'stock_name':       _stock_name_with_gtd(row['stock_name'], row['gtd']),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): append GTD suffix to contract stock names"
```

---

## Final verification (after all tasks)

- [ ] Run the whole ltv-stocks test file: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -q` → all PASS.
- [ ] Live spot check (server already running; auto-reloads): open `/ltv-stocks/`, report date `2026-07-06`, click **Download Excel**. On the Deutsche Bank Personal (DBPe) sheet confirm the ACCU section now lists Alibaba-6/7, China Molybdenum-19, Geely-14, HK Exchange-18, Tencent-8/10 with GTD suffixes (e.g. "Alibaba GTD 3m"), and the Positions section shows non-zero Blocked shares for active DECUs.

## Self-review

- **Spec coverage:** Req 1 (received count) → Task 2 (`_load_contracts`) + Task 3 (`_get_blocked_map`). Req 2 (list all non-inactive) → Task 1. Req 3 (blocked shares) → Task 3. Req 4 (GTD suffix) → Task 4 (`_stock_name_with_gtd`). Req 5 (active count/column-M unchanged) → no task touches `_active_count` or the `next_date`='DONE' logic; existing `test_generate_excel_count_is_plain_integer` and `test_active_count_excludes_done_and_ko` remain and stay green.
- **Placeholder scan:** none — every code step shows exact before/after.
- **Type consistency:** `_load_contracts(db, result, price_map)` (3-arg) is defined in Task 1 and used unchanged in Tasks 2 and 4 and in `get_ltv_stocks_full`. `_get_blocked_map(db)` unchanged. `_stock_name_with_gtd(stock_name, gtd) -> str` defined and consumed consistently. `received_count` SELECT expression is identical in both queries.
