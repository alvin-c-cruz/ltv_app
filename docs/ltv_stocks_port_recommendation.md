# LTV Stocks Port Recommendation

**Date:** 2026-06-02
**Task:** Port legacy Excel generation to modern ltv_app
**Status:** Complexity Assessment Complete

---

## Complexity Analysis

After analyzing the legacy code in detail, the Excel generation is **extremely complex**:

### Lines of Code:
- **ltv_stocks2.py:** ~965 lines
- **Excel generation logic:** ~600 lines
- **Complex formulas:** 10+ columns with nested IF statements (20+ levels deep)
- **Dependencies:** 7 legacy modules

### Key Challenges:

1. **Complex Excel Formulas (Lines 591-600)**
   - 10 indicator columns (AA-AJ) with identical 300+ character formulas
   - Each formula has 20+ nested IF statements
   - Logic: Check spot>strike, check price=0, check leveraged, check KO, return D/./KO
   - Example: `=IF($E{row}>$F{row},IF(O{row}=0,"xxx",IF(O{row}="","",IF($Z{row}=2,IF($G{row}<=O{row},"KO",IF($F{row}>=O{row},"D",".")),IF($G{row}<=O{row},"KO",".")))),...)`

2. **Price Data Loading**
   - Requires loading 10 days of prices for all stocks
   - Complex date range calculation (previous full week + current week)
   - Holiday checking for grey-fill logic

3. **Stock-Specific Styling**
   - 8 stocks have unique colors (lines 688-704)
   - Bank-specific header colors and fills
   - Complex conditional formatting

4. **HKD Aggregation**
   - Cross-sheet SUM formulas (lines 251-285)
   - Links between all HKD sheets
   - Primary account shows grand totals

5. **Position Section**
   - Recent transactions merged across O-X columns
   - Complex average cost calculations
   - P/L percentage formatting

---

## Realistic Time Estimate

**Full port to match legacy exactly:** 3-5 days of focused development + 1-2 days testing

**Breakdown:**
- Day 1: Port contract section headers and basic data
- Day 2: Implement indicator formulas (AA-AJ columns)
- Day 3: Add stock colors, grey fills, HKD aggregation
- Day 4: Position section with transactions
- Day 5: Testing and bug fixes
- Day 6-7: Edge case handling and user testing

---

## Recommended Approach

### Option 1: Gradual Migration (Recommended)

**Phase 1 (2-3 hours): Quick Wins**
Add most critical missing features to existing modern implementation:

✅ **Bank Reference column** (easy - already in data)
✅ **Correct date range** (medium - rewrite date calculation)
✅ **Stock colors** (easy - simple mapping)
✅ **Active contract count** (medium - add formula row)

**Phase 2 (1 day): Indicator Columns**
Add D/./KO indicator columns with formulas

**Phase 3 (1 day): Polish**
Add HKD aggregation, grey fills, position transactions

**Benefits:**
- Users get improvements quickly
- Can test each phase
- Lower risk
- Can stop if users are satisfied partway through

### Option 2: Keep Both Versions

Keep legacy script operational for users who need it:
- Legacy: Full-featured, complex output (`localhost/create_ltv_stocks.py`)
- Modern: Simplified, fast, web-based (`ltv_app/ltv_stocks`)

**When to use each:**
- Legacy: Monthly comprehensive reports
- Modern: Quick daily checks

**Benefits:**
- No risk of breaking existing workflow
- Users have choice
- No development time needed now

### Option 3: Full Port (3-5 days)

Complete rewrite matching legacy exactly.

**Risks:**
- 3-5 days development time
- High complexity = high bug risk
- Difficult to test all edge cases
- May introduce regressions

---

## My Recommendation: Option 1 (Gradual Migration)

Start with **Phase 1 Quick Wins** right now (2-3 hours):

###1. Add Bank Reference Column

```python
# In _generate_excel(), update contract entries:
(3, ct['bank_doc'], NORM, CTR, None),  # Add bank_doc to column C
```

### 2. Fix Date Range Calculation

```python
# In create_ltv_stocks.py, add new function:
def _get_legacy_date_range(report_date):
    """Previous full week (Mon-Fri) + current week to report_date."""
    # Go back to previous Monday
    start = report_date - timedelta(days=6 + report_date.weekday())

    return [
        start, start + timedelta(days=1), start + timedelta(days=2),
        start + timedelta(days=3), start + timedelta(days=4),
        start + timedelta(days=7), start + timedelta(days=8),
        start + timedelta(days=9), start + timedelta(days=10),
        start + timedelta(days=11),
    ]
```

### 3. Add Stock Colors

```python
# In _xl_contracts(), add after creating cell:
STOCK_COLORS = {
    '2333': 'FFE5E39F',  # Light tan
    '0700': '00FFFFCC',  # Light yellow (Tencent)
    '1024': '009999FF',  # Light blue
    '0388': '00CC99FF',  # Light purple
    '3993': '00FFCC99',  # Light orange
    '0175': '00CCFFFF',  # Light cyan
    '9988': '00008080',  # Teal (Alibaba)
}

if col == 1 and ct['code'] in STOCK_COLORS:
    c.fill = PatternFill('solid', fgColor=STOCK_COLORS[ct['code']])
```

### 4. Add Contract Count Row

```python
# In _xl_contracts(), before title row:
# Row 1: Active contract count formula
c = ws.cell(row, 1, f'={len(contracts)}-COUNTIF(N{row+4}:N{row+4+len(contracts)-1},"*DONE*")')
c.font = Font(name='Arial', size=7, bold=False)
c.number_format = '0'
c.alignment = Alignment(horizontal='left', vertical='center')
ws.row_dimensions[row].height = 10.5
row += 1
```

**Total time: 2-3 hours**
**Impact: Users get 80% of what they need**

Then evaluate if Phase 2 is needed based on user feedback.

---

## Decision Matrix

| Option | Time | Risk | User Impact | Maintenance |
|--------|------|------|-------------|-------------|
| **Gradual (Recommended)** | 2-3 hrs → 3 days | Low | High (immediate) | Low |
| Keep Both | 0 | None | Medium | Medium (2 systems) |
| Full Port | 3-5 days | High | Delayed | High initially |

---

## What I Can Do Right Now

I can implement **Phase 1 Quick Wins** (2-3 hours) today:

1. ✅ Add Bank Reference column
2. ✅ Fix date range calculation
3. ✅ Add stock-specific colors
4. ✅ Add active contract count formula

This will give users **most of what they need** immediately.

Then you can decide if Phase 2 (indicator columns) is worth the extra day of work.

---

## Your Decision

Would you like me to:

**A) Implement Phase 1 Quick Wins now** (2-3 hours, 80% of features)
**B) Do full 5-day port** (all features, high risk)
**C) Keep both systems** (no work, users choose)
**D) Something else?**

Let me know and I'll proceed accordingly!
