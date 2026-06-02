# Fixing Reversal Relationship Plan

**Date:** 2026-06-02
**Purpose:** Design a robust way to relate term sheet details to ACCU/DECU transactions for reversal operations

---

## Current State Analysis

### What We Have

#### 1. Database Schema (Line 62-90 in [conftest.py](../tests/functional/conftest.py))

```sql
CREATE TABLE tbl_transaction (
    ref_num          INTEGER PRIMARY KEY,
    -- ... other fields ...
    spot             REAL,           -- Spot price at fixing time
    ko               REAL,           -- Knockout price
    contract_ref     INTEGER,        -- ✅ Links to tbl_stock_contract.ref_num
    periods          TEXT,           -- ✅ Available for storing period data
    -- ... other fields ...
);
```

**Key Finding:** Both `contract_ref` and `periods` fields **already exist** in the database schema!

#### 2. Transaction Recording Process ([record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py))

**Current Flow:**
```python
# Line 30-36: Insert transaction
sql = "INSERT INTO tbl_transaction (trade_date, value_date, bank_ref, code_ref,
       transaction_type, quantity, price, brokerage, commission, foreign_charge,
       stamp_duty, misc, spot, ko) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?);"

# Line 39-51: Update term sheet
if fixing["next_date"] == "KO":
    sql = "UPDATE tbl_stock_contract SET status='KO' WHERE ref_num=?;"
else:
    for period in fixing["fixings"]:
        sql = "UPDATE tbl_stock_contract_period SET received=? WHERE ref_num=?;"
```

**Critical Issue:** `contract_ref` and `periods` are **NOT** being inserted during transaction recording!

#### 3. Fixing Data Structure ([generate_fixings.py](../ltv_app/blueprints/fixings/extensions/generate_fixings.py))

The `fixing` dictionary passed to `RecordFixings` contains rich data:

```python
{
    "contract_ref": 123,              # ✅ Contract reference
    "transaction_type": "ACCU",
    "code": "9988",
    "stock_name": "Alibaba",
    "spot": 88.50,                    # ✅ Spot price
    "strike": 85.00,
    "ko": 79.90,                      # ✅ KO price
    "next_date": "KO" or "2026-06-15" or "Done",
    "fixings": [                      # ✅ Period details!
        {
            "period_ref": 456,        # Which period
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "shares_fixing": 25000,   # Definite shares
            "shares_indicative": 10000, # Indicative shares
            "days_fixing": 20,
            "days_indicative": 2,
            "days_double": 5,
            "days_closing": [(date, price), ...]
        }
    ],
    "shares_fixing": 25000,           # ✅ Total fixing shares
    "shares_indicative": 10000,       # ✅ Total indicative shares
    "value_date": "2026-06-03"
}
```

**Key Insight:** All the data we need for reversal is already available in the `fixing` dictionary during recording!

---

## Relationship Design

### Transaction ↔ Term Sheet Relationship

```
tbl_transaction (Fixing Transaction)
│
├─ contract_ref → tbl_stock_contract.ref_num
│                 ├─ status: 'active' → 'KO' (on KO fixing)
│                 └─ ref_num
│
└─ periods (JSON) → [
       {
           "period_ref": 456,
           "shares_fixing": 25000,
           "shares_indicative": 10000,
           "shares_total": 35000
       }
   ]
                    └─ tbl_stock_contract_period.ref_num
                       └─ received: 0 → 35000 (updated on recording)
```

### JSON Structure for `periods` Field

We'll store a JSON array linking each period affected by this fixing:

```json
[
    {
        "period_ref": 456,
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "shares_fixing": 25000,
        "shares_indicative": 10000,
        "shares_total": 35000
    }
]
```

**Rationale:**
- ✅ **period_ref**: Essential for identifying which period to reverse
- ✅ **shares_total**: Essential for calculating reversal amount
- ✅ **shares_fixing/indicative**: Useful for audit trail and validation
- ✅ **start_date/end_date**: Useful for UI display and debugging
- ✅ **Multiple periods**: Handles KO fixings that affect multiple periods

---

## Implementation Plan

### Phase 1: Update RecordFixings to Store Relationship Data

**File:** [ltv_app/blueprints/fixings/extensions/record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py)

**Changes:**

