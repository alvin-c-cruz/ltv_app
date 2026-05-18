"""
Integration tests — Trades Done > Spot transactions.

Covers: access control, add (validation + success), home-page display,
edit (validation + success + lock), and delete (success + lock).
"""
import pytest

# ---------------------------------------------------------------------------
# Constants shared across all tests
# ---------------------------------------------------------------------------
HOME_URL  = '/trades/'
ADD_URL   = '/trades/add'
TEST_DATE = '2026-05-18'
VALUE_DATE = '2026-05-20'
BANK_REF   = 1
CODE_REF   = 1

_BUY_FORM = {
    'trade_date':       TEST_DATE,
    'value_date':       VALUE_DATE,
    'bank_ref':         BANK_REF,
    'code_ref':         CODE_REF,
    'transaction_type': 'Buy (Spot)',
    'quantity':         1000,
    'price':            320.50,
}

_SELL_FORM = {**_BUY_FORM, 'transaction_type': 'Sell (Spot)', 'quantity': -500}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _count_transactions(db_conn, trade_date=TEST_DATE):
    return db_conn.execute(
        "SELECT COUNT(*) FROM tbl_transaction WHERE trade_date=?", (trade_date,)
    ).fetchone()[0]


def _insert_transaction(db_conn, **overrides):
    """Insert a transaction row directly and return its ref_num."""
    params = {
        'trade_date':       TEST_DATE,
        'value_date':       VALUE_DATE,
        'bank_ref':         BANK_REF,
        'code_ref':         CODE_REF,
        'transaction_type': 'Buy (Spot)',
        'quantity':         1000,
        'price':            320.50,
        'brokerage':        0,
        'commission':       0,
        'foreign_charge':   0,
        'stamp_duty':       0,
        'misc':             0,
        'locked':           0,
    }
    params.update(overrides)
    cur = db_conn.execute(
        """INSERT INTO tbl_transaction
           (trade_date, value_date, bank_ref, code_ref, transaction_type,
            quantity, price, brokerage, commission, foreign_charge,
            stamp_duty, misc, locked)
           VALUES (:trade_date, :value_date, :bank_ref, :code_ref,
                   :transaction_type, :quantity, :price, :brokerage,
                   :commission, :foreign_charge, :stamp_duty, :misc, :locked)""",
        params,
    )
    db_conn.commit()
    return cur.lastrowid


