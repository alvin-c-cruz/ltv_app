# LTV Stocks Report Analysis

**Date:** 2026-06-02
**Source:** `localhost/create_ltv_stocks.py` and `localhost/modules/ltv_stocks2.py`

---

## Overview

The **LTV Stocks** module generates a comprehensive Excel report showing:
1. **ACCU/DECU Contracts** - Active accumulator and decumulator derivative contracts
2. **Stock Positions** - Current portfolio holdings with unrealized P&L
3. **Stock Prices** - 10-day price history for monitoring

**Output:** Excel workbook with multiple sheets (one per bank account + currency combination)

---

## How It Works

### Entry Point: `create_ltv_stocks.py`

```python
# User specifies which bank accounts to include
test = LTV_Stocks('DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG')

# Opens the generated Excel file automatically
os.startfile(test.file_copy)
```

### Main Class: `LTV_Stocks`

**Constructor (`__init__`):**
1. Prompts user for report date (year, month, day)
2. Calculates date range (previous Monday + 10 trading days)
3. Sets up output paths:
   - `temp\New LTV Stocks.xlsx` - For download
   - `excel_files\LTV_Stocks\{date} LTV Stocks.xlsx` - For archiving
4. Calls `create()` to generate report

**Report Generation (`create` method):**
```python
def create(self):
    # Create workbook with helper sheets
    self.wb = openpyxl.Workbook()
    self.wb.create_sheet("closing_price")  # Price lookup
    self.wb.create_sheet("record")         # Transaction record

    # For each currency (HKD, SGD)
    for ccy in self.ccys:
        # For each bank account
        for bank_account in self.bank_accounts:
            # Gather data
            info = Gather_Info(bank_account, ccy, start_date, report_date, end_date, db_file)

            if info.to_print():  # Has data to show
                # Create sheet for this account-currency combo
                sheet_name = f'{bank_account}-{ccy}'
                self.wb.create_sheet(sheet_name)

                # Build sheet content
                row_num = self.report_header(row_num, ccy)         # Bank name, date
                row_num = self.contract(row_num, 'ACCU', accu, ccy)  # ACCU contracts
                row_num = self.contract(row_num, 'DECU', decu, ccy)  # DECU contracts
                row_num = self.position(row_num, stock_position, ccy) # Stock positions

    # Save workbook
    self.wb.save(self.filename)
    self.wb.save(self.file_copy)
```

---

## Data Gathering: `Gather_Info` Class

**Purpose:** Collect all data needed for one bank account + currency combination

**Data Sources:**

###1. **Term Sheets (ACCU/DECU Contracts)**
```python
ts = summary_ts_raw(bank_ref, db_file)
self.accu = self.get_ts(ts.accu, ccy)  # Active ACCU contracts
self.decu = self.get_ts(ts.decu, ccy)  # Active DECU contracts
```

**Data Structure:**
```python
{
    'reference': 'DB-001',
    'stock': 'Alibaba - 9',
    'code': '9988',
    'bank_doc': 'TS-2026-05',
    'shares': '35,000 / 70,000',  # Single / Double
    'spot': 88.50,
    'strike': 85.00,
    'ko': 79.90,
    'start_date': '2026-01-01',
    'end_date': '2026-12-31',
    'received': 2.5,      # Months received
    'remaining': 9.5,     # Months remaining
    'total': 12.0,        # Total months
    'next_date': '2026-06-30',
    'yahoo_ticker': '9988.HK',
    'divisor': 1          # For bi-monthly contracts
}
```

### 2. **Stock Positions**
```python
stock_balances = stock_balance().stock_position(str(start_date)[:10], bank_account)
```

**Data Structure:**
```python
{
    '9988': {
        'stock_name': 'Alibaba - 9',
        'yahoo_ticker': '9988.HK',
        'unblocked': 350000,  # Shares available to sell
        'blocked': 70000,     # Shares in ACCU contracts
        'average': 85.50      # Average cost basis
    }
}
```

### 3. **Recent Transactions**
```python
transactions = get_ranged_transactions(report_date)
```

Includes transactions for display in stock position section.

---

## Excel Sheet Structure

### Sheet Naming: `{BankAccount}-{Currency}`
Examples: `DBPe-HKD`, `SHK-HKD`, `NSG-SGD`

### Layout:

