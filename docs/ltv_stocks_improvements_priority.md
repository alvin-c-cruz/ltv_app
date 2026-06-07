# LTV Stocks Improvements - Priority Action Plan

## Overview

Analysis of `instance/2026-05-29 LTV Stocks.xlsx` vs `localhost/create_LTV_Stocks.py` reveals significant discrepancies. This document provides an actionable plan to improve the legacy code.

---

## Critical Findings

### 1. Missing Currency: Philippines (PH)
- **Evidence:** RNS-PH sheet exists in output
- **Code:** Only supports `['HKD', 'SGD']`
- **Impact:** Cannot generate reports for Philippine stocks

### 2. Missing Position Formulas
- **Evidence:** Columns AF, AJ contain complex INDIRECT formulas
- **Code:** Not present in ltv_stocks2.py
- **Impact:** Position calculations may be incorrect

### 3. Column Visibility Mismatch
- **Evidence:** Bank Reference (Column C) is visible in output
- **Code:** Hides Column C
- **Impact:** User cannot see bank document references

---

## Quick Fixes (30 minutes)

### Fix 1: Unhide Bank Reference Column

**File:** `localhost/modules/ltv_stocks2.py`
**Line:** 339

```python
# BEFORE:
hidden_cols = ['C','M']

# AFTER:
hidden_cols = ['M']  # Keep M hidden, show C (Bank Reference)
```

**Benefit:** Users can see bank document numbers for each contract

---

### Fix 2: Add Philippines to Currency List

**File:** `localhost/modules/ltv_stocks2.py`
**Line:** 185

```python
# BEFORE:
self.ccys = ['HKD', 'SGD']

# AFTER:
self.ccys = ['HKD', 'SGD', 'PH']
```

**Additional Changes Needed:**

**Add RNS to bank_name dict (line 152):**
```python
self.bank_name = {
    "CB1":"CITIBANK",
    # ... existing entries ...
    "NSG": "NOMURA SINGAPORE",
    "RNS": "R. Nubla Securities",  # ADD THIS
}
```

**Add RNS to account dict (line 735):**
```python
self.account = {
    "CB1":{...},
    # ... existing entries ...
    "NSG": "NOMURA SINGAPORE",
    "RNS": "R. Nubla Securities Stocks",  # ADD THIS
}
```

**Update position header logic (after line 404):**
```python
elif ccy in ('USD', 'SGD'):
    row_num += 1
    cell = self.ws[f'A{row_num}']
    cell.value = f"{ccy} STOCKS"
    cell.font = self.xl_font_color(18, '00000000')

# ADD THIS:
elif ccy == 'PH':
    row_num += 1
    cell = self.ws[f'A{row_num}']
    cell.value = "PHILIPPINE STOCKS"
    cell.font = self.xl_font_color(18, '00000000')
```

**Benefit:** Support for Philippine market (RNS broker)

---

### Fix 3: Update create_LTV_Stocks.py to Include RNS

**File:** `localhost/create_LTV_Stocks.py`
**Line:** 9

```python
# BEFORE:
test = LTV_Stocks('DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG')

# AFTER:
test = LTV_Stocks('DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG', 'RNS')
```

**Benefit:** RNS account will be included in reports

---

## Medium Priority Fixes (2-4 hours)

### Fix 4: Reverse-Engineer Missing Position Formulas

**Problem:** Columns AF and AJ contain formulas not in code

**Investigation Needed:**
1. Analyze multiple position rows in Excel to understand pattern
2. Identify what columns AG, AH, AI represent
3. Determine calculation purpose

**Cell AF Formula:**
```excel
=IF(INDIRECT("AI"&ROW())="",INDIRECT("AH"&ROW()),IF(INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())=0,"",INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())))
```

**Analysis:**
- Uses INDIRECT to reference columns dynamically
- Logic: If AI is empty, use AH value; otherwise calculate AH-AG
- Appears to handle position adjustments

**Action Required:**
```python
# Add to position() method around line 864:
labels = {
    # ... existing columns ...
    'AG': f'[TBD - need to analyze more rows]',
    'AH': f'[TBD - need to analyze more rows]',
    'AI': f'[TBD - need to analyze more rows]',
    'AF': f'=IF(INDIRECT("AI"&ROW())="",INDIRECT("AH"&ROW()),IF(INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())=0,"",INDIRECT("AH"&ROW())-INDIRECT("AG"&ROW())))',
    'AJ': f'[TBD - need to analyze pattern]',
}

# Update dependent formulas:
'D': f'=IF(AF{row_num}="","",AF{row_num})',  # Changed from static value
'O': f'=IF(AJ{row_num}="","",AJ{row_num})',  # Changed from static value
```

**Next Steps:**
1. Open Excel file and examine columns AF-AJ across multiple rows
2. Document what each column represents
3. Implement formulas in code
4. Test with sample data

---

### Fix 5: Add Column Headers Beyond Column X

**Problem:** Code only defines columns up to X (line 323), but output uses columns beyond

