"""Unit tests for term-sheet numeric coercion.

`tbl_stock_contract_period.received` and `.days` are stored with mixed types
(int, numeric string, or comma-formatted string like '24,000', or empty).
`_to_int` normalises them so `__post_init__` can accumulate without crashing.
"""
from ltv_app.blueprints.term_sheet.models import _to_int


def test_plain_int():
    assert _to_int(12800) == 12800


def test_numeric_string():
    assert _to_int("12800") == 12800


def test_comma_formatted_string():
    # the value that crashed /term-sheet/DBPe (contract 1372)
    assert _to_int("24,000") == 24000


def test_empty_string_is_zero():
    assert _to_int("") == 0


def test_none_is_zero():
    assert _to_int(None) == 0


def test_whitespace_and_comma_string():
    assert _to_int("  3,500 ") == 3500