```python
import json

class RecordFixings:
    def __init__(self, db, fixing_data, trade_date):
        for ccy, accounts in fixing_data.items():
            for account, fixings in accounts.items():
                for fixing in fixings:
                    contract_ref = fixing["contract_ref"]
                    spot = fixing["spot"]
                    ko = fixing["ko"]
                    value_date = fixing["value_date"]
                    bank_ref = db.execute("SELECT ref_num FROM tbl_bank_account WHERE bank_id=?",
                                         (account,)).fetchone()[0]
                    code_ref = db.execute("SELECT ref_num FROM tbl_code WHERE code=?",
                                         (fixing["code"],)).fetchone()[0]
                    transaction_type = fixing["transaction_type"]
                    quantity = fixing["shares_fixing"] + fixing["shares_indicative"]
                    price = fixing["strike"]

                    if transaction_type == "DECU":
                        quantity = quantity * -1

                    if fixing["next_date"] == "KO":
                        if transaction_type == "ACCU":
                            transaction_type = "Buy (Accu-KO)"
                        else:
                            transaction_type = "Sell (Decu-KO)"
                    else:
                        if transaction_type == "ACCU":
                            transaction_type = "Buy (Accu)"
                        else:
                            transaction_type = "Sell (Decu)"

                    # ✅ NEW: Build periods JSON
                    periods_data = []
                    for period in fixing["fixings"]:
                        periods_data.append({
                            "period_ref": period["period_ref"],
                            "start_date": period["start_date"],
                            "end_date": period["end_date"],
                            "shares_fixing": period["shares_fixing"],
                            "shares_indicative": period["shares_indicative"],
                            "shares_total": period["shares_fixing"] + period["shares_indicative"]
                        })
                    periods_json = json.dumps(periods_data)

                    # ✅ UPDATED: Add contract_ref and periods to INSERT
                    sql = "INSERT INTO tbl_transaction " \
                          "(trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price, " \
                          "brokerage, commission, foreign_charge, stamp_duty, misc, spot, ko, contract_ref, periods) " \
                          "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?, ?, ?);"
                    args = (trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price,
                           spot, ko, contract_ref, periods_json)

                    db.execute(sql, args)
                    db.commit()

                    # Existing term sheet update logic remains the same
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

**Changes Made:**
1. Import `json` module
2. Build `periods_data` list from `fixing["fixings"]`
3. Convert to JSON string with `json.dumps()`
4. Add `contract_ref` and `periods` to SQL INSERT statement
5. Include in `args` tuple

---

### Phase 2: Create ReverseFixing Class

**File:** [ltv_app/blueprints/fixings/extensions/reverse_fixing.py](../ltv_app/blueprints/fixings/extensions/reverse_fixing.py) (NEW)

```python
import json


