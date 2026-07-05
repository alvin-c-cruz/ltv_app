"""
Integration tests — Trades Done > Transfer, Contract (ACCU/DECU), and Stock Dividends.

Transfer:  POST /trades/stock_transfer
Contract:  POST /term-sheet/add
Dividends: POST /trades/add_stock_dividends
"""
import pytest

TEST_DATE  = '2026-05-18'
VALUE_DATE = '2026-05-20'
BANK_REF   = 1
BANK_REF_2 = 2   # counter bank for transfers
CODE_REF   = 1

TRANSFER_URL = '/trades/stock_transfer'
CONTRACT_URL = '/term-sheet/add'
DIVIDEND_URL = '/trades/add_stock_dividends'

_TRANSFER_FORM = {
    'trade_date':       TEST_DATE,
    'value_date':       VALUE_DATE,
    'bank_ref':         BANK_REF,
    'code_ref':         CODE_REF,
    'transaction_type': 'Transfer-Out',
    'quantity':         -500,
    'price':            320.50,
    'counter_bank_ref': BANK_REF_2,
}

_DIVIDEND_FORM = {
    'trade_date':       TEST_DATE,
    'value_date':       TEST_DATE,   # dividends default to same date as trade_date
    'bank_ref':         BANK_REF,
    'code_ref':         CODE_REF,
    'transaction_type': 'Stock Dividend',
    'quantity':         100,
    'price':            0.0,
}

