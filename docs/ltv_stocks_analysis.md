# LTV Stocks Analysis: Code vs Actual Output

**Date:** 2026-06-05
**Analyzed File:** `instance/2026-05-29 LTV Stocks.xlsx`
**Legacy Code:** `localhost/create_LTV_Stocks.py` & `localhost/modules/ltv_stocks2.py`

## Executive Summary

The actual Excel output contains several features and improvements NOT present in the legacy `ltv_stocks2.py` code. This indicates the code has diverged from the actual production process or additional manual steps are being performed.

---

## Key Findings

### 1. ⚠️ CRITICAL: Missing Currency Support

**Finding:** Excel file contains `RNS-PH` sheet (Philippine Pesos)
**Code Status:** Legacy code only supports `['HKD', 'SGD']` (line 185)

```python
# Current code (line 185)
self.ccys = ['HKD', 'SGD']

# Should be:
self.ccys = ['HKD', 'SGD', 'PH']  # or dynamically query currencies
```

**Impact:** HIGH - Missing entire currency/market support

**Evidence:**
- Sheet `RNS-PH` exists with Philippines stock data (AREIT, INC.)
- Different formatting/structure than HKD/SGD sheets
- Contains Dowell Container and Packaging Corp. positions

---

### 2. ✅ CONFIRMED: Active Contract Count Formula

**Finding:** Working correctly in output
**Code:** Line 415 - `=7-COUNTIF(N7:N13,"*DONE*")`
**Output Cell A3:** `=7-COUNTIF(N7:N13,"*DONE*")`

**Status:** ✅ Matches expected behavior

---

### 3. ✅ CONFIRMED: Cross-Account HKD Totals

**Finding:** Cell B3 contains cross-sheet SUM formula
**Code:** Lines 251-289 implement this logic
**Output Cell B3:** `=SUM('DBPe-HKD'!A3, 'DBPL-HKD'!A4, 'SHK-HKD'!A3, 'SHK2-HKD'!A3, 'MST1-HKD'!A4, 'MSPL-HKD'!A4, 'NSG-HKD'!A3)`

**Status:** ✅ Working as designed

---

### 4. ⚠️ DISCREPANCY: Bank Reference Column (Column C)

**Finding:** Column C is visible and populated in output
**Code:** Line 339 hides column C (`hidden_cols = ['C','M']`)
**Output:** Cell C7 = 'CM' (bank reference visible)

```python
# Current code (line 339):
hidden_cols = ['C','M']
for col in hidden_cols: self.ws.column_dimensions[col].hidden= True

# Issue: Column C should be visible based on actual output
```

**Impact:** MEDIUM - Documentation/transparency issue

**Recommendation:** Remove 'C' from `hidden_cols` or make it configurable

---

### 5. ✅ CONFIRMED: Stock Color Coding

**Finding:** Alibaba (9988) has color fill
**Code:** Lines 688-704 implement color coding
**Output Cell A7:** `fill=FF008080` (teal color for 9988)

**Evidence:**
```python
# Code (lines 701-702)
elif row.code == '9988':
    cell.fill = self.xl_fill('00008080')
```

**Status:** ✅ Working correctly

---

### 6. ⚠️ NEW: Complex Position Formulas

**Finding:** Position rows contain advanced formulas NOT in legacy code

**Cell AF25:** `=IF(INDIRECT("AI"&ROW())="",INDIRECT("AH"&ROW()),IF(INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())=0,"",INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())))`

**Code Status:** NOT PRESENT in ltv_stocks2.py

**Impact:** HIGH - Missing calculation logic for position adjustments

**Analysis:** This formula appears to:
- Use INDIRECT to reference columns AG, AH, AI dynamically
- Calculate position differences/adjustments
- Handle zero-value cases

**Location in Code:** Should be in `position()` method around line 864+

---

### 7. ⚠️ DISCREPANCY: Position Data Sources