class ReverseFixing:
    """
    Reverse term sheet updates when a fixing transaction is deleted or modified.

    Usage:
        reverser = ReverseFixing(db, transaction_ref)
        reverser.reverse()
    """

    def __init__(self, db, transaction_ref):
        self.db = db
        self.transaction_ref = transaction_ref
        self.transaction = self.get_transaction()

    def get_transaction(self):
        """Retrieve transaction details"""
        sql = """
            SELECT ref_num, transaction_type, quantity,
                   contract_ref, periods, spot, ko
            FROM tbl_transaction
            WHERE ref_num = ?
        """
        result = self.db.execute(sql, (self.transaction_ref,)).fetchone()
        if not result:
            raise ValueError(f"Transaction {self.transaction_ref} not found")
        return dict(result)

    def reverse(self):
        """
        Reverse the term sheet updates made by this fixing transaction.

        Returns:
            dict: Summary of what was reversed
        """
        contract_ref = self.transaction["contract_ref"]
        transaction_type = self.transaction["transaction_type"]

        if not contract_ref:
            # Not a fixing transaction, nothing to reverse
            return {
                "status": "skipped",
                "reason": "Not a fixing transaction (no contract_ref)"
            }

        # Check if this was a KO transaction
        if "KO" in transaction_type or "-KO)" in transaction_type:
            return self.reverse_knockout(contract_ref)
        else:
            return self.reverse_regular_fixing()

    def reverse_knockout(self, contract_ref):
        """
        Revert contract status from KO back to active.

        Args:
            contract_ref: The contract reference number

        Returns:
            dict: Summary of reversal
        """
        # Change status back to active
        sql = "UPDATE tbl_stock_contract SET status='active' WHERE ref_num=?"
        self.db.execute(sql, (contract_ref,))
        self.db.commit()

        return {
            "status": "success",
            "type": "knockout",
            "contract_ref": contract_ref,
            "action": "Status changed from 'KO' to 'active'"
        }

    def reverse_regular_fixing(self):
        """
        Remove accumulated/decumulated shares from periods.

        Returns:
            dict: Summary of reversal
        """
        periods_text = self.transaction.get("periods")
        if not periods_text:
            return {
                "status": "warning",
                "reason": "No period data stored in transaction (legacy transaction)"
            }

        # Parse periods JSON
        try:
            periods = json.loads(periods_text)
        except (json.JSONDecodeError, TypeError) as e:
            return {
                "status": "error",
                "reason": f"Could not parse periods JSON: {e}"
            }

        reversed_periods = []
        for period in periods:
            period_ref = period.get("period_ref")
            shares_total = period.get("shares_total", 0)

            if not period_ref:
                continue

            # Subtract the shares that were previously added
            sql = """
                UPDATE tbl_stock_contract_period
                SET received = received - ?
                WHERE ref_num = ?
            """
            self.db.execute(sql, (shares_total, period_ref))

            reversed_periods.append({
                "period_ref": period_ref,
                "shares_removed": shares_total,
                "period_dates": f"{period.get('start_date')} to {period.get('end_date')}"
            })

        self.db.commit()

        return {
            "status": "success",
            "type": "regular_fixing",
            "contract_ref": self.transaction["contract_ref"],
            "periods_reversed": reversed_periods
        }

    def get_summary(self):
        """
        Get a human-readable summary of what will be reversed.
        Useful for confirmation dialogs.

        Returns:
            str: Human-readable summary
        """
        if not self.transaction["contract_ref"]:
            return "This is not a fixing transaction. No term sheet updates to reverse."

        transaction_type = self.transaction["transaction_type"]

        if "KO" in transaction_type or "-KO)" in transaction_type:
            return (
                f"This fixing transaction knocked out contract #{self.transaction['contract_ref']}.\n"
                f"Reversing will change the contract status from 'KO' back to 'active'."
            )
        else:
            periods_text = self.transaction.get("periods")
            if not periods_text:
                return "Warning: No period data stored. Cannot determine what will be reversed."

            try:
                periods = json.loads(periods_text)
                total_shares = sum(p.get("shares_total", 0) for p in periods)
                period_count = len(periods)

                return (
                    f"This fixing transaction added {total_shares:,} shares across {period_count} period(s).\n"
                    f"Reversing will remove these shares from the term sheet."
                )
            except (json.JSONDecodeError, TypeError):
                return "Warning: Could not parse period data."
```

**Key Features:**
- ✅ Handles both KO and regular fixings
- ✅ Returns detailed summary for logging/display
- ✅ Gracefully handles legacy transactions without period data
- ✅ Provides `get_summary()` for confirmation dialogs

---

### Phase 3: Update Delete Endpoint

**File:** [ltv_app/blueprints/fixings/views.py](../ltv_app/blueprints/fixings/views.py)

**Current Code (Lines 141-150):**
```python
@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete(ref_num):
    from .. database import get_db

    db = get_db()

    transaction = Transaction(db=db)
    transaction.get(ref_num=ref_num)
    transaction.delete()

    return redirect(url_for('fixings.home'))
