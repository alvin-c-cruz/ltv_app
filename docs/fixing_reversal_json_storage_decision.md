# Fixing Reversal: JSON Storage Decision

**Date:** 2026-06-02
**Decision:** Store period reversal data as JSON in `tbl_transaction.periods` field

---

## Decision Summary

**Store the period relationship data in the `tbl_transaction.periods` field as JSON.**

This allows the transaction itself to trigger and drive the reversal process when deleted or modified.

---

## Why Store in `tbl_transaction.periods`?

### 1. **Transaction-Driven Reversal**

The transaction is the **trigger for reversal**. When a transaction is deleted, we can immediately access the reversal data:

```python
# Get the transaction being deleted
transaction = get_transaction(ref_num)

# Read the periods JSON from that transaction
periods = json.loads(transaction["periods"])

# Use that data to reverse the term sheet updates
for period in periods:
    reverse_update(period["period_ref"], period["shares_total"])

# Then delete the transaction
delete_transaction(ref_num)
```

**Key Benefit:** The data travels with the transaction - no separate lookups or calculations needed.

---

### 2. **Self-Contained Reversal Data**

Each transaction carries its own "undo" information:

- Transaction #123 stores which periods **IT** affected
- Transaction #124 stores which periods **IT** affected
- No need to query other tables or recalculate
- Just read the JSON and reverse

**Example:**

```
Transaction #123 (2026-05-27):
  periods: [{"period_ref": 456, "shares_total": 35000, ...}]

Transaction #124 (2026-05-28):
  periods: [{"period_ref": 457, "shares_total": 42000, ...}]
```

When you delete #123, you know exactly what to reverse without touching #124's data.

---

### 3. **Handles Complex Scenarios**

#### Regular Fixing (Single Period)
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

#### KO Fixing (Multiple Periods)
```json
[
    {
        "period_ref": 456,
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "shares_total": 35000
    },
    {
        "period_ref": 457,
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
        "shares_total": 40000
    },
    {
        "period_ref": 458,
        "start_date": "2026-07-01",
        "end_date": "2026-07-31",
        "shares_total": 38000
    }
]
```

**KO fixings affect:**
- Current period being knocked out
- All future periods with GTD flag

The JSON can store all affected periods in one array.

---

### 4. **Audit Trail**

The JSON preserves **exactly what happened at recording time**:

```json
{
    "period_ref": 456,
    "shares_fixing": 25000,
    "shares_indicative": 10000,
    "shares_total": 35000,
    "start_date": "2026-05-01",
    "end_date": "2026-05-31"
}
```

**Questions this answers:**
- "Why did period 456 have 35,000 shares?" → Look at transaction's JSON
- "Was this fixing or indicative?" → See breakdown in JSON
- "What date range was this for?" → Dates stored in JSON

**Forensic Value:** If term sheets become inconsistent, you can trace back through transactions to see what updates were made.

---

### 5. **Alternative Approaches (Rejected)**

#### Option A: Store in Separate Table
```sql
CREATE TABLE tbl_transaction_period_link (
    transaction_ref INTEGER,
    period_ref INTEGER,
    shares_total INTEGER
)
```

**Rejected because:**
- ❌ Requires additional table
- ❌ Requires separate INSERT/DELETE operations
- ❌ More complex to maintain consistency
- ❌ Requires JOIN to get reversal data

#### Option B: Recalculate on Delete
```python
# When deleting, query all transactions and recalculate term sheet state
def delete_transaction(ref_num):
    contract_ref = get_contract_ref(ref_num)
    delete_transaction(ref_num)
    recalculate_entire_contract(contract_ref)  # Expensive!
```

**Rejected because:**
- ❌ Expensive - requires querying all related transactions
- ❌ Complex - requires reimplementing fixing logic
- ❌ Error-prone - calculation might differ from original
- ❌ Performance issues with many transactions

#### Option C: Store in `tbl_stock_contract` or `tbl_stock_contract_period`

**Rejected because:**
- ❌ Doesn't track which transaction made which update
- ❌ Multiple transactions can update the same period
- ❌ No clear way to reverse a specific transaction

