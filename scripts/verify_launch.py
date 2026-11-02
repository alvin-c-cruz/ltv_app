"""Regression harness: serve.py, the production entry point, opens the browser once and
never on import, and leaves a port that is already serving alone; flask_app.py is the
development server on 5002.

Alvin, 30 Oct 2026: "the legacy localhost app opens a browser automatically upon launch.
can you do that with ltv_app?" (BUGS.md 2026-11-02). Nothing here starts a server or
touches a database: importing serve builds no app.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_launch.py
"""
import os
import socket
import sys
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")


opened = []
real_open = webbrowser.open
webbrowser.open = lambda *args, **kwargs: opened.append(args)
try:
    import serve
    _case("S1 importing serve opens no browser", opened, [])

    got = []
    timer = serve.open_browser_later(delay=0, opener=got.append)
    timer.join(2)
    _case("S2 the browser opens once, on the app", got, ["http://127.0.0.1:5001/"])

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        _case("S3 a port already serving is seen as in use", serve.port_in_use(port=port), True)
    _case("S4 a closed port is free", serve.port_in_use(port=port), False)
finally:
    webbrowser.open = real_open

with open(os.path.join(SERVER, "flask_app.py"), encoding="utf-8") as f:
    source = f.read()
_case("S5 flask_app.py is the dev server on 5002", "port = 5002" in source, True)
_case("S6 flask_app.py opens no browser", "webbrowser" in source, False)

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