```
┌─────────────────────────────────────────────────────────────────┐
│ DEUTSCHE BANK as of June 02, 2026          updated: May 27, 2026│
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ACCUMULATOR SECTION                                             │
│ ┌──────────────┬──────┬─────────┬────────┬────────┬───────────┐│
│ │ Stock        │ Code │ Shares  │ Spot   │ Strike │ KO        ││
│ │ Alibaba - 9  │ 9988 │35k/70k  │ 88.50  │ 85.00  │ 79.90     ││
│ │ ...          │ ...  │ ...     │ ...    │ ...    │ ...       ││
│ └──────────────┴──────┴─────────┴────────┴────────┴───────────┘│
│                                                                  │
│ DECUMULATOR SECTION                                             │
│ ┌──────────────┬──────┬─────────┬────────┬────────┬───────────┐│
│ │ Stock        │ Code │ Shares  │ Spot   │ Strike │ KO        ││
│ │ ...          │ ...  │ ...     │ ...    │ ...    │ ...       ││
│ └──────────────┴──────┴─────────┴────────┴────────┴───────────┘│
│                                                                  │
│ STOCK POSITION SECTION                                          │
│ ┌──────────────┬──────┬──────────┬─────────┬──────────────────┐│
│ │ Stock        │ Code │ Unblocked│ Blocked │ Average  │ P/L %  ││
│ │ Alibaba - 9  │ 9988 │ 350,000  │ 70,000  │ 85.50    │ +3.51% ││
│ │ ...          │ ...  │ ...      │ ...     │ ...      │ ...    ││
│ └──────────────┴──────┴──────────┴─────────┴──────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Price History Columns (O-X)

Shows 10 days of closing prices with indicators:
- **D** - Double shares accumulated (Strike Price triggered)
- **.** - Single share accumulated
- **KO** - Knockout triggered
- **Done** - Contract completed
- **Grey fill** - Date outside contract period or holiday

### Formulas Used

**1. Stock Price Lookup:**
```excel
=INDEX(closing_price!A:C,MATCH(M{row},closing_price!A:A,),3)
```
Looks up closing price from helper sheet by Yahoo ticker.

**2. P/L Percentage:**
```excel
=(L{row}/I{row})-1
```
Compares current price to average cost.

**3. Total Shares:**
```excel
=D{row}+E{row}
```
Unblocked + Blocked shares.

---

## Key Features

### 1. **Multi-Account Support**
Can include any combination of bank accounts in a single report:
- DBPe (Deutsche Bank Personal)
- DBPL (Deutsche Bank Perfect Legend)
- SHK, SHK2 (Sun Hung Kai)
- MST1, MST2, MSPL (Morgan Stanley)
- NSG (Nomura Singapore)

### 2. **Multi-Currency Support**
Separate sheets for:
- HKD (Hong Kong stocks)
- SGD (Singapore stocks)
- USD, JPY, AUD (other markets - less common)

### 3. **Conditional Formatting**
- Stock-specific colors (Alibaba = teal, Tencent = yellow, etc.)
- Account-specific subtitle colors
- Grey fill for non-trading days

### 4. **Print-Ready Layout**
- Landscape orientation
- Paper size 4 (A4)
- Narrow margins
- Print area set dynamically

### 5. **HKD Aggregation**
Primary bank account (DBPe) includes sum formulas:
```excel
=SUM('DBPe-HKD'!A5, 'SHK-HKD'!A5, 'MST1-HKD'!A5, ...)
```
Shows total ACCU/DECU count across all accounts.

---

## Dependencies

### Legacy Modules (localhost/modules/)

| Module | Purpose |
|--------|---------|
| `database.database()` | Database connection |
| `term_sheet.summary_ts_raw()` | Get term sheet contracts |
| `bank_account.getbank_ref()` | Convert bank_id to ref_num |
| `transaction_list.stock_balance()` | Get stock positions |
| `stocks.label_stocks()` | Stock metadata |
| `stock_price.get_stock_price()` | Historical prices |
| `LTV_Transactions.get_ranged_transactions()` | Recent transactions |
| `working_day` | Holiday calendar |

### Python Packages
- `openpyxl` - Excel file generation
- `pandas` - DataFrames for contract data
- `datetime` - Date calculations

---

## User Interaction Flow

1. **Run script:** `python localhost/create_ltv_stocks.py`
2. **Enter date:**
   ```
   Year: 2026
   Month: 6
   Day: 2
   ```
3. **Processing:**
   ```
   Gathering info for DBPe-HKD
   Gathering info for DBPL-HKD
   Gathering info for SHK-HKD
   ...
   Time used is 0:00:08.123456
   ```
4. **Output:** Excel file opens automatically

---

## File Outputs

### 1. **Download Version**
**Path:** `temp\New LTV Stocks.xlsx`
**Purpose:** For immediate viewing/download
**Overwritten:** Each run

### 2. **Archive Version**
**Path:** `excel_files\LTV_Stocks\2026-06-02 LTV Stocks.xlsx`
**Purpose:** Historical record
**Unique:** Date-stamped filename

---

## Challenges for Modernization

### 1. **Console Input**
```python
year = int(input("Year: "))
month = int(input("Month: "))
day = int(input("Day: "))
```
**Solution:** Web form with date picker

### 2. **Multiple Legacy Dependencies**
Requires ~10 legacy modules from `localhost/modules/`

**Solution:** Refactor to use ltv_app models and blueprints

### 3. **Hardcoded Bank Names**
```python
self.bank_name = {
    "CB1":"CITIBANK",
    "DBPe":"DEUTSCHE BANK",
    ...
}
```
**Solution:** Query from `tbl_bank_account`

### 4. **No Template File**
Unlike fixings, this generates Excel from scratch using openpyxl

**Solution:** Continue generating programmatically (more flexible)

### 5. **Opening File Automatically**
```python
os.startfile(test.file_copy)
```
**Solution:** Download endpoint in Flask

---

## Proposed Modern Implementation

### Blueprint Structure
```
ltv_app/blueprints/ltv_stocks/
├── __init__.py
├── views.py          # Routes: /ltv-stocks, /ltv-stocks/generate, /ltv-stocks/download
├── models.py         # (Use existing models)
├── extensions/
│   ├── __init__.py
│   ├── gather_data.py      # Data collection logic
│   └── generate_report.py  # Excel generation logic
└── pages/
    └── ltv_stocks/
        └── home.html        # UI for selecting accounts and date
