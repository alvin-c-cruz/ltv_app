"""Serve ltv_app against the synthetic demo database.

Never touches instance/"LTV Stocks.db" -- DATABASE is overridden to the demo
copy built by scripts/make_demo_db.py, and instance/config.py is bypassed
(create_app skips from_pyfile when a test_config is supplied).

    ./venv/Scripts/python.exe scripts/run_demo_app.py [--port 5055]

Login: admin / demo1234 (superuser), analyst / demo1234 (staff).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "instance", "demo", "LTV Stocks.db",
)


def build_app(db_path=DEFAULT_DB):
    from ltv_app import create_app
    return create_app(test_config={
        "SECRET_KEY": "demo-secret-key-not-for-production",
        "DATABASE": db_path,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": False,
    })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args()

    if not os.path.exists(args.db):
        sys.exit("Demo database not found: {}\nRun scripts/make_demo_db.py first."
                 .format(args.db))

    app = build_app(args.db)
    print("Demo DB : {}".format(args.db))
    print("Serving : http://127.0.0.1:{}".format(args.port))
    from waitress import serve
    serve(app, host="127.0.0.1", port=args.port, threads=8)


if __name__ == "__main__":
    main()
