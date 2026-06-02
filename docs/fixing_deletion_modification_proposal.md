# Fixing Deletion and Modification Proposal

**Date:** 2026-06-01
**Issue:** When fixing transactions are deleted or modified, the related term sheet (stock contract) is not updated.

---

## Current Problem

### When Recording Fixings:
✅ **Currently Working:**
1. Transaction is inserted into `tbl_transaction`
2. If KO: `tbl_stock_contract.status` is updated to 'KO'
3. If regular fixing: `tbl_stock_contract_period.received` is updated with shares accumulated/decumulated

**File:** [ltv_app/blueprints/fixings/extensions/record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py)

### When Deleting/Modifying Fixings:
❌ **Currently NOT Working:**
1. Transaction is deleted/modified in `tbl_transaction`
2. **BUT** `tbl_stock_contract` status remains unchanged
3. **AND** `tbl_stock_contract_period.received` is not updated

**File:** [ltv_app/blueprints/fixings/views.py:141-150](../ltv_app/blueprints/fixings/views.py)

---

## Data Relationships

### Tables Involved:

```
tbl_stock_contract (Term Sheet)
├── ref_num (contract_ref)
├── status ('active', 'KO', 'Done')
└── [has many] tbl_stock_contract_period
    ├── ref_num (period_ref)
    ├── start_date
    ├── end_date
    └── received (shares accumulated/decumulated)

tbl_transaction (Fixing Transaction)
├── ref_num
├── transaction_type ('Buy (Accu)', 'Buy (Accu-KO)', 'Sell (Decu)', 'Sell (Decu-KO)')
├── quantity (shares)
├── spot (spot price at fixing)
├── ko (knockout price)
├── contract_ref → links to tbl_stock_contract.ref_num
└── periods (JSON/text of period_refs affected)
```

### Key Data in Transaction:
From schema analysis:
- `contract_ref` - Links transaction back to the term sheet
- `periods` - Text/JSON field storing which periods were affected
- `spot` - Spot price at fixing time
- `ko` - Knockout price

---

## Proposed Solution

### Option 1: Store Reverse Transaction Data (Recommended)

**Approach:** Store enough data in the transaction to reverse the term sheet updates.

#### Implementation:

**Step 1: Enhance Transaction Record**
Currently stores: `contract_ref`, `spot`, `ko`
Already available: `contract_ref`, `periods` fields

**Step 2: Create Reverse Function**

```python
# ltv_app/blueprints/fixings/extensions/reverse_fixing.py

class ReverseFixing:
    """Reverse term sheet updates when a fixing transaction is deleted or modified"""

    def __init__(self, db, transaction_ref):
        self.db = db
        self.transaction = self.get_transaction(transaction_ref)

    def get_transaction(self, ref_num):
        """Get transaction details"""
        sql = """
            SELECT ref_num, transaction_type, quantity,
                   contract_ref, periods, spot, ko
            FROM tbl_transaction
            WHERE ref_num = ?
        """
        result = self.db.execute(sql, (ref_num,)).fetchone()
        if not result:
            raise ValueError(f"Transaction {ref_num} not found")
        return dict(result)

    def reverse(self):
        """Reverse the term sheet updates"""
        contract_ref = self.transaction['contract_ref']
        transaction_type = self.transaction['transaction_type']

        if not contract_ref:
            # Not a fixing transaction, nothing to reverse
            return

        # Check if this was a KO transaction
        if 'KO' in transaction_type:
            self.reverse_knockout(contract_ref)
        else:
            self.reverse_regular_fixing(contract_ref)

    def reverse_knockout(self, contract_ref):
        """Revert contract status from KO back to active"""
        sql = "UPDATE tbl_stock_contract SET status='active' WHERE ref_num=?"
        self.db.execute(sql, (contract_ref,))
        self.db.commit()

    def reverse_regular_fixing(self, contract_ref):
        """Remove accumulated/decumulated shares from periods"""
        periods_text = self.transaction['periods']
        if not periods_text:
            # No period data stored, cannot reverse
            return

        # Parse periods (assuming JSON format: [{"period_ref": 123, "shares": 1000}, ...])
        import json
        try:
            periods = json.loads(periods_text)
        except (json.JSONDecodeError, TypeError):
            # If periods is stored differently, handle accordingly
            return

        for period in periods:
            period_ref = period.get('period_ref')
            shares = period.get('shares', 0)

            if period_ref:
                # Subtract the shares that were previously added
                sql = """
                    UPDATE tbl_stock_contract_period
                    SET received = received - ?
                    WHERE ref_num = ?
                """
                self.db.execute(sql, (shares, period_ref))

        self.db.commit()
```