```

### UI Design (home.html)

```
┌────────────────────────────────────────────┐
│ LTV Stocks Report Generator                │
├────────────────────────────────────────────┤
│                                            │
│ Report Date: [___________] (date picker)   │
│                                            │
│ Select Bank Accounts:                      │
│ ☑ DBPe  - Deutsche Bank Personal           │
│ ☑ DBPL  - Deutsche Bank Perfect Legend     │
│ ☑ SHK   - Sun Hung Kai Account No. 1       │
│ ☑ SHK2  - Sun Hung Kai Account No. 2       │
│ ☑ MST1  - Morgan Stanley Titan No. 1       │
│ ☑ MST2  - Morgan Stanley Titan No. 2       │
│ ☑ MSPL  - Morgan Stanley Perfect Legend    │
│ ☑ NSG   - Nomura Singapore                 │
│                                            │
│ [Generate Report]                          │
│                                            │
│ Recent Reports:                            │
│ • 2026-06-01 LTV Stocks.xlsx (Download)    │
│ • 2026-05-31 LTV Stocks.xlsx (Download)    │
│ • 2026-05-30 LTV Stocks.xlsx (Download)    │
└────────────────────────────────────────────┘
```

### Routes

#### 1. Home Page
**GET /ltv-stocks**
```python
@bp.route('/', methods=['GET'])
@login_required
def home():
    # Get all bank accounts
    db = get_db()
    accounts = db.execute("SELECT ref_num, bank_id, bank_name FROM tbl_bank_account WHERE is_active=1 ORDER BY priority").fetchall()

    # Get recent reports
    reports = get_recent_reports()

    return render_template('ltv_stocks/home.html', accounts=accounts, reports=reports)
```

#### 2. Generate Report
**POST /ltv-stocks/generate**
```python
@bp.route('/generate', methods=['POST'])
@login_required
def generate():
    report_date = request.form['report_date']
    bank_accounts = request.form.getlist('bank_accounts')  # ['DBPe', 'SHK', ...]

    # Generate report
    from .extensions.generate_report import LTVStocksReport
    report = LTVStocksReport(bank_accounts, report_date)
    filename = report.create()

    flash(f"Report generated successfully", "success")
    return redirect(url_for('ltv_stocks.download', filename=filename))
```

#### 3. Download Report
**GET /ltv-stocks/download/<filename>**
```python
@bp.route('/download/<filename>', methods=['GET'])
@login_required
def download(filename):
    file_path = os.path.join(current_app.instance_path, 'temp', filename)
    return send_file(file_path, as_attachment=True, download_name=filename)
```

---

## Implementation Steps

### Phase 1: Data Layer (Week 1)
- [x] Analyze legacy code
- [ ] Create `gather_data.py` extension
- [ ] Refactor `Gather_Info` to use ltv_app models
- [ ] Remove dependencies on localhost/modules/

### Phase 2: Report Generation (Week 2)
- [ ] Create `generate_report.py` extension
- [ ] Port `LTV_Stocks` class to modern code
- [ ] Test Excel generation with sample data

### Phase 3: UI & Routes (Week 3)
- [ ] Create blueprint structure
- [ ] Build home.html form
- [ ] Implement generate and download routes
- [ ] Add to navigation menu

### Phase 4: Testing & Polish (Week 4)
- [ ] Test with multiple bank accounts
- [ ] Test with different currencies
- [ ] Verify formulas work correctly
- [ ] Add error handling

---

## Benefits of Modernization

| Benefit | Description |
|---------|-------------|
| **Web-Based** | No need to run Python scripts manually |
| **User-Friendly** | Visual interface with checkboxes and date picker |
| **Multi-User** | Multiple users can generate reports simultaneously |
| **History** | View and download previous reports |
| **Permissions** | Control access with login_required decorator |
| **Logging** | Track who generated which reports and when |
| **Mobile-Friendly** | Access from any device |

---

## Next Steps

1. **Review this analysis** with stakeholders
2. **Decide on implementation priority**
3. **Begin Phase 1** (data layer refactoring)
4. **Create blueprint structure**

**Estimated Timeline:** 4 weeks for complete implementation
**Priority:** Medium (nice-to-have feature, existing script works)
