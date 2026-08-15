"""Verification of session cookie attributes.

SESSION_COOKIE_SECURE is deliberately NOT set in code -- it would stop the
cookie being sent over http://127.0.0.1:5001 and break local dev login. It is
set in PythonAnywhere's instance/config.py instead, so this script expects it
to be False locally and fails if it is True.

SameSite matters more than usual here: no CSRFProtect is registered in
create_app(), so Lax is the only barrier to a cross-site state-changing POST.

Run: server/.venv/Scripts/python.exe scripts/verify_session_cookie.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from flask import session

from ltv_app import create_app

app = create_app()


@app.route("/__cookie_probe")
def _cookie_probe():
    """Local-only probe route -- writes to the session so a cookie is issued.

    Registered on this script's app instance only, never on the real app.
    """
    session["probe"] = 1
    return "ok"


failures = []

samesite = app.config["SESSION_COOKIE_SAMESITE"]
httponly = app.config["SESSION_COOKIE_HTTPONLY"]
secure = app.config["SESSION_COOKIE_SECURE"]

print(f"SESSION_COOKIE_SAMESITE : {samesite!r}")
print(f"SESSION_COOKIE_HTTPONLY : {httponly}")
print(f"SESSION_COOKIE_SECURE   : {secure}  (expected False locally)")

if samesite != "Lax":
    failures.append(f"SESSION_COOKIE_SAMESITE is {samesite!r}, expected 'Lax'")
if not httponly:
    failures.append("SESSION_COOKIE_HTTPONLY is not True")
if secure:
    failures.append("SESSION_COOKIE_SECURE is True locally -- this breaks "
                    "login over http://127.0.0.1:5001; set it only on PythonAnywhere")

header = app.test_client().get("/__cookie_probe").headers.get("Set-Cookie", "")
print(f"Set-Cookie              : {header}")

if "SameSite=Lax" not in header:
    failures.append("Set-Cookie lacks SameSite=Lax")
if "HttpOnly" not in header:
    failures.append("Set-Cookie lacks HttpOnly")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