**Step 3: Update Delete Function**

```python
# ltv_app/blueprints/fixings/views.py

@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete(ref_num):
    from .. database import get_db
    from . extensions import ReverseFixing

    db = get_db()

    # Reverse term sheet updates BEFORE deleting transaction
    try:
        reverser = ReverseFixing(db, ref_num)
        reverser.reverse()
    except Exception as e:
        flash(f"Warning: Could not reverse term sheet updates: {e}", "warning")

    # Now delete the transaction
    transaction = Transaction(db=db)
    transaction.get(ref_num=ref_num)
    transaction.delete()

    flash(f"Fixing #{ref_num} has been deleted and term sheet updated.")
    return redirect(url_for('fixings.home'))
```

**Step 4: Update Edit Function**

```python
# ltv_app/blueprints/fixings/views.py

@bp.route('/<ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit(ref_num):
    from .. database import get_db
    from . extensions import ReverseFixing

    db = get_db()
    transaction = Transaction(db=db)
    transaction.get(ref_num=ref_num)

    if request.method == 'POST':
        # Get old quantity before updating
        old_quantity = transaction.quantity
        old_contract_ref = transaction.contract_ref

        # Update transaction fields
        transaction.trade_date = request.form["trade_date"]
        transaction.value_date = request.form["value_date"]
        # ... (existing field updates)
        transaction.quantity = int(request.form["quantity"])

        # If quantity changed and this is a fixing transaction
        if old_quantity != transaction.quantity and old_contract_ref:
            quantity_diff = transaction.quantity - old_quantity

            # Update the term sheet periods
            # Note: This assumes we can recalculate which periods to update
            # This is the complex part - see detailed notes below
            update_period_shares(db, old_contract_ref, quantity_diff, transaction)

        transaction.save()
        flash(f"Fixing #{ref_num} has been updated.")
        return redirect(url_for('fixings.home'))

    # ... (existing GET logic)
```

---

### Option 2: Query and Recalculate (Alternative)

**Approach:** When deleting/modifying, query the contract and recalculate what the state should be.

#### Implementation:

```python
class RecalculateTermSheet:
    """Recalculate term sheet state by examining all fixing transactions"""

    def __init__(self, db, contract_ref):
        self.db = db
        self.contract_ref = contract_ref

    def recalculate(self):
        """Recalculate term sheet status and period shares"""
        # Get all transactions for this contract
        sql = """
            SELECT ref_num, transaction_type, quantity, periods
            FROM tbl_transaction
            WHERE contract_ref = ?
            ORDER BY trade_date
        """
        transactions = self.db.execute(sql, (self.contract_ref,)).fetchall()

        # Check if any transaction is a KO
        has_ko = any('KO' in t['transaction_type'] for t in transactions)

        if has_ko:
            sql = "UPDATE tbl_stock_contract SET status='KO' WHERE ref_num=?"
            self.db.execute(sql, (self.contract_ref,))
        else:
            # Check if all periods are complete
            is_done = self.check_if_done()
            status = 'Done' if is_done else 'active'
            sql = "UPDATE tbl_stock_contract SET status=? WHERE ref_num=?"
            self.db.execute(sql, (status, self.contract_ref))

        # Recalculate period shares
        self.recalculate_periods(transactions)

        self.db.commit()

    def recalculate_periods(self, transactions):
        """Reset and recalculate all period.received values"""
        # Reset all periods to 0
        sql = """
            UPDATE tbl_stock_contract_period
            SET received = 0
            WHERE contract_ref = ?
        """
        # Note: Need to add contract_ref to tbl_stock_contract_period if not exists

        # Reapply all transactions
        for txn in transactions:
            if 'KO' not in txn['transaction_type']:
                # Parse periods and add shares
                # ... (implementation depends on periods format)
                pass

    def check_if_done(self):
        """Check if all periods have been completed"""
        # Implementation depends on business logic
        pass
```

**Pros:**
- No dependency on stored period data in transaction
- Always accurate (rebuilds from scratch)
- Handles edge cases automatically

**Cons:**
- More complex logic
- Slower (requires querying all related transactions)
- May need to add `contract_ref` to `tbl_stock_contract_period` table

---

### Option 3: Soft Delete with Reversal Flag (Conservative)

**Approach:** Don't actually delete transactions, just mark them as deleted and reverse their effect.

```python
# Add column to tbl_transaction
ALTER TABLE tbl_transaction ADD COLUMN deleted INTEGER DEFAULT 0;

# When deleting
UPDATE tbl_transaction SET deleted = 1 WHERE ref_num = ?;

# Reverse term sheet updates
# ... (same as Option 1)

# All queries filter deleted transactions
SELECT * FROM tbl_transaction WHERE deleted = 0;
```

