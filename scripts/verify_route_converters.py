"""Verification that every ref-style route param is typed <int:...>.

An untyped <ref_num>/<contract_ref>/<period_ref> lets a non-integer reach the
view, turning a malformed URL into an HTTP 500 instead of a clean 404, and
feeding an unvalidated string into model code.

<source> is deliberately NOT included -- it is an enum-like segment resolved
through a hardcoded dict in lock/charges/workflow and must stay a string.

Routing happens before login_required, so the 404 probes need no auth. A probe
that still matches some rule redirects to login (302) instead of 404ing.

There is deliberately no probe for term_sheet.delete_period. Its URL shape,
/term-sheet/<contract_ref>/<period_ref>/delete, is shadowed for non-integer
values by the genuine three-segment route
/term-sheet/<bank_id>/<transaction_type>/<code> (term_sheet.term_sheet_summary),
so any three-segment probe matches that instead and can never 404. period_ref
is covered by the untyped-rule scan above rather than by a request probe.

Run: server/.venv/Scripts/python.exe scripts/verify_route_converters.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

UNTYPED = ("<ref_num>", "<contract_ref>", "<period_ref>")
PROBES = [
    "/term-sheet/abc/view",
    "/term-sheet/edit/abc",
    "/trades/abc/edit",
    "/trades/short/abc/edit",
    "/dividends/edit/abc",
    "/fixings/abc/edit",
]

app = create_app()
failures = []

offenders = sorted(rule.rule for rule in app.url_map.iter_rules()
                   if any(token in rule.rule for token in UNTYPED))
print(f"untyped ref rules remaining: {len(offenders)}")
for rule in offenders:
    print("  ", rule)
    failures.append(f"untyped rule: {rule}")

client = app.test_client()
for path in PROBES:
    status = client.get(path).status_code
    print(f"GET {path:28} -> {status}")
    if status != 404:
        failures.append(f"{path} returned {status}, expected 404")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
