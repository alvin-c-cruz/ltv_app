"""Unit tests for the shared weighted-average cost engine."""
from ltv_app.blueprints.transactions.models import accumulate_position


def _t(quantity, price, charges=0.0):
    return {
        'quantity': quantity, 'price': price,
        'brokerage': charges, 'commission': 0, 'foreign_charge': 0,
        'stamp_duty': 0, 'misc': 0,
    }


def test_single_buy():
    balance, cost, last_avg = accumulate_position([_t(1000, 10.0)])
    assert balance == 1000
    assert cost == 10000.0
    assert last_avg == 10.0


def test_buys_weighted_average_includes_charges():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0, charges=100.0),
        _t(1000, 12.0),
    ])
    assert balance == 2000
    assert cost == 22100.0
    assert last_avg == 11.05


def test_sell_keeps_average_unchanged():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0),
        _t(1000, 12.0),
        _t(-500, 15.0),
    ])
    assert balance == 1500
    assert cost == 16500.0          # 22000 - 22000*500/2000
    assert last_avg == 11.0


def test_sold_out_keeps_last_average():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0),
        _t(-1000, 15.0),
    ])
    assert balance == 0
    assert cost == 0
    assert last_avg == 10.0


def test_short_position_has_zero_cost():
    balance, cost, last_avg = accumulate_position([_t(-1000, 10.0)])
    assert balance == -1000
    assert cost == 0


def test_rebuy_after_flat_restarts_average():
    balance, cost, last_avg = accumulate_position([
        _t(1000, 10.0),
        _t(-1000, 15.0),
        _t(500, 20.0),
    ])
    assert balance == 500
    assert cost == 10000.0
    assert last_avg == 20.0
