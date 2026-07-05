#!/usr/bin/env python3
"""Smoke-drive the running LTV Stocks Flask app.

Logs in as admin and exercises the routes that PRs to this repo actually
touch (home dashboard, trades, notebook, ltv-stocks), then downloads the
LTV Stocks Excel report and checks it is a real .xlsx. Prints PASS/FAIL per
step and exits non-zero on the first failure.

Usage:
    python .claude/skills/run-ltv-app/driver.py [BASE_URL]

BASE_URL defaults to http://<gethostbyname>:5001 — the SAME address
flask_app.py binds to (socket.gethostbyname(socket.gethostname())). The dev
server binds ONLY to that LAN IP, NOT to 127.0.0.1 / localhost, so a
localhost URL will fail to connect. Override with an argument or the
LTV_BASE_URL env var if the host differs.

Prereqs: the server must already be running (`python flask_app.py`) and the
`requests` package installed (it is, in this repo's interpreter).

Read-only against the DB: only GETs pages, POSTs the login form, and POSTs
the report-download form (which generates an Excel in memory — no writes).
"""
import os
import socket
import sys

import requests

USERNAME = "admin"
PASSWORD = "ac1123581321"

# (path, marker string expected in the authenticated HTML)
PAGES = [
    ("/",            "LTV Stock Management System"),
    ("/trades/",     "Trades Done"),
    ("/notebook/",   "Notebook"),
    ("/ltv-stocks/", "LTV Stocks"),
]

XLSX_MAGIC = b"PK\x03\x04"  # every .xlsx is a zip; starts with this


def base_url() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].rstrip("/")
    if os.environ.get("LTV_BASE_URL"):
        return os.environ["LTV_BASE_URL"].rstrip("/")
    host = socket.gethostbyname(socket.gethostname())
    return f"http://{host}:5001"


def ok(msg):
    print(f"PASS  {msg}")


def die(msg):
    print(f"FAIL  {msg}")
    sys.exit(1)


def main():
    url = base_url()
    print(f"Driving LTV app at {url}\n")
    s = requests.Session()

    # 1. Unauthenticated root must redirect to /login.
    try:
        r = s.get(url + "/", allow_redirects=False, timeout=10)
    except requests.exceptions.RequestException as e:
        die(f"cannot reach {url} — is `python flask_app.py` running? ({e})")
    if r.status_code not in (301, 302) or "/login" not in r.headers.get("Location", ""):
        die(f"unauth / expected redirect to /login, got {r.status_code} "
            f"{r.headers.get('Location')!r}")
    ok(f"unauth / -> {r.status_code} {r.headers['Location']}")

    # 2. Log in.
    r = s.post(url + "/login", data={"username": USERNAME, "password": PASSWORD},
               allow_redirects=False, timeout=10)
    if r.status_code not in (301, 302):
        die(f"login POST expected redirect on success, got {r.status_code} "
            f"(check credentials {USERNAME}/****)")
    ok(f"login as {USERNAME} -> {r.status_code} {r.headers.get('Location')}")

    # 3. Authenticated pages return 200 and contain their marker.
    for path, marker in PAGES:
        r = s.get(url + path, timeout=15)
        if r.status_code != 200:
            die(f"GET {path} -> {r.status_code} (expected 200)")
        if marker not in r.text:
            die(f"GET {path} 200 but marker {marker!r} not found in body")
        ok(f"GET {path} -> 200, found {marker!r}")

    # 4. LTV Stocks Excel download returns a real .xlsx.
    r = s.post(url + "/ltv-stocks/download", data={"report_date": "2026-07-02"},
               timeout=30)
    if r.status_code != 200:
        die(f"POST /ltv-stocks/download -> {r.status_code} (expected 200)")
    if not r.content.startswith(XLSX_MAGIC):
        die(f"download did not return an .xlsx (first bytes {r.content[:8]!r})")
    ok(f"POST /ltv-stocks/download -> 200, {len(r.content):,} bytes of xlsx")

    print("\nALL PASS")


if __name__ == "__main__":
    main()
