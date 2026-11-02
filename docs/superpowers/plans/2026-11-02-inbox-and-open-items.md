# LTV app: the 30 Oct inbox and every open item — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clear the eight 30 Oct work orders, the 21 Sep term-sheet order and the open `BUGS.md` items. Start by
separating production from development, now that production runs on this PC.

**Architecture:**
- **Production** moves to its own detached git worktree, `products\ltv-app\prod\`, at a released commit. It is
  served by a new `serve.py` (waitress, 127.0.0.1:5001, no debugger) on the shared ledger.
- **Development** stays in `app\`: `flask_app.py` on port 5002, against the development copy.
- **Each fix** is a small change in the blueprint that owns the output, with a `scripts/verify_<topic>.py` harness
  that works out its expectations from the database at runtime.
- **The two large items** (Blocked Unblocked, term-sheet lifecycle) end in a spec and a plan of their own, after
  Alvin's answers.

**Tech Stack:** Flask 3.1, raw `sqlite3`, openpyxl 3.1.5, waitress 3.0.2 (new), Windows 11 / PowerShell 5.1.

**Spec:** the work orders in the product inbox `C:\envs\assistant\products\ltv-app\app-docs\bug-reports\` (local
repository, not public; they hold the client figures this plan leaves out):
- `2026-10-30-production-moves-local.md`
- `2026-10-30-notebook-hand-edits.md` (+ evidence folder)
- `2026-10-30-ltv-stocks-print-to-column-x.md` (+ evidence folder)
- `2026-10-30-maris-downloads-leave-out-short-trades.md`
- `2026-10-30-no-gain-loss-on-transfers.md`
- `2026-10-30-gain-loss-workbook-math.md` (+ evidence folder)
- `2026-10-30-open-browser-on-launch.md`
- `2026-10-30-blocked-unblocked-from-the-app.md` (+ evidence folder)
- `2026-09-21-term-sheet-lifecycle.md`
- `app/BUGS.md`, open entries: Medium 2026-09-06 (client figures in a public repo), Medium 2026-08-15 (one slow
  request freezes the site), Low 2026-10-27 (`verify_gain_loss_refactor` stale), Low 2026-09-06 (narrative vs balance
  basis).

## Global Constraints

- **This repository is public.** No client figure goes into any tracked file: this plan, a harness, a comment or a
  commit message. That covers share counts, prices, gains and balances. A harness finds its fixture at runtime,
  derives what to expect from the database, and its `_case()` prints no value on FAIL (model:
  `scripts/verify_zero_position_rows.py`).
- **The shared ledger is production:** `C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db`. Never run a
  harness, script or dev server against it.
  - Until Task 4 is done, `app\instance\config.py` points every bare `create_app()` at it. Until then, run only
    harnesses that pass `create_app({"DATABASE": <path>, "LOGIN_DISABLED": True})`.
  - Any other harness is run with the ledger's SHA-256 taken before and after (Task 2, step 3).
- Run everything from `C:\envs\assistant\products\ltv-app\app` with `..\venv\Scripts\python.exe`. Harness headers
  that say `server/.venv/...` are the old layout; ignore them.
- New harnesses run on a **temporary copy** of `instance\LTV Stocks.db`, made in the harness with
  `shutil.copy` into `tempfile.mkdtemp()`.
- `<scratchpad>` means the executing session's scratchpad directory, never a folder in this repository. One-off
  scripts that read client files (Alvin's workbooks, backups) live there and are never committed.
- Commits are `fix(<area>): …` / `feat(<area>): …`. A release is a separate `Bump version to 4.0.x` commit that
  changes only `VERSION`. Every commit message ends with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Push to GitHub, deploy and restart production only on Alvin's own request, one request per action.** A
  plan approval is not one.
- Every task updates its `app/BUGS.md` entry (Task 1 creates them): **Status:** Fixed with the commit, or what is
  left.
- Where a work order says "Alvin to say", build nothing until he has said. Those points are in the Decisions table.
- LibreOffice is not installed, so formulas openpyxl writes stay unevaluated until Excel opens the file.
  - Harnesses check formula structure.
  - Arithmetic is tied out once, by Excel COM, in the scratchpad.

## Decisions to ask Alvin

Ask D1 and D2 before Task 3. Ask the rest as a numbered list in chat when their task comes up; record each
answer in the task's `BUGS.md` entry.

| # | Question | Recommended default | Blocks |
|---|---|---|---|
| D1 | Run production from its own checkout (`prod\`, a released commit), served by waitress without the debugger, with development moving to port 5002 on the development copy? | Yes | Tasks 3–4 |
| D2 | A launcher, `app-ops\start-ltv.bat`, that starts ltv_app and the legacy app, each in its own window, and skips one already running? | Yes | Task 4, step 10 |
| D3 | larrylilia on PythonAnywhere: switch it off, and stop extending it with the student sites? (LTV PENDING #149) | His call. Relay it to the root session. | nothing here |
| D4 | LTV Stocks prints only to X, so a knock-out on the report date has no printed "KO" marker; the row is still red and the price bold. Is that enough? | Build to his instruction; ask | a follow-up to Task 7 only |
| D5 | Transfers: should a transfer carry the sender's exact running average as its price? | Ask; this plan changes no price | nothing here |
| D6 | Gain Loss. (a) Do short sales and covers get columns on SUM-HK / SUM-SG (their own, the Spot columns, or none)? (b) Does 6.06 HKD per SGD stay fixed? (c) Do AUD 5.5 and JPY 0.07 stay? (d) Do Top Sheet and Marissa Page get SHK2 and Nomura rows? | (a) none until he says; (b) fixed; (c) kept; (d) ask | (a), (d): new work; (b), (c): Task 12 as written |
| D7 | Blocked Unblocked. Which output: `.xlsm`, `.xlsx`, the two PDFs, or all? His rulings on the workbook faults in its section 4. Is the Shares Blocked basis (holdings including that day's fixings) confirmed? | Ask | Task 14 |
| D8 | `/maris/`: label short trades with the ledger's type names, "Sell (Short)" and "Buy (Pay Short)", like every other row? | Yes | nothing (Task 8 builds this) |
| D9 | Public repo: old harness figures stay in git history and in the 17 Jul plan, and `report_data.py` names the accounts. Leave it, rewrite history, or make the repo private? | His call. A history rewrite needs his explicit word for that step. | nothing here |
| D10 | The trade narrative and the balance beside it use different date bases (BUGS Low, 6 Sep). Settle which one governs? | Leave open | nothing here |
| D11 | Term sheets: which gaps from Task 13's audit to build | after Task 13 | a new plan |

## Order and releases

- **Phase A, separate production:** Tasks 1–4. Release **4.0.41** in Task 4; production moves to `prod\` at it.
- **Phase B, notebook:** Tasks 5–6.
- **Phase C, reports:** Tasks 7–12.
- **Phase D, studies:** Tasks 13–14. Their deliverables are an audit and a spec, not code.
- **Phase E:** Task 15, release **4.0.42**, put into production on this PC on Alvin's request.
  **Nothing goes to PythonAnywhere** (Alvin, 2 Nov 2026: "we will not deploy this to PA anymore. our local copy is
  our main database"). Here, "deploy" always means switching `prod\` to the release and restarting it.

Tasks 5–12 are independent of one another. Task 9 must come before Tasks 10–12, because it reads the gain-loss
baseline before they change it.

---

### Task 1: Log the inbox in BUGS.md

**Files:**
- Modify: `app/BUGS.md` (git-ignored, holds client detail)
- Commit in the product repository: `app-docs/bug-reports/2026-10-30-*.md`

- [ ] **Step 1: Add one entry per work order.** Each goes under its severity, in the house form: `### 2026-11-02 —
  <symptom>`, then **Area:**, **Severity:**, **Found while:** (the work order's file name and Alvin's quoted words),
  and **Status:** Open, with "Plan: docs/superpowers/plans/2026-11-02-inbox-and-open-items.md, Task N".

  | Severity | Heading | Task |
  |---|---|---|
  | High | Production runs this working tree with the debugger on, and bare `create_app()` opens the production ledger | 2–4 |
  | High | Gain Loss SUMMARY has no SHK No. 2 row and no Nomura section, so their gains miss the Total | 11 |
  | Medium | Gain Loss: opening-position USD value divides by `hkd_per_usd` on every sheet; SGD rates disagree | 12 |
  | Medium | `/maris/` downloads leave out Short Book trades | 8 |
  | Medium | The transaction list books a gain or loss on transfers | 10 |
  | Medium | LTV Stocks prints A:AJ; Alvin wants A:X, one page wide | 7 |
  | Medium | Notebook ships on paper 10001 (Long), but its pages are planned for 10000 (Notebook) | 5 |
  | Medium | Term sheets: no Done status or completion date; Inactive doubles as "hidden" (21 Sep) | 13 |
  | Low | Notebook KO blocks leave the closing price and date blank; Alvin types them | 6 |
  | Low | ltv_app does not open the browser on launch (the legacy app does) | 3 |
  | Low | Blocked Unblocked: produce the weekly file and its two PDFs from the app (study) | 14 |

- [ ] **Step 2: Commit the work orders in the product repository.** These are the `.md` files only; the evidence
  folders hold client workbooks and figures and stay untracked.

```powershell
git -C C:\envs\assistant\products\ltv-app add app-docs/bug-reports/2026-10-30-*.md
git -C C:\envs\assistant\products\ltv-app commit -m "Inbox: the eight 30 Oct 2026 work orders" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Verify and commit the notebook page layout (already written, uncommitted)

The page-layout work of 26–27 Oct is in the working tree, uncommitted. `BUGS.md` 2026-10-26, item 2, says it is
done and its harness passes. Production ran it from 30 Oct. It needs proving, then committing.

**Files:**
- Commit: `ltv_app/blueprints/notebook/extensions/create_notebook.py` (modified), `scripts/verify_notebook_page_layout.py`
  (new), `scripts/verify_notebook_transfer_opening.py` (modified: skips a repeated "Transfer of Stocks" heading)

- [ ] **Step 1: Know which snapshot the development copy is.**

```powershell
(Get-FileHash 'instance\LTV Stocks.db').Hash
(Get-FileHash 'C:\envs\assistant\clients\ltv\backups\LTV Stocks 2026-10-30-1355.db').Hash
```
Expected: equal, so the copy is the 30 Oct 13:55 pull. If they differ, note which backup it matches, and test on it
anyway. The point is to know the date.

- [ ] **Step 2: Run the two harnesses that boot on their own database.**

```powershell
..\venv\Scripts\python.exe scripts\verify_notebook_page_layout.py
..\venv\Scripts\python.exe scripts\verify_notebook_page_padding.py
```
Expected: `RESULT: ALL PASS` from each.

- [ ] **Step 3: Run the two that boot through a bare `create_app()`, proving the ledger is untouched.** Their boot
  runs the idempotent `_ensure_*` against the configured database, the ledger, before they switch to their copy.

```powershell
$ledger = 'C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db'
$before = (Get-FileHash $ledger).Hash
..\venv\Scripts\python.exe scripts\verify_notebook_short_book.py
..\venv\Scripts\python.exe scripts\verify_notebook_transfer_opening.py
$after = (Get-FileHash $ledger).Hash
"ledger unchanged: $($before -eq $after)"
```
Expected: both ALL PASS, and `ledger unchanged: True`. If the hash changed, stop and report. Do not run any other
bare harness until Task 4.

- [ ] **Step 4: Check the 30 Oct case against Alvin's hand-finished file.** Write
  `<scratchpad>\nb_1030_compare.py` (client data, never in the repo):

