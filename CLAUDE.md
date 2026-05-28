# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is a Flask-based stock portfolio management application for tracking Long-Term Value (LTV) investments. It manages stock transactions (spot and derivative contracts), calculates P&L, tracks positions across multiple bank accounts, and generates financial reports.

**Tech Stack:** Python 3, Flask 4.0.6, SQLite, Jinja2, Pandas, OpenPyXL

## Project Scope

**IMPORTANT:** Work is focused exclusively on the `ltv_app/` directory. Other directories are legacy/reference code only:
- **Active Development:** `ltv_app/` - Main Flask application with all blueprints
- **Reference Only:** `localhost/`, `pricing/`, `app.py` - Legacy code for reference, DO NOT modify
- **Tests:** `tests/` - Test suite for ltv_app
- **Entry Point:** `flask_app.py` - Uses ltv_app via `create_app()`

When adding features or fixing bugs, always work within `ltv_app/` structure. Only reference legacy code in `localhost/` when understanding existing behavior.

## Development Commands

### Running the Application
```bash
python flask_app.py  # Starts development server on auto-detected host:5000
```

### Testing
```bash
pytest                                    # Run all tests
pytest tests/functional/                  # Run functional tests only
pytest tests/functional/test_auth.py      # Run specific test file
pytest -k test_login                      # Run tests matching pattern
```

Test markers (from pytest.ini):
- `@pytest.mark.log_in` - Tests requiring authentication
- `@pytest.mark.log_out` - Tests for unauthenticated users
- `@pytest.mark.home_page` - Tests for home page
- `@pytest.mark.auth` - Tests for auth blueprint

## Architecture

### Application Structure

The app uses a **modular blueprint architecture** with 32+ blueprints, each handling a specific domain:

```
flask_app.py → create_app() (ltv_app/__init__.py)
    ├─ Registers all blueprints
    ├─ Configures SQLite database connection
    ├─ Sets up Flask-Login authentication
    └─ Loads VERSION file (4.0.6)
```

**Key blueprints:**
- `auth/` - User authentication (login/logout)
- `transactions/` - Spot buy/sell/transfer transactions
- `stock_price/` - Upload Yahoo Finance CSV, view historical prices
- `term_sheet/` - Derivative stock contracts (leveraged products)
- `stock_position/` - Balance and position reports
- `gain_loss/` - P&L calculations per stock
- `hkd_margin/` - HKD margin requirement analysis
- `bank/` - Bank account management
- `dividend/`, `fixings/`, `forecasts/`, `pricing/` - Supporting features

### Blueprint Pattern

Each blueprint typically contains:
```
blueprints/{name}/
├── views.py         # Flask routes (@bp.route)
├── models.py        # Database model classes (dataclass-based)
├── dataclass.py     # Domain objects
├── extensions/      # Complex business logic
└── pages/           # Jinja2 templates
```

### Database Architecture

**Location:** `ltv_database/LTV Stocks.db` (SQLite)

**Core tables:**
- `tbl_user` - User accounts (username, email, password, level, role)
- `tbl_currency` - Currency definitions
- `tbl_bank_account` - Bank accounts with transaction basis
- `tbl_code` - Stock codes (company_name, stock_name, currency)
- `tbl_transaction` - Spot transactions (trade_date, bank_ref, code_ref, quantity, price, charges)
- `tbl_stock_contract` - Derivative contracts (daily_shares, leveraged, spot, strike_rate, ko_rate)
- `tbl_stock_price` - Historical stock prices
- `tbl_transaction_type` - Reference table (Buy/Sell/Transfer/Dividend)
- `tbl_holiday` - Market holidays

**Model Pattern:**
All models inherit from `Model` base class (in `data_model/__init__.py`) which provides:
- `save()` - Insert/update records
- `get(ref_num)` - Retrieve by ID
- `all()` - Get all records
- `delete()` - Remove record

Models use Python `dataclass` with automatic field mapping to SQLite columns.

### Database Connection Pattern

```python
from ltv_app.blueprints.database.views import get_db

def my_view():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT ...")
    results = cursor.fetchall()
```

**Important:** Always use `get_db()` from the database blueprint, not direct sqlite3.connect().

### Authentication

**User Levels:**
- 1 = admin
- 2 = audit
- 3 = accountant
- 4 = bookkeeper
- 5 = viewer

**Decorators:**
- `@login_required` - Requires authenticated user
- `@superuser_required` - Requires superuser role

**Test Authentication:**
Test fixtures provide:
- `client` - Unauthenticated client
- `auth_client` - Regular authenticated user
- `superuser_client` - Superuser authenticated client

### Legacy Code Structure

The `localhost/` directory contains legacy modules still in use:
- `localhost/modules/` - Business logic (fixings, term_sheet calculations, stock_balance)
- `localhost/DB/db.py` - Database helpers

When working with older features, you may need to reference or refactor these modules.

## Common Development Patterns

### Adding a New Transaction Type

1. Check `tbl_transaction_type` reference table for existing types
2. Add route in appropriate blueprint (usually `transactions/`)
3. Use `Transaction` model from `transactions/models.py`
4. Handle gain_loss calculations if applicable
5. Update position reports if needed

### Working with Stock Prices

