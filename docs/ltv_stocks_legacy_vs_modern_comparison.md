# LTV Stocks: Legacy vs Modern Comparison

**Date:** 2026-06-02
**Issue:** The modern implementation looks nothing like the legacy output

---

## Key Differences Identified

### 1. **Header Structure - MAJOR DIFFERENCE**

#### Legacy (localhost/ltv_stocks2.py):
```
Row 1: Contract Count Formula (small font, 7pt)
Row 2: "ACCUMULATOR" (or "DECUMULATOR")
Row 3: Strike Price < Closing Price = QTYx1
Row 4: Strike Price > Closing Price = QTYx2
```

**Three-row header with formulas and explanations!**

#### Modern (ltv_app/):
```
Row 1: "ACCUMULATOR" (title only, dark navy background)
Row 2-3: Column headers only
```

**Simple title row - missing the contract count and price logic explanations**

---

### 2. **Column A Content - HUGE DIFFERENCE**

#### Legacy:
**Column A contains THREE pieces of info:**
- Row 1: **Active contract count formula** `=5-COUNTIF(N5:N9,"*DONE*")`
- Row 2: **Explanation text** "Strike Price < Closing Price = QTYx1"
- Row 3: **Explanation text** "Strike Price > Closing Price = QTYx2"
- Rows 4+: Stock names

**This is critical** - it shows how many contracts are still active!

#### Modern:
- Column A only has stock names
- **Missing** the contract count
- **Missing** the explanatory text

---

### 3. **Column C - Bank Reference**

#### Legacy:
- Column C: "Bank Reference" (bank_doc field)
- Shows values like "TS-2026-05", "DB-001", etc.

#### Modern:
- Column C: "Shares / Day"
- **Bank Reference column is missing entirely**

---

### 4. **Date Range - COMPLETELY DIFFERENT**

#### Legacy:
```python
# Shows 10 specific trading days (2 weeks: 5 days + 5 days)
start = report_date - timedelta(days = 6 + report_date.isoweekday())
self.date_range = [
    start,                              # Monday week 1
    start + timedelta(days = 1),        # Tuesday
    start + timedelta(days = 2),        # Wednesday
    start + timedelta(days = 3),        # Thursday
    start + timedelta(days = 4),        # Friday
    start + timedelta(days = 7),        # Monday week 2
    start + timedelta(days = 8),        # Tuesday
    start + timedelta(days = 9),        # Wednesday
    start + timedelta(days = 10),       # Thursday
    start + timedelta(days = 11),       # Friday
]
```

**Shows LAST Monday through previous Friday, PLUS current week Monday through report date**

Example for report_date = 2026-06-02 (Tuesday):
- Week 1: May 25-29 (Mon-Fri)
- Week 2: June 1-2 (Mon-Tue)

#### Modern:
```python
trading_dates = _get_two_week_dates(report_date)
```

**Different calculation - not the same dates!**

---

### 5. **Price Display - DUAL COLUMNS**

#### Legacy:
**TWO sets of price columns:**
- Columns O-X: First set of 10 closing prices
- Columns AA-AJ: Second set showing indicators (D, ., KO, Done)

**Columns AA-AJ contain complex formulas:**
```excel
=IF($E{row}>$F{row},
    IF(O{row}=0,"xxx",
        IF(O{row}="","",
            IF($Z{row}=2,
                IF($G{row}<=O{row},"KO",
                    IF($F{row}>=O{row},"D",".")
                ),
                IF($G{row}<=O{row},"KO",".")
            )
        )
    ),
    IF(O{row}=0,"xxx",
        IF(O{row}="","",
            IF($Z{row}=2,
                IF($G{row}>=O{row},"KO",
                    IF($F{row}<=O{row},"D",".")
                ),
                IF($G{row}>=O{row},"KO",".")
            )
        )
    )
)
```

**Shows:**
- **D** = Double shares (Strike triggered)
- **.** = Single share
- **KO** = Knockout
- **Done** = Contract completed
- **xxx** = Price is 0
- **(blank)** = No price data

#### Modern:
- Only ONE set of price columns
- Shows raw closing prices only
- **No indicators for D/./KO/Done**

---

### 6. **Stock-Specific Colors**

#### Legacy (lines 688-704):
```python
if col =='A':
    if row.code == '2333':
        cell.fill = self.xl_fill('FFE5E39F')  # Light tan
    elif row.code == '0700':
        cell.fill = self.xl_fill('00FFFFCC')  # Light yellow
    elif row.code == '1024':
        cell.fill = self.xl_fill('009999FF')  # Light blue
    elif row.code == '0388':
        cell.fill = self.xl_fill('00CC99FF')  # Light purple
    elif row.code == '3993':
        cell.fill = self.xl_fill('00FFCC99')  # Light orange
    elif row.code == '0175':
        cell.fill = self.xl_fill('00CCFFFF')  # Light cyan
    elif row.code == '9988':
        cell.fill = self.xl_fill('00008080')  # Teal (Alibaba)
    elif row.code in ('0981', '2196'):
        cell.font = self.xl_font(9)
```

**Each stock has a specific color!**

#### Modern:
- No stock-specific colors
- All rows same format

---

### 7. **HKD Aggregation Formulas**

