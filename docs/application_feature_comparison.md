# Application Feature Comparison: ltv_app vs localhost/

**Date:** 2026-06-05
**Purpose:** Document features in both applications to guide migration and prevent data loss

---

## Executive Summary

**ltv_app** (modern Flask app) has **91 routes across 32 blueprints** with web UI and modern architecture.
**localhost/** (legacy app) has **14 routes, 103 Python files, 28 modules** with CLI-based report generation and legacy features.

**Key Finding:** While ltv_app has broader feature coverage, localhost/ contains unique implementations and report formats that users may still rely on.

---

## Application Overview

### ltv_app (Modern Flask Application)

- **Entry Point:** `flask_app.py`
- **Port:** 5000 (auto-detected host)
- **Architecture:** Blueprint-based Flask 4.0.6
- **UI:** Full web interface with templates
- **Database:** `instance/LTV Stocks.db` (unified)
- **Routes:** 91 endpoints across 32 blueprints
- **Authentication:** Flask-Login with user levels (1-5)
- **Test Coverage:** pytest suite in tests/

### localhost/ (Legacy Application)

- **Entry Point:** `localhost/flask_app.py`
- **Port:** 9000 (127.0.0.1)
- **Architecture:** Flask with routes + standalone scripts
- **UI:** Minimal web interface + CLI scripts
- **Database:** Now uses `instance/LTV Stocks.db` (consolidated 2026-06-05, previously `ltv_database/`)
- **Routes:** 14 endpoints + standalone scripts
- **Files:** 103 Python files, 28 modules
- **Unique Feature:** Opens Excel files automatically via `os.startfile()`

---

## Feature Comparison Matrix

### Core Transaction Management

| Feature | ltv_app | localhost/ | Status |
|---------|---------|------------|--------|
| **Buy/Sell Transactions** | ✅ transactions/ | ✅ my_routes/spot_trade.py | Both |
| **Transaction List** | ✅ transaction_list/ | ✅ my_routes/transaction_list.py | Both |
| **Cash Transfer** | ✅ cash_transfer/ | ✅ blueprints/transfer/ | Both |
| **Dividends** | ✅ dividends/ | ❌ | ltv_app only |
| **Charges** | ✅ charges/ | ❌ | ltv_app only |
| **Transaction Review** | ✅ review/ (9 routes) | ❌ | ltv_app only |

---

### Contract Management

| Feature | ltv_app | localhost/ | Status |
|---------|---------|------------|--------|
| **Stock Contracts (ACCU/DECU)** | ✅ term_sheet/ (8 routes) | ✅ my_routes/stock_contract.py | Both |
| **Commodity Contracts** | ❌ | ✅ my_routes/commodity_contract.py (16KB) | **localhost/ only** |
| **Fixings** | ✅ fixings/ (5 routes) | ✅ my_routes/fixings.py + modules/fixings.py (43KB) | Both (different impl) |
| **Term Sheet Import** | ❌ | ✅ modules/import_term_sheet.py (15KB) | **localhost/ only** |
| **Update Term Sheet** | ❌ | ✅ modules/update_term_sheet.py (7.5KB) | **localhost/ only** |

**Note:** Commodity contracts are a significant feature (16KB) that does NOT exist in ltv_app.

---

### Reports & Excel Generation

| Report | ltv_app | localhost/ | Comparison |
|--------|---------|------------|------------|
| **LTV Stocks** | ✅ ltv_stocks/ (2 routes) | ✅ modules/ltv_stocks2.py (37KB) | **localhost/ has more features** |
| **Trades Done** | ❌ | ✅ modules/trades_done.py (38KB) | **localhost/ only** |
| **Notebook** | ✅ notebook/ (2 routes) | ✅ modules/notebook.py (26KB) | Both (different impl) |
| **Gain/Loss** | ✅ gain_loss/ (1 route) | ✅ my_routes/gain_loss.py (26KB) | Both (different impl) |
| **Stock Position** | ✅ stock_position/ (2 routes) | ✅ modules/stock_balance.py (5.1KB) | Both (different impl) |
| **Forecast** | ✅ forecasts/ (2 routes) | ✅ libraries/Forecast/ (5 files) | Both (different impl) |
| **Transaction List** | ✅ transaction_list/ (1 route) | ✅ modules/transaction_list.py (11KB) | Both (different impl) |
| **Unconfirmed Transactions** | ❌ | ✅ get_unconfirmed.py | **localhost/ only** |

**Key Difference:** localhost/ modules contain legacy report formats that may have features not yet ported to ltv_app.

---

### Stock Price Management

| Feature | ltv_app | localhost/ | Status |
|---------|---------|------------|--------|
| **Stock Price Upload** | ✅ stock_price/ (CSV upload) | ✅ my_routes/stock_price.py | Both |
| **Stock Price View** | ✅ Last 10 trading days grid | ❌ | ltv_app only |
| **Stock Price Module** | ❌ | ✅ modules/stock_price.py (1.9KB) | localhost/ only |

---

### Portfolio Analysis

| Feature | ltv_app | localhost/ | Status |
|---------|---------|------------|--------|
| **Portfolio View** | ✅ portfolio/ (1 route) | ❌ | ltv_app only |
| **HKD Margin** | ✅ hkd_margin/ (1 route) | ✅ my_routes/margin.py (25KB) | Both (different impl) |
| **Shares Margin** | ❌ | ✅ libraries/Shares_Margin/ | **localhost/ only** |
| **Long/Short Analysis** | ❌ | ✅ modules/long_short.py (3.8KB) | **localhost/ only** |
| **Cash Margin** | ❌ | ✅ modules/cash_margin.py (15KB) | **localhost/ only** |

---

### Master Data Management

| Feature | ltv_app | localhost/ | Status |
|---------|---------|------------|--------|
| **Stock Codes** | ✅ stocks/ (4 routes) | ✅ modules/stocks.py (4.4KB) | Both |
| **Bank Accounts** | ✅ bank_accounts/ (3 routes) | ✅ modules/bank_account.py (4.9KB) | Both |
| **Banks** | ✅ bank/ (4 routes) | ❌ | ltv_app only |
| **Currencies** | ✅ currency/ (blueprint) | ✅ modules/currency.py (842 bytes) | Both |
| **Holidays** | ✅ holiday/ (2 routes) | ✅ blueprints/holiday/ | Both |
| **Users** | ✅ users/ (5 routes) | ❌ | ltv_app only |

---

### Authentication & Security

| Feature | ltv_app | localhost/ | Status |
|---------|---------|------------|--------|
| **Login/Logout** | ✅ auth/ (Flask-Login) | ✅ my_routes/login.py | Both |
| **User Levels** | ✅ 5 levels (admin to viewer) | ❌ | ltv_app only |
| **Superuser Role** | ✅ @superuser_required | ❌ | ltv_app only |
| **Block/Unblock Users** | ✅ block_unblock/ | ✅ block_unblocked.py | Both |
| **Session Management** | ✅ Flask-Login | ✅ Flask session | Both |

---

### Special Features

| Feature | ltv_app | localhost/ | Description |
|---------|---------|------------|-------------|
| **Pricing** | ✅ pricing/ (2 routes) | ✅ libraries/Pricing/ | Both (derivative pricing) |
| **Marissa Orders** | ❌ | ✅ libraries/Marissa_Orders/ | **localhost/ only** - Special order system |
| **Email Integration** | ❌ | ✅ my_routes/send_email.py (3.0KB) | **localhost/ only** |
| **Transitory Data** | ✅ transitory/ (2 routes) | ✅ my_routes/transitory.py | Both (temporary data storage) |
| **Lock/Unlock** | ✅ lock/ (3 routes) | ❌ | ltv_app only |
| **File Download** | ✅ upload/ (3 routes) | ✅ my_routes/download.py | Both |

---

## Detailed Module Analysis

### localhost/ Unique Modules (Not in ltv_app)

#### 1. **Commodity Contracts** (my_routes/commodity_contract.py - 16KB)
- Handles derivative contracts for commodities (not stocks)
- Transaction types: ACCU, DECU for commodity markets
- CCY type: "COM" (Commodity currency)
- **Impact:** Users trading commodities cannot use ltv_app

#### 2. **Trades Done Report** (modules/trades_done.py - 38KB)
- Comprehensive transaction report with averages
- Groups by CCY (HKD, JPY, AUD, USD, SGD, COM)
- Includes commodity contracts
- Uses Excel template: `excel_templates/Trades Done.xlsx`
- **Impact:** Specific report format users may rely on

#### 3. **Marissa Orders System** (libraries/Marissa_Orders/)
- Special order processing system
- Has its own views and methods
- Purpose unclear from file names alone
- **Impact:** Unknown - requires user confirmation

#### 4. **Shares Margin Library** (libraries/Shares_Margin/)
- Advanced margin calculations
- Separate from HKD margin in ltv_app
- **Impact:** May have different calculation logic

#### 5. **Email Integration** (my_routes/send_email.py - 3.0KB)
- Send reports via email
- **Impact:** ltv_app has no email functionality

#### 6. **Long/Short Analysis** (modules/long_short.py - 3.8KB)
- Position analysis by direction
- **Impact:** Not available in ltv_app

#### 7. **Cash Margin Analysis** (modules/cash_margin.py - 15KB)
- Detailed cash margin calculations
- **Impact:** Different from HKD margin in ltv_app

#### 8. **Term Sheet Import** (modules/import_term_sheet.py - 15KB)
- Bulk import term sheets
- **Impact:** ltv_app requires manual entry

#### 9. **Update Term Sheet** (modules/update_term_sheet.py - 7.5KB)
- Bulk update existing term sheets
- **Impact:** ltv_app requires manual updates

#### 10. **Unconfirmed Transactions Report** (get_unconfirmed.py)
- Report of transactions pending confirmation
- **Impact:** Not available in ltv_app

---

## Implementation Differences

### LTV Stocks Report

**localhost/ (modules/ltv_stocks2.py - 965 lines):**
- ✅ Active contract count formula
- ✅ Bank Reference column
- ✅ Legacy date range (10 dates: prev week Mon-Fri + current week)
- ✅ Stock-specific colors
- ✅ Indicator columns (D/./KO/Done) - Complex 300+ char formulas
- ✅ HKD cross-account aggregation
- ✅ Grey fills for holidays
- ✅ "Done" indicator in price grid
- ✅ Recent transactions section

**ltv_app (ltv_app/blueprints/ltv_stocks/):**
- ✅ Active contract count formula (Phase 1 - added 2026-06-05)
- ✅ Bank Reference column (Phase 1 - added 2026-06-05)
- ✅ Legacy date range (Phase 1 - added 2026-06-05)
- ✅ Stock-specific colors (Phase 1 - added 2026-06-05)
- ❌ Indicator columns (Phase 2 - pending)
- ❌ HKD aggregation (Phase 2 - pending)
- ❌ Holiday fills (Phase 2 - pending)
- ❌ "Done" markers (Phase 2 - pending)
- ❌ Recent transactions (Phase 2 - pending)

**Status:** Phase 1 complete (4 features), Phase 2 pending (5 features)

---

### Fixings Report

**localhost/ (modules/fixings.py - 43KB):**
- Complex calculation logic
- Multiple helper functions
- Legacy format

**ltv_app (ltv_app/blueprints/fixings/):**
- Modern implementation using Excel templates
- Uses `instance/excel_templates/fixings.xlsx`
- Evaluated implementation: see [docs/fixings_implementation_evaluation.md](fixings_implementation_evaluation.md)

**Status:** Both functional, different implementations

---

### Notebook Report

**localhost/ (modules/notebook.py - 26KB):**
- Uses `excel_templates/Notebook.xlsx`
- Complex multi-section layout
- Stock balance integration

**ltv_app (ltv_app/blueprints/notebook/):**
- Modern implementation
- Uses `instance/excel_templates/notebook.xlsx`
- Simpler structure

**Status:** Both functional, different implementations

---

## Database Usage Analysis

### Tables Used by localhost/ Only

After analyzing localhost/ code, these tables/features may have unique usage:

1. **tbl_commodity_contract** - Commodity derivatives (not in ltv_app UI)
2. **Specific column usage** - Some columns may only be populated by localhost/ scripts

### Scripts That Modify Database

**localhost/ scripts that write to database:**
- `modules/fixings.py` - Updates tbl_stock_contract_period
- `modules/import_term_sheet.py` - Inserts into tbl_stock_contract
- `modules/update_term_sheet.py` - Updates tbl_stock_contract
- `my_routes/stock_contract.py` - CRUD for contracts
- `my_routes/commodity_contract.py` - CRUD for commodity contracts
- `my_routes/spot_trade.py` - Transaction CRUD

**Impact:** Database schema changes must not break these scripts.

---

## User Workflow Differences

### ltv_app Workflow (Web-Based)
1. User logs into web interface (http://192.168.1.48:5000)
2. Navigates through menus and forms
3. Downloads reports via browser
4. All actions logged and authenticated

### localhost/ Workflow (Hybrid)
1. May start Flask app on port 9000
2. OR run standalone scripts (e.g., `python create_LTV_Stocks.py`)
3. Scripts auto-open Excel files via `os.startfile()`
4. Files saved to `localhost/temp/` directory
5. CLI-based execution for some operations

**Key Difference:** localhost/ scripts are designed for automation and CLI usage, while ltv_app is purely web-based.

---

## File Organization

### Excel Templates

**ltv_app:**
- `instance/excel_templates/*.xlsx` (tracked in git)
- 6 templates: fixings, trades_done, trades_done_with_gain_loss, gain_loss, notebook, transaction_forecast

**localhost/:**
- `localhost/excel_templates/*.xlsx` (not tracked)
- May have additional or different templates

### Output Directories

**ltv_app:**
- `instance/temp/` - Temporary Excel files before download
- `ltv_database/Reports/` - Persistent report storage
- `ltv_database/transitory/` - Temporary processing files

**localhost/:**
- `localhost/temp/` - Generated Excel files
- `localhost/excel_files/` - Excel file storage
- `localhost/working_files/` - Work in progress files
- `localhost/transitory/` - Temporary data
- `localhost/TERM_SHEET/` - Term sheet specific files

---

## Testing & Quality

### ltv_app
- ✅ pytest test suite in tests/
- ✅ Functional tests for auth, transactions
- ✅ Test database fixtures
- ✅ pytest.ini configuration
- ✅ Test markers for different scenarios

### localhost/
- ❌ No automated tests found
- ❌ No test suite
- ⚠️ Quality assurance relies on manual testing

**Risk:** Changes to database or business logic harder to verify in localhost/.

---

## Maintenance & Development

### ltv_app
- **Active Development:** ✅ Yes (recent commits daily)
- **Documentation:** ✅ CLAUDE.md, docstrings
- **Git Tracking:** ✅ Full source code tracked
- **Version Control:** ✅ VERSION file (displayed in navbar)
- **Architecture:** ✅ Modern blueprint pattern
- **Code Quality:** ✅ Structured, organized

### localhost/
- **Active Development:** ⚠️ Unclear (most files 2021-2022)
- **Documentation:** ❌ Minimal
- **Git Tracking:** ❌ Not tracked (reference only)
- **Version Control:** ❌ None
- **Architecture:** ⚠️ Mixed patterns (Flask + standalone scripts)
- **Code Quality:** ⚠️ Legacy code, some duplication

---

## Migration Risk Assessment

### High Risk Features (localhost/ only)

1. **Commodity Contracts** - 16KB module, no ltv_app equivalent
2. **Marissa Orders** - Unknown impact, no ltv_app equivalent
3. **Email Integration** - No ltv_app equivalent
4. **Term Sheet Import/Update** - Bulk operations not in ltv_app
5. **Trades Done Report** - Specific format (38KB), users may rely on exact output

### Medium Risk Features (Different Implementations)

1. **LTV Stocks Report** - Phase 2 features still pending
2. **Fixings** - Different logic, need to verify calculations match
3. **Notebook** - Different format
4. **Gain/Loss** - Different calculation approach
5. **Forecast** - Different implementation
6. **HKD Margin vs Shares Margin** - May have calculation differences

### Low Risk Features (Well Covered in ltv_app)

1. **Transactions** - ltv_app has comprehensive UI
2. **Authentication** - ltv_app has superior implementation
3. **User Management** - ltv_app only
4. **Stock Price Upload** - ltv_app has modern UI
5. **Master Data** - ltv_app covers all needs

---

## Recommendations

### Immediate Actions

1. ✅ **Database consolidation complete** (2026-06-05)
2. ⚠️ **Document localhost/ usage** - Ask users:
   - Which localhost/ features are still actively used?
   - Are commodity contracts in use?
   - Is Marissa Orders system still needed?
   - Which reports are critical?

### Before Schema Changes

1. ✅ **Search localhost/ for table/column references**
2. ✅ **Test with both applications**
3. ✅ **Verify reports still generate**
4. ⚠️ **Consider deprecation timeline for localhost/**

### Migration Path Options

#### Option A: Gradual Deprecation (Recommended)
1. Keep both applications running
2. Port localhost/ features to ltv_app one-by-one
3. User acceptance testing for each feature
4. Deprecate localhost/ only when ALL features ported

#### Option B: Feature Freeze
1. Declare localhost/ feature-complete
2. Maintain for read-only operations
3. All new development in ltv_app only
4. Run both indefinitely

#### Option C: Hard Cutover (High Risk)
1. Identify critical localhost/ features
2. Port all at once
3. Switch all users to ltv_app
4. Archive localhost/
⚠️ **Not recommended** - too many unknowns

---

## Critical Questions for User

Before making any database schema changes, ask user:

1. **Which localhost/ features are actively used?**
   - Commodity contracts?
   - Marissa Orders?
   - Email integration?
   - Specific report formats?

2. **Are there users who ONLY use localhost/ (not ltv_app)?**

3. **What is the business timeline for deprecating localhost/?**

4. **Are there localhost/ reports that must maintain exact formatting?**

5. **Is there documentation on what Marissa Orders does?**

---

## Summary Statistics

| Metric | ltv_app | localhost/ |
|--------|---------|------------|
| **Python Files** | ~150+ (32 blueprints) | 103 files |
| **Routes/Endpoints** | 91 | 14 |
| **Lines of Code** | ~50,000+ (estimated) | ~30,000+ (estimated) |
| **Blueprints/Modules** | 32 blueprints | 28 modules + 3 libraries |
| **Test Coverage** | pytest suite | None |
| **Documentation** | CLAUDE.md + inline | Minimal |
| **Git Tracked** | Yes (all source) | No (reference only) |
| **Active Development** | Yes (daily commits) | No (2021-2022 files) |
| **Database** | instance/LTV Stocks.db | instance/LTV Stocks.db (consolidated) |
| **Port** | 5000 | 9000 |
| **UI** | Full web interface | Minimal web + CLI |

---

## Conclusion

**Key Findings:**

1. ✅ **ltv_app has broader feature coverage** with modern architecture
2. ⚠️ **localhost/ has 10+ unique features** not in ltv_app
3. ⚠️ **Commodity contracts** are a major feature gap
4. ⚠️ **Report formatting differences** may affect users
5. ✅ **Database consolidation complete** - single source of truth
6. ⚠️ **Unknown usage patterns** - need user input

**Recommendation:**
Before any database schema changes, **analyze localhost/ code first and consult with users** about active usage of legacy features. Some features may be critical to operations and not yet available in ltv_app.

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Project instructions with database warnings
- [database_divergence_analysis.md](database_divergence_analysis.md) - Database consolidation details
- [database_consolidation_complete.md](database_consolidation_complete.md) - Consolidation summary
- [ltv_stocks_phase1_complete.md](ltv_stocks_phase1_complete.md) - LTV Stocks Phase 1 features
- [fixings_implementation_evaluation.md](fixings_implementation_evaluation.md) - Fixings evaluation

---

**Document Status:** Complete
**Last Updated:** 2026-06-05
**Next Action:** User consultation on localhost/ usage patterns
