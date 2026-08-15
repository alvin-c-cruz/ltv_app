"""Verification that authentication is default-deny, not opt-in.

The bank blueprint shipped with no @login_required on any route and served
client holdings anonymously for months (BUGS.md, 2026-08-15). Nothing caught
it, because privacy depended on every author remembering a decorator.

This checks the structural property instead of the instance: a route with NO
decorator at all must still be denied to an anonymous caller. That is the test
that would have failed before the fix and cannot be satisfied by adding another
decorator somewhere.

Three parts:
  1. an undecorated route registered at runtime is denied  <- the real test
  2. every existing route is denied anonymously, except the allowlist
  3. the allowlist itself still works (login page reachable, static reachable),
     and LOGIN_DISABLED still bypasses everything so the other verify_*.py
     scripts keep working

Read-only: GETs only, nothing mutating is requested.

Run: server/.venv/Scripts/python.exe scripts/verify_auth_default_deny.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from flask import Blueprint

from ltv_app import create_app

failures = []

# ---------------------------------------------------------------- part 1
# A brand-new blueprint with no @login_required anywhere -- exactly the shape
# the bank blueprint had. Registered before the first request so the app's
# before_request hook governs it.
app = create_app()
app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")

naive = Blueprint("naive_newcomer", __name__, url_prefix="/naive-newcomer")


@naive.route("/secret")
def secret():
    return "client holdings would be here"


app.register_blueprint(naive)

status = app.test_client().get("/naive-newcomer/secret").status_code
ok = status == 302
print("1. undecorated route must still be denied")
print(f"   GET /naive-newcomer/secret -> {status} "
      f"{'ok (redirected to login)' if ok else 'FAIL -- SERVED WITHOUT AUTH'}")
if not ok:
    failures.append(
        f"an undecorated route returned {status}; auth is still opt-in, so the next "
        "blueprint written without @login_required will be public again")

# ---------------------------------------------------------------- part 2
PUBLIC = {"auth.login", "static"}
SAMPLES = {"ref_num": 1, "contract_ref": 1, "period_ref": 1, "bank_id": "DBPe",
           "code": "0175", "transaction_type": "DECU", "source": "spot",
           "filename": "css/main.css"}
MUTATING = ("delete", "unlock", "/lock", "mark", "no_charges", "set-active",
            "set-inactive", "toggle", "add-line", "save", "logout")

app2 = create_app()
app2.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
client2 = app2.test_client()

served, checked = [], 0
for rule in sorted(app2.url_map.iter_rules(), key=lambda r: r.rule):
    if "GET" not in rule.methods or rule.endpoint in PUBLIC:
        continue
    if any(m in rule.rule.lower() for m in MUTATING):
        continue
    if not set(rule.arguments) <= set(SAMPLES):
        continue
    try:
        path = rule.build({a: SAMPLES[a] for a in rule.arguments}, append_unknown=False)[1]
        status = client2.get(path).status_code
    except Exception:
        continue
    checked += 1
    if status != 302:
        served.append((path, rule.endpoint, status))

print(f"\n2. every non-allowlisted GET route denied anonymously ({checked} probed)")
if served:
    for path, endpoint, status in served:
        print(f"   FAIL {status} {path:38} {endpoint}")
        failures.append(f"{path} ({endpoint}) returned {status} anonymously, expected 302")
else:
    print("   ok -- all redirected to login")

# ---------------------------------------------------------------- part 3
print("\n3. allowlist and test-bypass still work")
login_status = client2.get("/login").status_code
print(f"   GET /login                -> {login_status} {'ok' if login_status == 200 else 'FAIL'}")
if login_status != 200:
    failures.append(f"/login returned {login_status}; the login page must stay reachable "
                    "or nobody can authenticate at all")

app3 = create_app(test_config={"LOGIN_DISABLED": True})
app3.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
bypass = app3.test_client().get("/bank/DBPe").status_code
print(f"   LOGIN_DISABLED /bank/DBPe -> {bypass} {'ok' if bypass == 200 else 'FAIL'}")
if bypass != 200:
    failures.append(f"LOGIN_DISABLED bypass returned {bypass}, expected 200 -- the other "
                    "verify_*.py scripts rely on it")

if failures:
    print()
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("\nPASS")