#### Legacy (lines 251-285):
```python
# For primary account (DBPe-HKD), adds SUM formulas
accu_formula = "=SUM('DBPe-HKD'!A5, 'SHK-HKD'!A5, 'MST1-HKD'!A5, ...)"
decu_formula = "=SUM('DBPe-HKD'!B5, 'SHK-HKD'!B5, 'MST1-HKD'!B5, ...)"

# Cell A5 in DBPe-HKD shows TOTAL ACCU count across ALL HKD accounts
# Cell B5 in DBPe-HKD shows TOTAL DECU count across ALL HKD accounts
```

**Primary bank sheet shows GRAND TOTAL counts!**

#### Modern:
- Each sheet independent
- No cross-sheet aggregation

---

### 8. **Position Section - Recent Transactions**

#### Legacy (lines 864):
```python
'O': self.stock_position[code]['transactions'] if 'transactions' in self.stock_position[code] else None
```

Column O shows recent transactions in the position section!

**Merged cells O-X** with transaction details.

#### Modern:
- No transaction history in positions
- Only shows balance, average, P/L

---

### 9. **Grey Fill for Non-Trading Days**

#### Legacy (lines 638-674):
```python
if self.date_range[col_date[col]] < row.start_date:
    cell.fill = self.xl_fill('00C0C0C0')  # Grey - before contract start
elif self.date_range[col_date[col]] > row.end_date:
    # Complex logic for "Done" vs grey fill
elif working_day().isHoliday(self.date_range[col_date[col]], getccy(row.code)):
    cell.fill = self.xl_fill('00C0C0C0')  # Grey - holiday
```

**Price cells are greyed out for:**
- Dates before contract start
- Dates after contract end
- Holidays

#### Modern:
- No conditional formatting based on dates
- All cells same format

---

### 10. **"Done" Indicator Logic**

#### Legacy:
Shows "Done" in the FIRST price column AFTER contract ends:
- If Friday (col_date 4): Check if date is end_date + 3 days
- If after Friday: Check if date is end_date + 1 day
- Handles holidays specially

**"Done" appears ONCE in the price grid**

#### Modern:
- "DONE" appears in "Next Mo." column only
- Not in price grid

---

## Summary of Missing Features

| Feature | Legacy | Modern | Priority |
|---------|--------|--------|----------|
| Active contract count formula | ✅ | ❌ | **CRITICAL** |
| Price logic explanations (x1/x2) | ✅ | ❌ | **HIGH** |
| Bank Reference column | ✅ | ❌ | **HIGH** |
| Correct date range calculation | ✅ | ❌ | **CRITICAL** |
| Indicator columns (D/./KO/Done) | ✅ | ❌ | **CRITICAL** |
| Stock-specific colors | ✅ | ❌ | **MEDIUM** |
| HKD cross-account totals | ✅ | ❌ | **HIGH** |
| Recent transactions in positions | ✅ | ❌ | **MEDIUM** |
| Grey fill for non-trading days | ✅ | ❌ | **HIGH** |
| "Done" in price grid | ✅ | ❌ | **MEDIUM** |

---

## Visual Layout Comparison

### Legacy Layout:

```
┌────────────────────────────────────────────────────────────────┐
│ Row 1: =5-COUNTIF(...)  [Active contract count]               │
├────────────────────────────────────────────────────────────────┤
│ Row 2: ACCUMULATOR                                             │
│        Strike Price < Closing Price = QTYx1                    │
├────────────────────────────────────────────────────────────────┤
│ Row 3: Strike Price > Closing Price = QTYx2                    │
├────────────────────────────────────────────────────────────────┤
│ Row 4: Headers                                                 │
│  Stock | Code | Bank Ref | Shares | Spot | Strike | KO | ...  │
├────────────────────────────────────────────────────────────────┤
│ Row 5+: Contract data                                          │
│  Alibaba (teal) | 9988 | DB-001 | 35k/70k | ...               │
│                                                                 │
│  Prices (O-X):  88.50 | 88.20 | 89.00 | ...                   │
│  Indicators (AA-AJ):  D | . | KO | Done | ...                 │
└────────────────────────────────────────────────────────────────┘
```

### Modern Layout:

```
┌────────────────────────────────────────────────────────────────┐
│ Row 1: ACCUMULATOR [dark navy background]                     │
├────────────────────────────────────────────────────────────────┤
│ Row 2-3: Headers                                               │
│  Stock | Code | Shares | Spot | Strike | KO | ...            │
├────────────────────────────────────────────────────────────────┤
│ Row 4+: Contract data                                          │
│  Alibaba | 9988 | 35k/70k | ...                               │
│                                                                 │
│  Prices (M+): 88.50 | 88.20 | 89.00 | ...                     │
│  [No indicators]                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Recommendation

The modern implementation is **NOT equivalent** to the legacy one. It's missing critical features that users rely on:

1. **Active contract count** - Users need to know how many contracts are still active
2. **Price indicators (D/./KO)** - Users need to see single/double/knockout status at a glance
3. **Bank reference** - Important tracking information
4. **Correct date range** - The legacy shows "previous full week + current week to date"
5. **Stock colors** - Visual identification of key stocks
6. **HKD totals** - Aggregation across accounts

### Next Steps:

1. Port the legacy Excel generation logic to modern ltv_app
2. Keep the web UI (date picker, download)
3. Replace the `_generate_excel()` function with legacy-style output
4. Test thoroughly to match legacy appearance

**Estimated effort:** 2-3 days to port and test properly.
