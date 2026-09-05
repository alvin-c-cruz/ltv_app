"""Build a self-contained *synthetic* demo database for ltv_app.

Nothing here is derived from the live `instance/LTV Stocks.db` -- the schema is
embedded, the banks and users are invented, and every price, contract and
transaction is generated from a fixed seed. Safe to screenshot and hand out.

The only real-world values are public HK ticker symbols and HK public holidays.

Usage (from server/):
    ./venv/Scripts/python.exe scripts/make_demo_db.py

The generated DB has one superuser (admin / demo1234) and one staff user
(analyst / demo1234).
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

TODAY = date(2026, 9, 3)          # the demo's "today" -- matches the capture date
PRICE_START = date(2025, 1, 2)
SEED = 20260903

DEMO_PASSWORD = "demo1234"

SCHEMA = """
CREATE TABLE dividends_declaration (id INTEGER NOT NULL, ex_date DATETIME, pay_out_date DATETIME, ccy_ref INTEGER, dividends_per_share FLOAT, comment VARCHAR, PRIMARY KEY (id));
CREATE TABLE tbl_bank_account (ref_num INTEGER PRIMARY KEY, bank_id TEXT, bank_name TEXT, indicative TEXT, priority INTEGER, transaction_basis text, report_label TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE tbl_cash_dividends (ref_num INTEGER PRIMARY KEY AUTOINCREMENT, bank_id INT, stock_id INT, ex_date TIMESTAMP, pay_out TIMESTAMP, nominal REAL, ccy_id INT, dividends_per_share REAL, tax REAL, charges REAL, status text default '', declaration_date TIMESTAMP, record_date TIMESTAMP);
CREATE TABLE tbl_cash_transfer (ref_num INTEGER PRIMARY KEY, bank_ref INTEGER, counter_bank_ref INTEGER, ccy_ref INTEGER, trade_date TIMESTAMP, value_date TIMESTAMP, amount DOUBLE);
CREATE TABLE tbl_code (ref_num INTEGER PRIMARY KEY, code TEXT, company_name TEXT, stock_name TEXT, yahoo_ticker TEXT, security_code TEXT, ccy_ref INTEGER);
CREATE TABLE tbl_commodity_contract (ref_num INTEGER PRIMARY KEY, trade_date timestamp, start_date timestamp, bank_ref integer, code_ref integer, transaction_type text, daily_shares integer, leveraged text, spot real, strike real, ko real, tenor text, frequency text, gtd text, status text);
CREATE TABLE tbl_currency (ref_num INTEGER PRIMARY KEY, ccy_id TEXT, ccy_name TEXT, priority INTEGER);
CREATE TABLE tbl_gmail_thread_bank (thread_id TEXT PRIMARY KEY, bank_label TEXT NOT NULL);
CREATE TABLE tbl_gmail_thread_labels (thread_id TEXT PRIMARY KEY, bank_id TEXT, sublabel_id TEXT);
CREATE TABLE tbl_holiday (ref_num INTEGER PRIMARY KEY, ccy_ref INTEGER, holi_date timestamp);
CREATE TABLE tbl_pricing (ref_num INTEGER PRIMARY KEY, bank_ref INTEGER, code_ref INTEGER, product TEXT, leverage TEXT, gtd TEXT, strike TEXT, ko TEXT, tenor TEXT, frequency TEXT);
CREATE TABLE tbl_stock_contract (ref_num INTEGER PRIMARY KEY, reference text, trade_date timestamp, start_date timestamp, bank_ref integer, code_ref integer, transaction_type text, daily_shares integer, leveraged text, spot real, strike_rate real, ko_rate real, tenor text, frequency text, gtd text, status text, bank_doc text, reviewed INTEGER NOT NULL DEFAULT 0, locked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE tbl_stock_contract_period (ref_num INTEGER PRIMARY KEY, contract_ref INTEGER, end_date timestamp, days integer, received integer, start_date timestamp, gtd TEXT);
CREATE TABLE tbl_stock_price (ref_num INTEGER PRIMARY KEY, code_ref INTEGER, trade_date timestamp, closing_price real);
CREATE TABLE tbl_stock_transfer (ref_num INTEGER PRIMARY KEY, trade_date timestamp, value_date timestamp, from_bank_ref integer, to_bank_ref integer, code_ref integer, quantity real, price real, stamp_duty real);
CREATE TABLE tbl_transaction (ref_num INTEGER PRIMARY KEY, trade_date timestamp, fixing_date timestamp, value_date timestamp, bank_ref integer, code_ref integer, transaction_type text, quantity integer, price real, brokerage real, commission real, foreign_charge real, stamp_duty real, misc real, comments text, gain_loss real, balance real, average real, spot real, ko real, contract_ref integer, periods text, counter_bank_ref integer, class text, reviewed INTEGER NOT NULL DEFAULT 0, locked INTEGER NOT NULL DEFAULT 0, no_charges INTEGER NOT NULL DEFAULT 0);
CREATE TABLE tbl_transaction_short (ref_num INTEGER PRIMARY KEY, trade_date timestamp, fixing_date timestamp, value_date timestamp, bank_ref integer, code_ref integer, transaction_type text, quantity integer, price real, brokerage real, commission real, foreign_charge real, stamp_duty real, misc real, comments text, gain_loss real, balance real, average real, spot real, ko real, contract_ref integer, periods text, reviewed INTEGER NOT NULL DEFAULT 0, locked INTEGER NOT NULL DEFAULT 0, no_charges INTEGER NOT NULL DEFAULT 0);
CREATE TABLE tbl_transaction_type (ref_num integer primary key, transaction_type text, priority integer);
CREATE TABLE tbl_user (id INTEGER PRIMARY KEY, username VARCHAR(255), email VARCHAR(255), password VARCHAR(255), level INTEGER, role TEXT NOT NULL DEFAULT 'staff');
"""

CURRENCIES = [
    (1, "HKD", "Hongkong Dollar", 1),
    (2, "JPY", "Japan Yen", 2),
    (3, "AUD", "Australian Dollar", 3),
    (4, "USD", "US Dollar", 4),
    (5, "SGD", "Singapore Dollar", 5),
]

TRANSACTION_TYPES = [
    "INITIALIZE", "Buy (Accu-KO)", "Buy (Accu)", "Buy (Spot)", "Stock Dividend",
    "Transfer-In", "Sell (Decu-KO)", "Sell (Decu)", "Sell (Spot)",
    "From Account (Pay Short)", "Transfer-Out", "Buy (Pay Short)",
    "Sell (Short)", "Borrow Shares", "Return Shares",
]

# Entirely invented private-bank / broker accounts.
BANKS = [
    # ref, bank_id, bank_name, indicative, priority, basis, report_label, active
    (1, "MPB1", "Meridian Private Bank No. 1", "No",  1, "value_date", "Meridian Private Bank", 1),
    (2, "MPB2", "Meridian Private Bank No. 2", "No",  2, "value_date", "Meridian Private Bank", 1),
    (3, "NGS",  "Northgate Securities Ltd",    "No",  3, "trade_date", None, 1),
    (4, "HRC",  "Harbourline Capital (HK)",    "Yes", 4, "value_date", None, 1),
    (5, "SVP",  "Silverpoint Bank Singapore",  "No",  5, "value_date", None, 1),
    (6, "ATC",  "Ashcroft Trust Company",      "Yes", 6, "value_date", None, 0),
]

# Public HK-listed tickers, HKD (ccy_ref 1). base_price is where the seeded
# random walk starts; it is not a quote of any real closing price.
STOCKS = [
    # ref, code, company_name, stock_name, base_price, vol
    (1,  "0002", "CLP Holdings Limited",                     "CLP",             68.0, 0.011),
    (2,  "0005", "HSBC Holdings plc",                        "HSBC",            72.0, 0.013),
    (3,  "0011", "Hang Seng Bank Limited",                   "Hang Seng Bank", 105.0, 0.012),
    (4,  "0016", "Sun Hung Kai Properties Limited",          "SHK Properties",  82.0, 0.015),
    (5,  "0388", "Hong Kong Exchanges and Clearing Limited", "HKEX",           305.0, 0.017),
    (6,  "0700", "Tencent Holdings Limited",                 "Tencent",        420.0, 0.018),
    (7,  "0941", "China Mobile Limited",                     "China Mobile",    78.0, 0.012),
    (8,  "1299", "AIA Group Limited",                        "AIA",             64.0, 0.016),
    (9,  "1810", "Xiaomi Corporation",                       "Xiaomi",          38.0, 0.024),
    (10, "2318", "Ping An Insurance (Group) Company",        "Ping An",         48.0, 0.018),
    (11, "3690", "Meituan",                                  "Meituan",        128.0, 0.026),
    (12, "9988", "Alibaba Group Holding Limited",            "Alibaba",        112.0, 0.022),
]

# HK public holidays 2025-2027 (published SAR general holidays).
HK_HOLIDAYS = [
    "2025-01-01", "2025-01-29", "2025-01-30", "2025-01-31", "2025-04-04",
    "2025-04-18", "2025-04-21", "2025-05-01", "2025-05-05", "2025-05-31",
    "2025-07-01", "2025-10-01", "2025-10-07", "2025-10-29", "2025-12-25",
    "2025-12-26",
    "2026-01-01", "2026-02-17", "2026-02-18", "2026-02-19", "2026-04-03",
    "2026-04-06", "2026-04-07", "2026-05-01", "2026-05-25", "2026-06-19",
    "2026-07-01", "2026-09-26", "2026-10-01", "2026-10-19", "2026-12-25",
    "2026-12-26",
    "2027-01-01", "2027-02-06", "2027-02-08", "2027-02-09", "2027-03-26",
    "2027-03-29", "2027-04-05", "2027-05-01", "2027-05-13", "2027-06-09",
    "2027-07-01", "2027-09-16", "2027-10-01", "2027-10-08", "2027-12-25",
    "2027-12-27",
]

USERS = [
    (1, "admin",   "admin@meridian-demo.test",   1, "superuser"),
    (2, "analyst", "analyst@meridian-demo.test", 5, "staff"),
]

HOLIDAY_SET = set(HK_HOLIDAYS)


def _daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _is_business_day(d):
    return d.isoweekday() < 6 and d.isoformat() not in HOLIDAY_SET


def _prev_business_day(d):
    d -= timedelta(days=1)
    while not _is_business_day(d):
        d -= timedelta(days=1)
    return d


def _next_business_day(d):
    d += timedelta(days=1)
    while not _is_business_day(d):
        d += timedelta(days=1)
    return d


def build_reference_data(con):
    con.executescript(SCHEMA)

    con.executemany("INSERT INTO tbl_currency VALUES (?,?,?,?)", CURRENCIES)
    con.executemany(
        "INSERT INTO tbl_transaction_type (ref_num, transaction_type, priority) VALUES (?,?,?)",
        [(i, t, i) for i, t in enumerate(TRANSACTION_TYPES, start=1)],
    )
    con.executemany("INSERT INTO tbl_bank_account VALUES (?,?,?,?,?,?,?,?)", BANKS)
    con.executemany(
        "INSERT INTO tbl_code (ref_num, code, company_name, stock_name, yahoo_ticker, "
        "security_code, ccy_ref) VALUES (?,?,?,?,?,'',1)",
        [(r, code, company, name, code + ".HK") for r, code, company, name, _, _ in STOCKS],
    )
    con.executemany("INSERT INTO tbl_holiday (ccy_ref, holi_date) VALUES (1, ?)",
                    [(h,) for h in HK_HOLIDAYS])
    con.executemany(
        "INSERT INTO tbl_user (id, username, email, password, level, role) VALUES (?,?,?,?,?,?)",
        [(i, u, e, generate_password_hash(DEMO_PASSWORD), lvl, role)
         for i, u, e, lvl, role in USERS],
    )
    con.commit()


def build_prices(con, rng):
    """Seeded random walk per stock. Returns {code_ref: {isodate: price}}."""
    days = [d for d in _daterange(PRICE_START, TODAY) if _is_business_day(d)]

    prices = {}
    rows = []
    for ref, _code, _company, _name, base, vol in STOCKS:
        level = base
        # Mean-reverting walk around a slowly drifting anchor. A pure random
        # walk at realistic daily vol wanders through the knock-out barrier
        # within weeks and leaves the demo with nothing but dead contracts;
        # the pull-back keeps every name inside a plausible trading band.
        drift = rng.uniform(-0.00025, 0.00040)
        reversion = 0.035
        series = {}
        for i, d in enumerate(days):
            anchor = base * (1 + drift) ** i
            level += reversion * (anchor - level) + level * rng.gauss(0, vol * 0.45)
            level = max(level, base * 0.4)
            px = round(level, 2 if level < 200 else 1)
            series[d.isoformat()] = px
            rows.append((ref, d.isoformat(), px))
        prices[ref] = series

    con.executemany(
        "INSERT INTO tbl_stock_price (code_ref, trade_date, closing_price) VALUES (?,?,?)",
        rows,
    )
    con.commit()
    return prices


# Which stocks each bank holds outright before any accumulator starts. These
# opening positions are what the decumulators sell down.
OPENING = [
    (1, 1, 180000), (1, 2, 260000), (1, 6, 24000), (1, 12, 90000),
    (2, 5, 16000), (2, 8, 240000), (2, 12, 60000),
    (3, 3, 40000), (3, 9, 320000), (3, 10, 150000),
    (4, 2, 120000), (4, 7, 180000), (4, 11, 22000),
    (5, 4, 90000), (5, 6, 12000), (5, 8, 110000),
]


def build_openings(con, prices):
    open_date = "2025-06-30"
    rows = []
    for bank_ref, code_ref, qty in OPENING:
        px = prices[code_ref][open_date]
        rows.append((open_date, open_date, bank_ref, code_ref, "INITIALIZE", qty,
                     round(px * 0.94, 4)))
    con.executemany(
        "INSERT INTO tbl_transaction (trade_date, value_date, bank_ref, code_ref, "
        "transaction_type, quantity, price, brokerage, commission, foreign_charge, "
        "stamp_duty, misc, spot, ko, reviewed, locked, no_charges) "
        "VALUES (?,?,?,?,?,?,?,0,0,0,0,0,0,0,1,1,1)", rows,
    )
    con.commit()


# (bank_ref, code_ref, ACCU|DECU, trade_date, tenor, frequency, gtd, leveraged, daily_shares)
CONTRACTS = [
    (1,  2, "ACCU", "2025-09-15", "12m", "monthly",    "1m", "Yes", 3000),
    (1,  6, "DECU", "2025-10-06", "6m",  "monthly",    "No", "Yes",  250),
    (1, 12, "ACCU", "2026-01-12", "12m", "monthly",    "2m", "Yes", 1200),
    (1,  1, "DECU", "2026-03-02", "9m",  "monthly",    "No", "No",  1500),
    (2,  8, "ACCU", "2025-11-03", "12m", "bi-monthly", "1m", "Yes", 2500),
    (2, 12, "DECU", "2026-02-09", "6m",  "monthly",    "No", "Yes",  900),
    (2,  5, "ACCU", "2026-04-13", "12m", "monthly",    "1m", "Yes",  180),
    (3,  9, "ACCU", "2025-10-20", "12m", "monthly",    "No", "Yes", 4500),
    (3, 10, "DECU", "2026-01-05", "9m",  "monthly",    "1m", "Yes", 1800),
    (3,  3, "ACCU", "2026-05-11", "6m",  "monthly",    "No", "No",   700),
    (4,  7, "DECU", "2025-12-01", "12m", "monthly",    "1m", "Yes", 2200),
    (4, 11, "ACCU", "2026-02-16", "12m", "monthly",    "No", "Yes",  400),
    (4,  2, "DECU", "2026-06-08", "6m",  "monthly",    "No", "Yes", 1600),
    (5,  4, "DECU", "2025-11-17", "12m", "monthly",    "1m", "Yes", 1100),
    (5,  6, "ACCU", "2026-03-16", "12m", "bi-monthly", "1m", "Yes",  150),
    (5,  8, "DECU", "2026-05-04", "9m",  "monthly",    "No", "Yes", 1400),
    (1,  5, "ACCU", "2026-06-15", "12m", "monthly",    "1m", "Yes",  120),
    (2, 11, "ACCU", "2026-07-06", "6m",  "monthly",    "No", "Yes",  300),
    (3, 12, "DECU", "2026-07-20", "12m", "monthly",    "1m", "Yes", 1000),
    (4,  9, "ACCU", "2026-08-10", "12m", "monthly",    "1m", "Yes", 3800),
    (5, 10, "ACCU", "2026-08-17", "9m",  "monthly",    "No", "Yes", 2000),
    (1,  8, "ACCU", "2026-08-24", "12m", "monthly",    "1m", "Yes", 2600),
    # Monthly fixings land on the trade date's day-of-month, so this block --
    # traded on the 2nd (settled banks) and the 3rd (the indicative one) -- is
    # what gives the demo's "today" a full fixing run rather than a single row.
    (1,  3, "ACCU", "2025-10-02", "12m", "monthly", "1m", "Yes",  900),
    (2,  1, "DECU", "2025-12-02", "12m", "monthly", "No", "Yes", 1300),
    (3,  6, "ACCU", "2026-02-02", "12m", "monthly", "1m", "Yes",  200),
    (5, 12, "ACCU", "2026-04-02", "12m", "monthly", "No", "Yes", 1500),
    (2,  4, "DECU", "2026-06-02", "9m",  "monthly", "1m", "Yes", 1200),
    (1, 11, "DECU", "2025-09-02", "12m", "monthly", "No", "Yes",  350),
    (3,  8, "ACCU", "2026-07-02", "12m", "monthly", "1m", "Yes", 2800),
    (5,  9, "DECU", "2026-01-02", "12m", "monthly", "No", "Yes", 3600),
    (4,  5, "ACCU", "2025-12-03", "12m", "monthly", "1m", "Yes",  150),
    (4, 12, "DECU", "2026-02-03", "12m", "monthly", "No", "Yes", 1100),
    (4,  3, "ACCU", "2026-06-03", "12m", "monthly", "1m", "Yes",  800),
    (4, 10, "ACCU", "2026-08-03", "12m", "monthly", "No", "Yes", 2400),
    (1,  7, "DECU", "2026-04-14", "12m", "monthly", "1m", "Yes", 1900),
    (2,  6, "ACCU", "2026-05-19", "12m", "monthly", "No", "Yes",  180),
    (3,  4, "DECU", "2026-03-10", "9m",  "monthly", "1m", "Yes",  950),
    (5, 11, "ACCU", "2026-06-22", "12m", "monthly", "1m", "Yes",  350),
    (1,  9, "ACCU", "2025-11-11", "12m", "monthly", "No", "Yes", 5200),
    (2,  3, "DECU", "2026-07-13", "12m", "monthly", "1m", "Yes",  600),
]


def build_contracts(db, prices, rng):
    from ltv_app.blueprints.term_sheet import StockContract
    from ltv_app.blueprints.term_sheet.models import CreateSchedules

    counters = {}
    bank_ids = {b[0]: b[1] for b in BANKS}

    for idx, (bank_ref, code_ref, ttype, trade_date, tenor,
              freq, gtd, leveraged, shares) in enumerate(CONTRACTS):
        stock_name = STOCKS[code_ref - 1][3]
        key = (bank_ref, code_ref, ttype)
        counters[key] = counters.get(key, 0) + 1
        reference = "{} - {}".format(stock_name, counters[key])

        spot = prices[code_ref][trade_date]
        if ttype == "ACCU":
            strike_rate = round(rng.uniform(86.0, 94.0), 2)
            ko_rate = round(rng.uniform(114.0, 126.0), 2)
        else:
            strike_rate = round(rng.uniform(106.0, 115.0), 2)
            ko_rate = round(rng.uniform(76.0, 87.0), 2)

        start_date = _next_business_day(date.fromisoformat(trade_date)).isoformat()

        # Every fourth contract is left without its bank document reference and
        # unlocked, so the demo shows both the "missing" flag and the visual
        # difference between a locked (read-only) and an open contract.
        outstanding = idx % 4 == 3
        bank_doc = "" if outstanding else "{}/{}/{}".format(
            bank_ids[bank_ref], ttype[:3], trade_date.replace("-", "")[2:])

        contract = StockContract(
            db=db, reference=reference, bank_ref=bank_ref, code_ref=code_ref,
            transaction_type=ttype, trade_date=trade_date, start_date=start_date,
            daily_shares=shares, leveraged=leveraged, spot=spot,
            strike_rate=strike_rate, ko_rate=ko_rate, tenor=tenor, frequency=freq,
            gtd=gtd, status="active", bank_doc=bank_doc,
            reviewed=1, locked=0 if outstanding else 1,
        )
        contract.save()
        contract.__post_init__()
        CreateSchedules(term_sheet=contract, db=db)


def run_fixings(db, start, end):
    """Drive the app's own fixing engine day by day, exactly as the operator
    would, so the demo transactions are produced by production code."""
    from ltv_app.blueprints.fixings.extensions import GenerateFixings, RecordFixings

    recorded = 0
    for d in _daterange(start, end):
        if not _is_business_day(d):
            continue
        fixings = GenerateFixings(trade_date=d.isoformat()).fixings
        if fixings:
            RecordFixings(db=db, fixing_data=fixings, trade_date=d.isoformat())
            recorded += sum(len(v) for acc in fixings.values() for v in acc.values())
    print("  recorded {} fixing transactions".format(recorded))


# A handful of hand-entered spot trades, so Trades Done / Notebook / Review are
# not made up purely of accumulator fixings.
SPOT_TRADES = [
    ("2026-08-04", 1,  6, "Buy (Spot)",   4000),
    ("2026-08-11", 3,  5, "Buy (Spot)",   1200),
    ("2026-08-18", 2,  8, "Sell (Spot)", -30000),
    ("2026-08-25", 4, 11, "Buy (Spot)",   2500),
    ("2026-08-28", 5,  4, "Sell (Spot)", -12000),
    ("2026-09-01", 1,  2, "Buy (Spot)",  20000),
    ("2026-09-02", 3,  9, "Sell (Spot)", -40000),
    ("2026-09-02", 2, 12, "Buy (Spot)",   6000),
    ("2026-09-03", 4,  7, "Buy (Spot)",  15000),
    ("2026-09-03", 5,  8, "Sell (Spot)", -18000),
    ("2026-09-03", 1,  9, "Buy (Spot)",  120000),
    ("2026-09-03", 2,  5, "Sell (Spot)",  -2000),
    ("2026-09-03", 3, 11, "Buy (Spot)",    8000),
    ("2026-09-03", 1, 12, "Sell (Spot)", -25000),
    ("2026-09-03", 5,  6, "Buy (Spot)",    1500),
    ("2026-09-03", 2,  3, "Buy (Spot)",   14000),
]


def build_spot_trades(con, prices):
    rows = []
    for i, (trade_date, bank_ref, code_ref, ttype, qty) in enumerate(SPOT_TRADES):
        px = prices[code_ref][trade_date]
        value_date = _next_business_day(
            _next_business_day(date.fromisoformat(trade_date))).isoformat()
        gross = abs(qty) * px
        # Older trades are fully processed; the most recent four are left
        # unreviewed / uncharged so the Workflow queue has something in it.
        settled = i < len(SPOT_TRADES) - 10
        brokerage = round(gross * 0.0012, 2) if settled else 0.0
        stamp = round(gross * 0.001, 2) if settled else 0.0
        misc = round(gross * 0.00005, 2) if settled else 0.0
        rows.append((trade_date, value_date, bank_ref, code_ref, ttype, qty, px,
                     brokerage, stamp, misc,
                     1 if settled else 0, 1 if settled else 0))
    con.executemany(
        "INSERT INTO tbl_transaction (trade_date, value_date, bank_ref, code_ref, "
        "transaction_type, quantity, price, brokerage, commission, foreign_charge, "
        "stamp_duty, misc, comments, spot, ko, reviewed, locked, no_charges) "
        "VALUES (?,?,?,?,?,?,?,?,0,0,?,?,'',0,0,?,?,0)", rows,
    )

    con.execute(
        "INSERT INTO tbl_stock_transfer (trade_date, value_date, from_bank_ref, "
        "to_bank_ref, code_ref, quantity, price, stamp_duty) VALUES (?,?,?,?,?,?,?,?)",
        ("2026-08-20", "2026-08-24", 1, 2, 2, 25000, prices[2]["2026-08-20"], 0.0),
    )
    con.execute(
        "INSERT INTO tbl_cash_transfer (bank_ref, counter_bank_ref, ccy_ref, "
        "trade_date, value_date, amount) VALUES (?,?,?,?,?,?)",
        (1, 3, 1, "2026-08-26", "2026-08-28", 5000000.0),
    )
    con.commit()


def fix_negative_positions(con, prices):
    """Top up the 2025-06-30 opening holdings so no account ends the demo short.

    The decumulators sell a share count that only falls out of the generated
    price path, so the opening inventory that has to back them cannot be
    written down in advance -- it is sized here, once every sale is known.
    """
    open_date = "2025-06-30"
    balances = con.execute(
        "SELECT bank_ref, code_ref, SUM(quantity) FROM tbl_transaction "
        "GROUP BY bank_ref, code_ref"
    ).fetchall()

    topped = 0
    for bank_ref, code_ref, balance in balances:
        if balance >= 0:
            continue
        need = int(-balance * 1.35)
        need = ((need // 1000) + 1) * 1000
        existing = con.execute(
            "SELECT ref_num FROM tbl_transaction WHERE bank_ref=? AND code_ref=? "
            "AND transaction_type='INITIALIZE'", (bank_ref, code_ref)
        ).fetchone()
        if existing:
            con.execute("UPDATE tbl_transaction SET quantity=quantity+? WHERE ref_num=?",
                        (need, existing[0]))
        else:
            px = prices[code_ref][open_date]
            con.execute(
                "INSERT INTO tbl_transaction (trade_date, value_date, bank_ref, code_ref, "
                "transaction_type, quantity, price, brokerage, commission, foreign_charge, "
                "stamp_duty, misc, spot, ko, reviewed, locked, no_charges) "
                "VALUES (?,?,?,?,'INITIALIZE',?,?,0,0,0,0,0,0,0,1,1,1)",
                (open_date, open_date, bank_ref, code_ref, need, round(px * 0.94, 4)),
            )
        topped += 1
    con.commit()
    print("  topped up {} opening holdings".format(topped))


def stage_workflow(con):
    """Spread the current day's trades across the four workflow stages.

    Everything the fixing engine writes arrives unreviewed and uncharged, which
    would leave the Charges / For Locking / Locked tabs empty on the default
    same-day filter. Walking a repeating four-step pattern over today's rows
    puts a realistic handful in each stage instead.
    """
    rows = con.execute(
        "SELECT ref_num, quantity, price FROM tbl_transaction WHERE trade_date=? "
        "ORDER BY ref_num", (TODAY.isoformat(),)
    ).fetchall()

    for i, (ref_num, quantity, price) in enumerate(rows):
        stage = i % 4
        if stage == 3:
            continue                              # still awaiting review
        if stage == 0:
            con.execute("UPDATE tbl_transaction SET reviewed=1, locked=0 WHERE ref_num=?",
                        (ref_num,))               # reviewed, charges outstanding
            continue

        gross = abs(quantity) * price
        locked = 1 if stage == 2 else 0           # 1 = charged and locked, 2 = ready to lock
        con.execute(
            "UPDATE tbl_transaction SET reviewed=1, locked=?, brokerage=?, "
            "stamp_duty=?, misc=? WHERE ref_num=?",
            (locked, round(gross * 0.0012, 2), round(gross * 0.001, 2),
             round(gross * 0.00005, 2), ref_num),
        )
    con.commit()
    print("  staged {} of today's trades across the workflow".format(len(rows)))


CASH_DIVIDENDS = [
    # bank_ref, code_ref, declaration, ex, record, payout, nominal, dps
    (1, 2,  "2026-05-04", "2026-05-14", "2026-05-15", "2026-06-26", 260000, 0.62),
    (2, 8,  "2026-03-12", "2026-03-26", "2026-03-27", "2026-05-08", 240000, 0.148),
    (3, 10, "2026-03-20", "2026-04-14", "2026-04-15", "2026-05-29", 150000, 1.62),
    (4, 7,  "2026-03-19", "2026-05-21", "2026-05-22", "2026-07-10", 180000, 2.44),
    (1, 1,  "2026-02-24", "2026-03-19", "2026-03-20", "2026-04-16", 180000, 1.21),
    (5, 4,  "2026-02-26", "2026-03-25", "2026-03-26", "2026-04-24",  90000, 1.25),
    (1, 6,  "2026-03-18", "2026-05-15", "2026-05-18", "2026-06-30",  24000, 4.50),
    (3, 3,  "2026-02-18", "2026-03-06", "2026-03-09", "2026-04-02",  40000, 3.20),
]


def build_dividends(con):
    rows = []
    for bank, stock, decl, ex, rec, pay, nominal, dps in CASH_DIVIDENDS:
        gross = nominal * dps
        rows.append((bank, stock, ex, pay, nominal, 1, dps, 0.0,
                     round(gross * 0.0005, 2), "Received", decl, rec))
    con.executemany(
        "INSERT INTO tbl_cash_dividends (bank_id, stock_id, ex_date, pay_out, nominal, "
        "ccy_id, dividends_per_share, tax, charges, status, declaration_date, record_date) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows,
    )
    con.commit()


PRICING_ROWS = [
    (1, 6,  "Accumulator", "2x", "1m", "88.5",  "104.0", "12m", "monthly"),
    (1, 12, "Decumulator", "2x", "No", "112.0", "94.0",  "12m", "monthly"),
    (3, 9,  "Accumulator", "2x", "1m", "90.0",  "106.0", "6m",  "monthly"),
    (5, 5,  "Accumulator", "2x", "1m", "87.0",  "103.5", "12m", "bi-monthly"),
]


def build_pricing(con):
    con.executemany(
        "INSERT INTO tbl_pricing (bank_ref, code_ref, product, leverage, gtd, strike, "
        "ko, tenor, frequency) VALUES (?,?,?,?,?,?,?,?,?)", PRICING_ROWS,
    )
    con.commit()


def main():
    global TODAY

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join("instance", "demo", "LTV Stocks.db"))
    parser.add_argument("--today", default=TODAY.isoformat(),
                        help="the demo's 'today' (YYYY-MM-DD) -- prices, fixings and the "
                             "contract window all run up to this date. Set it to the "
                             "capture date so the date-defaulted pages aren't empty.")
    args = parser.parse_args()

    TODAY = date.fromisoformat(args.today)

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        os.remove(out)

    rng = random.Random(SEED)

    print("Building demo database at {}".format(out))
    con = sqlite3.connect(out)
    con.row_factory = sqlite3.Row
    build_reference_data(con)
    print("  reference data")
    prices = build_prices(con, rng)
    print("  {:,} closing prices".format(sum(len(v) for v in prices.values())))
    build_openings(con, prices)
    build_dividends(con)
    build_pricing(con)
    con.close()

    # Everything from here on runs through the app itself, against the demo DB.
    from ltv_app import create_app
    app = create_app(test_config={
        "SECRET_KEY": "demo-secret-key-not-for-production",
        "DATABASE": out,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "WTF_CSRF_ENABLED": False,
    })

    with app.test_request_context():
        from ltv_app.blueprints.database.views import get_db
        db = get_db()
        build_contracts(db, prices, rng)
        n = db.execute("SELECT COUNT(*) FROM tbl_stock_contract").fetchone()[0]
        p = db.execute("SELECT COUNT(*) FROM tbl_stock_contract_period").fetchone()[0]
        print("  {} contracts, {} fixing periods".format(n, p))

        run_fixings(db, date(2025, 9, 16), TODAY)

    con = sqlite3.connect(out)
    build_spot_trades(con, prices)
    fix_negative_positions(con, prices)
    stage_workflow(con)
    total = con.execute("SELECT COUNT(*) FROM tbl_transaction").fetchone()[0]
    print("  {:,} transactions total".format(total))
    con.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