---

## JSON Schema Design

### Structure

```json
[
    {
        "period_ref": <integer>,           // Required: Which period to reverse
        "start_date": "YYYY-MM-DD",        // Audit: Period start
        "end_date": "YYYY-MM-DD",          // Audit: Period end
        "shares_fixing": <integer>,        // Audit: Definite shares
        "shares_indicative": <integer>,    // Audit: Indicative shares
        "shares_total": <integer>          // Required: Total to reverse
    }
]
```

### Required vs. Audit Fields

**Required for Reversal:**
- `period_ref` - Which period to update
- `shares_total` - How many shares to remove

**Audit/Display Only:**
- `start_date`, `end_date` - For UI display and debugging
- `shares_fixing`, `shares_indicative` - For understanding breakdown

### Example: Real-World Transaction

**Scenario:** Alibaba ACCU fixing on 2026-05-27

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

**What this means:**
- This transaction updated period #456
- Added 35,000 shares total (25k fixing + 10k indicative)
- Period covered May 1-31, 2026
- To reverse: Subtract 35,000 from period #456's `received` field

---

## Database Storage

### Existing Schema (Already Available!)

From [tests/functional/conftest.py:83-84](../tests/functional/conftest.py):

```sql
CREATE TABLE tbl_transaction (
    ref_num          INTEGER PRIMARY KEY,
    -- ... other fields ...
    spot             REAL,
    ko               REAL,
    contract_ref     INTEGER,        -- ✅ Links to tbl_stock_contract.ref_num
    periods          TEXT,           -- ✅ Store JSON here!
    -- ... other fields ...
);
```

**Field Type:** `TEXT` (can store JSON strings of any length)

**Current State:** Likely NULL for all existing transactions (not currently populated)

---

## Implementation Flow

### Phase 1: Recording (Update RecordFixings)

**File:** [ltv_app/blueprints/fixings/extensions/record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py)

```python
import json

class RecordFixings:
    def __init__(self, db, fixing_data, trade_date):
        for fixing in fixings:
            # ... existing code ...

            # ✅ NEW: Build periods JSON from fixing["fixings"]
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
            sql = """INSERT INTO tbl_transaction
                     (trade_date, value_date, bank_ref, code_ref, transaction_type,
                      quantity, price, brokerage, commission, foreign_charge,
                      stamp_duty, misc, spot, ko, contract_ref, periods)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?, ?, ?)"""
            args = (trade_date, value_date, bank_ref, code_ref, transaction_type,
                   quantity, price, spot, ko, contract_ref, periods_json)

            db.execute(sql, args)
            db.commit()

            # ... existing term sheet update code ...
```

**Key Changes:**
1. Loop through `fixing["fixings"]` array
2. Build `periods_data` list with required fields
3. Convert to JSON string with `json.dumps()`
4. Add `contract_ref` and `periods` to SQL INSERT
5. Include in args tuple

---

### Phase 2: Reversal (New ReverseFixing Class)

**File:** [ltv_app/blueprints/fixings/extensions/reverse_fixing.py](../ltv_app/blueprints/fixings/extensions/reverse_fixing.py)

```python
import json

class ReverseFixing:
    def __init__(self, db, transaction_ref):
        self.db = db
        self.transaction = self.get_transaction(transaction_ref)

    def get_transaction(self, ref_num):
        sql = """SELECT ref_num, transaction_type, contract_ref, periods
                 FROM tbl_transaction WHERE ref_num = ?"""
        result = self.db.execute(sql, (ref_num,)).fetchone()
        return dict(result)

    def reverse(self):
        """Reverse term sheet updates"""
        if "KO" in self.transaction["transaction_type"]:
            return self.reverse_knockout()
        else:
            return self.reverse_regular_fixing()

    def reverse_knockout(self):
        """Change status from KO back to active"""
        sql = "UPDATE tbl_stock_contract SET status='active' WHERE ref_num=?"
        self.db.execute(sql, (self.transaction["contract_ref"],))
        self.db.commit()
        return {"status": "success", "type": "knockout"}

    def reverse_regular_fixing(self):
        """Remove shares from periods"""
        periods_json = self.transaction["periods"]
        if not periods_json:
            return {"status": "warning", "reason": "No period data"}

        periods = json.loads(periods_json)

        for period in periods:
            sql = """UPDATE tbl_stock_contract_period
                     SET received = received - ?
                     WHERE ref_num = ?"""
            self.db.execute(sql, (period["shares_total"], period["period_ref"]))

        self.db.commit()
        return {"status": "success", "type": "regular_fixing"}
```