**Pros:**
- Audit trail preserved
- Can undo deletions
- Safer

**Cons:**
- Database schema change required
- All existing queries need updating
- More complex data model

---

## Recommended Approach: Hybrid Solution

Combine **Option 1** (for immediate reversals) with **Option 2** (as verification/correction tool):

### Implementation Plan:

#### Phase 1: Immediate Fix (Option 1)
1. **Update `RecordFixings` to store period data**
   - Store `contract_ref` (already done via spot/ko fields)
   - Store `periods` as JSON: `[{"period_ref": 123, "shares": 1000}, ...]`

2. **Create `ReverseFixing` class**
   - Reverse KO: Change status back to 'active'
   - Reverse regular: Subtract shares from periods

3. **Update delete endpoint** to call `ReverseFixing`

4. **Update edit endpoint** to handle quantity changes

#### Phase 2: Safety Net (Option 2)
5. **Create `RecalculateTermSheet` tool**
   - Admin function to recalculate contract state
   - Run on-demand or scheduled
   - Catches any inconsistencies

6. **Add verification checks**
   - Compare stored state vs. calculated state
   - Alert if mismatch found
   - Provide fix button

---

## Technical Challenges

### Challenge 1: Periods Field Format
**Question:** How is `periods` currently stored in `tbl_transaction`?

**Options:**
- JSON string: `'[{"period_ref": 123, "shares": 1000}]'`
- Comma-separated: `'123,456,789'`
- Not stored at all (need to add)

**Action:** Need to examine existing data or modify `RecordFixings` to store this.

### Challenge 2: Multiple Periods per Fixing
Some fixings affect multiple periods (e.g., KO affects all future periods with GTD flag).

**Solution:** Store all affected periods in the `periods` field:
```json
[
    {"period_ref": 123, "shares": 1000},
    {"period_ref": 124, "shares": 2000}
]
```

### Challenge 3: Edit vs. Delete
**Edit** is trickier than delete because:
- Quantity might change
- Transaction type might change (Buy → Sell?)
- Which periods are affected might change

**Proposed Edit Logic:**
1. If `contract_ref` changed: Full reverse old + apply new
2. If quantity changed: Calculate diff and adjust periods
3. If transaction type changed: Full reverse old + apply new

**Simpler Alternative:** Treat edit as delete + re-record:
```python
# Reverse the old state
reverser = ReverseFixing(db, ref_num)
reverser.reverse()

# Update transaction
transaction.save()

# Re-apply with new values
# (Requires re-running fixing logic - complex!)
```

---

## Database Schema Changes Needed

### Option A: Use Existing Fields
- ✅ `contract_ref` - Already exists
- ✅ `periods` - Already exists (check if populated)
- ✅ `spot`, `ko` - Already exists

**No schema changes needed!** Just need to ensure `periods` is populated during recording.

### Option B: Add Tracking Fields (If needed)
```sql
ALTER TABLE tbl_transaction ADD COLUMN contract_ref INTEGER;
ALTER TABLE tbl_transaction ADD COLUMN periods TEXT;
ALTER TABLE tbl_transaction ADD COLUMN fixing_metadata TEXT; -- JSON with all needed data
```

---

## Implementation Steps

### Step 1: Investigate Current Data
```python
# Check if periods is being stored
SELECT ref_num, transaction_type, contract_ref, periods
FROM tbl_transaction
WHERE transaction_type LIKE '%Accu%' OR transaction_type LIKE '%Decu%'
LIMIT 5;
```

### Step 2: Update RecordFixings
Modify [record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py) to store period data:

```python
# Line 30-34: When inserting transaction
import json

periods_json = json.dumps([
    {
        "period_ref": period["period_ref"],
        "shares": period["shares_fixing"] + period["shares_indicative"]
    }
    for period in fixing["fixings"]
])

sql = "INSERT INTO tbl_transaction " \
      "(trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price, " \
      "brokerage, commission, foreign_charge, stamp_duty, misc, spot, ko, contract_ref, periods) " \
      "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?, ?, ?);"
args = (trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price,
        spot, ko, contract_ref, periods_json)
```

### Step 3: Create ReverseFixing Class
Create new file: `ltv_app/blueprints/fixings/extensions/reverse_fixing.py`

### Step 4: Update Delete/Edit Routes
Modify [views.py](../ltv_app/blueprints/fixings/views.py)

