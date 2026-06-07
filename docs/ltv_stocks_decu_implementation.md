# LTV Stocks DECU Blocked Shares Implementation

**Date:** 2026-06-05
**File Modified:** `localhost/modules/ltv_stocks2.py`
**Feature:** Automatic calculation of BLOCKED/UNBLOCKED shares based on DECU requirements

---

## Business Logic

### The Problem

When holding stock positions with DECU (Decumulator) contracts, a certain number of shares must remain "blocked" to fulfill contract obligations. The remaining shares are "unblocked" and available for other use.

### Calculation Formula

```
For each DECU contract:
  - Check if contract is leveraged (from tbl_stock_contract.leveraged field)
  - Multiplier = 2 if leveraged='Yes', else 1
  - Contract Requirement = Daily Shares × Multiplier × Remaining Months

DECU Requirement (AI) = Sum of all contract requirements
Total Shares (AH) = Current position balance as of report date
Blocked Shares (AG) = MIN(DECU Requirement, Total Shares)
Unblocked Shares (AF) = Total Shares - Blocked Shares
```

### Leveraged vs Non-Leveraged DECU

**Leveraged DECU (`leveraged='Yes'`):**
- Requires double shares when price is on wrong side of strike
- Multiplier = 2
- Example: 100 shares/day × 2 × 3 months = 600 shares requirement

**Non-Leveraged DECU (`leveraged='No'`):**
- Requires only base shares (no doubling)
- Multiplier = 1
- Example: 100 shares/day × 1 × 3 months = 300 shares requirement

---

## Implementation Details

### New Method: `calculate_decu_requirements(ccy)`

**Location:** Lines 920-962 in `ltv_stocks2.py`

**Purpose:** Calculate DECU requirement for each stock position before generating the position section

**Logic:**
1. Initialize `decu_requirement` and `total_shares` for each stock in `self.stock_position`
2. Query `trades_done_average()` to get current balance (`total_shares`)
3. Iterate through `self.decu` dataframe (DECU contracts for this account/currency)
4. For each DECU contract:
   - Extract daily shares (handle "100 / 200" format)
   - Get remaining months from contract
   - **Query database to check if contract is leveraged**
   - Calculate: `daily_shares × (2 if leveraged else 1) × remaining_months`
   - Add to stock's `decu_requirement`

**Key Code:**
```python
# Extract daily shares (handle "xxx / yyy" format)
shares_str = str(row['shares'])
if '/' in shares_str:
    # Format: "100 / 200" - take first number (base shares)
    daily_shares = int(shares_str.split('/')[0].strip())
else:
    daily_shares = int(shares_str)

# Remaining months
remaining_months = float(row['remaining'])

# Check if contract is leveraged (from database)
contract_ref = row['contract_ref']
leveraged_result = self.db_file.Execute(
    f"SELECT leveraged FROM tbl_stock_contract WHERE ref_num = {contract_ref}"
)
is_leveraged = leveraged_result[0][0] == 'Yes'

# DECU requirement: daily_shares * (2 if leveraged else 1) * remaining_months
multiplier = 2 if is_leveraged else 1
decu_shares = daily_shares * multiplier * remaining_months

self.stock_position[code]['decu_requirement'] += decu_shares
```

---

### New Excel Columns

#### Column AH: Total Shares
- **Value:** `balance_basis` from `trades_done_average()`
- **Meaning:** Current position balance as of report date
- **Type:** Static value

#### Column AI: DECU Requirement
- **Value:** Calculated by `calculate_decu_requirements()`
- **Meaning:** Total shares needed for all DECU obligations (doubled)
- **Type:** Static value (calculated from DECU contracts)
- **Display:** Only shown if > 0

#### Column AG: Blocked Shares
- **Formula:** `=IF(INDIRECT("AI"&ROW())="",0,IF(INDIRECT("AI"&ROW())>INDIRECT("AH"&ROW()),INDIRECT("AH"&ROW()),INDIRECT("AI"&ROW())))`
- **Meaning:** Shares reserved for DECU contracts
- **Logic:**
  - If no DECU requirement (AI empty): 0
  - If DECU requirement exists: MIN(AI, AH) - can't block more than you have
