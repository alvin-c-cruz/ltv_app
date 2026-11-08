"""Verification that the app signs its user in by itself and answers only to this computer.

Alvin, 8 Nov 2026: no login screen ("auto login as admin ... since no body uses this app except this
computer"), and "be sure this is not shared via LAN". Design: docs/superpowers/specs/
2026-11-08-auto-login-local-only-design.md.

  A1 a first visit from this computer is signed in as AUTO_LOGIN_USER, and again after a restart
  A2 /login goes to the home page; /logout goes to the home page and the user is signed in again
  A3 the navbar shows no Logout link while auto-login is on
  A4 AUTO_LOGIN_USER naming no user, or None, falls back to the login (default-deny)
  L1 a client on another address is refused on every GET route, the login page, static, an unknown URL
     and a POST, and is not signed in
  L2 loopback client addresses (127.0.0.1, 127.0.0.2, ::1, ::ffff:127.0.0.1) are served
  H1 a Host that isn't this computer is refused; localhost, 127.0.0.1 and [::1] are served
  F1 Sec-Fetch-Site cross-site and same-site are refused; same-origin and none are served
  F2 from elsewhere, a whole-page GET is served; a frame, image, script, fetch or POST is refused
  O1 a POST whose Origin is another site, another port or "null" is refused; its own Origin is served
  O2 with no Origin, a POST whose Referer is another site is refused; its own Referer, or none, is served
  S1 serve.py binds to a loopback address and refuses to start on any other

Read-only: runs on a temporary copy of instance/LTV Stocks.db (the development copy), taken through SQLite's
backup API with the source opened read-only. Refused requests never reach a view; the POSTs go to a probe
route registered here, which writes nothing.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_local_only.py
"""
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from flask import Blueprint, url_for

from ltv_app import create_app

SOURCE = os.path.join(SERVER, "instance", "LTV Stocks.db")
LAN = "192.168.1.50"
failures = []


def check(label, ok, detail=""):
    print(f"  {label}: {'PASS' if ok else 'FAIL'}{'' if ok or not detail else ' -- ' + detail}")
    if not ok:
        failures.append(label)


def copy_db():
    dst_path = os.path.join(tempfile.mkdtemp(), "LTV Stocks.db")
    src = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    dst = sqlite3.connect(dst_path)
    src.backup(dst)
    src.close()
    dst.close()
    return dst_path


def user_id(db_path, username):
    con = sqlite3.connect(db_path)
    row = con.execute("SELECT id FROM tbl_user WHERE username=?", (username,)).fetchone()
    con.close()
    return None if row is None else str(row[0])


probe = Blueprint("local_only_probe", __name__)


@probe.route("/local-only-probe", methods=["GET", "POST"])
def probe_view():
    return "probe ok"


def boot(db_path, **config):
    app = create_app({"DATABASE": db_path, "WTF_CSRF_ENABLED": False, **config})
    app.register_blueprint(probe)
    return app


def signed_in_id(client):
    with client.session_transaction() as s:
        return s.get("_user_id")


DB = copy_db()
app = boot(DB)
AUTO = app.config.get("AUTO_LOGIN_USER")
admin_id = user_id(DB, AUTO) if AUTO else None

print(f"A. auto-login (AUTO_LOGIN_USER = {AUTO!r})")
check("A0 the setting names a user in the database", admin_id is not None,
      "no tbl_user row for it, so nothing else here can sign in")

client = app.test_client()
r = client.get("/")
check("A1 a first visit is served, not sent to the login", r.status_code == 200, f"status {r.status_code}")
check("A1 and it is signed in as that user", signed_in_id(client) == admin_id)

app_restarted = boot(DB)
client_r = app_restarted.test_client()
r = client_r.get("/")
check("A1 after a restart, the first visit is signed in again",
      r.status_code == 200 and signed_in_id(client_r) == admin_id, f"status {r.status_code}")

with app.test_request_context():
    home_path = url_for("home_page.home")
    logout_path = url_for("auth.logout")
    login_path = url_for("auth.login")

r = client.get(login_path)
check("A2 /login goes to the home page", r.status_code == 302 and r.headers["Location"].endswith(home_path),
      f"status {r.status_code}")
r = client.get(logout_path)
check("A2 /logout goes to the home page", r.status_code == 302 and r.headers["Location"].endswith(home_path),
      f"status {r.status_code}")
r = client.get("/")
check("A2 after /logout the user is signed in again", r.status_code == 200 and signed_in_id(client) == admin_id)

page = client.get("/").get_data(as_text=True)
check("A3 the navbar has no Logout link", f'href="{logout_path}"' not in page)

for label, value in (("A4 a setting naming no user", "no-such-user-for-this-check"), ("A4 the setting None", None)):
    fallback = boot(DB, AUTO_LOGIN_USER=value).test_client()
    r = fallback.get("/")
    check(f"{label} falls back to the login",
          r.status_code == 302 and login_path in r.headers.get("Location", "") and signed_in_id(fallback) is None,
          f"status {r.status_code}")
    page = fallback.get(login_path).get_data(as_text=True)
    check(f"{label}: the login page is served", 'name="password"' in page)

print("\nL. client address")
SAMPLES = {"ref_num": 1, "contract_ref": 1, "period_ref": 1, "bank_id": "x", "code": "x", "transaction_type": "x",
           "source": "x", "filename": "x.css", "id": 1, "user_id": 1, "year": 2026, "month": 1}
