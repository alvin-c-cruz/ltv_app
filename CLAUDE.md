# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is a Flask-based stock portfolio management application for tracking Long-Term Value (LTV) investments. It manages stock transactions (spot and derivative contracts), calculates P&L, tracks positions across multiple bank accounts, and generates financial reports.

**Tech Stack:** Python 3, Flask, SQLite, Jinja2, Pandas, OpenPyXL

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
python flask_app.py  # Starts development server on auto-detected host:5001
```

**Important:** Always launch via `! python flask_app.py` in the Claude Code prompt (not as a hidden background process) so output is visible in the conversation.

### Spec Enhancer (auto-invoked after brainstorming)

After brainstorming writes and self-reviews a spec, always invoke `spec-enhancer` on the spec file before asking the user to review it. This runs four automated improvement passes (vagueness resolution, edge cases + permission checks, codebase grounding, convention compliance).

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
    ├─ Registers all blueprints (auto-discovered via bp attribute)
    ├─ Configures SQLite database connection
    ├─ Sets up Flask-Login authentication
    └─ Loads VERSION file → app_version Jinja2 global
```

**Blueprint auto-discovery:** `create_app()` iterates `dir(blueprints)`, finds submodules that expose a `bp` attribute, and registers them automatically. When adding a new blueprint, ensure `views.py` defines `bp = Blueprint(...)` at module level and the package `__init__.py` imports it.

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

**Location:** `instance/LTV Stocks.db` (SQLite) - **UNIFIED DATABASE** (consolidated 2026-06-05)

**⚠️ THIS IS A LIVE DATABASE WITH REAL PRODUCTION DATA. Destructive changes (DROP, ALTER, DELETE without WHERE, data migrations) can cause permanent data loss. Always get explicit user approval before any schema or data changes.**

**CRITICAL:** Both ltv_app and localhost/ now use the same database (`instance/LTV Stocks.db`). Before making ANY database structure changes:
1. ✅ **Analyze localhost/ first** - Some features exist only in legacy code
2. ✅ Check if schema changes affect existing localhost/ scripts
3. ✅ Test changes with both ltv_app AND localhost/ applications
4. ✅ See [docs/database_divergence_analysis.md](docs/database_divergence_analysis.md) for consolidation history

**Core tables:**
- `tbl_user` - User accounts (username, email, password, level, role)
- `tbl_currency` - Currency definitions
- `tbl_bank_account` - Bank accounts with transaction basis
- `tbl_code` - Stock codes (company_name, stock_name, currency)
- `tbl_transaction` - Spot transactions (trade_date, bank_ref, code_ref, quantity, price, charges)
- `tbl_transaction_short` - Short sell transactions (separate table from spot)
- `tbl_stock_contract` - Derivative contracts (daily_shares, leveraged, spot, strike_rate, ko_rate)
- `tbl_stock_contract_period` - Contract period records
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

**ltv_app (modern):**
```python
from ltv_app.blueprints.database.views import get_db

def my_view():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT ...")
    results = cursor.fetchall()
```

**localhost/ (legacy):**
```python
from database import database

db = database()
db.Open
results = db.Execute("SELECT ...")
db.Close
```

**Important:**
- Always use `get_db()` in ltv_app, not direct sqlite3.connect()
- Both connection patterns now access the same unified database (`instance/LTV Stocks.db`)

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

The `localhost/` directory contains legacy modules **still in use** with features not yet ported to ltv_app:
- `localhost/modules/` - Business logic (fixings, term_sheet calculations, stock_balance, ltv_stocks2.py)
- `localhost/DB/db.py` - Database helpers
- `localhost/database.py` - Database connection class (now uses `instance/LTV Stocks.db`)

**IMPORTANT:** When working with older features:
1. Reference localhost/ to understand existing behavior
2. Check if feature exists only in localhost/ before modifying database schema
3. Some reports and calculations only exist in legacy code (e.g., ltv_stocks2.py has features not yet in ltv_app)
4. Legacy scripts still actively used - test changes with both applications

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

There are two conftest files with different fixture names:

**`tests/functional/conftest.py`** (use for new tests):
- `client` - Unauthenticated client against isolated temp SQLite database
- `auth_client` - Logged in as `staff_user`/`staffpass` (level 1, staff role)
- `superuser_client` - Logged in as `super_user`/`superpass` (level 1, superuser role)
- `db_conn` - Direct database connection for assertions
- Seed data: 1 currency (HKD), 2 banks, 1 stock code (700), 7 transaction types

**`conftest.py`** (root, legacy fixtures):
- `test_client` - Unauthenticated
- `test_client_logged_in` - Logged in as `admin`/`ac1123581321` against live database

When writing tests:
```python
def test_something(auth_client, db_conn):
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

- **Database file path:** `instance/LTV Stocks.db` - **UNIFIED DATABASE** used by both ltv_app and localhost/ (consolidated 2026-06-05)
  - ⚠️ **Before ANY database schema changes:** Analyze localhost/ first - some features exist only in legacy code
  - Old path `ltv_database/LTV Stocks.db` is deprecated (backup preserved)
  - See [docs/database_divergence_analysis.md](docs/database_divergence_analysis.md) for details
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

**CRITICAL:** Always update VERSION file before pushing to GitHub. Use `push.sh` to auto-increment the patch version:

```bash
# Auto-increment patch version (e.g. 4.0.8 → 4.0.9) and print the new version
bash push.sh

# Then commit the bump
git add VERSION
git commit -m "Bump version to $(cat VERSION)"
git push origin main
```

Or manually edit VERSION if bumping major/minor. The VERSION content is displayed in the application navbar (top-left) as "LTV vX.Y.Z".

See [docs/git_repository_structure.md](docs/git_repository_structure.md) for detailed repository structure and commit workflow.

## Business Logic Extensions

Complex calculations are isolated in extensions:
- `ltv_app/blueprints/transactions/extensions/TransactionSummary` - Transaction aggregations
- `ltv_app/extensions/Forecast/` - Portfolio forecasting and margin calculations (top-level extensions, not inside a blueprint)
- `localhost/modules/fixings.py` - FX rate fixing calculations
- `localhost/modules/term_sheet.py` - Derivative contract pricing

When adding new financial calculations, follow this pattern of creating extension classes separate from view logic.
