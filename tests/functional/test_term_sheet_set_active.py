import pytest


def _insert_contract(db_conn, ref_num, status, locked=0):
    """Insert one ACCU contract. Returns ref_num."""
    db_conn.execute(
        "INSERT INTO tbl_stock_contract "
        "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
        " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status, reviewed, locked) "
        "VALUES (?, ?, 1, 1, '2026-01-02', '2026-01-05', 'ACCU', 1000, 'No', "
        "        100.0, 90.0, 105.0, '3m', 'monthly', 'No', NULL, ?, 0, ?)",
        (ref_num, f"Tencent - {ref_num}", status, locked),
    )
    db_conn.commit()
    return ref_num


def _insert_periods(db_conn, contract_ref, count, received):
    """Insert `count` periods. `received` is '' (open) or a share count string."""
    for i in range(count):
        db_conn.execute(
            "INSERT INTO tbl_stock_contract_period "
            "(contract_ref, start_date, end_date, days, received, gtd) "
            "VALUES (?, ?, ?, '20', ?, 'No')",
            (contract_ref, f"2026-0{i + 1}-05", f"2026-0{i + 1}-28", received),
        )
    db_conn.commit()


def _status_of(db_conn, ref_num):
    return db_conn.execute(
        "SELECT status FROM tbl_stock_contract WHERE ref_num=?", (ref_num,)
    ).fetchone()["status"]


def test_superuser_reverts_ko_to_active(superuser_client, db_conn):
    _insert_contract(db_conn, 900, status="KO", locked=1)

    resp = superuser_client.post("/term-sheet/900/set-active")

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert _status_of(db_conn, 900) == "active"


def test_non_superuser_blocked_on_locked_contract(auth_client, db_conn):
    _insert_contract(db_conn, 901, status="KO", locked=1)

    resp = auth_client.post("/term-sheet/901/set-active")

    assert resp.status_code == 403
    assert resp.get_json()["success"] is False
    assert _status_of(db_conn, 901) == "KO"  # nothing was written


def test_non_ko_contract_rejected(superuser_client, db_conn):
    _insert_contract(db_conn, 902, status="active", locked=0)

    resp = superuser_client.post("/term-sheet/902/set-active")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    assert _status_of(db_conn, 902) == "active"  # nothing was written


def test_unknown_contract_returns_404(superuser_client):
    resp = superuser_client.post("/term-sheet/99999/set-active")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_ko_contract_that_is_also_done_can_be_reverted(superuser_client, db_conn):
    """A KO contract whose periods are all received renders as DONE, not KO
    (models.py:163 checks next_date before status). The route must gate on
    `status`, not on the displayed value, so this must still succeed."""
    _insert_contract(db_conn, 903, status="KO", locked=1)
    _insert_periods(db_conn, 903, count=3, received="20000")

    resp = superuser_client.post("/term-sheet/903/set-active")

    assert resp.status_code == 200
    assert _status_of(db_conn, 903) == "active"