```python
import io, sys
sys.path.insert(0, r"C:\envs\assistant\products\ltv-app\app")
from openpyxl import load_workbook
from ltv_app import create_app

DB = r"C:\envs\assistant\products\ltv-app\app\instance\LTV Stocks.db"
ALVIN = (r"C:\envs\assistant\products\ltv-app\app-docs\bug-reports\2026-10-30-notebook-hand-edits"
         r"\2026-10-30 notebook - Alvin edited 13-32.xlsx")
app = create_app({"DATABASE": DB, "LOGIN_DISABLED": True})
gen = load_workbook(io.BytesIO(app.test_client().get("/notebook/generate/2026-10-30").get_data()))["notebook"]
alv = load_workbook(ALVIN)["notebook"]
diffs = [f"{c}{r}" for r in range(41, 74) for c in "ABCDEFGHIJKLMNOPQ"
         if gen[f"{c}{r}"].value != alv[f"{c}{r}"].value]
merges = lambda ws: sorted(str(m) for m in ws.merged_cells.ranges if m.min_row >= 41)
print("cells differing in rows 41-73:", diffs)
print("merges equal:", merges(gen) == merges(alv))
print("print areas:", gen.print_area, "|", alv.print_area)
```
Run: `..\venv\Scripts\python.exe <scratchpad>\nb_1030_compare.py`
Expected:
- the only differing cells are the `O` cells under each red "Closing" label (KO closings, Task 6);
- merges equal: True;
- both print areas are `'notebook'!$A$1:$Q$73`.

Anything else differing is a layout defect: stop and investigate it with superpowers:systematic-debugging.

- [ ] **Step 5: Review the diff and commit.**