```

**Updated Code:**
```python
@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete(ref_num):
    from flask import request, flash
    from .. database import get_db
    from . extensions.reverse_fixing import ReverseFixing

    db = get_db()

    # Handle GET request: Show confirmation page
    if request.method == 'GET':
        try:
            reverser = ReverseFixing(db, ref_num)
            summary = reverser.get_summary()
            transaction = reverser.transaction

            # Render confirmation template
            return render_template(
                'fixings/delete_confirmation.html',
                ref_num=ref_num,
                transaction=transaction,
                reversal_summary=summary
            )
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('fixings.home'))

    # Handle POST request: Perform deletion
    # Reverse term sheet updates BEFORE deleting transaction
    try:
        reverser = ReverseFixing(db, ref_num)
        result = reverser.reverse()

        if result["status"] == "success":
            flash(f"Term sheet updated: {result.get('action', 'Shares removed')}", "success")
        elif result["status"] == "warning":
            flash(f"Warning: {result['reason']}", "warning")
        elif result["status"] == "error":
            flash(f"Error: {result['reason']}", "error")
            return redirect(url_for('fixings.home'))
    except Exception as e:
        flash(f"Error reversing term sheet: {e}", "error")
        return redirect(url_for('fixings.home'))

    # Now delete the transaction
    transaction = Transaction(db=db)
    transaction.get(ref_num=ref_num)
    transaction.delete()

    flash(f"Fixing #{ref_num} has been deleted and term sheet updated.", "success")
    return redirect(url_for('fixings.home'))
```

**Changes:**
1. Import `ReverseFixing` class
2. On GET: Show confirmation page with reversal summary
3. On POST: Reverse term sheet updates before deletion
4. Provide detailed feedback to user

---

### Phase 4: Handle Edit Operations

**File:** [ltv_app/blueprints/fixings/views.py](../ltv_app/blueprints/fixings/views.py)

**Strategy for Edits:**

Editing is more complex than deletion because:
- Quantity might change
- Transaction type might change
- Which periods are affected might change
- Recalculating which periods should be updated requires regenerating fixing logic

**Recommended Approach: Treat Edit as Delete + Recreate**

1. **Option A: Block Edits (Simplest)**
   - Display warning message
   - User must delete and recreate fixing

2. **Option B: Partial Edit (Recommended)**
   - Allow editing non-critical fields (comments, dates)
   - Block editing critical fields (quantity, type, contract)

3. **Option C: Full Edit with Reversal (Complex)**
   - Reverse old fixing
   - Regenerate fixing with new parameters
   - Reapply to term sheet

**Recommended: Option B**

```python
# Add to edit view
EDITABLE_FIELDS = ['trade_date', 'value_date', 'comments']
NON_EDITABLE_FIELDS = ['quantity', 'price', 'transaction_type', 'contract_ref']

if request.method == 'POST':
    # Check if any non-editable fields changed
    for field in NON_EDITABLE_FIELDS:
        if field in request.form and getattr(transaction, field) != request.form[field]:
            flash(
                f"Cannot edit {field}. To change this, delete the fixing and regenerate it.",
                "error"
            )
            return redirect(url_for('fixings.edit', ref_num=ref_num))

    # Proceed with edit for editable fields only
    # ...
```

---

## Data Migration

### Existing Transactions

Transactions created before this implementation will have:
- ✅ `contract_ref`: May already exist (check schema)
- ❌ `periods`: Will be NULL or empty

**Migration Strategy:**

1. **Accept Limitation**
   - Old transactions without `periods` data cannot be auto-reversed
   - `ReverseFixing` will return a warning status
   - User must manually fix term sheets if needed

2. **Provide Manual Fix Tool** (Future)
   - Admin page to recalculate term sheet state
   - Query all transactions for a contract
   - Rebuild term sheet from scratch

---

## Testing Strategy

### Unit Tests

**File:** `tests/unit/test_reverse_fixing.py` (NEW)

```python
import json
import pytest
from ltv_app.blueprints.fixings.extensions.reverse_fixing import ReverseFixing


def test_reverse_knockout(db_conn):
    """Test reversing a KO fixing"""
    # Setup: Create contract and KO transaction
    db_conn.execute("INSERT INTO tbl_stock_contract (ref_num, status) VALUES (1, 'KO')")
    db_conn.execute("""
        INSERT INTO tbl_transaction (ref_num, contract_ref, transaction_type, periods)
        VALUES (1, 1, 'Buy (Accu-KO)', NULL)
    """)
    db_conn.commit()

    # Execute reversal
    reverser = ReverseFixing(db_conn, 1)
    result = reverser.reverse()

    # Assert contract status changed back to active
    status = db_conn.execute("SELECT status FROM tbl_stock_contract WHERE ref_num=1").fetchone()[0]
    assert status == 'active'
    assert result["status"] == "success"
    assert result["type"] == "knockout"


