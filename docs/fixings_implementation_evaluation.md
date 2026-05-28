# Fixings Implementation Evaluation

**Date:** 2026-05-28
**Module:** `ltv_app/blueprints/fixings/`
**URL:** http://192.168.100.79:5000/fixings/

---

## Architecture Overview

The fixings implementation follows a well-structured **three-phase workflow**:

1. **Generate** - Calculate what fixings are due based on ACCU/DECU contracts
2. **Record** - Save the calculated fixings as transactions in the database
3. **View/Edit** - Display recorded fixings grouped by bank account

### Key Components

- **[views.py](../ltv_app/blueprints/fixings/views.py)** - Route handlers
- **[extensions/generate_fixings.py](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)** - Contract analysis and fixing calculations
- **[extensions/download_fixings.py](../ltv_app/blueprints/fixings/extensions/download_fixings.py)** - Excel report generation
- **[extensions/record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py)** - Database persistence
- **[extensions/fixing_average.py](../ltv_app/blueprints/fixings/extensions/fixing_average.py)** - Average price calculations
- **[pages/fixings/home.html](../ltv_app/blueprints/fixings/pages/fixings/home.html)** - User interface

---

## Strengths

### 1. Clean Separation of Concerns

- **Views** - Route handlers only, delegate to extensions
- **Business Logic** - Isolated in extension classes
- **Presentation** - Clean template with JavaScript for interactivity
- **Data Access** - Centralized through `get_db()`

### 2. Performance Optimizations

