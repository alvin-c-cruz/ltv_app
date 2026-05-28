# Knockout Sheet Improvements

**Date:** 2026-05-28
**File Modified:** [ltv_app/blueprints/fixings/extensions/download_fixings.py](../ltv_app/blueprints/fixings/extensions/download_fixings.py)

---

## Changes Made

### 1. ✅ Date Calculation Fixed
**Issue:** Date was showing current date instead of previous HK banking day.

**Solution:** Added `get_previous_business_day()` method (lines 405-423) that:
- Calculates one day before the fixing date
- Queries `tbl_holiday` table for HK holidays
- Skips weekends (Saturday/Sunday)
- Skips HK public holidays
- Returns the correct previous business day

**Example:** If fixing date is May 28, 2026, it will show "Date: May 27, 2026" (or earlier if May 27 is a holiday/weekend)

### 2. ✅ Date Font Size and Style
**Change:** Date row now uses size 14 bold font (line 437-438)

**Before:**
```python
cell.font = Font(size=11)
```

**After:**
```python
cell.font = Font(size=14, bold=True)
```

### 3. ✅ No. Column Formula Error Fixed
**Issue:** First row used `=INDIRECT("A"&ROW()-1)+1` which referenced a string value causing `#####` error.

**Solution:** Changed to use simple numeric index (line 506)

**Before:**
```python
"A": f'=INDIRECT("A"&ROW()-1)+1',
```

**After:**
```python
"A": idx,  # Direct integer from enumerate(start=1)
```

### 4. ✅ Grey Fill Color Removed from Headers
**Change:** Removed grey background from all header columns (lines 459-468)

**Before:**
```python
cell.fill = PatternFill(patternType="solid", fill_type="solid", fgColor="00D3D3D3")
```

**After:**
```python
# No fill for most columns
# Pink fill only for KO and Closing columns
if column_letter in ("I", "J"):
    cell.fill = PatternFill(patternType="solid", fill_type="solid", fgColor="00FFC7CE")
```

### 5. ✅ Row Height Doubled
**Change:** Entry rows now have double height (30 points) with vertical center alignment (line 544)

**Code:**
```python
self.ws.row_dimensions[self.row_num].height = 30
```

All cells already have `vertical="center"` alignment (lines 527, 529, 531).