lan = app.test_client()
probed, served = 0, []
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if "GET" not in rule.methods:
        continue
    try:
        path = rule.build({a: SAMPLES.get(a, 1) for a in rule.arguments}, append_unknown=False)[1]
    except Exception:
        continue
    probed += 1
    status = lan.get(path, environ_base={"REMOTE_ADDR": LAN}).status_code
    if status != 403:
        served.append(f"{rule.endpoint} {status}")
check(f"L1 every GET route refused to {LAN} ({probed} probed)", probed > 0 and not served, ", ".join(served[:5]))
for label, call in (("an unknown URL", lambda: lan.get("/no-such-page", environ_base={"REMOTE_ADDR": LAN})),
                    ("a POST", lambda: lan.post("/local-only-probe", environ_base={"REMOTE_ADDR": LAN})),
                    ("no client address", lambda: lan.get("/", environ_base={"REMOTE_ADDR": ""}))):
    status = call().status_code
    check(f"L1 {label} is refused", status == 403, f"status {status}")
check("L1 the refused client was not signed in", signed_in_id(lan) is None)

for addr in ("127.0.0.1", "127.0.0.2", "::1", "::ffff:127.0.0.1"):
    status = app.test_client().get("/local-only-probe", environ_base={"REMOTE_ADDR": addr}).status_code
    check(f"L2 {addr} is served", status == 200, f"status {status}")

print("\nH. Host")
for host, want in (("http://evil.example:5001", 403), ("http://192.168.1.50:5001", 403),
                   ("http://localhost.evil.example:5001", 403), ("http://127.0.0.1.evil.example", 403),
                   ("http://127.0.0.1:5001", 200), ("http://localhost:5001", 200), ("http://[::1]:5001", 200),
                   ("http://LOCALHOST:5001", 200)):
    status = app.test_client().get("/local-only-probe", base_url=host).status_code
    check(f"H1 Host {host[7:]} -> {want}", status == want, f"status {status}")

print("\nF. fetch metadata")
for site, want in (("cross-site", 403), ("same-site", 403), ("same-origin", 200), ("none", 200)):
    status = app.test_client().get("/local-only-probe", headers={"Sec-Fetch-Site": site}).status_code
    check(f"F1 Sec-Fetch-Site {site} -> {want}", status == want, f"status {status}")
# A whole-page GET from elsewhere is served (Claude in Chrome's navigations arrive as cross-site even from
# the app's own page, and the root session drives the app that way); anything else from elsewhere is not.
for method, site, mode, dest, want in (("GET", "cross-site", "navigate", "document", 200),
                                       ("GET", "same-site", "navigate", "document", 200),
                                       ("GET", "cross-site", "navigate", "iframe", 403),
                                       ("GET", "cross-site", "no-cors", "image", 403),
                                       ("GET", "cross-site", "cors", "empty", 403),
                                       ("GET", "same-site", "no-cors", "script", 403),
                                       ("POST", "cross-site", "navigate", "document", 403)):
    headers = {"Sec-Fetch-Site": site, "Sec-Fetch-Mode": mode, "Sec-Fetch-Dest": dest}
    status = app.test_client().open("/local-only-probe", method=method, headers=headers).status_code
    check(f"F2 {method} {site} {mode}/{dest} -> {want}", status == want, f"status {status}")

print("\nO. Origin and Referer on a POST")
BASE = "http://127.0.0.1:5001"
for origin, want in (("http://evil.example", 403), ("null", 403), ("http://127.0.0.1:9000", 403),
                     ("http://localhost:5001", 403), ("https://127.0.0.1:5001", 403), (BASE, 200)):
    status = app.test_client().post("/local-only-probe", base_url=BASE, headers={"Origin": origin}).status_code
    check(f"O1 Origin {origin} -> {want}", status == want, f"status {status}")
for referer, want in (("http://evil.example/page", 403), ("http://127.0.0.1:9000/x", 403),
                      (BASE + "/blocked-unblocked/", 200), (None, 200)):
    headers = {} if referer is None else {"Referer": referer}
    status = app.test_client().post("/local-only-probe", base_url=BASE, headers=headers).status_code
    check(f"O2 Referer {referer} -> {want}", status == want, f"status {status}")
status = app.test_client().get("/local-only-probe", base_url=BASE,
                               headers={"Origin": "http://evil.example"}).status_code
check("O1 a GET is not judged by its Origin (fetch metadata covers GETs)", status == 200, f"status {status}")

print("\nS. serve.py")
import serve  # noqa: E402  (no side effects at import; main() runs only as a script)

check(f"S1 serve.py binds to a loopback address ({serve.HOST})", serve.HOST in ("127.0.0.1", "localhost", "::1"))
for host in ("0.0.0.0", "192.168.1.50", "", "::"):
    try:
        serve.refuse_unless_loopback(host)
        refused = False
    except SystemExit:
        refused = True
    check(f"S1 serve.py refuses to start on {host!r}", refused)
for host in ("127.0.0.1", "localhost", "::1"):
    try:
        serve.refuse_unless_loopback(host)
        started = True
    except SystemExit:
        started = False
    check(f"S1 serve.py starts on {host!r}", started)

if failures:
    print(f"\n{len(failures)} FAIL")
    sys.exit(1)
print("\nPASS")