**File:** [generate_fixings.py:19-35](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

The `GenerateFixings` class shows excellent optimization by pre-loading all reference data:

```python
# Pre-loads ALL holidays once
holidays = {
    (str(r['holi_date'])[:10], r['ccy_id'])
    for r in db.execute(
        "SELECT holi_date, tbl_currency.ccy_id "
        "FROM tbl_holiday "
        "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_holiday.ccy_ref"
    ).fetchall()
}

# Pre-loads ALL closing prices once
closing_cache = {
    (r['code_ref'], str(r['trade_date'])[:10]): r['closing_price']
    for r in db.execute(
        "SELECT code_ref, trade_date, closing_price FROM tbl_stock_price"
    ).fetchall()
}
```

**Impact:** Eliminates N+1 query problems. Instead of hitting the database for every date/contract, it loads all reference data upfront.

### 3. Complex Financial Logic Handled Correctly

#### Single/Double/KO Logic
**File:** [generate_fixings.py:276-286](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

```python
def single_double_ko(transaction_type, strike, ko, closing):
    strike = float(strike)
    ko     = float(ko)
    if transaction_type == "ACCU":
        if ko <= closing:   return 0  # Knocked out
        elif strike >= closing: return 2  # Double shares
        else:               return 1  # Single shares
    else:  # DECU
        if ko >= closing:   return 0  # Knocked out
        elif strike <= closing: return 2  # Double shares
        else:               return 1  # Single shares
```

Correctly determines share accumulation based on ACCU/DECU thresholds.

#### Holiday/Weekend Handling
**File:** [generate_fixings.py:38-55](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

- Properly skips non-trading days
- Uses in-memory lookup for performance
- Supports currency-specific holidays

#### Indicative vs Fixing Days
**File:** [generate_fixings.py:222-240](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

Handles days without closing prices by using previous available closing price:

```python
else:
    # Indicative day — use most recent available closing
    prev_date = prev_day(str(date)[:10])
    prev_closing = get_closing(ts.code_ref, prev_date)
    while prev_closing is None:
        prev_date = prev_day(prev_date)
        prev_closing = get_closing(ts.code_ref, prev_date)
```

#### GTD (Good Till Done) Support
**File:** [generate_fixings.py:218-220](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

Accumulates shares even when KO conditions met if GTD flag is set.

### 4. User-Friendly Interface

**File:** [home.html](../ltv_app/blueprints/fixings/pages/fixings/home.html)

The template provides:
- Date picker with refresh
- Grouped display by bank account
- Inline edit modal with real-time calculations (lines 202-247)
- Clear visual distinction for negative amounts
- Confirmation dialogs for destructive actions
- Keyboard support (ESC to close modal)

### 5. Excel Integration

**File:** [download_fixings.py:27-52](../ltv_app/blueprints/fixings/extensions/download_fixings.py)

The `DownloadFixings` class generates sophisticated Excel reports with:
- Multiple sheets per account/currency
- Dynamic formulas for balance tracking
- Cell styling (colors, borders, fonts)
- Sheet hiding for unused accounts
- Separate "Knockouts" summary sheet

---

## Issues & Concerns

### 1. ⚠️ CRITICAL: No Transaction Safety

**File:** [record_fixings.py:36-37](../ltv_app/blueprints/fixings/extensions/record_fixings.py)

```python
db.execute(sql, args)
db.commit()  # Commits EACH fixing individually
```

**Problem:** If fixing #5 of 20 fails, the first 4 are already committed. No rollback possible.

**Risk:**
- Partial data corruption
- Duplicate fixings if retried
- Inconsistent database state
- Contract status out of sync with transactions

**Fix Needed:**
```python
class RecordFixings:
    def __init__(self, db, fixing_data, trade_date):
        try:
            # All inserts/updates here
            for ccy, accounts in fixing_data.items():
                for account, fixings in accounts.items():
                    for fixing in fixings:
                        # ... insert transaction
                        # ... update contract status

            db.commit()  # Single commit at the end
        except Exception as e:
            db.rollback()
            raise
```

### 2. Security: SQL Injection Risk

**File:** [views.py:21-35](../ltv_app/blueprints/fixings/views.py)

```python
sql = "SELECT ... WHERE T.trade_date=? AND T.transaction_type LIKE '%cu%' ..."
```

The `LIKE '%cu%'` pattern is currently safe (no user input), but this pattern is fragile. If future code changes introduce user input here, it could become vulnerable.

**Recommendation:** Use parameterized queries or ORM for all database access.

### 3. User Experience Issues

#### a) No Error Feedback

**File:** [views.py:155-160](../ltv_app/blueprints/fixings/views.py)

```python
@bp.route('/generate/<trade_date>')
@login_required
def generate(trade_date):
    db = get_db()
    fixing_data = GenerateFixings(trade_date).fixings
    fixings = DownloadFixings(db, trade_date, fixing_data)
    filename = fixings.filename
    return send_file('{}'.format(filename), as_attachment=True)
```

**Issues:**
- No try/except block
- If Excel generation fails, user sees raw error page
- No flash messages for success/failure
- No validation that trade_date is valid format

**Fix Needed:**
```python
@bp.route('/generate/<trade_date>')
@login_required
def generate(trade_date):
    try:
        db = get_db()
        fixing_data = GenerateFixings(trade_date).fixings

        if not fixing_data:
            flash(f"No fixings found for {trade_date}")
            return redirect(url_for('fixings.home'))

        fixings = DownloadFixings(db, trade_date, fixing_data)
        return send_file(fixings.filename, as_attachment=True)
    except Exception as e:
        flash(f"Error generating fixings: {str(e)}", "error")
        return redirect(url_for('fixings.home'))
```

#### b) No Validation Before Recording

**File:** [views.py:163-170](../ltv_app/blueprints/fixings/views.py)

```python
@bp.route('/record/<trade_date>')
@login_required
def record(trade_date):
    db = get_db()
    fixing_data = GenerateFixings(trade_date).fixings
    RecordFixings(db, fixing_data, trade_date)
    flash(f"Recorded fixings for {trade_date}.")
    return redirect(url_for('fixings.home'))
```

**Issues:**
- No check if contracts exist
- No validation that stock prices are available
- No preview before committing transactions
- No error handling
- No check if fixings already recorded

**Needed:**
- Preview page showing what will be recorded
- Validation that all required data exists
- Confirmation before permanent commit

#### c) "Record Fixings" Button Misleading

**File:** [home.html:19-22](../ltv_app/blueprints/fixings/pages/fixings/home.html)

```html
{% if not has_fixings %}
<a href="{{ url_for('fixings.record', trade_date=trade_date) }}" class="btn btn-outline"
   onclick="return confirm('Record fixings for {{ trade_date }}?')">Record Fixings</a>
{% endif %}
```

**Problem:**
- Shows "Record Fixings" only when `not has_fixings`
- If user already recorded fixings for that date, button disappears
- No way to distinguish between "already recorded" vs "no fixings exist for this date"

**Fix Needed:**
- Show different message: "Already Recorded" or "No Fixings Available"
- Add button to "Re-generate" or "View Preview" even if already recorded
- Add timestamp showing when fixings were last recorded

### 4. Data Integrity Concerns

#### a) No Duplicate Prevention

**File:** [record_fixings.py:30-36](../ltv_app/blueprints/fixings/extensions/record_fixings.py)

```python
sql = "INSERT INTO tbl_transaction " \
      "(trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price, " \
      "brokerage, commission, foreign_charge, stamp_duty, misc, spot, ko) " \
      "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?);"
db.execute(sql, args)
db.commit()
```

**Issue:** Inserts transactions without checking if they already exist for that date/contract.

**Result:** Clicking "Record Fixings" twice = duplicate transactions in database

**Fix Needed:**
```python
# Check if fixing already recorded
existing = db.execute(
    "SELECT COUNT(*) FROM tbl_transaction "
    "WHERE trade_date=? AND bank_ref=? AND code_ref=? AND transaction_type=?",
    (trade_date, bank_ref, code_ref, transaction_type)
).fetchone()[0]

if existing > 0:
    raise ValueError(f"Fixing already recorded for {code} on {trade_date}")
```

#### b) Contract Status Update Logic Inconsistent

**File:** [record_fixings.py:39-51](../ltv_app/blueprints/fixings/extensions/record_fixings.py)

```python
if fixing["next_date"] == "KO":
    sql = "UPDATE tbl_stock_contract SET status='KO' WHERE ref_num=?;"
    args = (contract_ref, )
else:
    for period in fixing["fixings"]:
        period_ref = period["period_ref"]
        received = period["shares_fixing"] + period["shares_indicative"]

        sql = "UPDATE tbl_stock_contract_period SET received=? WHERE ref_num=?;"
        args = (received, period_ref)

db.execute(sql, args)
db.commit()
```

**Issues:**
1. No handling for "Done" status (when all periods completed)
2. Contracts that complete all periods remain "active" forever
3. Only the LAST period in the loop is updated (bug - sql/args overwritten)
4. Should update ALL periods in the fixing["fixings"] list

**Fix Needed:**
```python
if fixing["next_date"] == "KO":
    sql = "UPDATE tbl_stock_contract SET status='KO' WHERE ref_num=?;"
    db.execute(sql, (contract_ref,))
elif fixing["next_date"] == "Done":
    sql = "UPDATE tbl_stock_contract SET status='Done' WHERE ref_num=?;"
    db.execute(sql, (contract_ref,))

# Update ALL periods (not just last one)
for period in fixing["fixings"]:
    period_ref = period["period_ref"]
    received = period["shares_fixing"] + period["shares_indicative"]

    sql = "UPDATE tbl_stock_contract_period SET received=? WHERE ref_num=?;"
    db.execute(sql, (received, period_ref))
```

### 5. Code Smells

#### a) Inconsistent Error Handling

**File:** [views.py:94-95](../ltv_app/blueprints/fixings/views.py)

```python
transaction = Transaction(db=get_db())
transaction.get(ref_num=ref_num)
```

**Issue:** No check if transaction exists. If `ref_num` invalid, crashes with unclear error.

**Fix:**
```python
transaction = Transaction(db=get_db())
if not transaction.get(ref_num=ref_num):
    flash(f"Fixing #{ref_num} not found", "error")
    return redirect(url_for('fixings.home'))
```

#### b) Magic Strings

Transaction types hardcoded in multiple places:
- [views.py:97](../ltv_app/blueprints/fixings/views.py) - `'Buy (Accu)', 'Buy (Accu-KO)', 'Sell (Decu)', 'Sell (Decu-KO)'`
- [record_fixings.py:20-28](../ltv_app/blueprints/fixings/extensions/record_fixings.py) - Same strings
- [home.html:138](../ltv_app/blueprints/fixings/pages/fixings/home.html) - Same strings in template

**Recommendation:**
- Create constants file or reference `tbl_transaction_type` table
- Use enum or constants class

```python
# constants.py
TRANSACTION_TYPES = {
    'BUY_ACCU': 'Buy (Accu)',
    'BUY_ACCU_KO': 'Buy (Accu-KO)',
    'SELL_DECU': 'Sell (Decu)',
    'SELL_DECU_KO': 'Sell (Decu-KO)',
}
```

#### c) Mixed Responsibilities in `GenerateFixings`

**File:** [generate_fixings.py](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

The class mixes multiple responsibilities:
- Database queries (loading holidays, prices, contracts)
- Business logic (fixing calculations, KO detection)
- Data transformation (aggregating periods)
- Holiday/closing price caching

**Recommendation:** Split into:
- `HolidayService` - Holiday/trading day logic
- `PriceService` - Stock price lookups with caching
- `ContractRepository` - Load contracts and schedules
- `FixingCalculator` - Pure calculation logic
- `GenerateFixings` - Orchestrates the above

### 6. Performance Concerns

#### a) N+1 on Contract Schedules

**File:** [generate_fixings.py:89-93](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

```python
for contract_ref in active_contract_refs:
    ts = StockContract(db=db)
    ts.get(ref_num=contract_ref)  # Query per contract
    ts.__post_init__()
    ts.get_schedules()            # Query per contract
```

**Issue:** Loads each contract and its schedules individually (N+1 queries).

**Impact:** If 50 active contracts, this makes 100+ database queries.

**Fix:** Batch load all contracts and schedules in 2 queries total.

#### b) Full Table Scans

**File:** [generate_fixings.py:29-35](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)

```python
closing_cache = {
    (r['code_ref'], str(r['trade_date'])[:10]): r['closing_price']
    for r in db.execute("SELECT code_ref, trade_date, closing_price FROM tbl_stock_price")
}.fetchall()
```

**Issue:** Loads **ALL** stock prices from entire database into memory.

**Impact:**
- If database has 10 years of daily prices for 100 stocks = 250,000+ rows loaded
- High memory usage
- Slow query

**Fix:** Filter by date range and relevant stock codes:
```python
# Only load prices from last 90 days for active contracts
min_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
active_codes = [contract.code_ref for contract in active_contracts]

closing_cache = {
    (r['code_ref'], str(r['trade_date'])[:10]): r['closing_price']
    for r in db.execute(
        "SELECT code_ref, trade_date, closing_price FROM tbl_stock_price "
        "WHERE trade_date >= ? AND code_ref IN (...)",
        (min_date, *active_codes)
    ).fetchall()
}
```

### 7. Testing Concerns

**No tests found for fixings module.**

Complex financial logic should have extensive unit tests:
- Single/double/KO calculations
- Holiday handling
- Weekend skipping
- Indicative day fallback logic
- GTD scenarios
- Multiple period aggregation
- Knockout detection
- Average price calculations

**Needed:**
- Unit tests for `single_double_ko()` function
- Unit tests for `analyze_fixing()` with various scenarios
- Integration tests with test database
- Edge case tests (missing prices, all holidays, KO on first day, etc.)

---

## Recommendations

### Priority 1: Critical Fixes (Must Fix Before Production)

1. **Add transaction wrapper to `RecordFixings`**
   - File: [record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py)
   - Wrap entire recording operation in single transaction
   - Add rollback on error
   - Prevent partial commits

2. **Add duplicate detection before recording**
   - File: [record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py)
   - Check if fixings already recorded for date/contract
   - Raise error or skip if duplicate found
   - Add UI indication of already-recorded fixings

3. **Add error handling with user-friendly messages**
   - File: [views.py](../ltv_app/blueprints/fixings/views.py)
   - Wrap `generate()` and `record()` in try/except
   - Flash error messages to user
   - Log errors for debugging

4. **Add validation before recording**
   - File: [views.py](../ltv_app/blueprints/fixings/views.py)
   - Check contracts exist and are active
   - Validate stock prices available
   - Validate trade_date format and is business day

### Priority 2: Data Integrity (Important)

5. **Handle "Done" contract status**
   - File: [record_fixings.py:39-51](../ltv_app/blueprints/fixings/extensions/record_fixings.py)
   - Update contract status to "Done" when all periods completed
   - Fix bug where only last period is updated

6. **Add audit logging for fixing records**
   - Create audit table: `tbl_fixing_audit`
   - Log: user, timestamp, trade_date, count of fixings recorded
   - Track when fixings were generated vs recorded

7. **Show better feedback in UI**
   - File: [home.html](../ltv_app/blueprints/fixings/pages/fixings/home.html)
   - Distinguish "already recorded" vs "no fixings exist"
   - Show timestamp of last recording
   - Add preview before recording

### Priority 3: Code Quality (Should Fix)

8. **Extract constants for transaction types**
   - Create `constants.py` in fixings module
   - Define transaction type constants
   - Use throughout codebase

9. **Split `GenerateFixings` into smaller classes**
   - File: [generate_fixings.py](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)
   - Extract `HolidayService`, `PriceService`, `ContractRepository`, `FixingCalculator`
   - Improve testability and maintainability

10. **Add comprehensive unit tests**
    - Test all calculation functions
    - Test edge cases and error conditions
    - Achieve >80% code coverage

11. **Add integration tests with test database**
    - Test full generate → record → edit workflow
    - Test with various contract scenarios
    - Test error conditions (missing data, duplicates, etc.)

### Priority 4: Performance (Nice to Have)

12. **Batch load contracts and schedules**
    - File: [generate_fixings.py:89-93](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)
    - Load all contracts in single query
    - Load all schedules in single query
    - Reduce N+1 query problem

13. **Filter stock price query by date range**
    - File: [generate_fixings.py:29-35](../ltv_app/blueprints/fixings/extensions/generate_fixings.py)
    - Only load relevant date range (last 90 days)
    - Only load prices for active contract stocks
    - Reduce memory usage

14. **Add database indexes**
    - Add index on `tbl_transaction (trade_date, transaction_type)`
    - Add index on `tbl_stock_price (code_ref, trade_date)`
    - Add index on `tbl_stock_contract (bank_ref, status)`
    - Add index on `tbl_stock_contract_period (contract_ref, end_date)`

---

## Overall Assessment

**Score: 6.5/10**

### Pros:
- ✅ Well-structured architecture with clean separation of concerns
- ✅ Excellent performance optimizations (holiday/price caching)
- ✅ Complex financial logic implemented correctly
- ✅ Sophisticated Excel report generation
- ✅ User-friendly interface with inline editing

### Cons:
- ❌ Critical transaction safety issue (no rollback on partial failure)
- ❌ No duplicate prevention (can record same fixing multiple times)
- ❌ Weak error handling (crashes exposed to user)
- ❌ No test coverage (complex logic untested)
- ❌ Some performance issues (N+1 on contracts)
- ❌ Data integrity issues (contract status not updated correctly)

### Conclusion

The implementation shows sophisticated understanding of the business domain and good architectural patterns. The financial calculations appear correct and the performance optimizations (caching holidays/prices) are well-designed.

However, the module lacks **production-readiness** due to:
1. Missing transaction safety (critical)
2. No error handling
3. No duplicate prevention
4. No testing

**Recommendation:** Address Priority 1 items before using in production. The transaction safety issue could lead to data corruption and is a blocking issue.

---

## Next Steps

1. Review this evaluation with team
2. Prioritize fixes based on risk and impact
3. Create tickets for each recommendation
4. Implement Priority 1 fixes first
5. Add comprehensive test coverage
6. Re-evaluate after fixes applied
