"""Unit tests for monthly period generation (CreateSchedules).

Regression for the "end-of-month trade" bug: when a period-end was pushed
forward across a month boundary by check_date() (weekend/holiday), the next
period's month was derived from that *spilled* end date, so month + 1 skipped a
whole month and produced a single ~40-day period instead of two.

Reproduced with live contract 1427 (Geely Motor - 14):
    trade_date 2026-06-29, start_date 2026-06-30, tenor 12m, monthly, gtd 1m
Feb 2027 day-29 -> 28 (Sun) -> pushed to Mon 2027-03-01, which made the next
period jump straight to April, merging March+April into 2027-03-02..2027-04-29.
"""
import sqlite3
from types import SimpleNamespace

import pytest

from ltv_app.blueprints.term_sheet.models import CreateSchedules


# HKD holidays in the schedule window, copied from the live DB. 2027-03-29 is
# the one that legitimately pushes the March period-end to 2027-03-30.
HKD_HOLIDAYS_2026_2027 = [
    "2026-07-01", "2026-09-26", "2026-10-01", "2026-10-19", "2026-12-25",
    "2026-12-26", "2027-01-01", "2027-02-06", "2027-02-08", "2027-02-09",
    "2027-03-26", "2027-03-27", "2027-03-29", "2027-04-05", "2027-05-01",
    "2027-05-13", "2027-06-09", "2027-07-01",
]


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tbl_currency (ref_num INTEGER PRIMARY KEY, ccy_id TEXT, ccy_name TEXT, priority INTEGER);
        CREATE TABLE tbl_code (ref_num INTEGER PRIMARY KEY, code TEXT, company_name TEXT, stock_name TEXT, yahoo_ticker TEXT, security_code TEXT, ccy_ref INTEGER);
        CREATE TABLE tbl_holiday (ref_num INTEGER PRIMARY KEY, ccy_ref INTEGER, holi_date timestamp);
        CREATE TABLE tbl_stock_contract_period (ref_num INTEGER PRIMARY KEY, contract_ref INTEGER, end_date timestamp, days integer, received integer, start_date timestamp, gtd TEXT);
        """
    )
    conn.execute("INSERT INTO tbl_currency (ref_num, ccy_id, ccy_name, priority) VALUES (1, 'HKD', 'Hongkong Dollar', 1)")
    conn.execute("INSERT INTO tbl_code (ref_num, code, ccy_ref) VALUES (10, '0175', 1)")
    for h in HKD_HOLIDAYS_2026_2027:
        conn.execute("INSERT INTO tbl_holiday (ccy_ref, holi_date) VALUES (1, ?)", (h,))
    conn.commit()
    yield conn
    conn.close()


def _periods(db):
    rows = db.execute(
        "SELECT start_date, end_date FROM tbl_stock_contract_period "
        "ORDER BY ref_num"
    ).fetchall()
    return [(r[0][:10], r[1][:10]) for r in rows]


def test_end_of_month_trade_does_not_skip_a_month(db):
    """A monthly contract traded on the 29th must produce one period per month,
    never merging two months into a single ~40-day period."""
    contract = SimpleNamespace(
        ref_num=1427,
        trade_date="2026-06-29",
        start_date="2026-06-30",
        code_ref=10,
        tenor="12m",
        frequency="monthly",
        gtd="1m",
    )

    CreateSchedules(contract, db)

    assert _periods(db) == [
        ("2026-06-30", "2026-07-29"),
        ("2026-07-30", "2026-08-31"),
        ("2026-09-01", "2026-09-29"),
        ("2026-09-30", "2026-10-29"),
        ("2026-10-30", "2026-11-30"),
        ("2026-12-01", "2026-12-29"),
        ("2026-12-30", "2027-01-29"),
        ("2027-02-01", "2027-03-01"),
        ("2027-03-02", "2027-03-30"),
        ("2027-03-31", "2027-04-29"),
        ("2027-04-30", "2027-05-31"),
        ("2027-06-01", "2027-06-29"),
    ]