**Finding:** Position rows reference columns not in legacy code

**Output Formulas:**
- `D25: =IF(AF25="","",AF25)` - References AF column
- `O25: =IF(AJ25="","",AJ25)` - References AJ column

**Code Status:**
- Column AF not mentioned in code
- Column AJ not mentioned in code
- Lines 854-870 define columns up to AC, but not AF/AJ

**Impact:** HIGH - Formula dependencies missing

---

### 8. ✅ CONFIRMED: Closing Price Lookup

**Finding:** Uses INDEX/MATCH formula
**Code:** Line 677, 852
**Output Cell L25:** `=INDEX(closing_price!A:C,MATCH(C25,closing_price!A:A,),3)`

**Status:** ✅ Matches implementation

---

### 9. ⚠️ IMPROVED: Date Display Formula

**Finding:** RNS-PH sheet has dynamic date header
**Output Cell G1:** `="As of "&TEXT(F6,"mmmm d, yyyy")`

**Code Status:** Not in legacy code - uses static datetime formatting

**Impact:** LOW - Aesthetic improvement

---

### 10. ✅ CONFIRMED: Record Sheet for SUMIF

**Finding:** Positions use SUMIF against 'record' sheet
**Code:** Lines 865-866 create formulas
**Output Cells Y25, Z25:**
```
Y25: =SUMIF(record!B:B,AA25,record!G:G)
Z25: =SUMIF(record!B:B,AA25,record!H:H)
```

**Status:** ✅ Working as designed

---

## Summary of Issues

### Critical Issues (Require Immediate Attention)

1. **Missing Currency: PH (Philippines)**
   - Code only supports HKD, SGD
   - Output contains RNS-PH sheet
   - **Action:** Add 'PH' to ccys list or make dynamic

2. **Missing Position Formulas (Columns AF, AJ)**
   - Complex INDIRECT formulas not in code
   - Referenced by position calculations
   - **Action:** Reverse-engineer formulas and add to `position()` method

### Medium Issues (Should Fix)

3. **Bank Reference Column Visibility**
   - Code hides Column C
   - Output shows Column C visible
   - **Action:** Update `hidden_cols` to remove 'C'

### Low Issues (Nice to Have)

4. **Dynamic Date Headers**
   - RNS-PH uses TEXT formula for dates
   - More elegant than static formatting
   - **Action:** Consider adopting for all sheets

---

## Recommended Improvements

### Priority 1: Fix Currency Support

```python
# Current (line 185):
self.ccys = ['HKD', 'SGD']

# Improved (dynamic from database):
def get_active_currencies(self):
    """Query database for currencies with active positions."""
    sql = """
        SELECT DISTINCT tbl_currency.ccy_id
        FROM tbl_currency
        INNER JOIN tbl_code ON tbl_currency.ref_num = tbl_code.ccy_ref
        INNER JOIN tbl_transaction ON tbl_code.ref_num = tbl_transaction.code_ref
        WHERE tbl_transaction.trade_date >= ?
        ORDER BY tbl_currency.priority
    """
    result = self.db_file.execute(sql, (self.start_date,))
    return [row[0] for row in result]

# Then in __init__:
self.ccys = self.get_active_currencies()
```

### Priority 2: Add Missing Position Formulas

```python
# Add to position() method around line 864:
'AF': f'=IF(INDIRECT("AI"&ROW())="",INDIRECT("AH"&ROW()),IF(INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())=0,"",INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())))',
'AJ': '[formula TBD - need to analyze more rows]',

# Update dependent formulas:
'D': f'=IF(AF{row_num}="","",AF{row_num})',  # Instead of static value
'O': f'=IF(AJ{row_num}="","",AJ{row_num})',  # Instead of static value
```

### Priority 3: Fix Column Visibility

```python
# Change line 339:
hidden_cols = ['M']  # Remove 'C' from list
```

### Priority 4: Add PH Currency Handling