### Step 5: Test Thoroughly
- Test KO deletion → status back to active
- Test regular fixing deletion → shares removed from periods
- Test editing quantity → shares adjusted
- Test edge cases (missing data, multiple periods, etc.)

### Step 6: Add Admin Tool (Phase 2)
Create recalculation tool for fixing inconsistencies

---

## UI Considerations

### Confirmation Dialog
Before deleting, show user what will happen:

```
Delete Fixing #123?

This fixing transaction will be deleted and the related term sheet will be updated:

✓ Transaction: Buy (Accu) 35,000 shares will be removed
✓ Term Sheet: Contract #456 will have 35,000 shares removed from period 2026-05-01 to 2026-05-31

Are you sure you want to continue?

[Cancel] [Delete and Update Term Sheet]
```

### Edit Warning
When editing quantity:

```
⚠️ Warning: Changing quantity will update the term sheet

Old quantity: 35,000 shares
New quantity: 30,000 shares
Difference: -5,000 shares

The related term sheet will be adjusted by -5,000 shares.

[Cancel] [Save Changes]
```

---

## Testing Strategy

### Unit Tests
```python
def test_reverse_knockout():
    # Record a KO fixing
    # Delete the fixing
    # Assert contract status is back to 'active'

def test_reverse_regular_fixing():
    # Record a regular fixing
    # Delete the fixing
    # Assert period.received is reduced

def test_edit_quantity_increase():
    # Record a fixing with 1000 shares
    # Edit to 1500 shares
    # Assert period.received increased by 500

def test_edit_quantity_decrease():
    # Record a fixing with 1000 shares
    # Edit to 500 shares
    # Assert period.received decreased by 500
```

### Integration Tests
- Test with real database
- Test with multiple periods
- Test with GTD periods
- Test error cases (missing contract_ref, etc.)

---

## Rollout Plan

### Phase 1: Data Preparation (Week 1)
- ✅ Investigate current `periods` field usage
- ✅ Update `RecordFixings` to store period data
- ✅ Test new recordings work correctly

### Phase 2: Reverse Function (Week 2)
- ✅ Create `ReverseFixing` class
- ✅ Write unit tests
- ✅ Test with sample data

### Phase 3: Integration (Week 3)
- ✅ Update delete endpoint
- ✅ Update edit endpoint (if needed)
- ✅ Add confirmation dialogs
- ✅ Integration testing

### Phase 4: Verification Tool (Week 4)
- ✅ Create `RecalculateTermSheet` admin tool
- ✅ Run on existing data to find inconsistencies
- ✅ Fix any issues found

### Phase 5: Production (Week 5)
- ✅ Deploy to production
- ✅ Monitor for issues
- ✅ User training/documentation

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing period data in old transactions | High | Use Option 2 (recalculate) for old data |
| Complex edit scenarios | Medium | Start with delete-only, add edit later |
| Database inconsistency | High | Add verification checks, admin tool |
| User accidentally deletes important fixing | Medium | Add better confirmation, consider soft delete |
| Performance with many transactions | Low | Optimize queries, add indexes |

---

## Recommendation

**Start with Option 1 (Reverse Transaction Data) for new transactions:**

1. ✅ Update `RecordFixings` to store `contract_ref` and `periods` in JSON format
2. ✅ Create `ReverseFixing` class to reverse KO status and period shares
3. ✅ Update delete endpoint to call `ReverseFixing` before deletion
4. ✅ Add confirmation dialog showing what will be reversed
5. ✅ For edit: Start with blocking edits or treat as delete+recreate
6. ✅ Later: Add `RecalculateTermSheet` admin tool as safety net

**For existing transactions without period data:**
- Use Option 2 (recalculate) as needed
- Or: Accept that old fixings cannot be properly reversed (document limitation)

---

## Questions for Decision

1. **Should we allow editing fixing transactions, or only delete+recreate?**
   - Edit is more complex but better UX
   - Delete+recreate is simpler but requires regenerating fixing

2. **Should we use soft delete or hard delete?**
   - Soft delete preserves audit trail
   - Hard delete is simpler

3. **Do we need to handle historical data without period info?**
   - If yes: Need recalculation approach
   - If no: Only new fixings are reversible

4. **Should reversal be automatic or require confirmation?**
   - Automatic: Faster workflow
   - Manual confirmation: Safer, more transparent

---

## Next Steps

1. **Review this proposal** with stakeholders
2. **Decide on approach** (Option 1, 2, or 3)
3. **Answer decision questions** above
4. **Create implementation tickets**
5. **Begin Phase 1** (data preparation)

**Estimated Timeline:** 4-5 weeks for complete implementation
**Priority:** Medium-High (data integrity issue but workaround exists)