- **Type:** Formula

#### Column AF: Unblocked Shares
- **Formula:** `=IF(INDIRECT("AI"&ROW())="",INDIRECT("AH"&ROW()),IF(INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())=0,"",INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())))`
- **Meaning:** Shares available for other use
- **Logic:**
  - If no DECU requirement (AI empty): All shares unblocked (= AH)
  - If DECU requirement exists: Total - Blocked (AH - AG)
  - If result is 0: Show blank
- **Type:** Formula

---

### Updated Display Columns

#### Column D: Unblocked (Display)
**Before:** `'D': unblocked` (static value from database)
**After:** `'D': f'=IF(AF{row_num}="","",AF{row_num})'` (formula referencing AF)

**Reason:** Now calculated dynamically based on DECU requirements

#### Column E: Blocked (Display)
**Before:** `'E': blocked` (static value from database)
**After:** `'E': f'=IF(AG{row_num}=0,"",AG{row_num})'` (formula referencing AG)

**Reason:** Now calculated dynamically based on DECU requirements

---

## Changes Summary

### Modified Methods

1. **`position()` method (line 712)**
   - Added call to `calculate_decu_requirements(ccy)` before analyzing positions
   - Ensures DECU calculations are done before rendering position rows

2. **`column_width()` method (lines 298-341)**
   - Added column Y (was missing)
   - Updated widths for AF, AG, AH, AI (7.57 + 0.71 for shares columns)
   - Added AK for future use

3. **Position labels section (lines 857-884)**
   - Changed D and E from static values to formulas
   - Added AG, AH, AI, AF column definitions
   - Retrieve `total_shares` and `decu_requirement` from `self.stock_position`

4. **Cell formatting section (lines 886-920)**
   - Updated alignment handling for new columns
   - Added AF, AG, AH, AI to number format handling (`#,##0`)
   - Excluded hidden columns (AF, AG, AH, AI) from borders

### New Method

**`calculate_decu_requirements(ccy)`** (lines 920-962)
- Calculates DECU blocked share requirements
- Updates `self.stock_position` with `total_shares` and `decu_requirement`
- Handles "xxx / yyy" format for daily shares
- Sums requirements across multiple DECU contracts for same stock

---

## Example Calculation

### Sample Data

**Stock:** HK Exchange (0388)
**Current Position:** 15,000 shares (as of May 29, 2026)

**DECU Contracts:**
1. Contract 1: 100 shares/day, 3.5 months remaining
2. Contract 2: 80 shares/day, 2.0 months remaining

### Calculation

```
DECU Requirement (AI):
  = (100 × 2 × 3.5) + (80 × 2 × 2.0)
  = 700 + 320
  = 1,020 shares

Total Shares (AH): 15,000

Blocked Shares (AG):
  = MIN(1,020, 15,000)
  = 1,020 shares

Unblocked Shares (AF):
  = 15,000 - 1,020
  = 13,980 shares
```

### Excel Display

```
Column D (Unblocked): 13,980
Column E (Blocked):   1,020
Column G (Total):     15,000  (= D + E)
```

---

## Testing Recommendations

### Test Case 1: Stock with Leveraged DECU Contract
**Setup:**
- Stock with position: 10,000 shares
- 1 DECU contract: 50 shares/day, 4 months remaining, leveraged='Yes'

**Expected:**
- AI (DECU Req): 400 (= 50 × 2 × 4)
- AG (Blocked): 400
- AF (Unblocked): 9,600
- D displays: 9,600
- E displays: 400

### Test Case 1b: Stock with Non-Leveraged DECU Contract
**Setup:**
- Stock with position: 10,000 shares
- 1 DECU contract: 50 shares/day, 4 months remaining, leveraged='No'

**Expected:**
- AI (DECU Req): 200 (= 50 × 1 × 4)
- AG (Blocked): 200
- AF (Unblocked): 9,800
- D displays: 9,800
- E displays: 200

### Test Case 2: Stock without DECU Contracts
**Setup:**
- Stock with position: 5,000 shares
- No DECU contracts

**Expected:**
- AI (DECU Req): blank
- AG (Blocked): 0
- AF (Unblocked): 5,000
- D displays: 5,000
- E displays: blank

