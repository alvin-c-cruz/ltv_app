"""Unit tests for term-sheet numeric coercion.

`tbl_stock_contract_period.received` and `.days` are stored with mixed types
(int, numeric string, or comma-formatted string like '24,000', or empty).
`_to_int` normalises them so `__post_init__` can accumulate without crashing.
"""
from ltv_app.blueprints.term_sheet.models import _to_int, FixingSchedule


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


# --- on-save normalisation: FixingSchedule coerces days/received at construction
# so no new comma-strings get written to tbl_stock_contract_period ---

def test_fixing_schedule_normalises_comma_received_to_int():
    # form input like '24,000' must not be persisted as a string
    sched = FixingSchedule(db=None, days="120", received="24,000")
    assert sched.received == 24000
    assert isinstance(sched.received, int)


def test_fixing_schedule_normalises_comma_days_to_int():
    sched = FixingSchedule(db=None, days="1,200", received="")
    assert sched.days == 1200
    assert isinstance(sched.days, int)


def test_fixing_schedule_normalises_numeric_string():
    sched = FixingSchedule(db=None, days="20", received="15")
    assert sched.days == 20
    assert sched.received == 15


def test_fixing_schedule_keeps_plain_int():
    sched = FixingSchedule(db=None, days=20, received=15)
    assert sched.days == 20
    assert sched.received == 15


def test_fixing_schedule_preserves_blank_received():
    # un-received period: keep the empty-string marker, do not write 0
    sched = FixingSchedule(db=None, days=20, received="")
    assert sched.received == ""


def test_fixing_schedule_preserves_blank_days():
    sched = FixingSchedule(db=None, days="", received="")
    assert sched.days == ""


def test_fixing_schedule_none_received_becomes_blank():
    sched = FixingSchedule(db=None, days=20, received=None)
    assert sched.received == ""


def test_fixing_schedule_strips_whitespace_and_commas():
    sched = FixingSchedule(db=None, days="  3,500 ", received="  1,000 ")
    assert sched.days == 3500
    assert sched.received == 1000
