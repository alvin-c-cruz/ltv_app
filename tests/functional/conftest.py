"""
Shared fixtures for functional integration tests.

Uses an isolated temporary SQLite database per test function so tests never
touch the production database and don't interfere with each other.
"""
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from ltv_app import create_app

# ---------------------------------------------------------------------------
# Minimal schema — only tables required by the transactions blueprint and the
# before_app_request hook in database/views.py
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS tbl_user (
    id              INTEGER PRIMARY KEY,
    username        VARCHAR(255),
    email           VARCHAR(255),
    password        VARCHAR(255),
    level           INTEGER,
    role            TEXT DEFAULT 'staff'
);

CREATE TABLE IF NOT EXISTS tbl_currency (
    ref_num  INTEGER PRIMARY KEY,
    ccy_id   TEXT,
    ccy_name TEXT,
    priority INTEGER
);

CREATE TABLE IF NOT EXISTS tbl_bank_account (
    ref_num          INTEGER PRIMARY KEY,
    bank_id          TEXT,
    bank_name        TEXT,
    indicative       TEXT,
    priority         INTEGER,
    transaction_basis TEXT,
    report_label     TEXT,
    is_active        INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tbl_code (
    ref_num       INTEGER PRIMARY KEY,
    code          TEXT,
    company_name  TEXT,
    stock_name    TEXT,
    yahoo_ticker  TEXT,
    security_code TEXT,
    ccy_ref       INTEGER
);

CREATE TABLE IF NOT EXISTS tbl_transaction_type (
    ref_num          INTEGER PRIMARY KEY,
    transaction_type TEXT,
    priority         INTEGER
);

CREATE TABLE IF NOT EXISTS tbl_transaction (
    ref_num          INTEGER PRIMARY KEY,
    trade_date       timestamp,
    fixing_date      timestamp,
    value_date       timestamp,
    bank_ref         INTEGER,
    code_ref         INTEGER,
    transaction_type TEXT,
    quantity         INTEGER,
    price            REAL,
    brokerage        REAL DEFAULT 0,
    commission       REAL DEFAULT 0,
    foreign_charge   REAL DEFAULT 0,
    stamp_duty       REAL DEFAULT 0,
    misc             REAL DEFAULT 0,
    comments         TEXT,
    gain_loss        REAL,
    balance          REAL,
    average          REAL,
    spot             REAL,
    ko               REAL,
    contract_ref     INTEGER,
    periods          TEXT,
    counter_bank_ref INTEGER,
    class            TEXT,
    reviewed         INTEGER DEFAULT 0,
    locked           INTEGER DEFAULT 0,
    no_charges       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tbl_transaction_short (
    ref_num          INTEGER PRIMARY KEY,
    trade_date       timestamp,
    value_date       timestamp,
    bank_ref         INTEGER,
    code_ref         INTEGER,
    transaction_type TEXT,
    quantity         INTEGER,
    price            REAL,
    brokerage        REAL DEFAULT 0,
    commission       REAL DEFAULT 0,
    foreign_charge   REAL DEFAULT 0,
    stamp_duty       REAL DEFAULT 0,
    misc             REAL DEFAULT 0,
    locked           INTEGER DEFAULT 0,
    no_charges       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tbl_stock_contract (
    ref_num          INTEGER PRIMARY KEY,
    reference        TEXT,
    bank_ref         INTEGER,
    code_ref         INTEGER,
    trade_date       timestamp,
    start_date       timestamp,
    transaction_type TEXT,
    daily_shares     INTEGER,
    leveraged        TEXT,
    spot             REAL,
    strike_rate      REAL,
    ko_rate          REAL,
    tenor            TEXT,
    frequency        TEXT,
    gtd              TEXT,
    bank_doc         TEXT,
    status           TEXT,
    reviewed         INTEGER DEFAULT 0,
    locked           INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tbl_stock_contract_period (
    ref_num      INTEGER PRIMARY KEY,
    contract_ref INTEGER,
    start_date   TEXT,
    end_date     TEXT,
    days         TEXT,
    received     TEXT,
    gtd          TEXT
);

CREATE TABLE IF NOT EXISTS tbl_holiday (
    ref_num   INTEGER PRIMARY KEY,
    holi_date TEXT,
    ccy_ref   INTEGER
);

CREATE TABLE IF NOT EXISTS tbl_stock_price (
    ref_num       INTEGER PRIMARY KEY,
    code_ref      INTEGER,
    trade_date    TEXT,
    closing_price REAL
);
"""


def _seed(conn):
    """Insert the minimum reference rows every test needs."""
    conn.execute("INSERT INTO tbl_currency VALUES (1,'HKD','Hong Kong Dollar',1)")
    conn.execute(
        "INSERT INTO tbl_bank_account "
        "VALUES (1,'CB1','Citibank No. 1',NULL,1,'value_date',NULL,1)"
    )
    conn.execute(
        "INSERT INTO tbl_bank_account "
        "VALUES (2,'CB2','Citibank No. 2',NULL,2,'value_date',NULL,1)"
    )
    conn.execute(
        "INSERT INTO tbl_code "
        "VALUES (1,'700',NULL,'Tencent Holdings Limited',NULL,NULL,1)"
    )
    conn.executemany(
        "INSERT INTO tbl_transaction_type VALUES (?,?,?)",
        [
            (1, 'Buy (Spot)', 1),
            (2, 'Sell (Spot)', 2),
            (3, 'Sell (Short)', 3),
            (4, 'Buy (Pay Short)', 4),
            (5, 'Transfer-In', 5),
            (6, 'Transfer-Out', 6),
            (7, 'Stock Dividend', 7),
        ],
    )
    # Staff user
    conn.execute(
        "INSERT INTO tbl_user VALUES (1,'staff_user','staff@test.com',?,1,'staff')",
        (generate_password_hash('staffpass'),),
    )
    # Superuser
    conn.execute(
        "INSERT INTO tbl_user VALUES (2,'super_user','super@test.com',?,1,'superuser')",
        (generate_password_hash('superpass'),),
    )
    conn.commit()


@pytest.fixture()
def app(tmp_path):
    """Flask app wired to an isolated temporary test database."""
    db_path = tmp_path / 'test.db'
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA)
    _seed(conn)
    conn.close()

    flask_app = create_app({
        'DATABASE': str(db_path),
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'INSPECT_UPLOAD_DIR': str(tmp_path / 'inspect_uploads'),
    })
    return flask_app


@pytest.fixture()
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture()
def auth_client(app):
    """Test client logged in as a staff user."""
    with app.test_client() as tc:
        tc.post('/login', data={'username': 'staff_user', 'password': 'staffpass'})
        yield tc


@pytest.fixture()
def superuser_client(app):
    """Test client logged in as a superuser."""
    with app.test_client() as tc:
        tc.post('/login', data={'username': 'super_user', 'password': 'superpass'})
        yield tc


@pytest.fixture()
def db_conn(app):
    """Direct connection to the test database for assertions and manual setup."""
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