```python
# Add to bank_name dict (line 152):
self.bank_name = {
    # ... existing entries ...
    "RNS": "R. Nubla Securities",  # Add PH broker
}

# Add to account dict (line 735):
self.account = {
    # ... existing entries ...
    "RNS": "R. Nubla Securities Stocks",
}

# Update position header logic to handle PH formatting
# (Currently only checks for JPY, AUD, USD, SGD - line 387-404)
```

### Priority 5: Make Bank Accounts Configurable

**Current:** Hardcoded in `create_LTV_Stocks.py` line 9:
```python
test = LTV_Stocks('DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG')
```

**Issue:** Doesn't include 'RNS' that appears in output

**Improved:**
```python
# Add to create_LTV_Stocks.py:
def get_active_accounts(db_file, report_date):
    """Query database for accounts with activity."""
    sql = """
        SELECT DISTINCT tbl_bank_account.acct_id
        FROM tbl_bank_account
        INNER JOIN tbl_transaction ON tbl_bank_account.ref_num = tbl_transaction.bank_ref
        WHERE tbl_transaction.trade_date >= ?
        ORDER BY tbl_bank_account.ref_num
    """
    result = db_file.execute(sql, (report_date - timedelta(days=365),))
    return [row[0] for row in result]

# Use dynamic list:
accounts = get_active_accounts(db, report_date)
test = LTV_Stocks(*accounts)
```

---

## Testing Recommendations

### 1. Comparative Testing
- Generate report with current code for 2026-05-29
- Compare cell-by-cell with actual `instance/2026-05-29 LTV Stocks.xlsx`
- Document all differences

### 2. Formula Validation
- Manually verify all INDEX/MATCH formulas
- Test INDIRECT formulas with sample data
- Confirm SUMIF calculations against database

### 3. Edge Cases
- Empty position rows (no transactions)
- Contracts with DONE status
- Multiple currencies in same account
- Missing stock prices

---

## Code Quality Improvements

### 1. Configuration Management

```python
# Create config file: config.py
class LTVStocksConfig:
    # Supported currencies
    CURRENCIES = ['HKD', 'SGD', 'PH', 'JPY', 'AUD', 'USD']

    # Bank account mappings
    BANK_NAMES = {...}
    SUB_TITLES = {...}
    ACCOUNT_LABELS = {...}

    # Stock color mappings
    STOCK_COLORS = {
        '2333': 'FFE5E39F',
        '0700': '00FFFFCC',
        '9988': '00008080',
        # ...
    }

    # Excel formatting
    COLUMN_WIDTHS = {...}
    HIDDEN_COLUMNS = ['M']  # Remove 'C'
```

### 2. Separate Concerns

```python
# Split into multiple files:
# - ltv_stocks_data.py: Data gathering
# - ltv_stocks_format.py: Excel formatting
# - ltv_stocks_formulas.py: Formula generation
# - ltv_stocks_generator.py: Main orchestration
```

### 3. Add Logging

```python
import logging

logger = logging.getLogger(__name__)

class LTV_Stocks:
    def __init__(self, *bank_accounts):
        logger.info(f"Generating LTV Stocks for accounts: {bank_accounts}")
        # ...

    def contract(self, row_num, product, contracts, ccy):
        logger.debug(f"Processing {len(contracts)} {product} contracts for {ccy}")
        # ...
```

---

## Conclusion

The legacy code is mostly functional but is missing critical features present in the actual output:

1. **Philippines market support (RNS-PH)**
2. **Advanced position adjustment formulas (columns AF, AJ)**
3. **Proper column visibility settings**

The code should be updated to match the actual production output, or the output should be regenerated to verify consistency.

**Estimated effort to fix:** 6-8 hours
- 2 hours: Add PH currency support
- 2 hours: Reverse-engineer and add missing formulas
- 1 hour: Fix column visibility and config
- 1-2 hours: Testing and validation
- 1 hour: Documentation updates