**Key Operations:**
1. Read `periods` field from transaction
2. Parse JSON with `json.loads()`
3. Loop through periods array
4. Subtract `shares_total` from each period's `received` field
5. Commit changes

---

### Phase 3: Delete Endpoint Integration

**File:** [ltv_app/blueprints/fixings/views.py](../ltv_app/blueprints/fixings/views.py)

```python
@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete(ref_num):
    from .. database import get_db
    from . extensions.reverse_fixing import ReverseFixing

    db = get_db()

    # Step 1: Reverse term sheet updates
    reverser = ReverseFixing(db, ref_num)
    result = reverser.reverse()

    if result["status"] == "success":
        flash(f"Term sheet updated successfully", "success")
    elif result["status"] == "warning":
        flash(f"Warning: {result['reason']}", "warning")

    # Step 2: Delete the transaction
    transaction = Transaction(db=db)
    transaction.get(ref_num=ref_num)
    transaction.delete()

    flash(f"Fixing #{ref_num} deleted", "success")
    return redirect(url_for('fixings.home'))
```

**Execution Flow:**
1. Get transaction to delete
2. Create `ReverseFixing` instance
3. Call `reverse()` - reads JSON and updates term sheets
4. Delete the transaction
5. Provide user feedback

---

## Legacy Data Handling

### Transactions Without Period Data

Transactions created before this implementation will have `periods = NULL`.

**Strategy:**

```python
def reverse_regular_fixing(self):
    periods_json = self.transaction["periods"]

    if not periods_json:
        # Legacy transaction - no period data
        return {
            "status": "warning",
            "reason": "No period data stored (legacy transaction). "
                     "Cannot automatically reverse. Manual fix required."
        }

    # ... proceed with reversal ...
```

**User Experience:**
- Display warning message
- User must manually fix term sheet
- Or: Provide admin tool to recalculate term sheet from scratch

**Acceptance Criteria:**
- ✅ New transactions: Full automatic reversal
- ✅ Old transactions: Graceful failure with clear message
- ✅ No database errors or crashes

---

## Benefits Summary

| Benefit | Description |
|---------|-------------|
| **Self-Contained** | Each transaction carries its own reversal data |
| **Transaction-Driven** | Delete triggers reversal automatically |
| **Handles Complexity** | Single or multiple periods, KO or regular |
| **Audit Trail** | Preserves what happened at recording time |
| **No Schema Changes** | Uses existing `periods` field |
| **Performance** | No expensive recalculations needed |
| **Maintainable** | Clear, simple JSON structure |

---

## Next Steps

1. ✅ Review and approve this decision
2. ⏳ Phase 1: Update `RecordFixings` to populate `contract_ref` and `periods`
3. ⏳ Phase 2: Create `ReverseFixing` class
4. ⏳ Phase 3: Update delete endpoint
5. ⏳ Testing and deployment

**Estimated Timeline:** 5 weeks
**Priority:** High (data integrity)

---

## References

- [Fixing Reversal Relationship Plan](fixing_reversal_relationship_plan.md) - Full implementation plan
- [Fixing Deletion Modification Proposal](fixing_deletion_modification_proposal.md) - Original proposal with 3 options
- [record_fixings.py](../ltv_app/blueprints/fixings/extensions/record_fixings.py) - Current recording implementation
- [generate_fixings.py](../ltv_app/blueprints/fixings/extensions/generate_fixings.py) - Fixing data structure
