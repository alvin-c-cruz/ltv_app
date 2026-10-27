"""Regression harness: the dead /forecasts/ and /transaction-list/ routes are gone,
and no page still points at them.

Three registered routes answered every request with a 500 and nothing linked to
them (BUGS.md 2026-10-27): /forecasts/ rendered a template that was never written,
/forecasts/transaction_forecast filled a workbook template with no CBSG sheet,
and /transaction-list/ called Transaction.query, Flask-SQLAlchemy from the old
prototype. Alvin chose on 2026-10-27 to remove them rather than repair them.

  R1  each of the three URLs is a 404, not a 500;
  R2  no endpoint of the forecasts or transaction_list blueprints is registered;
  R3  every parameterless GET page answers below 500, so no template or view is
      left building a URL to a removed endpoint (that would raise BuildError).

Runs on a throwaway copy of instance/LTV Stocks.db; only GETs are sent, and none
of these views writes on a GET. Uses LOGIN_DISABLED so the requests reach the views.

Run: server/.venv/Scripts/python.exe scripts/verify_removed_routes.py
"""
import gc
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

REMOVED_URLS = ("/forecasts/", "/forecasts/transaction_forecast", "/transaction-list/")
REMOVED_BLUEPRINTS = ("forecasts", "transaction_list")


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), tmp)
    ok = True
    try:
        app = create_app({"DATABASE": tmp, "LOGIN_DISABLED": True})
        client = app.test_client()

        for url in REMOVED_URLS:
            status = client.get(url).status_code
            passed = status == 404
            ok &= passed
            print(f"  R1 {url} is 404: {'PASS' if passed else f'FAIL  ({status})'}")

        left = sorted(rule.endpoint for rule in app.url_map.iter_rules()
                      if rule.endpoint.split(".")[0] in REMOVED_BLUEPRINTS)
        ok &= not left
        print(f"  R2 no forecasts / transaction_list endpoint registered: "
              f"{'PASS' if not left else 'FAIL  ' + ', '.join(left)}")

        crashed = []
        pages = sorted(rule.rule for rule in app.url_map.iter_rules()
                       if "GET" in rule.methods and not rule.arguments
                       and not rule.rule.startswith("/static"))
        for url in pages:
            status = client.get(url).status_code
            if status >= 500:
                crashed.append(f"{url} ({status})")
        ok &= not crashed
        print(f"  R3 all {len(pages)} parameterless GET pages answer below 500: "
              f"{'PASS' if not crashed else 'FAIL  ' + ', '.join(crashed)}")
    finally:
        # get_db() never closes its per-request connections; collect them so
        # Windows lets go of the file (WinError 32 otherwise).
        gc.collect()
        os.unlink(tmp)

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