### Test Case 3: DECU Requirement > Total Shares
**Setup:**
- Stock with position: 1,000 shares
- 1 DECU contract: 100 shares/day, 10 months remaining

**Expected:**
- AI (DECU Req): 2,000 (= 100 × 2 × 10)
- AG (Blocked): 1,000 (capped at total)
- AF (Unblocked): blank (0, so blank)
- D displays: blank
- E displays: 1,000

### Test Case 4: Multiple DECU Contracts
**Setup:**
- Stock with position: 20,000 shares
- DECU 1: 100 shares/day, 3 months remaining
- DECU 2: 80 shares/day, 2.5 months remaining

**Expected:**
- AI (DECU Req): 1,000 (= 600 + 400)
- AG (Blocked): 1,000
- AF (Unblocked): 19,000
- D displays: 19,000
- E displays: 1,000

---

## Benefits

### 1. Automation
- **Before:** User manually calculates and enters DECU requirements
- **After:** Automatically calculated from DECU contracts

### 2. Accuracy
- **Before:** Risk of calculation errors
- **After:** Consistent formula-based calculation

### 3. Real-time Updates
- **Before:** Static values need manual update when contracts change
- **After:** Recalculates automatically when report is regenerated

### 4. Transparency
- **Before:** DECU requirement not visible
- **After:** Visible in column AI for verification

### 5. Audit Trail
- **Before:** No clear link between DECU contracts and blocked shares
- **After:** Clear calculation from contract details → requirement → blocked shares

---

## Backward Compatibility

### No Breaking Changes
- Existing reports will continue to work
- Old logic of reading `unblocked`/`blocked` from database is replaced with formula-based calculation
- Column positions unchanged (D, E, G remain in same location)

### Migration Notes
- Previous `unblocked` and `blocked` values in `self.stock_position` are no longer used
- System now calculates from `total_shares` and `decu_requirement`
- No database schema changes required

---

## Future Enhancements

### Potential Improvements

1. **ACCU Contracts**
   - Similar calculation for ACCU contracts (accumulator shares needed)
   - Different logic (may not require blocking)

2. **Contract Status Filtering**
   - Only count active DECU contracts (not "DONE")
   - Currently counts all contracts in `self.decu`

3. **Date-aware Calculations**
   - Adjust remaining months based on actual remaining trading days
   - Currently uses contract's `remaining` field as-is

4. **Visual Indicators**
   - Color code blocked shares (red) vs unblocked (green)
   - Warning when blocked > total (insufficient shares)

5. **Summary Row**
   - Show total blocked/unblocked across all stocks
   - Account-level DECU requirement summary

---

## Troubleshooting

### Issue: DECU Requirement Shows 0 But There Are DECU Contracts

**Possible Causes:**
1. DECU contracts are for different currency than position section
2. Stock code in DECU doesn't match position code
3. `remaining` months is 0 (contract near completion)
4. DECU dataframe is empty (no contracts loaded)

**Debug:**
```python
# Add after line 945:
print(f"Processing DECU for {code}: {len(self.decu[self.decu['code'] == code])} contracts")
```

### Issue: Blocked Shares Greater Than Total Shares

**Expected Behavior:**
- Formula AG caps blocked at total (MIN function)
- This situation indicates insufficient shares for DECU obligations
- User should review contracts or add shares

**Action:**
- Consider adding visual warning (red cell background)
- Add note in transactions column

### Issue: Unblocked Shows as Blank But Should Show Value

**Possible Cause:**
- AF formula returns blank when AH - AG = 0
- This is intentional (cleaner display)

**If Wrong:**
- Check AH value (total shares)
- Check AG calculation (blocked shares)
- Verify AI has correct DECU requirement

---

## Code References

**Main Changes:**
- `calculate_decu_requirements()`: Lines 920-962
- Position labels update: Lines 857-884
- Column width definitions: Lines 323-336
- Cell formatting: Lines 886-920

**Integration Point:**
- `position()` method calls: Line 717

**Related Methods:**
- `trades_done_average()` - Gets current balance
- `getbank_ref()` - Bank account lookup
- `get_code_ref_num()` - Stock code to ref_num mapping
