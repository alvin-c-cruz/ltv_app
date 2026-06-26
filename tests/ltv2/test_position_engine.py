from datetime import date
from decimal import Decimal
import pytest
from ltv2.services.positions import PositionState, compute_position

D = Decimal


def txn(book="long", behavior="increase", qty="100", price="10", charges="0",
        bank_id=1, stock_id=1, sort_date=date(2026, 1, 1), priority=0):
    return {
        "bank_id": bank_id, "stock_id": stock_id, "book": book,
        "behavior_category": behavior, "quantity": D(qty), "price": D(price),
        "charges": D(charges), "sort_date": sort_date, "priority": priority,
    }


def only(positions):
    assert len(positions) == 1
    return next(iter(positions.values()))


def test_single_long_buy():
    s = only(compute_position([txn(qty="100", price="10", charges="5")]))
    assert s.balance == D("100")
    assert s.cost_basis == D("1005")
    assert s.average == D("10.05")
    assert s.realized_pnl == D("0")


def test_single_short_open():
    s = only(compute_position([txn(book="short", behavior="increase",
                                   qty="50", price="15", charges="2")]))
    assert s.balance == D("-50")
    assert s.cost_basis == D("-748")
    assert s.average == D("14.96")
    assert s.realized_pnl == D("0")


def test_two_long_buys_weighted_average():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(qty="100", price="20", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    assert s.balance == D("200")
    assert s.cost_basis == D("3000")
    assert s.average == D("15")


def test_separate_keys_for_each_bank_stock_book():
    positions = compute_position([
        txn(bank_id=1, stock_id=1, book="long"),
        txn(bank_id=2, stock_id=1, book="long"),
        txn(bank_id=1, stock_id=1, book="short", behavior="increase"),
    ])
    assert set(positions.keys()) == {(1, 1, "long"), (2, 1, "long"), (1, 1, "short")}


def test_unsupported_book_behavior_raises():
    with pytest.raises(ValueError):
        compute_position([txn(book="short", behavior="transfer_in")])


def test_neutral_has_no_effect():
    positions = compute_position([txn(behavior="neutral", qty="100")])
    # neutral creates the key but leaves a zero position
    s = only(positions)
    assert s.balance == D("0") and s.cost_basis == D("0")


def test_long_partial_sell_realizes_pnl():
    s = only(compute_position([
        txn(qty="100", price="10", charges="5", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="40", price="12", charges="3", sort_date=date(2026, 1, 2)),
    ]))
    # released = 40/100 * 1005 = 402 ; closing_cash = 40*12 - 3 = 477
    assert s.realized_pnl == D("75")
    assert s.cost_basis == D("603")
    assert s.balance == D("60")
    assert s.average == D("10.05")


def test_long_full_sell_zeroes_position():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="100", price="12", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    assert s.balance == D("0")
    assert s.cost_basis == D("0")
    assert s.realized_pnl == D("200")  # 1200 - 1000


def test_short_partial_cover_realizes_pnl():
    s = only(compute_position([
        txn(book="short", behavior="increase", qty="50", price="15", charges="2",
            sort_date=date(2026, 1, 1)),
        txn(book="short", behavior="decrease", qty="20", price="14", charges="1",
            sort_date=date(2026, 1, 2)),
    ]))
    # released = 20/50 * -748 = -299.2 ; closing_cash = -(20*14 + 1) = -281
    assert s.realized_pnl == D("18.2")
    assert s.cost_basis == D("-448.8")
    assert s.balance == D("-30")
    assert s.average == D("14.96")


def test_long_oversell_flips_to_short():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="150", price="12", charges="0", sort_date=date(2026, 1, 2)),
    ]))
    # Step A: close 100 @12 -> closing_cash 1200, released 1000, pnl +200
    # Step B: open 50 short within long book @12 -> cost_basis -(50*12) = -600
    assert s.realized_pnl == D("200")
    assert s.balance == D("-50")
    assert s.cost_basis == D("-600")
    assert s.average == D("12")


def test_oversell_then_buyback_crosses_again():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="150", price="12", charges="0", sort_date=date(2026, 1, 2)),
        txn(behavior="increase", qty="80", price="11", charges="0", sort_date=date(2026, 1, 3)),
    ]))
    # After step 2: balance -50, cost_basis -600 (avg 12)
    # Buy 80 (long) vs balance -50: Case 3. Close 50 short @11:
    #   closing_cash = -(50*11) = -550 ; released = -600 ; pnl += -550 -(-600)= +50
    # Open 30 long @11 -> cost_basis +330
    assert s.realized_pnl == D("250")  # 200 + 50
    assert s.balance == D("30")
    assert s.cost_basis == D("330")
    assert s.average == D("11")


def test_short_over_cover_flips_to_long():
    s = only(compute_position([
        txn(book="short", behavior="increase", qty="50", price="15", charges="0",
            sort_date=date(2026, 1, 1)),
        txn(book="short", behavior="decrease", qty="80", price="14", charges="0",
            sort_date=date(2026, 1, 2)),
    ]))
    # Step A: close 50 short @14 -> closing_cash -(50*14) = -700 ; released -750 ; pnl +50
    # Step B: open 30 long within short book @14 -> cost_basis +420
    assert s.realized_pnl == D("50")
    assert s.balance == D("30")
    assert s.cost_basis == D("420")
    assert s.average == D("14")


def test_zero_cross_prorates_charges():
    s = only(compute_position([
        txn(qty="100", price="10", charges="0", sort_date=date(2026, 1, 1)),
        txn(behavior="decrease", qty="200", price="12", charges="10", sort_date=date(2026, 1, 2)),
    ]))
    # close_qty 100, open_qty 100 -> charges split 5 / 5
    # Step A: closing_cash = 100*12 - 5 = 1195 ; released 1000 ; pnl +195
    # Step B: open 100 short @12 charges_open 5 -> cost_basis = -(100*12) + 5 = -1195
    assert s.realized_pnl == D("195")
    assert s.balance == D("-100")
    assert s.cost_basis == D("-1195")
