"""Production entry point: the LTV app on http://127.0.0.1:5001, served by waitress.

Production runs on this PC since 30 Oct 2026, from its own checkout
(products\\ltv-app\\prod), whose instance\\config.py points DATABASE at the ledger the
legacy app shares. No debugger and no reloader here: those belong to flask_app.py, the
development server on 5002.
"""
import socket
import sys
import threading
import webbrowser

HOST = "127.0.0.1"
PORT = 5001
URL = f"http://{HOST}:{PORT}/"


def port_in_use(host=HOST, port=PORT):
    """True when something already answers on host:port."""
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def open_browser_later(url=URL, delay=1.5, opener=webbrowser.open):
    """Open the default browser on the app once, after waitress has had time to listen."""
    timer = threading.Timer(delay, opener, args=(url,))
    timer.daemon = True
    timer.start()
    return timer


def refuse_unless_loopback(host=HOST):
    """Exit unless host is this computer's own address.

    The app signs its user in by itself (AUTO_LOGIN_USER), so serving it on 0.0.0.0 or a LAN address
    would hand the ledger to anyone on the network. The app also refuses other clients itself
    (ltv_app/local_only.py); this stops a change to HOST from even getting that far.
    """
    from ltv_app.local_only import is_loopback_host
    if not is_loopback_host(host):
        sys.exit(f"Refusing to serve the LTV app on {host!r}: it must stay on this computer (127.0.0.1).")


def main():
    refuse_unless_loopback()
    if port_in_use():
        print(f"The LTV app is already running on {URL}; opening it.")
        webbrowser.open(URL)
        return

    from waitress import serve
    from ltv_app import create_app

    app = create_app()
    print(f"LTV app (production) on {URL}")
    print(f"Database: {app.config['DATABASE']}")
    open_browser_later()
    serve(app, host=HOST, port=PORT, threads=8)


if __name__ == "__main__":
    main()