### 6. ✅ Pink Fill Color for KO and Closing Columns
**Change:** Added pink/red background color (#FFC7CE) to KO and Closing columns

**Implementation:**
- Header row (lines 466-468)
- Data rows (lines 539-541)

**Color:** `00FFC7CE` (light pink/red - matches screenshot)

### 7. ✅ Closing Price Populated
**Solution:** Added `get_closing_price()` method (lines 470-490) that:
- Looks up stock `code_ref` from `tbl_code` table
- Queries `tbl_stock_price` for closing price on the date
- Falls back to most recent price before the date if exact date not found
- Populates "Closing" column (J) with the price

**Implementation in write_details()** (lines 499-502, 515):
```python
code_ref = self.db.execute("SELECT ref_num FROM tbl_code WHERE code=?",
                           (fixing["code"],)).fetchone()[0]
closing_price = self.get_closing_price(code_ref, prev_business_day)
...
"J": closing_price if closing_price else "",
```

**Number Format:** Closing column uses `#,##0.00` (2 decimal places) format (line 555)

---

## Technical Details

### Method Signatures Changed

**WriteKnockouts.__init__():**
```python
# Before
def __init__(self, db, wb, knockouts):

# After
def __init__(self, db, wb, knockouts, trade_date):
```

**Call site updated** (line 49):
```python
WriteKnockouts(self.db, wb, self.knockouts, self.trade_date)
```

### New Methods Added

1. **get_previous_business_day(date_str)** - Calculates previous HK business day
2. **get_closing_price(code_ref, trade_date)** - Retrieves stock closing price with fallback

### Database Queries Added

```sql
-- Get HK holidays
SELECT holi_date FROM tbl_holiday
INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_holiday.ccy_ref
WHERE tbl_currency.ccy_id = 'HKD'

-- Get closing price for specific date
SELECT closing_price FROM tbl_stock_price
WHERE code_ref=? AND trade_date=?

-- Fallback: get most recent closing price before date
SELECT closing_price FROM tbl_stock_price
WHERE code_ref=? AND trade_date<?
ORDER BY trade_date DESC LIMIT 1

-- Get stock code_ref
SELECT ref_num FROM tbl_code WHERE code=?
```

---

## Final Layout

The Knockout sheet now appears as:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Knock Out Summary                         [Bold 14pt]                   │
│ Date: May 27, 2026                        [Bold 14pt]                   │
│                                                                          │
│ ┌────┬──────┬─────────────┬─────────┬──────┬────────┬─────────┬────────┤
│ │No. │ TYPE │BANK ACCOUNT │  STOCK  │ CODE │ SHARES │  SPOT   │ STRIKE │
│ │    │      │             │         │      │        │         │        │
│ ├────┼──────┼─────────────┼─────────┼──────┼────────┼─────────┼────────┤
│ │  1 │ DECU │Deutsche...  │ Alibaba │ 9988 │170/340 │138.7000 │173.0144│
│ │    │      │             │         │      │        │  (30pt  │        │
│ ├────┼──────┼─────────────┼─────────┼──────┼────────┤  height)├────────┤
│ │  2 │ DECU │Sun Hung...  │ Alibaba │ 9988 │160/320 │132.5000 │175.7612│
│ └────┴──────┴─────────────┴─────────┴──────┴────────┴─────────┴────────┘
│
│ ┬────────┬─────────┬────────┐
│ │   KO   │ Closing │ SHARES │  [Pink background: #FFC7CE]
│ │        │         │        │
│ ├────────┼─────────┼────────┤
│ │124.8300│ 124.30  │  170   │
│ │        │         │        │
│ ├────────┼─────────┼────────┤
│ │125.8750│ 124.30  │ 2,400  │
│ └────────┴─────────┴────────┘
```

### Formatting Applied:
- ✅ Bold headers (no grey background)
- ✅ Pink fill for KO and Closing columns
- ✅ All cells bordered
- ✅ 30pt row height for data rows
- ✅ Vertical center alignment
- ✅ Number formatting (integers: #,##0, decimals: #,##0.0000)
- ✅ Proper column widths
- ✅ Correct date (previous business day)
- ✅ No formula errors (direct index numbers)
- ✅ Closing prices populated from database

---

### 8. ✅ Red Color for "(KO)" in Underlying Column
**Change:** When the Underlying cell contains "(KO)", only the "(KO)" portion is colored red while the rest remains black (lines 189-203)

**Implementation:** Uses Excel rich text formatting with `InlineFont`
```python
if col == "A" and "(KO)" in str(value):
    text_str = str(value)
    ko_index = text_str.index("(KO)")

    # Split text: black part + red "(KO)" part
    black_text = text_str[:ko_index]  # "Alibaba - 11 "
    ko_text = text_str[ko_index:]     # "(KO)"

    rich_text = CellRichText(
        TextBlock(InlineFont(sz=11, b=True), black_text),
        TextBlock(InlineFont(sz=11, b=True, color=RED_FONT), ko_text)
    )
    cell.value = rich_text
```

**Example:**
- "Alibaba - 11 (KO)" will appear as: "Alibaba - 11" (black) + "(KO)" (red)
- The font remains bold size 11 for both parts

**Note:** This applies to the individual account sheets (e.g., "Deutsche Bank Personal-HKD"), not the Knockout Summary sheet.

**Imports Added:**
- `from openpyxl.cell.rich_text import TextBlock, CellRichText`
- `from openpyxl.cell.text import InlineFont`

**Important:** `TextBlock` requires `InlineFont` (not regular `Font`). `InlineFont` uses different parameter names:
- `sz` instead of `size`
- `b` instead of `bold`
- `color` works the same way

---

## Testing Checklist

Before deploying, verify:

### Knockout Summary Sheet:
- [ ] Date shows correct previous HK business day (skips weekends/holidays)
- [ ] Date is bold 14pt font
- [ ] No. column shows 1, 2, 3... (no ##### errors)
- [ ] Headers have no grey fill
- [ ] KO and Closing columns have pink fill (#FFC7CE)
- [ ] Data rows are taller (30pt height)
- [ ] All cells vertically centered
- [ ] Closing prices appear for all stocks
- [ ] Number formatting correct (commas, decimals)
- [ ] Borders on all cells

### Individual Account Sheets:
- [ ] Underlying column shows entries with "(KO)" in red text
- [ ] Non-KO entries remain in black text

### Additional Improvements (May 28, 2026):
- [ ] All columns in Knockout Summary sheet are centered horizontally
- [ ] Closing column uses `#,##0.00` format (2 decimals: 124.30 instead of 124.3000)

---

## Dependencies

This implementation requires:
- `tbl_holiday` table with HK holidays
- `tbl_stock_price` table with historical closing prices
- `tbl_code` table with stock codes
- `tbl_currency` table with HKD currency reference

If any of these tables are missing data, the fallback logic will:
- Use previous available date for closing prices
- Skip holiday checking if `tbl_holiday` is empty (weekends still skipped)