- Stock prices are uploaded via `stock_price/views.py:upload_stock_price()`
- Supports Yahoo Finance CSV format with multiple date formats
- Recent fixes handle string-type price columns and date parsing
- View prices at `stock_price/views.py:stock_price_view()`

### Generating Reports

Reports are typically:
1. Generated using Pandas dataframes
2. Exported to Excel via OpenPyXL
3. Saved to `ltv_database/Reports/`
4. Downloaded via `upload/views.py:download()`

Example: HKD Margin report (`hkd_margin/views.py`) generates Excel with position analysis.

### Testing with Database

Tests use isolated database created in `tests/functional/conftest.py`:
- `@pytest.fixture` `db_conn` provides pre-populated test database
- Schema includes all 13 tables with reference data
- Transaction data, stock codes, and bank accounts pre-seeded

When writing tests:
```python
def test_something(auth_client, db_conn):
    # auth_client = authenticated test client
    # db_conn = test database connection
    response = auth_client.get('/some-route')
    assert response.status_code == 200
```

## Configuration

**Test config:** `flask_test.cfg`
```
DEBUG = True
DEVELOPMENT = True
SECRET_KEY = 'do-i-really-need-this'
```

**Timezone utilities:** `ltv_app/tz.py` - Use `ph_now()` and `ph_today()` for Philippine timezone

**Jinja2 globals:**
- `ph_now()` - Current Philippine datetime
- `ph_today()` - Current Philippine date
- `app_version` - From VERSION file

## Recent Development Focus

Recent commits show active development on:
- Stock price viewing (last 10 trading days grid format)
- CSV upload date format handling
- Stock price data quality (string-to-float conversions)
- HKD margin calculation edge cases (stocks with fewer than 3 price records)

## Excel Template System

The application uses Excel templates for report generation, located in `instance/excel_templates/`:
- `fixings.xlsx` - FX rate fixing reports (ACCU/DECU contracts)
- `trades_done.xlsx` - Transaction reports
- `trades_done_with_gain_loss.xlsx` - Transaction reports with P&L
- `gain_loss.xlsx` - Gain/loss reports
- `notebook.xlsx` - Notebook/journal reports
- `transaction_forecast.xlsx` - Forecast reports

**Template Usage Pattern:**
```python
from flask import current_app
import os
from openpyxl import load_workbook

# Load template
template_file = os.path.join(current_app.instance_path, "excel_templates", "fixings.xlsx")
wb = load_workbook(template_file)

# Populate data using openpyxl
ws = wb['SheetName']
ws['A1'].value = some_value

# Save to temp directory
filename = os.path.join(current_app.instance_path, "temp", "output.xlsx")
wb.save(filename)
wb.close()
```

Templates are pre-formatted with:
- Sheet structures and formulas
- Cell styling (borders, fonts, fills, number formats)
- Multiple sheets for different accounts/currencies
- Dynamic sheet hiding based on data availability

See `ltv_app/blueprints/fixings/extensions/download_fixings.py` for a complete example.

## Important Notes

- **Database file path:** Code references `c:\envs\LTV\server\ltv_database\LTV Stocks.db`
- **Entry point:** Use `flask_app.py` (not `app.py`) for running the application
- **Version tracking:** Update `VERSION` file when releasing - **IMPORTANT: Update VERSION before pushing to GitHub (displayed in navbar)**
- **Reports directory:** `ltv_database/Reports/` stores generated Excel files
- **Transitory data:** `ltv_database/transitory/` used for temporary processing
- **Temp directory:** `instance/temp/` stores temporarily generated Excel files before download

## Git Repository

**Git Strategy:** Whitelist approach - tracks source code, templates, tests, and documentation

**Tracked:**
- `ltv_app/` - Main application source code
- `tests/` - Test suite
- `docs/` - Project documentation (evaluations, guides)
- `instance/excel_templates/` - Excel template files (required by app)
- `CLAUDE.md`, `conftest.py`, `pytest.ini`, `flask_test.cfg`
- `flask_app.py`, `VERSION`, `.gitignore`, `push.sh`

**Not Tracked:**
- `instance/temp/` - Generated Excel files
- `localhost/`, `pricing/` - Legacy reference code
- `ltv_database/` - Database files and reports
- `venv/` - Python virtual environment

### Version Management Workflow

**CRITICAL:** Always update VERSION file before pushing to GitHub:

```bash
# 1. Check current version
cat VERSION

# 2. Update to new version
echo "4.0.7" > VERSION

# 3. Commit version bump
git add VERSION
git commit -m "Bump version to 4.0.7"

# 4. Push to GitHub
git push origin main
```

**Why:** The VERSION file content is displayed in the application navbar (top-left). Users see "LTV v4.0.7" after the app restarts. This helps track deployed versions and identify which code version is running.

See [docs/git_repository_structure.md](docs/git_repository_structure.md) for detailed repository structure and commit workflow.

## Business Logic Extensions

Complex calculations are isolated in extensions:
- `transactions/extensions/TransactionSummary` - Transaction aggregations
- `extensions/Forecast/` - Portfolio forecasting and margin calculations
- `localhost/modules/fixings.py` - FX rate fixing calculations
- `localhost/modules/term_sheet.py` - Derivative contract pricing

When adding new financial calculations, follow this pattern of creating extension classes separate from view logic.
