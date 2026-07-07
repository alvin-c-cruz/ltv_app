import sqlite3
from datetime import date
from ltv_app.blueprints.ltv_stocks.legacy_port.working_day import WorkingDay
from ltv_app.blueprints.ltv_stocks.legacy_port.stock_price import get_stock_price


def test_next_and_previous_skip_weekends(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    wd = WorkingDay(conn, 'HKD')
    # 2026-07-03 is a Friday -> next working day is Monday 2026-07-06
    assert wd.next_day(date(2026, 7, 3)) == date(2026, 7, 6)
    # previous working day before Monday 2026-07-06 is Friday 2026-07-03
    assert wd.previous_day(date(2026, 7, 6)) == date(2026, 7, 3)
    conn.close()


def test_next_day_skips_holiday(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    # seed HKD (ccy_ref=1) holiday on Monday 2026-07-06
    conn.execute("INSERT INTO tbl_holiday (ccy_ref, holi_date) VALUES (1, '2026-07-06')")
    conn.commit()
    wd = WorkingDay(conn, 'HKD')
    assert wd.next_day(date(2026, 7, 3)) == date(2026, 7, 7)   # skips Fri->Mon(holiday)->Tue
    conn.close()


def test_count_days_inclusive_weekdays(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    wd = WorkingDay(conn, 'HKD')
    # Mon 2026-07-06 .. Fri 2026-07-10 inclusive = 5 weekdays
    assert wd.count_days(date(2026, 7, 6), date(2026, 7, 10)) == 5
    conn.close()


def test_get_stock_price_returns_close_or_none(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO tbl_stock_price (code_ref, trade_date, closing_price) "
                 "VALUES (1, '2026-07-06', 431.2)")
    conn.commit()
    assert get_stock_price(conn, 1, date(2026, 7, 6)) == 431.2
    assert get_stock_price(conn, 1, date(2026, 7, 7)) is None
    conn.close()