**Action:**
```python
# Extend column_width() method (line 298):
cols = {
    # ... existing A-X columns ...
    'Y':5.71 + 0.71,
    'Z':5.71 + 0.71,
    'AA':10 + 0.71,  # Wider for composite key
    'AB':5.71 + 0.71,
    'AC':5.71 + 0.71,
    'AD':5.71 + 0.71,
    'AE':5.71 + 0.71,
    'AF':5.71 + 0.71,
    'AG':5.71 + 0.71,
    'AH':5.71 + 0.71,
    'AI':5.71 + 0.71,
    'AJ':5.71 + 0.71,
    'AK':10 + 0.71,  # Reference column
}
```

---

## Low Priority Enhancements (1-2 hours)

### Enhancement 1: Dynamic Date Headers

**Current:** Static datetime formatting
**Improved:** Formula-based date display

```python
# In report_header() method (line 342):
# BEFORE:
cell.value = f'{self.bank_name[self.bank_account]} as of {self.end_date.strftime("%B %d, %Y")}'

# AFTER:
cell.value = self.bank_name[self.bank_account]
# Add new cell with formula:
date_cell = self.ws[f'K{row_num}']
date_cell.value = f'="as of "&TEXT(I{row_num},"mmmm d, yyyy")'
```

---

### Enhancement 2: Configuration File

**Create:** `localhost/config/ltv_stocks_config.py`

```python
"""Configuration for LTV Stocks report generator."""

class Config:
    # Supported currencies (in priority order)
    CURRENCIES = ['HKD', 'SGD', 'PH', 'JPY', 'AUD', 'USD']

    # Bank account display names
    BANK_NAMES = {
        "CB1": "CITIBANK",
        "CB2": "CITIBANK",
        # ... all accounts ...
        "RNS": "R. Nubla Securities",
    }

    # Account subtitles and colors
    SUBTITLES = {
        'CB2': {'title': 'ACCOUNT # 2 (REALGOLD)', 'color': 'FF7030A0'},
        # ... all subtitles ...
    }

    # Account position labels
    POSITION_LABELS = {
        "CB1": {
            "HKD": "Citibank Account No. 1 Stocks",
            "JPY": "Citibank Account No. 1 Stocks",
            # ... all labels ...
        },
        # ... all accounts ...
        "RNS": "R. Nubla Securities Stocks",
    }

    # Stock color coding
    STOCK_COLORS = {
        '2333': 'FFE5E39F',  # Great Wall Motor
        '0700': '00FFFFCC',  # Tencent
        '1024': '009999FF',  # Kuaishou
        '0388': '00CC99FF',  # HKEx
        '3993': '00FFCC99',  # CMOC
        '0175': '00CCFFFF',  # Geely
        '9988': '00008080',  # Alibaba
    }

    # Excel column widths
    COLUMN_WIDTHS = {
        'A': 27.57 + 0.71,
        'B': 4.86 + 0.71,
        # ... all columns ...
    }

    # Hidden columns
    HIDDEN_COLUMNS = ['M']  # Column C (Bank Reference) now visible

    # Primary account for HKD aggregation
    PRIMARY_ACCOUNT = 'DBPe'
```

**Then in ltv_stocks2.py:**
```python
from config.ltv_stocks_config import Config

class LTV_Stocks:
    def __init__(self, *bank_accounts):
        self.config = Config()
        self.ccys = self.config.CURRENCIES
        self.bank_name = self.config.BANK_NAMES
        # ... etc
```

**Benefits:**
- Centralized configuration
- Easier to maintain
- Can be overridden for testing
- Clear separation of data vs logic

---

### Enhancement 3: Add Logging

```python
import logging

# At top of ltv_stocks2.py:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In LTV_Stocks class:
class LTV_Stocks:
    def __init__(self, *bank_accounts):
        logger.info(f"Initializing LTV Stocks report for accounts: {bank_accounts}")
        # ...

    def create(self):
        logger.info(f"Creating workbook with {len(self.ccys)} currencies")
        # ...

    def contract(self, row_num, product, contracts, ccy):
        logger.debug(f"Processing {len(contracts)} {product} contracts for {ccy}")
        # ...
```

---

## Testing Plan

### Phase 1: Quick Fixes Validation (30 min)
1. Apply Fix 1, 2, 3
2. Run `create_LTV_Stocks.py` with test date
3. Open generated Excel file
4. Verify:
   - Column C (Bank Reference) is visible
   - RNS-PH sheet exists
   - RNS positions appear

### Phase 2: Formula Validation (2 hours)
1. Investigate columns AF, AG, AH, AI, AJ manually
2. Document purpose of each column
3. Implement formulas
4. Test calculations against known-good output

### Phase 3: Comprehensive Testing (1 hour)
1. Generate report for same date as reference file (2026-05-29)
2. Compare cell-by-cell with `instance/2026-05-29 LTV Stocks.xlsx`
3. Document all differences
4. Fix remaining discrepancies

---

## Summary

**Immediate Actions (30 min):**
1. Unhide Column C ✓
2. Add 'PH' currency support ✓
3. Add RNS account to bank_accounts list ✓

**Short-Term (2-4 hours):**
4. Reverse-engineer missing formulas (AF, AJ columns)
5. Extend column definitions

**Long-Term (1-2 hours):**
6. Extract configuration to separate file
7. Add logging for debugging
8. Improve date header formatting

**Total Estimated Time:** 3.5-6.5 hours

**Expected Outcome:** Code will generate reports matching actual production output exactly.
