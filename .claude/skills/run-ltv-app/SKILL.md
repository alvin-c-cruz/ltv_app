---
name: run-ltv-app
description: Run, start, launch, smoke-test, or screenshot the LTV Stocks Flask app. Use when asked to run the app, bring up the dev server, verify a change works in the real running app (not just tests), drive a route end-to-end, or capture a screenshot. Covers login, the LAN-IP binding gotcha, and the ltv-stocks Excel download.
---

# Run the LTV Stocks app

Flask stock-portfolio app. Entry point `flask_app.py` → `create_app()` in `ltv_app/`.
It is a **web app**, so you drive it two ways:

- **`driver.py`** (committed here) — logs in and smoke-tests the routes PRs touch
  (home, trades, notebook, ltv-stocks) plus the LTV Stocks Excel download. This is the
  fast agent path; use it first.
- **Playwright MCP tools** — for anything visual or interactive (click a button, fill a
  form, screenshot). This repo's standing preference is Playwright, **not** the
  Claude-in-Chrome extension.

All paths below are relative to the repo root (`C:\envs\LTV\server`). Environment is
**Windows** (win32); the Bash tool runs Git Bash, so the commands below work as written.

## Prerequisites

Python 3 with the repo's deps installed (`flask`, `flask-login`, `requests`, `openpyxl`,
`pandas`). They are already present in this machine's interpreter. If starting clean:

```bash
python -m pip install -r requirements.txt
```

## Run the server

The server must be running before you drive it. Launch it (it auto-reloads on code changes,
so you rarely restart):

```bash
python flask_app.py
```

It prints e.g. `Starting host @ http://192.168.100.79:5001` and serves there.

**⚠️ It binds ONLY to the LAN IP** from `socket.gethostbyname(socket.gethostname())`,
**not** `127.0.0.1`/`localhost`. A `localhost:5001` URL returns connection-refused. Get the
real address with:

```bash
python -c "import socket; print(f'http://{socket.gethostbyname(socket.gethostname())}:5001')"
```

To keep it alive across turns while you drive it, run it as a background process rather than
a foreground `!` launch (a foreground launch exits and the browser then sees
`ERR_CONNECTION_REFUSED`).

## Run (agent path) — the driver

With the server up, smoke everything in one shot:

```bash
python .claude/skills/run-ltv-app/driver.py
```

Expected output (every line PASS, ends with `ALL PASS`):

```
Driving LTV app at http://192.168.100.79:5001

PASS  unauth / -> 302 /login?next=%2F
PASS  login as admin -> 302 /
PASS  GET / -> 200, found 'LTV Stock Management System'
PASS  GET /trades/ -> 200, found 'Trades Done'
PASS  GET /notebook/ -> 200, found 'Notebook'
PASS  GET /ltv-stocks/ -> 200, found 'LTV Stocks'
PASS  POST /ltv-stocks/download -> 200, 21,556 bytes of xlsx

ALL PASS
```

The driver derives the base URL the same way the server does; override with an argument or
the `LTV_BASE_URL` env var if needed:

```bash
python .claude/skills/run-ltv-app/driver.py http://192.168.100.79:5001
```

It logs in as `admin` and is read-only against the database (GETs + the login POST + the
report-download POST, which builds the Excel in memory).

## Run (agent path) — visual / interactive with Playwright

For anything the driver can't assert (rendering, clicking, forms), use the Playwright MCP
tools. Log in by POSTing the form or by filling the login page: navigate to the base URL,
enter `admin` / `ac1123581321` in the `username` / `password` fields, click **Login**. A
reference screenshot of the ltv-stocks page is at
`.claude/skills/run-ltv-app/ltv-stocks-page.png`.

## Run (human path)

`python flask_app.py`, then open the printed `http://<lan-ip>:5001` in a browser and log in.
Ctrl-C to stop. (Useful for a human; the driver/Playwright path is what agents should use.)

## Test

Unit/functional suite (isolated temp SQLite, does not touch production data):

```bash
pytest                                             # all
pytest tests/functional/test_ltv_stocks_active_count.py -q   # ltv-stocks only
```

## Gotchas

- **LAN-IP binding, not localhost.** See above — this is the #1 source of "refused to
  connect". Always use the `gethostbyname` address.
- **Live production database.** `instance/LTV Stocks.db` holds real financial data. The
  driver is read-only; do **not** add write flows (creating transactions/contracts) to a
  smoke run without explicit approval.
- **Credentials:** `admin` / `ac1123581321` (level 1). The user `alvin` no longer exists.
- **The `/ltv-stocks/` web page is download-only** — it renders just a date picker + Download
  button. The real report content is the **Excel** (`POST /ltv-stocks/download`), which is why
  the driver asserts on the .xlsx bytes rather than page HTML for that feature.
- **Auto-reload:** the dev server reloads on file save; verify changes against the running
  server without restarting it.
- **This skill is git-ignored.** The repo's `.gitignore` whitelists specific paths and does
  not include `.claude/`. The skill works locally (Claude Code discovers it from disk) but is
  not committed unless `!/.claude/` is added to `.gitignore`.

## Troubleshooting

- `cannot reach ... is python flask_app.py running?` / `ERR_CONNECTION_REFUSED` — the server
  isn't alive, or you used `localhost`. Start it and use the `gethostbyname` URL.
- `login POST expected redirect ... got 200` — credentials rejected (login re-renders the form
  with a flash). Confirm `admin` / `ac1123581321` against `tbl_user`.
- `download did not return an .xlsx` — the report route errored or returned HTML; check the
  server log for a traceback in `ltv_app/blueprints/ltv_stocks/`.