```powershell
git diff --stat
git add ltv_app/blueprints/notebook/extensions/create_notebook.py scripts/verify_notebook_page_layout.py scripts/verify_notebook_transfer_opening.py
git commit -m "feat(notebook): repeat the account heading at a page start; never split a line item across pages" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: BUGS.md.** In the 2026-10-26 notebook entry: "Item 2 committed `<sha>`". Leave the release to Task 4.

---

### Task 3: `serve.py`, the production entry point; the dev server moves to 5002 (needs D1)

The open-browser work order asked `flask_app.py` to open the browser. Once production is `serve.py`, that is where
Alvin launches, so the browser opens there. The dev server opens none, because Claude starts it in the background
and a tab would pop up on Alvin's screen. Waitress has no reloader, so it opens exactly once.

**Files:**
- Create: `serve.py`
- Modify: `flask_app.py` (port 5002)
- Modify: `.gitignore` (whitelist `serve.py`; the root rule `/*` ignores every top-level file not listed)
- Modify: `requirements.txt` (add `waitress==3.0.2`)
- Test: `scripts/verify_launch.py`

**Interfaces:**
- Produces: `serve.HOST = "127.0.0.1"`, `serve.PORT = 5001`, `serve.URL = "http://127.0.0.1:5001/"`,
  `serve.open_browser_later(url=URL, delay=1.5, opener=webbrowser.open) -> threading.Timer`,
  `serve.port_in_use(host=HOST, port=PORT) -> bool`, `serve.main()`. Task 4 runs `serve.py`.

- [ ] **Step 1: Write the failing harness** `scripts/verify_launch.py`:

```python
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
```

- [ ] **Step 2: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_launch.py`
  Expected: `ModuleNotFoundError: No module named 'serve'`.

- [ ] **Step 3: Install waitress and pin it.**

```powershell
..\venv\Scripts\python.exe -m pip install waitress==3.0.2
```
Append `waitress==3.0.2` to `requirements.txt`, after `pytest==8.3.4`.

- [ ] **Step 4: Write `serve.py`.**

```python
"""Production entry point: the LTV app on http://127.0.0.1:5001, served by waitress.

Production runs on this PC since 30 Oct 2026, from its own checkout
(products\\ltv-app\\prod), whose instance\\config.py points DATABASE at the ledger the
legacy app shares. No debugger and no reloader here: those belong to flask_app.py, the
development server on 5002.
"""
import socket
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


def main():
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
```

- [ ] **Step 5: Move the dev server to 5002.** In `flask_app.py`, replace `    port = 5001` with `    port = 5002`.

- [ ] **Step 6: Whitelist `serve.py`.** In `.gitignore`, under `!flask_app.py`, add `!serve.py`.

- [ ] **Step 7: Run the harness.**
  Run: `..\venv\Scripts\python.exe scripts\verify_launch.py`
  Expected: S1–S6 PASS, `RESULT: ALL PASS`.

- [ ] **Step 8: Commit.**

```powershell
git status --short   # serve.py must show as new, not ignored
git add serve.py flask_app.py .gitignore requirements.txt scripts/verify_launch.py
git commit -m "feat(app): serve.py runs production under waitress and opens the browser once; dev server on 5002" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Run production from its own checkout (needs D1; launcher needs D2)

**Files:**
- Modify: `VERSION` → `4.0.41` (release commit)
- Create, outside the repo: `C:\envs\assistant\products\ltv-app\prod\` (detached worktree), with
  `prod\instance\config.py` (untracked)
- Modify: `app\instance\config.py` (untracked: drop the `DATABASE` line)
- Product repo: modify `.gitignore` (add `prod/`), `CLAUDE.md` ("Where it runs", "Commands", "Deploying"); create
  `app-ops\start-ltv.bat`
- Client record: `C:\envs\assistant\clients\ltv\PENDING.md`, **Last session**
- Product memory: delete `deploy-pa-signin-and-checks.md` and its `MEMORY.md` line (it describes the PythonAnywhere
  deploy, which no longer exists)

**Interfaces:**
- Consumes: `serve.py` (Task 3).

- [ ] **Step 1: Release 4.0.41.** Set `VERSION` to `4.0.41`, then:

```powershell
git add VERSION
git commit -m "Bump version to 4.0.41" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
$release = git rev-parse HEAD
```

- [ ] **Step 2: Make sure neither app is running.**

```powershell
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 5001,9000 }
```
Expected: nothing. If production is running, ask Alvin to close it. Never stop a process he started without his
word.

- [ ] **Step 3: Back up the ledger** (root convention: a dated copy, taken with neither app writing).

```powershell
$ledger = 'C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db'
$copy = "C:\envs\assistant\clients\ltv\backups\LTV Stocks $(Get-Date -Format 'yyyy-MM-dd-HHmm').db"
Copy-Item $ledger $copy
(Get-FileHash $ledger).Hash -eq (Get-FileHash $copy).Hash
```
Expected: `True`.

- [ ] **Step 4: Create the production worktree.**

```powershell
git -C C:\envs\assistant\products\ltv-app\app worktree add --detach C:\envs\assistant\products\ltv-app\prod $release
```
Add `prod/` to `C:\envs\assistant\products\ltv-app\.gitignore`, under `app/`.

- [ ] **Step 5: Give production its config, without printing the key.** It keeps the same `SECRET_KEY`, so
  Alvin's login cookie stays valid.

```powershell
$key = (Select-String -Path 'instance\config.py' -Pattern '^SECRET_KEY').Line
$lines = @($key, '',
  '# Production since 30 Oct 2026: the shared LTV ledger, also read by the legacy app (port 9000).',
  "DATABASE = r'C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db'")
[System.IO.File]::WriteAllLines('C:\envs\assistant\products\ltv-app\prod\instance\config.py', $lines)
```

- [ ] **Step 6: Point development back at its own copy.** Edit `app\instance\config.py`: delete the two
  `# 30 Oct 2026 (Alvin): …` comment lines and the `DATABASE = r'…legacy\instance\LTV Stocks.db'` line, and add:
  `# Development copy: instance\LTV Stocks.db (the default). Production's config is ..\prod\instance\config.py.`

- [ ] **Step 7: Verify each checkout's database.**

```powershell
..\venv\Scripts\python.exe -c "from ltv_app import create_app; print(create_app().config['DATABASE'])"
Push-Location C:\envs\assistant\products\ltv-app\prod
..\venv\Scripts\python.exe -c "from ltv_app import create_app; print(create_app().config['DATABASE'])"
Pop-Location
```
Expected:
- the first prints `...\products\ltv-app\app\instance\LTV Stocks.db`;
- the second prints `C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db`.

Booting production runs only the idempotent `_ensure_*`, exactly as a production start does.

- [ ] **Step 8: Show waitress serves two requests at once** (closes BUGS Medium 2026-08-15, which was about
  PythonAnywhere's single worker). Write `<scratchpad>\concurrency.py`:

```python
import os, shutil, sys, tempfile, threading, time, urllib.parse, urllib.request
sys.path.insert(0, r"C:\envs\assistant\products\ltv-app\app")
from waitress.server import create_server
from ltv_app import create_app

tmp = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(r"C:\envs\assistant\products\ltv-app\app\instance\LTV Stocks.db", tmp)
app = create_app({"DATABASE": tmp, "LOGIN_DISABLED": True})
server = create_server(app, host="127.0.0.1", port=5003, threads=8)
threading.Thread(target=server.run, daemon=True).start()
time.sleep(1)

def report():
    form = urllib.parse.urlencode({"date_from": "2026-01-01", "date_to": "2026-10-30",
                                   "bank_ref": 0, "code_ref": 0}).encode()
    urllib.request.urlopen("http://127.0.0.1:5003/gain-loss/", data=form, timeout=180).read()

slow = threading.Thread(target=report)
t0 = time.time(); slow.start(); time.sleep(0.5)
t1 = time.time(); urllib.request.urlopen("http://127.0.0.1:5003/bank/", timeout=30).read()
print(f"a page while the report builds: {time.time() - t1:.2f}s")
slow.join(); print(f"the report: {time.time() - t0:.2f}s")
server.close()
```
Run: `..\venv\Scripts\python.exe <scratchpad>\concurrency.py`
Expected: the page answers in well under a second while the report takes several seconds. In `BUGS.md`, move the
2026-08-15 entry to Fixed: "No longer applies since 2 Nov 2026: production is waitress with 8 threads on this PC.
PythonAnywhere's single uWSGI worker is gone. Measured: <times>."

- [ ] **Step 9: Start production and check its version.**

```powershell
Start-Process -FilePath C:\envs\assistant\products\ltv-app\venv\Scripts\python.exe -ArgumentList serve.py -WorkingDirectory C:\envs\assistant\products\ltv-app\prod
Start-Sleep -Seconds 3
(curl.exe -sL http://127.0.0.1:5001/ | Select-String -Pattern 'v4\.0\.\d+').Matches.Value
```
Expected: `v4.0.41`. The login page prints the version, and a browser tab opens. Only start it after Alvin says
production may come up now; it is his live app.

- [ ] **Step 10 (if D2 = yes): Write the launcher** `C:\envs\assistant\products\ltv-app\app-ops\start-ltv.bat`:

```bat
@echo off
rem Starts LTV's two local apps on the one ledger, each in its own window.
rem serve.py leaves a running production alone (it only opens the browser on it);
rem the legacy app is started only if nothing listens on port 9000.
start "LTV app (production) :5001" /D "C:\envs\assistant\products\ltv-app\prod" "C:\envs\assistant\products\ltv-app\venv\Scripts\python.exe" serve.py
netstat -ano | findstr /R /C:"127.0.0.1:9000 .*LISTENING" >nul || start "LTV legacy app :9000" /D "C:\envs\assistant\clients\ltv\legacy\localhost" python flask_app.py
```
Test it by double-clicking it with production already up. Expected: no second server; the browser opens on the
app; the legacy app starts if it was not running.

- [ ] **Step 11: Rewrite the product `CLAUDE.md`.**
  - Replace the "Where it runs" table with this:

```markdown
| Where | Client | Checkout | Database | Records |
|---|---|---|---|---|
| `http://127.0.0.1:5001`, this PC (since 30 Oct 2026) | LTV, **production** | `prod\`: a detached worktree of `app\` at a released commit, served by `serve.py` (waitress, no debugger) | `C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db`, shared with the legacy app on port 9000 | `clients/ltv/`: `PENDING.md` **Last session**, `backups/` |
| `http://127.0.0.1:5002` | development | `app\`, `flask_app.py` (debug) | `app\instance\LTV Stocks.db`, a dated development copy | `app/BUGS.md` |

`larrylilia.pythonanywhere.com` has not been read since 30 Oct 2026 (Alvin: "we will stop using the larrylilia
PA from hereon"). Its records stay in `clients/ltv/ltv_app/` as history.
```
  - **Commands:** the dev server line becomes `..\venv\Scripts\python.exe flask_app.py  # dev server,
    http://127.0.0.1:5002`.
  - Replace "Deploying" with:

```markdown
## Deploying

Claude deploys on Alvin's request, one request per deploy ("deploy", "kindly deploy"); a commit or a push is not one.
Production is `prod\`, a detached worktree of `app\`'s repository, served by `serve.py`.

1. In `prod\`, run `git status --short`. Any modified tracked file (an uploaded template, a hand fix) means stop
   and report. Never reset or overwrite it without his word.
2. Ask Alvin to close the production window, or stop the process listening on 5001 on his word.
3. Back up the ledger to `clients\ltv\backups\LTV Stocks <yyyy-MM-dd-HHmm>.db` while nobody is entering data, and
   compare the hashes.
4. `git -C prod checkout --detach <release commit>`.
5. Start it with `app-ops\start-ltv.bat`. The login page and the navbar show `v<VERSION>` of that commit.

Record the deploy in `clients/ltv/PENDING.md` under **Last session**.
```
  - Delete the sentence about the auto-mode allow rule for browser steps.

- [ ] **Step 12: Commit the product repository.** This includes the `CLAUDE.md` additions already pending from 27–30
  Oct.

```powershell
git -C C:\envs\assistant\products\ltv-app add CLAUDE.md .gitignore app-ops/start-ltv.bat
git -C C:\envs\assistant\products\ltv-app commit -m "Production runs from prod\ under serve.py; dev on 5002; new deploy steps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 13: Hand off to the client side.**
  - Add to `clients\ltv\PENDING.md` under **Last session**: the move, the release commit, the backup file name, and
    the new start (`app-ops\start-ltv.bat`, or `prod\serve.py`).
  - Tell Alvin in chat that `clients\ltv\CLAUDE.md` ("The ledger is local", the ltv_app bullet) and any root skill
    that starts ltv_app from `products\ltv-app\app` need the root session's update. Port 5001 is unchanged.
  - Delete the product memory `deploy-pa-signin-and-checks.md` and its `MEMORY.md` line.

- [ ] **Step 14: BUGS.md.** Mark the "Production runs this working tree…" entry Fixed, with the release commit. Mark
  the open-browser entry Fixed, with Task 3's commit.

---

### Task 5: The notebook prints on the Notebook form (paper 10000)

**Files:**
- Modify: `ltv_app/blueprints/notebook/extensions/create_notebook.py` (constants near `FIRST_PAGE_END`;
  `create_file()`)
- Test: `scripts/verify_notebook_page_layout.py` (new case L6)

- [ ] **Step 1: Add the failing case.** In `verify_notebook_page_layout.py`:
  - add `"L6": 0` to the `wrong` dict;
  - inside the per-date loop, after `checked += 1`, add the first block below;
  - after the L5 line, add the second.

```python
    if ws.page_setup.paperSize != 10000:
        wrong["L6"] += 1
```
```python
_case("L6 notebooks not on the Notebook form (paper 10000)", wrong["L6"], 0)
```
Add to the docstring: `L6  the sheet is set to paper 10000, the "Notebook" form (5.5 x 8.5 in) the page model assumes;`

- [ ] **Step 2: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_notebook_page_layout.py`
  Expected: `L6 notebooks not on the Notebook form (paper 10000): FAIL`, with the others still PASS.

- [ ] **Step 3: Implement.** In `create_notebook.py`, under `PAGE_ROWS = 32`:

```python
# The printer driver's "Notebook" form, 5.5 x 8.5 in, which Alvin prints on. FIRST_PAGE_END and
# PAGE_ROWS hold only on it; the template ships 10001 ("Long", 8.5 x 13).
NOTEBOOK_PAPER = 10000
```
In `create_file()`, after `ws.print_area = f"A1:Q{rule_to_page_end(ws)}"`:

```python
        # Set here, not only in the template, so an uploaded template cannot undo it.
        ws.page_setup.paperSize = NOTEBOOK_PAPER
```

- [ ] **Step 4: Run the notebook harnesses.**

```powershell
..\venv\Scripts\python.exe scripts\verify_notebook_page_layout.py
..\venv\Scripts\python.exe scripts\verify_notebook_page_padding.py
..\venv\Scripts\python.exe scripts\verify_notebook_short_book.py
..\venv\Scripts\python.exe scripts\verify_notebook_transfer_opening.py
```
Expected: ALL PASS from each.

- [ ] **Step 5: Commit.**

```powershell
git add ltv_app/blueprints/notebook/extensions/create_notebook.py scripts/verify_notebook_page_layout.py
git commit -m "fix(notebook): set paper 10000, the 5.5 x 8.5 Notebook form the pages are planned for" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Notebook KO blocks print the knock-out day's close and date

**Files:**
- Modify: `ltv_app/blueprints/notebook/extensions/create_notebook.py`: imports; `write_balance()`, the
  `# Closing Rate` loop; a new method `_ko_closing()`
- Test: `scripts/verify_notebook_ko_closing.py` (new)

**Interfaces:**
- Produces: `CreateNotebook._ko_closing(self, code: str) -> tuple[date, float] | None`

- [ ] **Step 1: Write the failing harness** `scripts/verify_notebook_ko_closing.py`:

```python
"""Regression harness: a notebook KO block prints the knock-out day's close and its date.

Alvin types both under the red "Closing" label of every KO block (BUGS.md 2026-11-02). They
are the stock's close on its last trading day before the notebook's date, which is
tbl_stock_price's close for that day. KO rows carry no fixing_date, so the day comes from
the calendar. For the newest dates with a KO trade, generated through the route on a copy
of the database:
  K1 a block whose close is held shows that close under the label;
  K2 ... and that day as the date under it;
  K3 a block whose close is not held leaves both cells blank;
  K0 enough blocks were seen, at least one with a close held.
The expected day is worked out here from tbl_holiday and weekends, not with WorkingDay.
No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_notebook_ko_closing.py
"""
import io
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app

DATES_TO_CHECK = 30
FIRST_ACCOUNT_ROW = 24
TITLE_CODE = re.compile(r"\(([^()]*)\)\s*$")

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


def _previous_trading_day(db, ccy_id, d):
    holidays = {str(r[0])[:10] for r in db.execute(
        "SELECT h.holi_date FROM tbl_holiday h INNER JOIN tbl_currency c ON c.ref_num = h.ccy_ref "
        "WHERE c.ccy_id = ?", (ccy_id,))}
    d -= timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d -= timedelta(days=1)
    return d


def _expected(db, code, notebook_date):
    row = db.execute(
        "SELECT tbl_code.ref_num, tbl_currency.ccy_id FROM tbl_code "
        "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref WHERE tbl_code.code = ?",
        (code,)).fetchone()
    day = _previous_trading_day(db, row["ccy_id"], notebook_date)
    price = db.execute(
        "SELECT closing_price FROM tbl_stock_price WHERE code_ref = ? AND substr(trade_date, 1, 10) = ?",
        (row["ref_num"], day.isoformat())).fetchone()
    return day, (price[0] if price else None)


def _block_code(ws, label_row):
    """The stock of a Closing label: the code in the nearest numbered line title above it."""
    for r in range(label_row, FIRST_ACCOUNT_ROW - 1, -1):
        title = ws[f"C{r}"].value
        if isinstance(ws[f"B{r}"].value, int) and isinstance(title, str) and TITLE_CODE.search(title):
            return TITLE_CODE.search(title).group(1)
    return None


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    dates = [r[0] for r in db.execute(
        "SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction "
        "WHERE transaction_type LIKE '%KO%' ORDER BY 1 DESC LIMIT ?", (DATES_TO_CHECK,))]
    seen, held = 0, 0
    wrong = {"K1": 0, "K2": 0, "K3": 0}
    for d in dates:
        response = client.get(f"/notebook/generate/{d}")
        data = response.get_data()
        response.close()
        if response.status_code != 200:
            continue
        ws = load_workbook(io.BytesIO(data))["notebook"]
        for r in range(FIRST_ACCOUNT_ROW, ws.max_row + 1):
            if ws[f"O{r}"].value != "Closing":
                continue
            code = _block_code(ws, r)
            if code is None:
                continue
            seen += 1
            day, price = _expected(db, code, date.fromisoformat(d))
            shown_price, shown_day = ws[f"O{r + 1}"].value, ws[f"O{r + 2}"].value
            if price is None:
                if shown_price is not None or shown_day is not None:
                    wrong["K3"] += 1
                continue
            held += 1
            if shown_price is None or abs(float(shown_price) - float(price)) > 1e-9:
                wrong["K1"] += 1
            if not isinstance(shown_day, datetime) or shown_day.date() != day:
                wrong["K2"] += 1

_case(f"K0 KO blocks seen ({seen}), some with a close held", seen >= 5 and held >= 1, True)
_case("K1 KO blocks without the knock-out day's close", wrong["K1"], 0)
_case("K2 KO blocks without the knock-out day's date", wrong["K2"], 0)
_case("K3 KO blocks with no close held that are not blank", wrong["K3"], 0)
print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
```

- [ ] **Step 2: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_notebook_ko_closing.py`
  Expected: K0 PASS, K1 and K2 FAIL (the cells are blank today), K3 PASS.

- [ ] **Step 3: Implement.**
  - In `create_notebook.py`, change `from datetime import datetime` to `from datetime import date, datetime`.
  - Below the other `ltv_app` imports, add
    `from ltv_app.blueprints.ltv_stocks.legacy_port.working_day import WorkingDay`.
  - Add this method to `CreateNotebook`, after `_opening_short_balance`:

```python
    def _ko_closing(self, code):
        """(knock-out day, its close) for a stock's KO block, or None when no close is held.

        The knock-out day is the stock's last trading day before the notebook's date, on its
        own currency's calendar: KO rows carry no fixing_date. Alvin typed this close and
        date by hand on every KO block (BUGS.md 2026-11-02)."""
        row = self.db.execute(
            "SELECT tbl_code.ref_num, tbl_currency.ccy_id FROM tbl_code "
            "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref "
            "WHERE tbl_code.code = ?", (code,)).fetchone()
        if row is None:
            return None
        ko_day = WorkingDay(self.db, row["ccy_id"]).previous_day(date.fromisoformat(self.trade_date))
        price = self.db.execute(
            "SELECT closing_price FROM tbl_stock_price "
            "WHERE code_ref = ? AND substr(trade_date, 1, 10) = ?",
            (row["ref_num"], ko_day.isoformat())).fetchone()
        if price is None or price[0] is None:
            return None
        return ko_day, price[0]
```
  - In `write_balance()`, change the `# Closing Rate` loop to fill the two cells. The label and formats stay as they
    are.

```python
        # Closing Rate: the knock-out day's close and date, as Alvin types them
        ko_closing = None
        for transaction_type, _ in trades.items():
            if "KO" in transaction_type:
                if ko_closing is None:
                    ko_closing = self._ko_closing(code) or ()
                cell = ws[f"O{row_num-3}"]
                cell.value = "Closing"
                cell.alignment = Alignment(horizontal="center")
                cell.font = Font(size=9, color=RED_COLOR)
                ws.merge_cells(f"O{row_num-3}:Q{row_num-3}")

                cell = ws[f"O{row_num-2}"]
                cell.value = ko_closing[1] if ko_closing else None
                cell.alignment = Alignment(horizontal="center")
                cell.number_format = "#,##0.00"
                cell.font = Font(size=9, color=RED_COLOR)
                ws.merge_cells(f"O{row_num-2}:Q{row_num-2}")

                cell = ws[f"O{row_num-1}"]
                cell.value = ko_closing[0] if ko_closing else None
                cell.alignment = Alignment(horizontal="center")
                cell.number_format = "d-mmm-yyyy"
                cell.font = Font(size=9, color=RED_COLOR)
                ws.merge_cells(f"O{row_num-1}:Q{row_num-1}")
```
  Read the current loop first. Keep every line of it that is not shown here (if there are any) unchanged.

- [ ] **Step 4: Run the harnesses.**

```powershell
..\venv\Scripts\python.exe scripts\verify_notebook_ko_closing.py
..\venv\Scripts\python.exe scripts\verify_notebook_page_layout.py
..\venv\Scripts\python.exe scripts\verify_notebook_page_padding.py
..\venv\Scripts\python.exe scripts\verify_notebook_short_book.py
..\venv\Scripts\python.exe scripts\verify_notebook_transfer_opening.py
```
Expected: ALL PASS from each.

- [ ] **Step 5: Re-run the 30 Oct comparison** (Task 2, step 4).
  Run: `..\venv\Scripts\python.exe <scratchpad>\nb_1030_compare.py`
  Expected: `cells differing in rows 41-73: []`. Rows 41–73 now equal Alvin's hand-finished file.

- [ ] **Step 6: Commit.**

```powershell
git add ltv_app/blueprints/notebook/extensions/create_notebook.py scripts/verify_notebook_ko_closing.py
git commit -m "feat(notebook): print the knock-out day's close and date on KO blocks" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: LTV Stocks prints only A:X, fitted to one page wide

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`: page setup at line ~1037, `print_area` at
  ~1101 and the comment above it
- Test: `scripts/verify_last_day_ko_marker.py`, `live_print_area()` and the module docstring

- [ ] **Step 1: Change the harness expectation first.** In `live_print_area()`, replace the check
  `"every sheet prints to the same last column"` with:

```python
    check("every sheet prints to column X (Alvin, 30 Oct 2026)", sorted(last_cols), ['X'])
    fits = [(wb[n].page_setup.fitToWidth, wb[n].page_setup.fitToHeight,
             bool(wb[n].sheet_properties.pageSetUpPr and wb[n].sheet_properties.pageSetUpPr.fitToPage))
            for n in sheets]
    check("every sheet is one page wide, height automatic", sorted(set(fits)), [(1, 0, True)])
```
Update the docstring paragraph that explains printing through AJ. It now says: printing stops at X on Alvin's
instruction; the AA:AJ grid is still built but not printed; a knock-out on the report date therefore has no printed
"KO" marker (D4).

- [ ] **Step 2: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_last_day_ko_marker.py`
  Expected: the two new checks FAIL; the earlier checks in `isolated()` still PASS. After Task 4 this harness's bare
  `create_app()` opens the development copy.

- [ ] **Step 3: Implement.**
  - In `excel_writer.py`, add `from openpyxl.worksheet.properties import PageSetupProperties` to the imports.
  - Directly after the `set_printer_settings(ws, paper_size=4, orientation='landscape')` call, add the first block
    below.
  - Replace the comment block and the `ws.print_area = f'A1:{_STATUS_COLS[-1]}{r}'` line with the second.

```python
            # A:X on one page width, on any paper (Alvin, 30 Oct 2026: "the pagebreak should be
            # up to column x only"). Height runs to as many pages as the sheet needs.
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
```
```python
            # Through X only, on Alvin's instruction (30 Oct 2026). The Z:AJ tracking grid is
            # still built, but it no longer prints, so a knock-out on the report date (column X)
            # shows only as the reddened row and bold price, with no "KO" marker on the page.
            # The 17 Sep 2026 widening to AJ was a review suggestion, not his. BUGS.md 2026-11-02.
            ws.print_area = f'A1:X{r}'
```

- [ ] **Step 4: Run the LTV Stocks harnesses.**

```powershell
..\venv\Scripts\python.exe scripts\verify_last_day_ko_marker.py
..\venv\Scripts\python.exe scripts\verify_status_grid.py
..\venv\Scripts\python.exe scripts\verify_status_grid_ko_marker.py
..\venv\Scripts\python.exe scripts\verify_ko_presentation.py
..\venv\Scripts\python.exe scripts\verify_wide_price_font.py
```
Expected: all PASS.

- [ ] **Step 5: Check the page breaks in Excel once.** Write `<scratchpad>\ltv_stocks_pages.py`:

```python
import io, os, shutil, sys, tempfile
from datetime import date
sys.path.insert(0, r"C:\envs\assistant\products\ltv-app\app")
import win32com.client
from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import build_workbook

tmp = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(r"C:\envs\assistant\products\ltv-app\app\instance\LTV Stocks.db", tmp)
app = create_app({"DATABASE": tmp, "LOGIN_DISABLED": True})
out = os.path.join(tempfile.mkdtemp(), "ltv_stocks.xlsx")
with app.app_context():
    newest = get_db().execute("SELECT max(substr(trade_date, 1, 10)) FROM tbl_transaction").fetchone()[0]
    with open(out, "wb") as f:
        f.write(build_workbook(get_db(), date.fromisoformat(newest), ["SHK"]).getvalue())
xl = win32com.client.DispatchEx("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
try:
    wb = xl.Workbooks.Open(out, ReadOnly=True)
    for ws in wb.Worksheets:
        if ws.PageSetup.PrintArea:
            print(ws.Name, "vertical breaks:", ws.VPageBreaks.Count, "pages:", ws.PageSetup.Pages.Count)
    wb.Close(False)
finally:
    xl.Quit()
```
Run it with the Python that has `pywin32`; the work order's Excel builds used it. Check with
`python -c "import win32com"`.

Expected: `vertical breaks: 0` on every sheet, so A:X is one page wide.

- [ ] **Step 6: Commit.**

```powershell
git add ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py scripts/verify_last_day_ko_marker.py
git commit -m "fix(ltv-stocks): print A:X only, fitted to one page wide" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
In `BUGS.md`: Fixed. Note the D4 question as still with Alvin, and add a line to the 17 Sep entry saying its print
range was reversed on 2 Nov.

---

### Task 8: `/maris/` downloads include the Short Book's trades

**Files:**
- Modify: `ltv_app/blueprints/marissa_orders/extensions.py`: a new `_LEDGER`; the queries in
  `_posting_transactions`, `download_daily_transactions` and `download_transaction_range`
- Test: `scripts/verify_maris_short_book.py` (new)

**Interfaces:**
- Unchanged signatures: `download_posting(db, posting_month, posting_year) -> (BytesIO, name)`,
  `download_daily_transactions(db, trade_date) -> (BytesIO, name)`,
  `download_transaction_range(db, start_date, end_date) -> (BytesIO, name)`.

- [ ] **Step 1: Check the Short Book's date format.**

```powershell
..\venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'instance\LTV Stocks.db'); print(c.execute('SELECT DISTINCT length(trade_date), length(value_date) FROM tbl_transaction_short').fetchall()); print(c.execute(\"SELECT count(*) FROM tbl_transaction WHERE transaction_type IN ('Sell (Short)', 'Buy (Pay Short)')\").fetchone())"
```
Expected:
- `[(10, 10)]`. The writers slice `trade_date[:4]`, `[5:7]` and `[-2:]`; any other length must be normalised with
  `substr(…, 1, 10)` in `_LEDGER`.
- `(0,)`: no short type in the long book. If there are some, stop. The harness assumes every short trade is in
  `tbl_transaction_short`, so ask before going on.

- [ ] **Step 2: Write the failing harness** `scripts/verify_maris_short_book.py`:

```python
"""Regression harness: Marissa's three /maris/ downloads carry the Short Book's trades.

Sell (Short) and Buy (Pay Short) live in tbl_transaction_short, and all three downloads read
only tbl_transaction, so no short trade reached her files (BUGS.md 2026-11-02). Return
Shares / Borrow Shares are booked in both tables and must not print twice. On a copy of the
database:
  M1 each date with a short trade: the daily file holds exactly that date's short trades;
  M2 each month with a short trade: the range file holds exactly that month's short trades;
  M3 ... and the posting file does;
  M4 the range file holds Return/Borrow Shares exactly as often as tbl_transaction does;
  M5 the range file's other rows are tbl_transaction's rows, one for one.
Trades are compared as (account, stock, quantity) multisets. No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_maris_short_book.py
"""
import io
import os
import shutil
import sys
import tempfile
from calendar import monthrange
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.marissa_orders.extensions import (
    download_daily_transactions, download_posting, download_transaction_range)

SHORT_TYPES = ("Sell (Short)", "Buy (Pay Short)")
BORROW_RETURN = ("Return Shares", "Borrow Shares")
DATES_TO_CHECK = 30
MONTHS_TO_CHECK = 6

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


def _code(value):
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _qty(value):
    return round(float(value), 4)


def _db_trades(db, table, types, start, end, key):
    marks = ",".join("?" * len(types))
    rows = db.execute(
        f"SELECT b.bank_id, b.bank_name, c.code, t.quantity FROM {table} t "
        "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_code c ON c.ref_num = t.code_ref "
        f"WHERE t.transaction_type IN ({marks}) AND t.trade_date >= ? AND t.trade_date <= ?",
        (*types, start, end)).fetchall()
    return Counter((r[key], _code(r["code"]), _qty(r["quantity"])) for r in rows)


def _sheet_trades(output, types):
    """(account, code, quantity) of the rows whose Transaction column is one of types.
    Daily and range files: B account name, C type, D code, E quantity."""
    ws = load_workbook(io.BytesIO(output.getvalue())).active
    return Counter((r[1], _code(r[3]), _qty(r[4])) for r in ws.iter_rows(min_row=2, values_only=True)
                   if r[2] in types)


def _posting_trades(output):
    """Posting file: one sheet per <bank_id>-<ccy>; C type, D code, F quantity."""
    found = Counter()
    for ws in load_workbook(io.BytesIO(output.getvalue())).worksheets:
        bank_id = ws.title.rsplit("-", 1)[0]
        for r in ws.iter_rows(min_row=2, values_only=True):
            if len(r) > 5 and r[2] in SHORT_TYPES:
                found[(bank_id, _code(r[3]), _qty(r[5]))] += 1
    return found


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    dates = [r[0] for r in db.execute(
        "SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction_short "
        "WHERE transaction_type IN (?, ?) ORDER BY 1 DESC LIMIT ?", (*SHORT_TYPES, DATES_TO_CHECK))]
    months = sorted({d[:7] for d in dates}, reverse=True)[:MONTHS_TO_CHECK]
    bad = Counter()
    for d in dates:
        out, _ = download_daily_transactions(db, d)
        if _sheet_trades(out, SHORT_TYPES) != _db_trades(db, "tbl_transaction_short", SHORT_TYPES, d, d, "bank_name"):
            bad["M1"] += 1
    for m in months:
        year, month = int(m[:4]), int(m[5:7])
        start, end = f"{m}-01", f"{m}-{monthrange(year, month)[1]:02d}"
        out, _ = download_transaction_range(db, start, end)
        if _sheet_trades(out, SHORT_TYPES) != _db_trades(db, "tbl_transaction_short", SHORT_TYPES, start, end, "bank_name"):
            bad["M2"] += 1
        if _sheet_trades(out, BORROW_RETURN) != _db_trades(db, "tbl_transaction", BORROW_RETURN, start, end, "bank_name"):
            bad["M4"] += 1
        long_types = [r[0] for r in db.execute(
            "SELECT DISTINCT transaction_type FROM tbl_transaction WHERE transaction_type NOT IN (?, ?)",
            BORROW_RETURN)]
        if _sheet_trades(out, long_types) != _db_trades(db, "tbl_transaction", long_types, start, end, "bank_name"):
            bad["M5"] += 1
        out, _ = download_posting(db, month, year)
        if _posting_trades(out) != _db_trades(db, "tbl_transaction_short", SHORT_TYPES, start, end, "bank_id"):
            bad["M3"] += 1

_case(f"M0 short-trade dates checked ({len(dates)}) and months ({len(months)})", bool(dates and months), True)
for key, label in (("M1", "daily files missing or adding short trades"),
                   ("M2", "range files missing or adding short trades"),
                   ("M3", "posting files missing or adding short trades"),
                   ("M4", "range files printing Return/Borrow Shares twice"),
                   ("M5", "range files whose long-book rows changed")):
    _case(f"{key} {label}", bad[key], 0)
print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
```

- [ ] **Step 3: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_maris_short_book.py`
  Expected: M0, M4 and M5 PASS; M1, M2 and M3 FAIL.

- [ ] **Step 4: Implement.** In `extensions.py`, after the imports:

```python
# Every row the three downloads read: the long book, plus the Short Book's own trades.
# Return Shares / Borrow Shares are booked in both tables, so the Short Book's copy is left
# out, as the notebook's SHORT_SQL does. tbl_transaction_short has no counter_bank_ref: a
# short trade is never a transfer. BUGS.md 2026-11-02.
_LEDGER = """
    SELECT trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price,
           brokerage, commission, foreign_charge, stamp_duty, misc, counter_bank_ref
      FROM tbl_transaction
    UNION ALL
    SELECT trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price,
           brokerage, commission, foreign_charge, stamp_duty, misc, NULL
      FROM tbl_transaction_short
     WHERE transaction_type IN ('Sell (Short)', 'Buy (Pay Short)')
"""
```
Make each of the three `sql = """…"""` strings an f-string, then:
- replace `FROM tbl_transaction` (the line before the joins) with `FROM ({_LEDGER}) AS t`;
- replace every `tbl_transaction.` with `t.`. Do not touch `tbl_transaction_type.`, which is a different table;
  a plain replace of `tbl_transaction.` (with the dot) leaves it alone.

`_posting_transactions` then reads:

```python
    sql = f"""
      SELECT
        tbl_bank_account.bank_id,
        tbl_bank_account.bank_name,
        tbl_code.code,
        tbl_code.stock_name,
        t.trade_date,
        t.value_date,
        t.transaction_type,
        t.quantity,
        t.price,
        t.brokerage,
        t.commission,
        t.foreign_charge,
        t.stamp_duty,
        t.misc,
        t.counter_bank_ref,
        tbl_currency.ccy_id
      FROM ({_LEDGER}) AS t
      INNER JOIN tbl_bank_account on tbl_bank_account.ref_num = t.bank_ref
      INNER JOIN tbl_code on tbl_code.ref_num = t.code_ref
      INNER JOIN tbl_currency on tbl_currency.ref_num = tbl_code.ccy_ref
      INNER JOIN tbl_transaction_type on tbl_transaction_type.transaction_type = t.transaction_type
      WHERE t.trade_date >= ?
        AND t.trade_date <= ?
      ORDER BY tbl_bank_account.priority, tbl_currency.priority, t.trade_date, tbl_transaction_type.priority
      ;
    """
```
In `download_daily_transactions`:
- the selected columns become `t.trade_date`, `t.transaction_type`, `t.quantity`, `t.price`, `t.counter_bank_ref`;
- `FROM ({_LEDGER}) AS t`, and the joins on `t.bank_ref`, `t.code_ref`, `t.transaction_type`;
- `WHERE t.trade_date = ?`;
- ORDER BY unchanged.

In `download_transaction_range`, the same, with `WHERE t.trade_date >= ? AND t.trade_date <= ?` and
`ORDER BY tbl_bank_account.priority, tbl_code.code, t.trade_date, tbl_transaction_type.priority`.

The posting writer's side and type logic needs no change:
- `'Sell (Short)'` gives side SOLD and type `Sell (Short)`;
- `'Buy (Pay Short)'` gives PURCHASE and `Buy (Pay Short)`.

That is the D8 default.

- [ ] **Step 5: Run it.**
  Run: `..\venv\Scripts\python.exe scripts\verify_maris_short_book.py`, then
  `..\venv\Scripts\python.exe scripts\verify_transaction_range_grouping.py`
  Expected: ALL PASS, and the grouping harness still passes. That one boots bare; after Task 4 that is the
  development copy.

- [ ] **Step 6: Commit.**

```powershell
git add ltv_app/blueprints/marissa_orders/extensions.py scripts/verify_maris_short_book.py
git commit -m "fix(maris): the three downloads include Short Book trades" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Find out why `verify_gain_loss_refactor` differs (no re-save yet)

BUGS Low 2026-10-27: the harness reports DIFFERS at one cell, F12 of case `all-banks_all-codes_2018-04_shorts`. The
suspected cause is `38287ae`, a cover measured against the short it closes. Confirm the cause before Tasks 10–12
change gain-loss output deliberately. The re-save is Task 12's last step.

**Files:** none in the repo; `BUGS.md` only.

- [ ] **Step 1: Run the check on the current code.**
  Run: `..\venv\Scripts\python.exe scripts\verify_gain_loss_refactor.py --check > <scratchpad>\gl_main.txt`
  Expected: one DIFFERS, at that case and cell. Note the first lines of the difference. Don't paste figures into
  BUGS.md: name the cell only.

- [ ] **Step 2: Run it just before and at `38287ae`, in throwaway worktrees.**

```powershell
$py = 'C:\envs\assistant\products\ltv-app\venv\Scripts\python.exe'
foreach ($rev in '38287ae~1', '38287ae') {
  $wt = "<scratchpad>\gl-$($rev -replace '~','-')"
  git worktree add --detach $wt $rev
  Copy-Item scripts\_gain_loss_snapshot.txt "$wt\scripts\"
  Copy-Item instance\_gain_loss_baseline.db "$wt\instance\"
  Push-Location $wt; & $py scripts\verify_gain_loss_refactor.py --check > check.txt; Pop-Location
  Select-String -Path "$wt\check.txt" -Pattern 'DIFFERS|PASS' | Select-Object -First 5
}
```
The worktree has no `instance\config.py`, so its bare `create_app()` boots on its own (absent) default database,
which `_ensure_*` never creates. The harness then switches to the copied baseline. The templates come with the
checkout.

Expected:
- at `38287ae~1` the case does not differ at that cell;
- at `38287ae` it does.

If both differ, find the commit with
`git bisect start 38287ae <first commit after 2026-08-15>`, then `git bisect run` with the same `--check` command.

- [ ] **Step 3: Clean up and record.**
  - `git worktree remove --force <each worktree>`.
  - In the BUGS entry: "Cause confirmed: `<commit>` (2 Nov). Re-saved in Task 12 after the deliberate gain-loss
    changes."

---

### Task 10: No gain or loss on a transfer (transaction list and its download)

**Files:**
- Modify: `ltv_app/blueprints/transactions/models.py`, `restructure_transactions()`: also return
  `transaction_type`
- Modify: `ltv_app/blueprints/bank/views.py`: `_compute_transactions()` (~line 250) and the download's `GL` column
  (~line 542 and ~568)
- Test: `scripts/verify_bank_transfer_no_gain.py` (new)

**Interfaces:**
- Produces: every dict from `restructure_transactions()` gains the key `transaction_type: str`. Consumers that
  index by name are unaffected; Step 1 checks for any that iterate keys.

- [ ] **Step 1: Find every consumer of `restructure_transactions`.**
  Run: `git grep -n "restructure_transactions\|get_transactions(" -- ltv_app`
  Read each caller that iterates a row's keys or values (`.items()`, `.values()`, `**row`). Expected: none; if one
  does, add `transaction_type` there only where it cannot reach a cell.

- [ ] **Step 2: Write the failing harness** `scripts/verify_bank_transfer_no_gain.py`:

```python
"""Regression harness: no gain or loss on a transfer, on /bank/<id>/<code> or in its download.

A transfer moves shares and cost between Alvin's own accounts; it realises nothing. Alvin,
30 Oct 2026: "there shouldn't be any gain or loss in transfers" (BUGS.md 2026-11-02). The
transaction list treated every qty < 0 row on a long balance as a sale. On a copy of the
database, for every (account, stock, year) holding a transfer:
  T1 every Transfer-In / Transfer-Out row carries a gain/loss of 0;
  T2 every sale's gain is still proceeds - charges - (previous running average x shares);
  T3 in the download, transfer rows have no Gain/Loss formula and sales keep theirs;
  T0 transfers and sales were found.
No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_bank_transfer_no_gain.py
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.bank.views import _compute_transactions

TRANSFERS = ("Transfer-In", "Transfer-Out")
DOWNLOADS_TO_CHECK = 25
DATA_ROW = 7          # header row 5, Balance Forwarded row 6

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    transfer_refs = {r[0] for r in db.execute(
        "SELECT ref_num FROM tbl_transaction WHERE transaction_type IN (?, ?)", TRANSFERS)}
    combos = db.execute(
        "SELECT DISTINCT t.bank_ref, t.code_ref, substr(t.trade_date, 1, 4) AS year, b.bank_id, c.code "
        "FROM tbl_transaction t INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_code c ON c.ref_num = t.code_ref "
        "WHERE t.transaction_type IN (?, ?) ORDER BY year DESC", TRANSFERS).fetchall()

    transfers_seen = sales_seen = 0
    wrong = {"T1": 0, "T2": 0, "T3": 0}
    for i, combo in enumerate(combos):
        date_from, date_to = f"{combo['year']}-01-01", f"{combo['year']}-12-31"
        start_qty, start_avg, rows = _compute_transactions(
            db, combo["bank_ref"], combo["code_ref"], date_from, date_to)
        prev_avg, prev_bal = start_avg, start_qty
        for row in rows:
            if row["ref_num"] in transfer_refs:
                transfers_seen += 1
                if abs(row["gain_loss"]) > 1e-9:
                    wrong["T1"] += 1
            elif row["quantity"] < 0 and prev_bal > 0:
                sales_seen += 1
                q = abs(row["quantity"])
                expected = q * row["price"] - row["charges"] - prev_avg * q
                if abs(row["gain_loss"] - expected) > 1e-6 * max(1.0, abs(expected)):
                    wrong["T2"] += 1
            prev_avg, prev_bal = row["average"], row["balance"]

        if i < DOWNLOADS_TO_CHECK:
            response = client.get(f"/bank/{combo['bank_id']}/{combo['code']}/download"
                                  f"?date_from={date_from}&date_to={date_to}")
            ws = load_workbook(io.BytesIO(response.get_data())).active
            response.close()
            for r, row in enumerate(rows, start=DATA_ROW):
                gl = ws.cell(row=r, column=8).value
                if row["ref_num"] in transfer_refs:
                    if gl not in (None, ""):
                        wrong["T3"] += 1
                elif row["quantity"] < 0 and not (isinstance(gl, str) and gl.startswith("=IF(")):
                    wrong["T3"] += 1

_case(f"T0 transfers ({transfers_seen}) and sales ({sales_seen}) found",
      transfers_seen > 0 and sales_seen > 0, True)
_case("T1 transfer rows with a gain or loss", wrong["T1"], 0)
_case("T2 sales whose gain changed", wrong["T2"], 0)
_case("T3 download rows with the wrong Gain/Loss cell", wrong["T3"], 0)
print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
```

- [ ] **Step 3: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_bank_transfer_no_gain.py`
  Expected: T0 PASS, T1 FAIL, T2 PASS, T3 FAIL.

- [ ] **Step 4: Implement.**
  - In `restructure_transactions()`, add `'transaction_type': trans['transaction_type'],` to `_dict`, after
    `'description'`.
  - In `_compute_transactions()`, replace the gain block with:

```python
        # A transfer moves cost between Alvin's own accounts and realises nothing (Alvin,
        # 30 Oct 2026). Its cost still leaves at the running average, below.
        is_transfer = "Transfer" in data["transaction_type"]
        gain_loss = 0.0
        if qty < 0 and balance > 0 and not is_transfer:
            gain_loss = abs(qty) * price - charges - (cost_to_date / balance) * abs(qty)
```
  - In `download_transactions()`, change the `GL` comment to `# Gain/Loss: only on a sale (qty < 0), never on a
    transfer`.
  - Write the H cell as:

```python
        # H: Gain/Loss formula, none on a transfer
        c8 = ws.cell(row=r, column=8, value="" if "Transfer" in t["transaction_type"] else GL)
```

- [ ] **Step 5: Run it, and check the gain-loss report is unchanged.**

```powershell
..\venv\Scripts\python.exe scripts\verify_bank_transfer_no_gain.py
..\venv\Scripts\python.exe scripts\verify_gain_loss_refactor.py --check > <scratchpad>\gl_after_t10.txt
fc.exe <scratchpad>\gl_main.txt <scratchpad>\gl_after_t10.txt
..\venv\Scripts\python.exe scripts\verify_short_cover_gain.py
```
Expected:
- ALL PASS;
- `fc` reports no differences: the extra key changed nothing in the Gain Loss workbook;
- `verify_short_cover_gain` passes.

- [ ] **Step 6: Commit.**

```powershell
git add ltv_app/blueprints/transactions/models.py ltv_app/blueprints/bank/views.py scripts/verify_bank_transfer_no_gain.py
git commit -m "fix(bank): no gain or loss on transfers in the transaction list and its download" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
In `BUGS.md`: Fixed. Add that D5 (should the transfer price be the sender's exact running average) is still with
Alvin.

---

### Task 11: Gain Loss SUMMARY built from the accounts

The template's SUMMARY lists a fixed set of accounts, with no SHK2 row and no Nomura section. Alvin's hand-finished
30 Oct file is the target layout. It is the template's layout, plus:
- "SHKIS Account no. 1 / no. 2" under Sun Hung Kai;
- a "Nomura Singapore" group with an account row "Nomura".

The Marissa Page points at fixed SUMMARY rows (`=SUMMARY!C31`), so those links are rewritten to look an account up
by its id in column N, the way Top Sheet already does.

**Files:**
- Create: `ltv_app/blueprints/gain_loss/summary_sheet.py`
- Modify: `ltv_app/blueprints/gain_loss/create_gain_loss.py`, `create_file()`, just before `output = io.BytesIO()`
- Test: `scripts/verify_gain_loss_workbook.py` (new; Task 12 adds G5–G6)

**Interfaces:**
- Produces, in `summary_sheet.py`:
  - `SUMMARY_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]`;
  - `CONVERSION: tuple[tuple[str, str, object], ...]`;
  - `summary_groups(accounts, sheet_bank_ids) -> tuple`;
  - `account_rows(ws) -> dict[int, str]`;
  - `build_summary(ws, groups) -> dict[str, int]` (bank_id → row);
  - `relink_summary_refs(wb, old_rows: dict[int, str]) -> int` (links rewritten).

  Task 12 edits `CONVERSION` and adds `apply_rates(wb)`.

- [ ] **Step 1: Write the failing harness** `scripts/verify_gain_loss_workbook.py`:

```python
"""Regression harness: the Gain Loss workbook's SUMMARY carries every account, and its totals
and rates hang together.

The template's SUMMARY had no SHK No. 2 row and no Nomura section, so their gains never
reached the Total. Alvin widened it by hand each time, and that is where his 30 Oct file went
wrong (BUGS.md 2026-11-02). Generated through POST /gain-loss/ on a copy of the database, for
the newest month and the year to date (all banks, all stocks). Formulas stay unevaluated
(openpyxl), so this checks their structure:
  G1 every visible account sheet's bank has a SUMMARY row (column N);
  G2 every active account has a SUMMARY row;
  G3 each SUB-Total sums exactly its group's account rows, and the Total sums every SUB-Total;
  G4 each account row reads its own N and the currency key row;
  G7 no sheet links to a fixed SUMMARY account row (=SUMMARY!C31); they look up column N.
No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_gain_loss_workbook.py
"""
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app

CCYS = ("HKD", "JPY", "AUD", "USD", "SGD")
KEY_CURRENCIES = ["AUD", "HKD", "JPY", "USD", "SGD"]
NET_COLS = "BCDEF"
FIXED_LINK = re.compile(r"^=SUMMARY!\$?([A-Z]{1,2})\$?(\d+)$")

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


def _generate(date_from, date_to):
    response = client.post("/gain-loss/", data={"date_from": date_from, "date_to": date_to,
                                                "bank_ref": 0, "code_ref": 0})
    data = response.get_data()
    response.close()
    return load_workbook(io.BytesIO(data))


def _check(wb, active_ids, tag):
    ws = wb["SUMMARY"]
    n_rows = {ws[f"N{r}"].value: r for r in range(9, ws.max_row + 1) if ws[f"N{r}"].value}
    sheets = {name.rpartition("-")[0] for name in wb.sheetnames
              if name.rpartition("-")[2] in CCYS and name.rpartition("-")[0]
              and wb[name].sheet_state == "visible"}
    _case(f"G1 [{tag}] account sheets without a SUMMARY row", sorted(sheets - set(n_rows)), [])
    _case(f"G2 [{tag}] active accounts without a SUMMARY row", sorted(set(active_ids) - set(n_rows)), [])

    subtotals = [r for r in range(9, ws.max_row + 1) if ws[f"A{r}"].value == "SUB-Total"]
    total = next(r for r in range(9, ws.max_row + 1) if ws[f"A{r}"].value == "Total")
    key = next(r for r in range(total, ws.max_row + 1)
               if [ws[f"{c}{r}"].value for c in NET_COLS] == KEY_CURRENCIES)
    bad_sub = 0
    for s in subtotals:
        for c in NET_COLS:
            m = re.fullmatch(rf"=SUM\({c}(\d+):{c}(\d+)\)", str(ws[f"{c}{s}"].value))
            if not m:
                bad_sub += 1
                continue
            first, last = int(m.group(1)), int(m.group(2))
            if last != s - 1 or ws[f"N{first - 1}"].value or not ws[f"A{first - 1}"].value \
                    or not all(ws[f"N{r}"].value for r in range(first, last + 1)):
                bad_sub += 1
    bad_total = sum(1 for c in NET_COLS
                    if sorted(int(x) for x in re.findall(rf"{c}(\d+)", str(ws[f"{c}{total}"].value))) != subtotals)
    _case(f"G3 [{tag}] SUB-Totals or Total summing the wrong rows", bad_sub + bad_total, 0)

    bad_rows = sum(1 for r in n_rows.values() for c in NET_COLS
                   if f"$N{r}&" not in str(ws[f"{c}{r}"].value) or f"{c}${key}" not in str(ws[f"{c}{r}"].value))
    _case(f"G4 [{tag}] account rows not reading their own N and the key row", bad_rows, 0)

    fixed = 0
    for sheet in wb.worksheets:
        if sheet.title == "SUMMARY":
            continue
        for row in sheet.iter_rows():
            for cell in row:
                m = FIXED_LINK.match(str(cell.value)) if isinstance(cell.value, str) else None
                if m and int(m.group(2)) >= 9:
                    fixed += 1
    _case(f"G7 [{tag}] links to a fixed SUMMARY account row", fixed, 0)


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    newest = db.execute("SELECT max(substr(trade_date, 1, 10)) FROM tbl_transaction").fetchone()[0]
    active = [r[0] for r in db.execute("SELECT bank_id FROM tbl_bank_account WHERE is_active = 1")]

for tag, date_from in (("month", newest[:7] + "-01"), ("year", newest[:4] + "-01-01")):
    _check(_generate(date_from, newest), active, tag)

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
```

- [ ] **Step 2: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_gain_loss_workbook.py`
  Expected:
  - G1 and G2 FAIL, missing SHK2 and NSG;
  - G7 FAIL, the Marissa Page links;
  - G3 and G4 PASS on the template's rows.

- [ ] **Step 3: Write `summary_sheet.py`.**

```python
"""The Gain Loss workbook's SUMMARY sheet, built from the bank accounts.

The template's SUMMARY listed a fixed set of accounts, with no row for SHK No. 2 and no
Nomura section, so their gains never reached the Total. Alvin added the rows by hand each
time and widened the Total, and that is where his 30 Oct 2026 file went wrong (BUGS.md
2026-11-02). The rows now come from SUMMARY_GROUPS, his own layout, plus any account that is
active or has a sheet in this workbook, so a new account cannot drop out of the Total.
"""
import re
from copy import copy

# Alvin's layout (his hand-finished 30 Oct 2026 file): a bank heading, then (bank_id, row label).
SUMMARY_GROUPS = (
    ("Citibank", (("CBSG", "Singapore Account 1"),)),
    ("Bank of Singapore", (("BOS", "BOS"),)),
    ("Deutsche Bank", (("DBPe", "Personal"), ("DBPL", "PL"))),
    ("Standard Chartered", (("SC", "Stocks"),)),
    ("Sun Hung Kai", (("SHK", "SHKIS Account no. 1"), ("SHK2", "SHKIS Account no. 2"))),
    ("Morgan Stanley", (("MST1", "T1"), ("MST2", "T2"), ("MSPL", "PL"))),
    ("Nomura Singapore", (("NSG", "Nomura"),)),
)

KEY_CURRENCIES = ("AUD", "HKD", "JPY", "USD", "SGD")   # net columns B..F; HKD columns H..L
NET_COLS = "BCDEF"
HKD_COLS = "HIJKL"
FIRST_ROW = 9
STYLE_COLS = "ABCDEFGHIJKLMNOPQ"
# Template rows whose look each kind of generated row takes
STYLE_ROWS = {"heading": 9, "account": 10, "subtotal": 11, "blank": 12, "total": 36,
              "conversion": 38, "conversion_total": 43, "key": 46}
# (currency, its net column in the Total row, HKD per unit), in the template's order and values
CONVERSION = (
    ("HKD", "C", None),
    ("JPY", "D", 0.07),
    ("AUD", "B", 5.5),
    ("USD", "E", 7.85),
    ("SGD", "F", 0.18),
)
FIXED_LINK = re.compile(r"^=SUMMARY!\$?([A-Z]{1,2})\$?(\d+)$")


def summary_groups(accounts, sheet_bank_ids):
    """SUMMARY_GROUPS, then one group per account that is active or has a sheet here but is
    not listed, in priority order. accounts: tbl_bank_account rows (bank_id, bank_name,
    is_active), ordered by priority."""
    listed = {bank_id for _, rows in SUMMARY_GROUPS for bank_id, _ in rows}
    extra = tuple((a["bank_name"], ((a["bank_id"], a["bank_id"]),)) for a in accounts
                  if a["bank_id"] not in listed and (a["is_active"] or a["bank_id"] in sheet_bank_ids))
    return SUMMARY_GROUPS + extra


def account_rows(ws):
    """{row: bank_id} of the SUMMARY as it stands (read before rebuilding)."""
    return {r: ws[f"N{r}"].value for r in range(FIRST_ROW, ws.max_row + 1) if ws[f"N{r}"].value}


def _net(col, r, key):
    return (f'=IFERROR(SUMIF(INDIRECT("\'"&$N{r}&"-"&{col}${key}&"\'!L:L"),"TOTAL",'
            f'INDIRECT("\'"&$N{r}&"-"&{col}${key}&"\'!K:K")),0)')


def build_summary(ws, groups):
    """Rewrite SUMMARY from row 9 down: groups, Total, the HKD conversion block and the
    currency key row the account formulas read. Returns {bank_id: row}."""
    styles = {kind: {c: copy(ws[f"{c}{row}"]._style) for c in STYLE_COLS}
              for kind, row in STYLE_ROWS.items()}
    ws.delete_rows(FIRST_ROW, ws.max_row - FIRST_ROW + 1)

    layout, row = [], FIRST_ROW
    for heading, accounts in groups:
        layout.append(("heading", row, heading))
        first = row + 1
        for i, account in enumerate(accounts):
            layout.append(("account", first + i, account))
        row = first + len(accounts)
        layout.append(("subtotal", row, (first, row - 1)))
        layout.append(("blank", row + 1, None))
        row += 2
    total = row
    conversion_first = total + 2
    conversion_total = conversion_first + len(CONVERSION)
    key = total + 10

    def put(kind, r, values):
        for c in STYLE_COLS:
            ws[f"{c}{r}"]._style = copy(styles[kind][c])
        for c, v in values.items():
            ws[f"{c}{r}"] = v

    rows, subtotals = {}, []
    for kind, r, item in layout:
        if kind == "heading":
            put(kind, r, {"A": item})
        elif kind == "account":
            bank_id, label = item
            rows[bank_id] = r
            values = {"A": label, "M": f"=SUM(H{r}:L{r})", "N": bank_id, "Q": f"=C{r}-P{r}"}
            for net, hkd in zip(NET_COLS, HKD_COLS):
                values[net] = _net(net, r, key)
                values[hkd] = f"={net}{r}*{hkd}$7"
            put(kind, r, values)
        elif kind == "subtotal":
            first, last = item
            subtotals.append(r)
            put(kind, r, {"A": "SUB-Total", **{c: f"=SUM({c}{first}:{c}{last})" for c in NET_COLS}})
        else:
            put(kind, r, {})

    put("total", total, {"A": "Total", "M": f"=SUM(M8:M{total - 1})",
                         **{c: "=SUM(" + ", ".join(f"{c}{s}" for s in subtotals) + ")" for c in NET_COLS}})

    rate_row = {}
    for i, (ccy, net_col, rate) in enumerate(CONVERSION):
        r = conversion_first + i
        rate_row[ccy] = r
        values = {"B": ccy, "C": f"={net_col}{total}"}
        if rate is None:
            values["E"] = f"=C{r}"
        else:
            values["D"] = rate
            values["E"] = f"=C{r}*D{r}"
        put("conversion", r, values)
    put("conversion_total", conversion_total,
        {"B": "TOTAL", "E": f"=SUM(E{conversion_first}:E{conversion_total - 1})"})
    put("key", key, dict(zip(NET_COLS, KEY_CURRENCIES)))

    # The HKD-per-unit rates the H..L columns multiply by (row 7)
    ws["H7"] = f"=D{rate_row['AUD']}"
    ws["I7"] = 1
    ws["J7"] = f"=D{rate_row['JPY']}"
    ws["K7"] = f"=D{rate_row['USD']}"
    ws["L7"] = f"=D{rate_row['SGD']}"
    return rows


def relink_summary_refs(wb, old_rows):
    """Turn every =SUMMARY!<col><row> that pointed at an account row into a lookup by bank_id
    (=SUMIF(SUMMARY!$N:$N,"<id>",SUMMARY!$C:$C)), as Top Sheet already does, so the links
    survive the rebuilt row numbers. Returns how many links were rewritten."""
    rewritten = 0
    for sheet in wb.worksheets:
        if sheet.title == "SUMMARY":
            continue
        for row in sheet.iter_rows():
            for cell in row:
                m = FIXED_LINK.match(cell.value) if isinstance(cell.value, str) else None
                if m and int(m.group(2)) in old_rows:
                    col, bank_id = m.group(1), old_rows[int(m.group(2))]
                    cell.value = f'=SUMIF(SUMMARY!$N:$N,"{bank_id}",SUMMARY!${col}:${col})'
                    rewritten += 1
    return rewritten
```

- [ ] **Step 4: Call it from `create_file()`.**
  - In `create_gain_loss.py`, add `from .summary_sheet import account_rows, build_summary, relink_summary_refs,
    summary_groups` to the imports.
  - Just before `output = io.BytesIO()` at the end of `create_file()`, add:

```python
    # SUMMARY from the accounts, not the template's fixed list (BUGS.md 2026-11-02)
    summary = wb['SUMMARY']
    old_rows = account_rows(summary)
    sheet_bank_ids = {name.rpartition('-')[0] for name in wb.sheetnames
                      if name.rpartition('-')[2] in ('HKD', 'JPY', 'AUD', 'USD', 'SGD')
                      and wb[name].sheet_state == 'visible'}
    accounts = get_db().execute(
        "SELECT bank_id, bank_name, is_active FROM tbl_bank_account ORDER BY priority").fetchall()
    build_summary(summary, summary_groups(accounts, sheet_bank_ids))
    relink_summary_refs(wb, old_rows)
```

- [ ] **Step 5: Run the harness.**
  Run: `..\venv\Scripts\python.exe scripts\verify_gain_loss_workbook.py`
  Expected: G1–G4 and G7 PASS, for both "month" and "year".

- [ ] **Step 6: Check Top Sheet and Marissa Page by eye.** Their rows list fixed accounts in column P (Top Sheet) or
  fixed bank headings (Marissa Page).
  - List the bank ids Top Sheet's P column names.
  - If SHK2 or NSG is missing there, they still drop out of Top Sheet.
  - Do not change those sheets; it is D6(d) for Alvin. Record what is missing in the BUGS entry.

- [ ] **Step 7: Tie out in Excel once** (scratchpad; this is client data).
  - Pick the backup in `clients\ltv\backups\` closest after 30 Oct 15:22. If none is later, use the 13:55 pull and
    expect differences only where rows were keyed after it.
  - Write `<scratchpad>\gl_tieout.py`:

```python
import os, shutil, sys, tempfile
sys.path.insert(0, r"C:\envs\assistant\products\ltv-app\app")
import win32com.client
from openpyxl import load_workbook
from ltv_app import create_app

BACKUP = sys.argv[1]
ALVIN = (r"C:\envs\assistant\products\ltv-app\app-docs\bug-reports\2026-10-30-gain-loss-workbook-math"
         r"\2026-10-30 gain_loss - Alvin saved 15-22.xlsx")
tmp = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(BACKUP, tmp)
app = create_app({"DATABASE": tmp, "LOGIN_DISABLED": True})
data = app.test_client().post("/gain-loss/", data={"date_from": "2026-10-01", "date_to": "2026-10-30",
                                                   "bank_ref": 0, "code_ref": 0}).get_data()
out = os.path.join(tempfile.mkdtemp(), "gain_loss.xlsx")
with open(out, "wb") as f:
    f.write(data)

xl = win32com.client.DispatchEx("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
try:
    wb = xl.Workbooks.Open(out, ReadOnly=True)
    xl.CalculateFull()
    ws = wb.Worksheets("SUMMARY")
    total = next(r for r in range(9, 120) if ws.Cells(r, 1).Value == "Total")
    generated = [ws.Cells(total, c).Value or 0 for c in range(2, 7)]
    wb.Close(False)
finally:
    xl.Quit()

alvin = load_workbook(ALVIN, data_only=True)["SUMMARY"]
alvin_total = next(r for r in range(9, 120) if alvin.cell(r, 1).value == "Total")
for ccy, col, got in zip(("AUD", "HKD", "JPY", "USD", "SGD"), range(2, 7), generated):
    want = alvin.cell(alvin_total, col).value or 0
    print(ccy, "match" if abs(got - want) < 0.005 else "DIFFER")
```
  - Run: `python <scratchpad>\gl_tieout.py "<backup path>"`. Use the Python with `pywin32`; it also needs
    Flask and openpyxl. If it lacks them, run with `..\venv\Scripts\python.exe` after
    `..\venv\Scripts\python.exe -m pip install pywin32`.
  - Expected: `match` on all five. HKD and SGD are his corrected totals; AUD, JPY and USD are zero in both.

- [ ] **Step 8: Commit.**

```powershell
git add ltv_app/blueprints/gain_loss/summary_sheet.py ltv_app/blueprints/gain_loss/create_gain_loss.py scripts/verify_gain_loss_workbook.py
git commit -m "fix(gain-loss): build SUMMARY from the accounts, so SHK No. 2 and Nomura reach the Total" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Gain Loss rates: one SGD rate, and each sheet's USD value at its own rate; re-pin the baseline

Alvin, 30 Oct 2026: "use 6.06 for sgd".
- 6.06 HKD per SGD governs the conversion.
- SGD per USD must agree with it: hkd_per_usd / 6.06, not the template's static figure.
- The SUMMARY's SGD conversion of 0.18 goes.

**Files:**
- Modify: `ltv_app/blueprints/gain_loss/summary_sheet.py`: `CONVERSION`'s SGD rate; new `HKD_PER_SGD` and
  `apply_rates(wb)`
- Modify: `ltv_app/blueprints/gain_loss/create_gain_loss.py`: the two `=G{row_num}/hkd_per_usd` formulas (~lines
  227 and 246), and the call to `apply_rates`
- Test: `scripts/verify_gain_loss_workbook.py` (G5, G6)

**Interfaces:**
- Consumes: `CONVERSION`, `build_summary` (Task 11).
- Produces: `summary_sheet.HKD_PER_SGD = 6.06`, `summary_sheet.apply_rates(wb) -> None`.

- [ ] **Step 1: Add the failing cases.** In `verify_gain_loss_workbook.py`, add
  `from ltv_app.blueprints.gain_loss.summary_sheet import HKD_PER_SGD` to the imports. Then add this at the end of
  `_check()`:

```python
    wrong_usd = 0
    for name in wb.sheetnames:
        bank, _, ccy = name.rpartition("-")
        if ccy not in CCYS or not bank or wb[name].sheet_state != "visible":
            continue
        sheet = wb[name]
        for r in range(1, sheet.max_row + 1):
            h = sheet[f"H{r}"].value
            if isinstance(h, str) and h.startswith(f"=G{r}/") and h != f"=G{r}/$E$6":
                wrong_usd += 1
    _case(f"G5 [{tag}] USD values not at the sheet's own rate (E6)", wrong_usd, 0)

    sgd_row = next(r for r in range(total, ws.max_row + 1) if ws[f"B{r}"].value == "SGD")
    names = wb.defined_names
    rates = (
        "hkd_per_sgd" in names and names["hkd_per_sgd"].attr_text == "Sheet1!$C$10",
        wb["Sheet1"]["C10"].value == HKD_PER_SGD,
        wb["Sheet1"]["C8"].value == "=C2/C10",
        ws[f"D{sgd_row}"].value == "=hkd_per_sgd",
        ws["L7"].value == f"=D{sgd_row}",
    )
    _case(f"G6 [{tag}] one SGD rate: hkd_per_sgd, sgd_per_usd from it, SUMMARY uses it", rates, (True,) * 5)
```
Add G5 and G6 to the docstring:
```
  G5 every account sheet's opening-position USD value divides by that sheet's own rate (E6);
  G6 hkd_per_sgd is defined, sgd_per_usd is derived from it, and SUMMARY converts SGD with it.
```

- [ ] **Step 2: Run it and see it fail.**
  Run: `..\venv\Scripts\python.exe scripts\verify_gain_loss_workbook.py`
  Expected: G5 and G6 FAIL; G1–G4 and G7 PASS.

- [ ] **Step 3: Implement.**
  - In `summary_sheet.py`, change the SGD entry of `CONVERSION` to `("SGD", "F", "=hkd_per_sgd"),`.
  - Add `from openpyxl.workbook.defined_name import DefinedName` to the imports.
  - Add:

```python
# Alvin, 30 Oct 2026: "use 6.06 for sgd". Whether it stays fixed or later comes from a
# dated rate source is his call (BUGS.md 2026-11-02, D6).
HKD_PER_SGD = 6.06


def apply_rates(wb):
    """One SGD rate for the whole workbook: hkd_per_sgd on Sheet1, and sgd_per_usd derived
    from it and hkd_per_usd, so the sheets' USD values and SUMMARY's conversion agree."""
    ws = wb["Sheet1"]
    ws["B10"] = "hkd_per_sgd"
    ws["C10"] = HKD_PER_SGD
    ws["B10"]._style = copy(ws["B8"]._style)
    ws["C10"]._style = copy(ws["C8"]._style)
    ws["C8"] = "=C2/C10"          # sgd_per_usd = hkd_per_usd / hkd_per_sgd
    wb.defined_names["hkd_per_sgd"] = DefinedName("hkd_per_sgd", attr_text="Sheet1!$C$10")
```
  - In `create_gain_loss.py`:
    - in both opening-position blocks (long and short), replace
      `write_box_normal(ws, f'H{row_num}', f'=G{row_num}/hkd_per_usd', "currency_2")` with
      `write_box_normal(ws, f'H{row_num}', f'=G{row_num}/$E$6', "currency_2")`, where E6 is the sheet's own USD rate;
    - add `apply_rates` to the `summary_sheet` import;
    - call `apply_rates(wb)` directly after `relink_summary_refs(wb, old_rows)`.

- [ ] **Step 4: Run it.**
  Run: `..\venv\Scripts\python.exe scripts\verify_gain_loss_workbook.py`
  Expected: G1–G7 PASS for "month" and "year".

- [ ] **Step 5: Re-pin `verify_gain_loss_refactor`** (Task 9 found the cause).
  - Run: `..\venv\Scripts\python.exe scripts\verify_gain_loss_refactor.py --check > <scratchpad>\gl_after_t12.txt`
  - Read every difference against `<scratchpad>\gl_main.txt`. Expected: only
    - the F12 cell from Task 9;
    - SUMMARY's rows;
    - the opening-position H formulas;
    - Sheet1 C8, B10 and C10.
  - Anything else is a regression: stop.
  - If clean: `..\venv\Scripts\python.exe scripts\verify_gain_loss_refactor.py --save`, against the same frozen
    baseline (no `--freeze`). Then `--check` again → no DIFFERS.

- [ ] **Step 6: Commit.**

```powershell
git add ltv_app/blueprints/gain_loss/summary_sheet.py ltv_app/blueprints/gain_loss/create_gain_loss.py scripts/verify_gain_loss_workbook.py
git commit -m "fix(gain-loss): one SGD rate for the workbook; each sheet's USD value at its own rate" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
The snapshot file is git-ignored: nothing else to commit. In `BUGS.md`:
- mark the High and Medium gain-loss entries Fixed;
- mark the Low `verify_gain_loss_refactor` entry Fixed;
- list what is still with Alvin: D6 (a) short columns, (b) 6.06 fixed or sourced, (c) AUD/JPY, (d) Top Sheet and
  Marissa Page rows.

---

### Task 13: Term-sheet lifecycle (21 Sep): audit what still holds, then ask

Some of the 21 Sep order has been overtaken:
- recording a KO fixing sets status KO (`fixings/extensions/record_fixings.py:40`);
- `/ltv-stocks/` handles knock-outs in the report window (`legacy_port/term_sheet_calc.py:120`);
- the listing's POST shows all statuses (`term_sheet/views.py:52`).

Find out what is still missing before building anything.

**Files:** `BUGS.md` (the Medium term-sheet entry from Task 1); no code.

- [ ] **Step 1: For each of the order's seven acceptance criteria, find the code that meets it or show that none
  does.**

  | Criterion | Where to look |
  |---|---|
  | 1. A KO sets status KO and a KO date | `record_fixings.py` around line 40; `tbl_stock_contract` has no KO-date column (`PRAGMA table_info`) |
  | 2. The final period sets Done and a completion date | `term_sheet/views.py` `set_inactive` (~405); `grep -rn "received" ltv_app/blueprints/fixings` |
  | 3. KO/Done this week still shows, marked | `term_sheet/models.py` lines 176, 227, 271; `term_sheet_calc.py:120` |
  | 4. Gone after that week | the same |
  | 5. Every term sheet reachable without its id | `term_sheet/views.py:52` (POST shows "all"); the listing template's form |
  | 6. Inactive no longer means hidden | the status counts: `SELECT status, count(*) FROM tbl_stock_contract GROUP BY status` |
  | 7. Re-classify old Inactive ones that were KO or Done | count Inactive contracts whose periods are all received, and those with a KO fixing row |

  Run the read-only queries on the development copy.

- [ ] **Step 2: Write the result into the BUGS entry**, as a table: criterion, met / partly / not, and evidence
  (file:line or the count).

- [ ] **Step 3: Ask Alvin (D11)** which unmet criteria he still wants, in plain words (e.g. "a Done status set
  automatically when the last period is received").

- [ ] **Step 4: For whatever he wants:** superpowers:brainstorming, then a spec in
  `docs/superpowers/specs/2026-11-<dd>-term-sheet-lifecycle-design.md` (no client figures), then its own plan with
  superpowers:writing-plans. The schema change will be a `_ADDED_COLUMNS` entry and a migration of the Inactive rows.
  If he wants nothing, close the entry with his answer.

---

### Task 14: Blocked Unblocked from the app: study → spec

The work order is a study and proposal. The deliverable here is a spec Alvin can approve, then a plan of its own.

**Files:**
- Create: `docs/superpowers/specs/2026-11-<dd>-blocked-unblocked-design.md` (tracked, public: layout and rules only,
  no figures)
- Scratchpad: spike scripts

- [ ] **Step 1: Ask D7**: which output, the rulings on the five workbook faults, and the holdings basis.

- [ ] **Step 2: Spike the template route** on a copy of `2026-10-27 Blocked Unblocked.xlsm`. Write
  `<scratchpad>\bu_roundtrip.py`:

```python
import shutil, sys, tempfile, zipfile, os
from openpyxl import load_workbook

SRC = sys.argv[1]   # the evidence folder's 2026-10-27 Blocked Unblocked.xlsm
work = tempfile.mkdtemp()
before = os.path.join(work, "before.xlsm")
after = os.path.join(work, "after.xlsm")
shutil.copy(SRC, before)
load_workbook(before, keep_vba=True).save(after)


def parts(path):
    with zipfile.ZipFile(path) as z:
        return sorted(n for n in z.namelist())


b, a = parts(before), parts(after)
print("vbaProject.bin kept:", "xl/vbaProject.bin" in a)
print("drawings before/after:", sum(n.startswith("xl/drawings/drawing") for n in b),
      sum(n.startswith("xl/drawings/drawing") for n in a))
print("parts lost:", [n for n in b if n not in a])
print("after:", after)
```
  - Run it with `-I`, so nothing in the evidence folder can be imported: `..\venv\Scripts\python.exe -I
    <scratchpad>\bu_roundtrip.py "<evidence>\2026-10-27 Blocked Unblocked.xlsm"`.
  - Run the evidence's `scripts\page_setup_dump.py` on `before` and on `after`, and diff the two outputs: print
    areas, zoom, manual breaks, hidden rows and columns. Read that script before running it; it drives Excel.
  - Record what survives. openpyxl is known to drop drawings.

- [ ] **Step 3: Spike the native route.**
  - Build only the Blocked Unblocked sheet's skeleton with openpyxl on a database copy, the way the notebook builds
    its sheet.
  - Set Legal paper (5), landscape, zoom 75, the manual row break and the hidden columns from the work order's
    section 2.
  - Open it through Excel COM and confirm the page count.

- [ ] **Step 4: Write the spec.** It covers:
  - the approach chosen and why (from Steps 2–3);
  - the inputs and the existing code that yields each: `portfolio`, `block_unblock`, the `bank` short views,
    `tbl_stock_price` or Yahoo for closes, the edition date;
  - the rules Alvin has given (work order §3) and his D7 rulings;
  - Filter Active Stocks done in Python (work order §2, the macro's three steps);
  - the print layout table (work order §2), matched page for page against the two PDFs;
  - a harness: build the 30 Oct edition from the 30 Oct ledger copy and tie Equities, PAGE 3 and the account pages,
    with figures worked out at runtime.

  Keep the evidence's figures out of the spec: refer to the work order for them.

- [ ] **Step 5: Spec review with Alvin**, then superpowers:writing-plans for its implementation plan.

---

### Task 15: Release 4.0.42 and put it into production on this PC (on Alvin's request)

Nothing goes to PythonAnywhere: the local ledger is LTV's only database (Alvin, 2 Nov 2026). "Deploy" here means
switching `prod\` to the release and restarting it.

- [ ] **Step 1: Full harness run on the development copy.** After Task 4, bare `create_app()` is the development
  copy, so every harness is safe to run.

```powershell
Get-ChildItem scripts\verify_*.py | ForEach-Object { "== $($_.Name)"; ..\venv\Scripts\python.exe $_.FullName 2>&1 | Select-String -Pattern 'RESULT|FAIL|DIFFERS' | Select-Object -Last 3 }
```
Expected: no FAIL and no DIFFERS. `verify_report_data_extraction` may report DIFFERS by drift, which by itself says
nothing (CLAUDE.md). Confirm any such line by comparing dumps from before and after on the same database.

- [ ] **Step 2: Release.** Set `VERSION` to `4.0.42`, then
  `git add VERSION; git commit -m "Bump version to 4.0.42" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"`.

- [ ] **Step 3: Put it into production only when Alvin asks**, by the new "Deploying" steps in the product
  `CLAUDE.md`. These are local; nothing touches PythonAnywhere.
  1. `git status --short` in `prod\`.
  2. Production window closed.
  3. Ledger backup, hashes compared.
  4. `git -C prod checkout --detach <4.0.42 commit>`.
  5. Start it with `app-ops\start-ltv.bat`.
  6. Check that `v4.0.42` shows on the login page.

  Record it in `clients\ltv\PENDING.md` **Last session**.

- [ ] **Step 4: Push to GitHub only on Alvin's word** (`git push origin main`). Before pushing:
  - run `git log origin/main..HEAD --stat` and confirm no database, `BUGS.md` or `_*_snapshot.txt` is in it;
  - grep the new commits' diffs for anything that looks like a client figure.

---

## Not in this plan (seen while planning)

- `STOCK_TRANSACTIONS` in the notebook says "Stock Dividends", but the ledger's type is "Stock Dividend", so dividend
  rows may never print in the notebook (LTV PENDING #107 side note). Confirm and log in `BUGS.md` as its own entry.
- The template's AUD (5.5) and JPY (0.07) conversion rates disagree with its named rates. They are zero today; D6(c).
- `verify_quantity_parsing.py` posts forms through the test client with its default database. Check it writes only to
  a copy before its next run.