_CONTRACT_FORM = {
    'bank_ref':      BANK_REF,
    'code_ref':      CODE_REF,
    'transaction_type': 'ACCU',
    'trade_date':    '2026-05-01',
    'start_date':    '2026-05-04',
    'daily_shares':  100,
    'leveraged':     'Yes',
    'spot':          320.50,
    'strike_rate':   80.0,
    'ko_rate':       120.0,
    'tenor':         '1m',
    'frequency':     'monthly',
    'gtd':           'No',
    'bank_doc':      'DOC001',
    'status':        'active',
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _count_transactions(db_conn, trade_date=TEST_DATE):
    return db_conn.execute(
        "SELECT COUNT(*) FROM tbl_transaction WHERE trade_date=?", (trade_date,)
    ).fetchone()[0]


def _count_contracts(db_conn):
    return db_conn.execute("SELECT COUNT(*) FROM tbl_stock_contract").fetchone()[0]


def _count_periods(db_conn):
    return db_conn.execute("SELECT COUNT(*) FROM tbl_stock_contract_period").fetchone()[0]


# ===========================================================================
# 1. Transfer — /trades/stock_transfer
# ===========================================================================
class TransferTests:

    # ── Access control ──────────────────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get(TRANSFER_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    # ── Form renders ────────────────────────────────────────────────────────

    def test_form_loads(self, auth_client):
        response = auth_client.get(TRANSFER_URL)
        assert response.status_code == 200

    def test_form_shows_transfer_out_type(self, auth_client):
        response = auth_client.get(TRANSFER_URL)
        assert b'Transfer-Out' in response.data

    # ── Validation ──────────────────────────────────────────────────────────

    def test_positive_quantity_is_rejected(self, auth_client, db_conn):
        bad = {**_TRANSFER_FORM, 'quantity': 500}
        response = auth_client.post(TRANSFER_URL, data=bad, follow_redirects=True)
        assert b'negative quantity' in response.data
        assert _count_transactions(db_conn) == 0

    def test_rejected_form_creates_no_rows(self, auth_client, db_conn):
        auth_client.post(TRANSFER_URL, data={**_TRANSFER_FORM, 'quantity': 500})
        assert _count_transactions(db_conn) == 0

    # ── Successful transfer ─────────────────────────────────────────────────

    def test_valid_transfer_creates_two_rows(self, auth_client, db_conn):
        auth_client.post(TRANSFER_URL, data=_TRANSFER_FORM)
        assert _count_transactions(db_conn) == 2

    def test_transfer_out_row_has_correct_bank(self, auth_client, db_conn):
        auth_client.post(TRANSFER_URL, data=_TRANSFER_FORM)
        row = db_conn.execute(
            "SELECT * FROM tbl_transaction WHERE transaction_type='Transfer-Out'"
        ).fetchone()
        assert row['bank_ref'] == BANK_REF
        assert row['quantity'] == -500
        assert row['counter_bank_ref'] == BANK_REF_2

    def test_transfer_in_row_has_inverted_fields(self, auth_client, db_conn):
        auth_client.post(TRANSFER_URL, data=_TRANSFER_FORM)
        row = db_conn.execute(
            "SELECT * FROM tbl_transaction WHERE transaction_type='Transfer-In'"
        ).fetchone()
        assert row['bank_ref'] == BANK_REF_2
        assert row['quantity'] == 500       # quantity * -1
        assert row['counter_bank_ref'] == BANK_REF

    def test_success_redirects_to_trades_home(self, auth_client):
        response = auth_client.post(TRANSFER_URL, data=_TRANSFER_FORM)
        assert response.status_code == 302
        assert '/trades' in response.headers['Location']

    def test_success_redirects_to_correct_date(self, auth_client):
        response = auth_client.post(TRANSFER_URL, data=_TRANSFER_FORM)
        assert TEST_DATE in response.headers['Location']

    def test_success_shows_flash_message(self, auth_client):
        response = auth_client.post(TRANSFER_URL, data=_TRANSFER_FORM, follow_redirects=True)
        assert b'Transfer recorded' in response.data


# ===========================================================================
# 2. Stock Dividends — /trades/add_stock_dividends
# ===========================================================================
class DividendTests:

    # ── Access control ──────────────────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get(DIVIDEND_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    # ── Form renders ────────────────────────────────────────────────────────

    def test_form_loads(self, auth_client):
        response = auth_client.get(DIVIDEND_URL)
        assert response.status_code == 200

    def test_form_shows_stock_dividend_type(self, auth_client):
        response = auth_client.get(DIVIDEND_URL)
        assert b'Stock Dividend' in response.data

    # ── Validation ──────────────────────────────────────────────────────────

    def test_negative_quantity_is_rejected(self, auth_client, db_conn):
        bad = {**_DIVIDEND_FORM, 'quantity': -100}
        response = auth_client.post(DIVIDEND_URL, data=bad, follow_redirects=True)
        assert b'Buy transaction should have position quantity' in response.data
        assert _count_transactions(db_conn) == 0

    # ── Successful dividend ─────────────────────────────────────────────────

    def test_valid_dividend_creates_one_row(self, auth_client, db_conn):
        auth_client.post(DIVIDEND_URL, data=_DIVIDEND_FORM)
        assert _count_transactions(db_conn) == 1

    def test_dividend_row_has_correct_type(self, auth_client, db_conn):
        auth_client.post(DIVIDEND_URL, data=_DIVIDEND_FORM)
        row = db_conn.execute(
            "SELECT transaction_type FROM tbl_transaction WHERE trade_date=?", (TEST_DATE,)
        ).fetchone()
        assert row['transaction_type'] == 'Stock Dividend'

    def test_dividend_row_has_correct_quantity(self, auth_client, db_conn):
        auth_client.post(DIVIDEND_URL, data=_DIVIDEND_FORM)
        row = db_conn.execute(
            "SELECT quantity FROM tbl_transaction WHERE trade_date=?", (TEST_DATE,)
        ).fetchone()
        assert row['quantity'] == 100

    def test_success_redirects_to_trades_home(self, auth_client):
        response = auth_client.post(DIVIDEND_URL, data=_DIVIDEND_FORM)
        assert response.status_code == 302
        assert '/trades' in response.headers['Location']

    def test_success_redirects_to_correct_date(self, auth_client):
        response = auth_client.post(DIVIDEND_URL, data=_DIVIDEND_FORM)
        assert TEST_DATE in response.headers['Location']

    def test_success_shows_flash_message(self, auth_client):
        response = auth_client.post(DIVIDEND_URL, data=_DIVIDEND_FORM, follow_redirects=True)
        assert b'Stock dividend added' in response.data


# ===========================================================================
# 3. Contract (ACCU/DECU) — /term-sheet/add
# ===========================================================================
class ContractTests:

    # ── Access control ──────────────────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get(CONTRACT_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    # ── Form renders ────────────────────────────────────────────────────────

    def test_form_loads(self, auth_client):
        response = auth_client.get(CONTRACT_URL)
        assert response.status_code == 200

    # ── Successful contract creation ─────────────────────────────────────────

    def test_valid_accu_creates_contract_row(self, auth_client, db_conn):
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        assert _count_contracts(db_conn) == 1

    def test_contract_has_correct_type(self, auth_client, db_conn):
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        row = db_conn.execute("SELECT transaction_type FROM tbl_stock_contract").fetchone()
        assert row['transaction_type'] == 'ACCU'

    def test_contract_auto_generates_reference(self, auth_client, db_conn):
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        row = db_conn.execute("SELECT reference FROM tbl_stock_contract").fetchone()
        assert row['reference'] == 'Tencent Holdings Limited - 1'

    def test_second_contract_increments_reference(self, auth_client, db_conn):
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        rows = db_conn.execute(
            "SELECT reference FROM tbl_stock_contract ORDER BY ref_num"
        ).fetchall()
        assert rows[1]['reference'] == 'Tencent Holdings Limited - 2'

    def test_creates_period_schedules(self, auth_client, db_conn):
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        assert _count_periods(db_conn) >= 1

    def test_period_linked_to_contract(self, auth_client, db_conn):
        auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        contract = db_conn.execute("SELECT ref_num FROM tbl_stock_contract").fetchone()
        period = db_conn.execute(
            "SELECT contract_ref FROM tbl_stock_contract_period"
        ).fetchone()
        assert period['contract_ref'] == contract['ref_num']

    def test_success_redirects_to_trades_home(self, auth_client):
        response = auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        assert response.status_code == 302
        assert '/trades' in response.headers['Location']

    def test_success_redirects_to_correct_date(self, auth_client):
        response = auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM)
        assert _CONTRACT_FORM['trade_date'] in response.headers['Location']

    def test_success_shows_flash_message(self, auth_client):
        response = auth_client.post(CONTRACT_URL, data=_CONTRACT_FORM, follow_redirects=True)
        assert b'ACCU' in response.data