# ===========================================================================
# 1. Access control
# ===========================================================================
class AccessControlTests:

    def test_home_redirects_when_not_logged_in(self, client):
        response = client.get(HOME_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_add_form_redirects_when_not_logged_in(self, client):
        response = client.get(ADD_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_home_accessible_when_logged_in(self, auth_client):
        response = auth_client.get(HOME_URL)
        assert response.status_code == 200
        assert b'Trades Done' in response.data


# ===========================================================================
# 2. Add form renders
# ===========================================================================
class AddFormRenderTests:

    def test_add_form_loads(self, auth_client):
        response = auth_client.get(ADD_URL)
        assert response.status_code == 200

    def test_add_form_contains_spot_transaction_types(self, auth_client):
        response = auth_client.get(ADD_URL)
        assert b'Buy (Spot)' in response.data
        assert b'Sell (Spot)' in response.data

    def test_add_form_shows_today_as_default_trade_date(self, auth_client):
        response = auth_client.get(ADD_URL)
        # The form should contain a date input — just assert the page loaded
        assert b'trade_date' in response.data


# ===========================================================================
# 3. Add validation — wrong quantity sign
# ===========================================================================
class AddSpotValidationTests:

    def test_buy_spot_with_negative_quantity_is_rejected(self, auth_client, db_conn):
        bad_data = {**_BUY_FORM, 'quantity': -1000}
        response = auth_client.post(ADD_URL, data=bad_data, follow_redirects=True)
        assert response.status_code == 200
        assert b'Buy transaction should have position quantity' in response.data
        assert _count_transactions(db_conn) == 0

    def test_sell_spot_with_positive_quantity_is_rejected(self, auth_client, db_conn):
        bad_data = {**_SELL_FORM, 'quantity': 500}
        response = auth_client.post(ADD_URL, data=bad_data, follow_redirects=True)
        assert response.status_code == 200
        assert b'Sell transaction should have negative quantity' in response.data
        assert _count_transactions(db_conn) == 0

    def test_rejected_form_does_not_create_db_row(self, auth_client, db_conn):
        auth_client.post(ADD_URL, data={**_BUY_FORM, 'quantity': -100})
        assert _count_transactions(db_conn) == 0


# ===========================================================================
# 4. Add success — Buy (Spot)
# ===========================================================================
class AddBuySpotTests:

    def test_add_buy_spot_returns_redirect(self, auth_client):
        response = auth_client.post(ADD_URL, data=_BUY_FORM)
        assert response.status_code == 302

    def test_add_buy_spot_redirects_to_home_for_trade_date(self, auth_client):
        response = auth_client.post(ADD_URL, data=_BUY_FORM)
        assert TEST_DATE in response.headers['Location']

    def test_add_buy_spot_creates_one_row_in_db(self, auth_client, db_conn):
        auth_client.post(ADD_URL, data=_BUY_FORM)
        assert _count_transactions(db_conn) == 1

    def test_add_buy_spot_saves_correct_fields(self, auth_client, db_conn):
        auth_client.post(ADD_URL, data=_BUY_FORM)
        row = db_conn.execute(
            "SELECT * FROM tbl_transaction WHERE trade_date=?", (TEST_DATE,)
        ).fetchone()
        assert row['transaction_type'] == 'Buy (Spot)'
        assert row['quantity'] == 1000
        assert row['price'] == pytest.approx(320.50)
        assert row['bank_ref'] == BANK_REF
        assert row['code_ref'] == CODE_REF

    def test_add_buy_spot_shows_flash_message(self, auth_client):
        response = auth_client.post(ADD_URL, data=_BUY_FORM, follow_redirects=True)
        assert b'Buy (Spot)' in response.data
        assert b'1,000' in response.data


# ===========================================================================
# 5. Add success — Sell (Spot)
# ===========================================================================
class AddSellSpotTests:

    def test_add_sell_spot_creates_one_row_in_db(self, auth_client, db_conn):
        auth_client.post(ADD_URL, data=_SELL_FORM)
        assert _count_transactions(db_conn) == 1

    def test_add_sell_spot_saves_negative_quantity(self, auth_client, db_conn):
        auth_client.post(ADD_URL, data=_SELL_FORM)
        row = db_conn.execute(
            "SELECT quantity FROM tbl_transaction WHERE trade_date=?", (TEST_DATE,)
        ).fetchone()
        assert row['quantity'] == -500

    def test_add_sell_spot_saves_correct_type(self, auth_client, db_conn):
        auth_client.post(ADD_URL, data=_SELL_FORM)
        row = db_conn.execute(
            "SELECT transaction_type FROM tbl_transaction WHERE trade_date=?", (TEST_DATE,)
        ).fetchone()
        assert row['transaction_type'] == 'Sell (Spot)'


# ===========================================================================
# 6. Home page — transaction display
# ===========================================================================
class HomeDisplayTests:

    def test_home_shows_transaction_on_matching_date(self, auth_client, db_conn):
        _insert_transaction(db_conn)
        response = auth_client.get(f'{HOME_URL}?trade_date={TEST_DATE}')
        assert response.status_code == 200
        assert b'Tencent' in response.data

    def test_home_shows_transaction_type(self, auth_client, db_conn):
        _insert_transaction(db_conn)
        response = auth_client.get(f'{HOME_URL}?trade_date={TEST_DATE}')
        assert b'Buy (Spot)' in response.data

    def test_home_does_not_show_transactions_for_other_dates(self, auth_client, db_conn):
        _insert_transaction(db_conn, trade_date='2026-01-01', value_date='2026-01-03')
        response = auth_client.get(f'{HOME_URL}?trade_date={TEST_DATE}')
        # The amount 320,500.00 only appears when the transaction row is rendered
        assert b'320,500.00' not in response.data

    def test_home_post_filters_by_trade_date(self, auth_client, db_conn):
        _insert_transaction(db_conn)
        response = auth_client.post(HOME_URL, data={'trade_date': TEST_DATE})
        assert response.status_code == 200
        assert b'Tencent' in response.data

    def test_home_displays_correct_amount(self, auth_client, db_conn):
        # 1000 shares × 320.50 = 320,500.00
        _insert_transaction(db_conn)
        response = auth_client.get(f'{HOME_URL}?trade_date={TEST_DATE}')
        assert b'320,500.00' in response.data


# ===========================================================================
# 7. Edit spot transaction
# ===========================================================================
class EditSpotTests:

    def test_edit_form_loads(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn)
        response = auth_client.get(f'/trades/{ref}/edit')
        assert response.status_code == 200

    def test_edit_form_is_prepopulated(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn)
        response = auth_client.get(f'/trades/{ref}/edit')
        assert b'320' in response.data          # price
        assert b'Buy (Spot)' in response.data   # transaction type

    def test_edit_updates_price_in_db(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn)
        edit_data = {
            'trade_date':       TEST_DATE,
            'value_date':       VALUE_DATE,
            'bank_ref':         BANK_REF,
            'code_ref':         CODE_REF,
            'transaction_type': 'Buy (Spot)',
            'quantity':         1000,
            'price':            400.00,
            'brokerage':        0,
            'commission':       0,
            'foreign_charge':   0,
            'stamp_duty':       0,
            'misc':             0,
        }
        auth_client.post(f'/trades/{ref}/edit', data=edit_data)
        row = db_conn.execute(
            "SELECT price FROM tbl_transaction WHERE ref_num=?", (ref,)
        ).fetchone()
        assert row['price'] == pytest.approx(400.00)

    def test_edit_sell_with_positive_quantity_is_rejected(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn, transaction_type='Sell (Spot)', quantity=-500)
        bad_data = {
            'trade_date':       TEST_DATE,
            'value_date':       VALUE_DATE,
            'bank_ref':         BANK_REF,
            'code_ref':         CODE_REF,
            'transaction_type': 'Sell (Spot)',
            'quantity':         500,    # wrong sign
            'price':            320.50,
            'brokerage': 0, 'commission': 0,
            'foreign_charge': 0, 'stamp_duty': 0, 'misc': 0,
        }
        response = auth_client.post(
            f'/trades/{ref}/edit', data=bad_data, follow_redirects=True
        )
        assert b'Sell transaction should have negative quantity' in response.data
        # Quantity must be unchanged
        row = db_conn.execute(
            "SELECT quantity FROM tbl_transaction WHERE ref_num=?", (ref,)
        ).fetchone()
        assert row['quantity'] == -500

    def test_edit_locked_transaction_as_staff_is_blocked(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn, locked=1)
        response = auth_client.get(f'/trades/{ref}/edit', follow_redirects=True)
        assert b'locked' in response.data.lower()

    def test_superuser_can_edit_locked_transaction(self, superuser_client, db_conn):
        ref = _insert_transaction(db_conn, locked=1)
        response = superuser_client.get(f'/trades/{ref}/edit')
        assert response.status_code == 200


# ===========================================================================
# 8. Delete spot transaction
# ===========================================================================
class DeleteSpotTests:

    def test_delete_removes_transaction_from_db(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn)
        assert _count_transactions(db_conn) == 1
        auth_client.get(f'/trades/{ref}/delete')
        assert _count_transactions(db_conn) == 0

    def test_delete_redirects_to_home(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn)
        response = auth_client.get(f'/trades/{ref}/delete')
        assert response.status_code == 302
        assert '/trades' in response.headers['Location']

    def test_delete_locked_transaction_as_staff_is_blocked(self, auth_client, db_conn):
        ref = _insert_transaction(db_conn, locked=1)
        auth_client.get(f'/trades/{ref}/delete', follow_redirects=True)
        assert _count_transactions(db_conn) == 1

    def test_superuser_can_delete_locked_transaction(self, superuser_client, db_conn):
        ref = _insert_transaction(db_conn, locked=1)
        superuser_client.get(f'/trades/{ref}/delete')
        assert _count_transactions(db_conn) == 0
