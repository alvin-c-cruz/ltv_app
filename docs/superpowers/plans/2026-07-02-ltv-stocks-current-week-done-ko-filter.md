# LTV Stocks Current-Week DONE/KO Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the LTV Stocks Excel report, list all Active contracts but list DONE/KO contracts only when their `trade_date` falls within the current week (Mon–Fri of the report date).

**Architecture:** `_load_contracts` gains a `report_date` parameter, computes the current-week window once, selects `c.trade_date`, and skips any DONE/KO contract whose `trade_date` is outside that window. `get_ltv_stocks_full` passes `report_date` through. A tiny `_parse_trade_date` helper does defensive ISO parsing.

**Tech Stack:** Python 3, SQLite (sqlite3 Row), openpyxl (indirectly), pytest.

## Global Constraints

- Current week = Monday–Friday of the report date's week: `week_start = report_date - timedelta(days=report_date.weekday())`, `week_end = week_start + timedelta(days=4)`, inclusive both ends.
- "trade date" = the contract's own `tbl_stock_contract.trade_date` (ISO `YYYY-MM-DD`).
- Active contracts (not DONE, not KO) are always listed regardless of `trade_date`.
- A DONE or KO contract is listed only if `week_start <= trade_date <= week_end`; a missing/unparseable `trade_date` on a DONE/KO contract means omit it.
- Applies to both ACCU and DECU (shared loader).
- The active count (A3) and column-M rendering are unchanged; the filter only removes DONE/KO that were never counted.
- No schema/data changes. Changes limited to `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` and the test file `tests/functional/test_ltv_stocks_active_count.py`.

---

## File structure

- `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — `_load_contracts` (signature + `trade_date` select + week filter), new `_parse_trade_date` helper, and `get_ltv_stocks_full` caller update.
- `tests/functional/test_ltv_stocks_active_count.py` — extend the `_add_contract` helper with a `trade_date` kwarg, update the two existing `_load_contracts(...)` calls to pass `report_date`, and add current-week filter tests.

---

### Task 1: Current-week DONE/KO filter in `_load_contracts`

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` (`get_ltv_stocks_full:18`, `_load_contracts:50-69` and its loop, plus a new helper)
- Test: `tests/functional/test_ltv_stocks_active_count.py`

**Interfaces:**
- Consumes: existing `is_done`/`is_ko` computation already in `_load_contracts`.
- Produces: `_load_contracts(db, result, price_map, report_date)` — new required 4th arg `report_date: date`. New helper `_parse_trade_date(value) -> date | None`.

- [ ] **Step 1: Extend the test helper and update existing calls (write the failing test)**

In `tests/functional/test_ltv_stocks_active_count.py`, change the `_add_contract` helper to accept a `trade_date` kwarg. Replace the current helper:

```python
def _add_contract(conn, ref_num, ttype, status, *, tenor='12m'):
    """Insert a contract with a single period.

    With the default tenor ('12m') the contract expects 12 periods, so its one
    period leaves it not-DONE (remaining > 0). Pass tenor='1m' to make the one
    period complete the contract (remaining == 0).
    """
    conn.execute(
        "INSERT INTO tbl_stock_contract "
        "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
        " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) "
        "VALUES (?, ?, 1, 1, '2026-01-01', '2026-01-01', ?, 1000, 'No', "
        " 100.0, 95.0, 110.0, ?, 'monthly', '1m', 'DOC', ?)",
        (ref_num, f"REF{ref_num}", ttype, tenor, status),
    )
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (?, '2026-01-01', '2026-01-31', '20', '1000', '1m')",
        (ref_num,),
    )
```

with:

```python
def _add_contract(conn, ref_num, ttype, status, *, tenor='12m', trade_date='2026-01-01'):
    """Insert a contract with a single period.

    With the default tenor ('12m') the contract expects 12 periods, so its one
    period leaves it not-DONE (remaining > 0). Pass tenor='1m' to make the one
    period complete the contract (remaining == 0). `trade_date` sets the
    contract's inception date used by the current-week filter.
    """
    conn.execute(
        "INSERT INTO tbl_stock_contract "
        "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
        " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) "
        "VALUES (?, ?, 1, 1, ?, '2026-01-01', ?, 1000, 'No', "
        " 100.0, 95.0, 110.0, ?, 'monthly', '1m', 'DOC', ?)",
        (ref_num, f"REF{ref_num}", trade_date, ttype, tenor, status),
    )
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (?, '2026-01-01', '2026-01-31', '20', '1000', '1m')",
        (ref_num,),
    )
```

In the two existing tests, update the `_load_contracts` calls to pass a report date whose week contains `2026-01-01` (2026-01-01 is a Thursday; its week is Mon 2025-12-29 → Fri 2026-01-02), so the existing seeded contracts stay listed:

- In `test_load_contracts_sets_is_ko`, change `_load_contracts(conn, result, {})` to `_load_contracts(conn, result, {}, date(2026, 1, 1))`.
- In `test_ko_overrides_done_when_all_periods_received`, change `_load_contracts(conn, result, {})` to `_load_contracts(conn, result, {}, date(2026, 1, 1))`.

Then append two new tests at the end of the file:

```python
def test_current_week_filters_done_and_ko(app):
    """Active always shown; DONE/KO only when trade_date is in the current week."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    # Report date 2026-07-02 (Thu) -> week Mon 2026-06-29 .. Fri 2026-07-03.
    report_date = date(2026, 7, 2)
    in_week, out_week = '2026-06-30', '2026-05-01'

    _add_contract(conn, 30, 'ACCU', 'active', trade_date=out_week)             # active, old
    _add_contract(conn, 31, 'ACCU', 'active', tenor='1m', trade_date=in_week)  # DONE in week
    _add_contract(conn, 32, 'ACCU', 'active', tenor='1m', trade_date=out_week) # DONE out of week
    _add_contract(conn, 33, 'ACCU', 'KO', trade_date=in_week)                  # KO in week
    _add_contract(conn, 34, 'ACCU', 'KO', trade_date=out_week)                 # KO out of week
    conn.commit()

    result = {}
    _load_contracts(conn, result, {}, report_date)
    conn.close()

    refs = {c['ref_num'] for c in result['HKD']['CB1']['accu']}
    assert 30 in refs            # active always listed, even though trade_date is old
    assert 31 in refs            # DONE in current week -> listed
    assert 33 in refs            # KO in current week -> listed
    assert 32 not in refs        # DONE out of week -> omitted
    assert 34 not in refs        # KO out of week -> omitted


def test_missing_trade_date_done_ko_omitted(app):
    """A DONE/KO contract with NULL trade_date is treated as not-in-week (omitted)."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 40, 'ACCU', 'KO', trade_date=None)
    conn.commit()

    result = {}
    _load_contracts(conn, result, {}, date(2026, 7, 2))
    conn.close()

    accu = result.get('HKD', {}).get('CB1', {}).get('accu', [])
    assert all(c['ref_num'] != 40 for c in accu)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -v`
Expected: FAIL — the two updated existing tests and the two new tests call `_load_contracts` with 4 args, but the function currently takes 3, so they raise `TypeError: _load_contracts() takes 3 positional arguments but 4 were given`.

- [ ] **Step 3: Add the `_parse_trade_date` helper**

In `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`, add this module-level helper (place it just above `_load_contracts`, next to the "Contracts (ACCU / DECU)" section):

```python
def _parse_trade_date(value):
    """Parse a stored trade_date (ISO YYYY-MM-DD...) to a date, or None."""
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Change the `_load_contracts` signature and add `c.trade_date` to the SELECT**

Change the signature line:

```python
def _load_contracts(db, result: dict, price_map: dict):
```

to:

```python
def _load_contracts(db, result: dict, price_map: dict, report_date: date):
```

In the SELECT, add `c.trade_date` to the first column group. Change:

```python
            c.ref_num, c.transaction_type, c.bank_doc,
            c.daily_shares, c.spot, c.strike_rate, c.ko_rate,
            c.start_date, c.tenor, c.frequency, c.leveraged, c.status,
```

to:

```python
            c.ref_num, c.transaction_type, c.bank_doc,
            c.daily_shares, c.spot, c.strike_rate, c.ko_rate,
            c.start_date, c.trade_date, c.tenor, c.frequency, c.leveraged, c.status,
```

- [ ] **Step 5: Compute the current-week window and skip out-of-week DONE/KO**

Immediately after the `rows = db.execute(...).fetchall()` block and before `for row in rows:`, add:

```python
    week_start = report_date - timedelta(days=report_date.weekday())
    week_end   = week_start + timedelta(days=4)
```

Then, in the loop, right after the `is_ko` / `is_done` lines and before `next_date = ...`, add the filter:

```python
        is_ko   = row['status'] == 'KO'
        is_done = remaining == 0 and not is_ko

        # DONE/KO contracts are listed only when traded in the current week
        # (Mon-Fri of the report date). Active contracts are always listed.
        if is_done or is_ko:
            td = _parse_trade_date(row['trade_date'])
            if td is None or not (week_start <= td <= week_end):
                continue
```

- [ ] **Step 6: Update the caller `get_ltv_stocks_full`**

In `get_ltv_stocks_full`, change:

```python
    _load_contracts(db, result, price_map)
```

to:

```python
    _load_contracts(db, result, price_map, report_date)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/functional/test_ltv_stocks_active_count.py -v`
Expected: PASS — all tests (the two prior is_ko/is_done tests, the two active-count tests, and the two new filter tests).

- [ ] **Step 8: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py tests/functional/test_ltv_stocks_active_count.py
git commit -m "feat(ltv-stocks): list DONE/KO contracts only when traded in the current week"
```

---

## Manual verification (after the task)

1. `! python flask_app.py` (already running; auto-reloads).
2. Log in, `/ltv-stocks/`, report date `2026-07-02`, Download Excel. Confirm the 4 KO contracts (trade dates in May–June) are omitted from their sections.
3. Set the report date to `2026-05-27` (the week of ACCU `0981`'s trade date 2026-05-26) and re-download; confirm `0981` appears in the Deutsche/SHK ACCU section.

## Self-review

- **Spec coverage:** Req 1 (active always) → Step 5 filter only guards `is_done or is_ko`; test ref 30. Req 2 (DONE/KO in-week only) → Step 5; tests refs 31–34. Req 3 (both sections) → filter is before the `accu`/`decu` split, `continue` skips either; ACCU exercised in tests, DECU shares the identical code path. Req 4 (missing trade_date omitted) → `td is None` branch; `test_missing_trade_date_done_ko_omitted`. Req 5 (count unaffected) → filter removes only DONE/KO, which `_active_count` already excluded; no count code touched. Req 6 (column M unchanged) → not touched.
- **Placeholder scan:** none.
- **Type consistency:** `_load_contracts(..., report_date: date)` used consistently in caller and all test calls; `_parse_trade_date(value) -> date | None` used once in the filter.