def test_reverse_regular_fixing(db_conn):
    """Test reversing a regular fixing"""
    # Setup: Create period with shares
    db_conn.execute("""
        INSERT INTO tbl_stock_contract_period (ref_num, received)
        VALUES (1, 35000)
    """)

    periods_json = json.dumps([{
        "period_ref": 1,
        "shares_total": 35000
    }])

    db_conn.execute("""
        INSERT INTO tbl_transaction (ref_num, contract_ref, transaction_type, periods)
        VALUES (1, 1, 'Buy (Accu)', ?)
    """, (periods_json,))
    db_conn.commit()

    # Execute reversal
    reverser = ReverseFixing(db_conn, 1)
    result = reverser.reverse()

    # Assert shares removed
    received = db_conn.execute("SELECT received FROM tbl_stock_contract_period WHERE ref_num=1").fetchone()[0]
    assert received == 0
    assert result["status"] == "success"


def test_reverse_without_period_data(db_conn):
    """Test reversing old transaction without period data"""
    db_conn.execute("""
        INSERT INTO tbl_transaction (ref_num, contract_ref, transaction_type, periods)
        VALUES (1, 1, 'Buy (Accu)', NULL)
    """)
    db_conn.commit()

    reverser = ReverseFixing(db_conn, 1)
    result = reverser.reverse()

    assert result["status"] == "warning"
    assert "No period data" in result["reason"]
```

### Integration Tests

**File:** `tests/functional/test_fixing_delete.py` (NEW)

```python
def test_delete_fixing_with_reversal(auth_client, db_conn):
    """Test deleting a fixing reverses term sheet updates"""
    # Setup: Create full fixing transaction with term sheet
    # ... (setup code)

    # Delete fixing
    response = auth_client.post('/fixings/1/delete')

    # Assert transaction deleted
    txn = db_conn.execute("SELECT * FROM tbl_transaction WHERE ref_num=1").fetchone()
    assert txn is None

    # Assert term sheet reversed
    contract = db_conn.execute("SELECT status FROM tbl_stock_contract WHERE ref_num=1").fetchone()
    assert contract['status'] == 'active'
```

---

## Rollout Checklist

### Phase 1: Data Preparation (Week 1)
- [ ] Update `RecordFixings` to store `contract_ref` and `periods`
- [ ] Test new recordings generate correct JSON
- [ ] Verify no breaking changes to existing flow
- [ ] Deploy to test environment

### Phase 2: Reversal Logic (Week 2)
- [ ] Create `ReverseFixing` class
- [ ] Write unit tests (knockout and regular)
- [ ] Test with sample data
- [ ] Handle edge cases (missing data, multiple periods)

### Phase 3: Integration (Week 3)
- [ ] Update delete endpoint with confirmation page
- [ ] Create delete confirmation template
- [ ] Add flash messages for feedback
- [ ] Test end-to-end delete flow
- [ ] Handle edit strategy (blocking or partial)

### Phase 4: Testing (Week 4)
- [ ] Integration tests for delete flow
- [ ] Manual testing with real data
- [ ] Test with old transactions (no period data)
- [ ] Performance testing with large datasets

### Phase 5: Deployment (Week 5)
- [ ] Deploy to production
- [ ] Monitor for errors
- [ ] Document new workflow
- [ ] User training on delete confirmations

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing period data in old transactions | Medium | Accept limitation, provide warning, manual fix tool |
| JSON parsing errors | Low | Wrap in try/except, return error status |
| Database inconsistency during reversal | High | Use transactions, rollback on error |
| User confusion about blocking edits | Low | Clear error messages, documentation |
| Performance with large period arrays | Low | JSON parsing is fast, minimal overhead |

---

## Success Metrics

- ✅ All new fixing transactions store `contract_ref` and `periods`
- ✅ Delete operations successfully reverse term sheet updates
- ✅ No database inconsistencies after reversal
- ✅ Clear user feedback on what was reversed
- ✅ Legacy transactions handled gracefully with warnings

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Begin Phase 1**: Update `RecordFixings` class
3. **Test thoroughly** with sample data
4. **Proceed to Phase 2**: Create `ReverseFixing` class

**Estimated Timeline:** 5 weeks for complete implementation
**Priority:** High (data integrity issue)
