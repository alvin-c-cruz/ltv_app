"""Verification that /pricing/add_header never evaluates its query string.

The "Yes" button on /pricing/ (register an unknown header row) redirected to
/pricing/add_header?data=<repr of [bank_code, headers]>, and add_header ran
eval() on that parameter. Anyone who could get a signed-in user to open a
crafted link ran Python on the server: the session cookie is SameSite=Lax, which
a top-level GET from another site still carries, and no CSRF token guards a GET.
The repr was also put in the URL unencoded, so a header containing "&" or "#"
cut the parameter short and the page 500ed.

The parameter is now JSON, encoded by url_for and read with json.loads; anything
that is not a [bank_code, headers] pair is a 400.

  A  an expression with a side effect is not run, and is rejected with a 400;
  B  the button's own redirect still renders every header, "&" and "#" included;
  C  a missing or malformed parameter is a 400, not a 500.

Every probe is a GET or a POST to /pricing/ that only redirects; nothing is
written (the add_header POST, which saves instance/pricing_columns.txt, is not
called). Uses LOGIN_DISABLED so the probes reach the view.

Run: server/.venv/Scripts/python.exe scripts/verify_pricing_add_header.py
"""
import os
import sys
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.pricing.extensions import BANKS

app = create_app(test_config={
    "LOGIN_DISABLED": True,
    "DATABASE": os.path.join(SERVER, "instance", "LTV Stocks.db"),
})
client = app.test_client()
failures = []


def check(label, ok):
    print(f"  {label}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        failures.append(label)


# --- A: the hole. If this expression is evaluated it sets an environment
# variable in this process and returns a well-formed pair, so the page renders
# 200 and nothing else gives it away.
PROBE = "LTV_PRICING_EVAL_PROBE"
os.environ.pop(PROBE, None)
payload = f"(__import__('os').environ.__setitem__('{PROBE}', '1'), ['DB', ['h']])[1]"
r = client.get("/pricing/add_header?data=" + quote(payload))
check("A1 a Python expression in ?data= is not evaluated", PROBE not in os.environ)
check("A2 and is rejected with 400", r.status_code == 400)
os.environ.pop(PROBE, None)

# --- B: the flow the parameter exists for. Post an unknown header row the way
# the "Yes" button does and follow its redirect.
bank_code = next(iter(BANKS))
headers = ["Underlying", "Strike & KO", "Tenor #", "Notes"]
r = client.post("/pricing/", data={
    "cmd_button": "Yes",
    "bank_code": bank_code,
    "textarea_data": "\t".join(headers) + "\r\nrow\trow\trow\trow",
})
check("B1 Yes redirects to add_header", r.status_code == 302
      and "/pricing/add_header" in r.headers.get("Location", ""))
page = client.get(r.headers.get("Location", "/pricing/add_header")) if r.status_code == 302 else None
check("B2 add_header renders", page is not None and page.status_code == 200)
body = page.get_data(as_text=True) if page is not None else ""
check("B3 the bank code is carried through", f'value="{bank_code}"' in body)
check("B4 every header is listed, '&' and '#' included",
      all(f'name="{h.replace("&", "&amp;")}"' in body for h in headers))

# --- C: no parameter, or one that is not a [bank_code, headers] pair.
for label, query in [
    ("C1 no ?data= is 400", ""),
    ("C2 ?data= that is not JSON is 400", "?data=" + quote("['DB', ['h']]")),
    ("C3 ?data= that is not a pair is 400", "?data=" + quote("[1, 2, 3]")),
]:
    check(label, client.get("/pricing/add_header" + query).status_code == 400)

print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAIL")
sys.exit(1 if failures else 0)
