"""Verification that every /bank/ route requires authentication.

The bank blueprint shipped with NO @login_required on any of its 5 routes,
while every other blueprint has one per route. That left client holdings --
stock names and share quantities -- readable by anyone who requested the URL,
on the public production site. Found 2026-08-15 while sweeping for the
bank_id-not-found bug.

An anonymous request must be redirected to the login page (302), never served
(200). Two control routes from other blueprints are included so a regression in
the *test* (e.g. an app-wide auth change) is distinguishable from a regression
in the bank blueprint.

Read-only: every probe is a GET.

Run: server/.venv/Scripts/python.exe scripts/verify_bank_requires_login.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

# No LOGIN_DISABLED: this client is genuinely anonymous.
app = create_app()
app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
client = app.test_client()

BANK_ROUTES = [
    "/bank/",
    "/bank/DBPe",
    "/bank/DBPe/0175",
    "/bank/DBPe/0175/short",
    "/bank/DBPe/0175/download",
]
CONTROLS = ["/", "/trades/"]

failures = []

print("bank routes (must redirect to login):")
for path in BANK_ROUTES:
    status = client.get(path).status_code
    ok = status == 302
    print(f"  GET {path:28} -> {status} {'ok' if ok else 'FAIL -- SERVED WITHOUT AUTH'}")
    if not ok:
        failures.append(f"{path} returned {status}, expected 302 (anonymous access must redirect)")

print("\ncontrol routes from other blueprints (should already redirect):")
for path in CONTROLS:
    status = client.get(path).status_code
    ok = status == 302
    print(f"  GET {path:28} -> {status} {'ok' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"control {path} returned {status}, expected 302 -- "
                        "app-wide auth may be broken, not just the bank blueprint")

if failures:
    print()
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("\nPASS")
