"""Drive the ltv_app demo instance with Playwright and capture one PNG per screen.

Requires scripts/run_demo_app.py to already be serving on port 5055. Since the
2026-09-04 review the database behind it is a COPY of the real client ledger
(instance/demo/live/), not the synthetic build -- so every screenshot carries
real client holdings and demo/ is gitignored at the workspace root. Writes PNGs plus a manifest.json into demo/shots/ at
the workspace root -- deliberately outside server/, whose .gitignore
un-ignores scripts/ recursively and would make generated files committable.
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

# Two builds come out of these scripts:
#   live   -- a copy of the real client ledger (demo/, confidential)
#   sample -- the synthetic database from make_demo_db.py, invented names and
#             numbers in the identical layout (demo_sample/, shareable)
# Only the account references and the as-of date differ; everything else is shared.
PROFILES = {
    "live": {
        "port": 5055,
        "dir": "demo",
        "as_of": "2026-09-04",
        "trades": "/trades/",
        "fixings": "/fixings/",
        "ltv_stocks": "/ltv-stocks/",
        "term_sheet": "/term-sheet/NSG",
        "contract": "/term-sheet/edit/1276",
        "drill": "/bank/NSG/3993",
    },
    "sample": {
        "port": 5056,
        "dir": "demo_sample",
        "as_of": "2026-09-03",
        # the synthetic ledger's own last trading day, so the date-defaulted
        # pages aren't empty when the wall clock has moved on
        "trades": "/trades/?trade_date=2026-09-03",
        "fixings": "/fixings/?trade_date=2026-09-03",
        "ltv_stocks": "/ltv-stocks/?report_date=2026-09-03",
        "term_sheet": "/term-sheet/NGS",
        "contract": "/term-sheet/edit/8",
        "drill": "/bank/NGS/1810",
    },
}
DRILL_MONTH = ("2026-08-01", "2026-08-31")

BASE = None   # set from the chosen profile in main()
OUT = None

VIEWPORT = {"width": 1500, "height": 950}

# (slug, path, caption-title, caption-body, full_page)
SCREENS = [
    ("01-login", "/login", "Sign in",
     "Authentication is default-deny: every endpoint requires a logged-in user "
     "unless it is on an explicit two-entry allowlist, so a newly added blueprint "
     "is private automatically.", False),
    ("02b-nav", "/", "One menu over the whole operation",
     "Daily operations sit on the top level — workflow, trades, fixings, pricing — with "
     "reference data under Other Records and every Excel deliverable under Reports.", False),
    ("02-home", "/", "Consolidated position dashboard",
     "The landing page rebuilds every holding from the transaction ledger itself — "
     "there is no stored balance. Each bank card lists shares held and the running "
     "average cost per stock; any row drills through to that stock's full history.", True),
    ("03-workflow", "/workflow/", "Daily workflow queue",
     "The superuser view of everything still in flight: trades awaiting review, "
     "reviewed trades still missing broker charges, and completed rows ready to lock. "
     "Each section is a step in the daily close.", True),
    ("03b-workflow-charges", "/workflow/", "Workflow: charges outstanding",
     "The Charges tab lists reviewed trades that still carry no brokerage, stamp duty or "
     "other fees. Fees can be applied in bulk, or a row flagged as genuinely charge-free "
     "so it stops coming back.", True),
    ("03c-workflow-locking", "/workflow/", "Workflow: ready to lock",
     "Reviewed and costed rows queue here for locking. Locking freezes a trade — it drops "
     "out of every queue and can only be reopened by a superuser.", True),
    ("04-trades", "{trades}", "Trades Done",
     "The day's blotter across all accounts, grouped by bank and settlement currency, "
     "with a print/export view and per-row edit. Accumulator fixings and hand-entered "
     "spot trades land in the same ledger.", True),
    ("05-trade-add", "/trades/add", "Booking a trade",
     "The add-trade form resolves the next banking day from the HK holiday calendar, "
     "pre-fills the running average for the chosen stock and account, and validates "
     "charges before the row is written.", False),
    ("06-fixings", "{fixings}", "Fixing generation",
     "For the chosen trade date the app walks every live accumulator and decumulator, "
     "compares each observation day's close against strike and knock-out, and works out "
     "the shares fixed — doubled below strike, zero once knocked out. Generate exports "
     "the day's sheet for the banks; Record writes the trades into the ledger, shown here "
     "grouped by account with amounts, charges and net settlement.", True),
    ("07-term-sheets", "{term_sheet}", "Term sheets by account",
     "Every accumulator/decumulator contract on one account: strike and knock-out "
     "levels, daily share size, periods received against periods remaining, and the "
     "next fixing date. Locked contracts are read-only until deliberately unlocked.", True),
    ("08-term-sheet-edit", "{contract}", "Contract detail and fixing schedule",
     "Opening a contract shows the generated fixing schedule — one period per month "
     "over the tenor, each with its observation-day count, guaranteed-period flag and "
     "shares actually received. The schedule is validated for gaps against the tenor.", True),
    ("09-bank-drill", "{drill}", "Per-stock transaction history",
     "Drilling into a position replays every transaction that built it, with the "
     "running balance and average cost recomputed line by line — the audit trail "
     "behind the dashboard number.", True),
    ("10-review", "/review/", "Review",
     "Newly imported or hand-entered trades sit unreviewed until an operator confirms "
     "them against the broker advice. Review is the gate before charges and locking.", True),
    ("11-charges", "/charges/", "Charges",
     "Reviewed trades that still carry no brokerage, stamp duty or other fees. Rows can "
     "be costed here, or explicitly flagged as genuinely charge-free so they stop "
     "reappearing in the queue.", True),
    ("12-lock", "/lock/", "Locking",
     "The final step: locked rows become immutable and drop out of the workflow queues. "
     "Unlocking is a superuser action and is deliberately awkward.", True),
    ("13-ltv-stocks", "{ltv_stocks}", "LTV Stocks report",
     "The main client report — an Excel workbook of every holding across every account, "
     "valued at the chosen closing date. Backed by dedicated report indexes so it "
     "completes well inside the hosting request timeout.", False),
    ("14-gain-loss", "/gain-loss/", "Realised gain / loss",
     "Realised results per stock and account over a date range, computed from the same "
     "average-cost pass the dashboard uses, exported to Excel.", False),
    ("15-stock-position", "/stock-position/", "Stock position export",
     "A point-in-time position snapshot across all accounts, in the layout the "
     "custodians' reconciliation expects.", False),
    ("16-dividends", "/dividends/", "Cash dividends",
     "Declared dividends recorded per account and stock with declaration, ex, record and "
     "payment dates, nominal held, rate per share and withholding — the basis for "
     "checking whether a broker credit actually arrived.", True),
    ("17-block-unblock", "/block-unblock/", "Blocked / unblocked shares",
     "Which of the shares held are pledged against a live decumulator and which are free "
     "to sell — derived by netting positions against the undelivered leg of each contract.", True),
    ("18-margin", "/cash-margin/", "Margin reports",
     "Cash and HKD margin exports summarise the exposure each account carries from its "
     "live contracts — the figure the credit-line review runs on.", False),
    ("19-prices", "/stock-price/", "Price loading",
     "Closing prices are pulled per ticker from Yahoo and stored daily; the fixing engine "
     "reads them from this table and falls back to the previous close on a data gap.", False),
    # full_page=False on purpose: the price history and the stock master both run to
    # hundreds of rows, and a full-page capture shrinks the type to nothing in the PDF
    # (2026-09-04 review). A viewport's worth shows the shape without the wall.
    ("20-prices-view", "/stock-price/view", "Stored closing prices",
     "The loaded price history, filterable by stock and date — useful when a fixing "
     "result needs to be traced back to the observation it came from.", False),
    ("21-pricing", "/pricing/", "Pricing sheets",
     "Indicative term sheets pasted straight from an issuer's email are parsed into a "
     "comparison grid and exported as an Excel pricing sheet for the client.", False),
    ("22-notebook", "/notebook/", "Notebook export",
     "The day's trades and transfers as a single formatted workbook — the hand-off "
     "document produced at the end of each trading day.", False),
    ("23-stocks", "/stocks/", "Stock master",
     "The instrument master: local code, company name, Yahoo ticker and settlement "
     "currency. Everything else keys off these rows.", False),
    ("24-bank-accounts", "/bank-accounts/", "Bank accounts",
     "Accounts carry the settings that change how the engine treats them — trade-date "
     "versus value-date basis, whether the bank quotes indicatively, report label and "
     "display order.", True),
    ("25-users", "/users/", "Users and roles",
     "Two roles: staff can operate the daily workflow, superusers can additionally lock, "
     "unlock, manage users and inspect uploads.", True),
    ("26-downloads", "/upload/downloads", "Downloads",
     "Every generated workbook in one place, so a report can be re-fetched without "
     "regenerating it.", False),
]


# Screens dropped from the walkthrough after the 2026-09-04 marked-up review of
# v4.0.25 (scan 0035.pdf). Kept in SCREENS above so the captions survive for
# whenever the feature is ready -- remove a slug from here to put it back.
DEFERRED = {
    # "already in workflow" -- pages 13/14/15 duplicate the workflow tour
    "10-review",
    "11-charges",
    "12-lock",
    # marked "not ready for demo" / struck through
    "15-stock-position",
    "16-dividends",
    "17-block-unblock",
    "18-margin",
    "21-pricing",
    "26-downloads",
}
SCREENS = [s for s in SCREENS if s[0] not in DEFERRED]

ACTIONS = {
    "03b-workflow-charges": ("js", "switchWorkflowTab('charges')"),
    "03c-workflow-locking": ("js", "switchWorkflowTab('locking')"),
    "02b-nav": ("hover", "li.has-dropdown:has(> span:text-is('Reports'))"),
    # The drill defaults to the whole current year on GET; date_from/date_to are
    # POST-only. One month keeps the table readable at PDF size (2026-09-04 review).
    "09-bank-drill": ("submit", """
        document.querySelector('input[name=date_from]').value = '%s';
        document.querySelector('input[name=date_to]').value   = '%s';
        document.querySelector('form.txn-filter').submit();
    """ % DRILL_MONTH),
}


def main():
    global BASE, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(PROFILES), default="live")
    args = parser.parse_args()
    prof = PROFILES[args.profile]

    BASE = "http://127.0.0.1:{}".format(prof["port"])
    OUT = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", prof["dir"], "shots"))
    os.makedirs(OUT, exist_ok=True)
    screens = [(slug, path.format(**prof), title, body, full)
               for slug, path, title, body, full in SCREENS]
    print("profile {} -> {} (port {})".format(args.profile, OUT, prof["port"]))

    manifest = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        # 1. login screen, captured before authenticating
        page.goto(BASE + "/login", wait_until="networkidle")
        page.screenshot(path=os.path.join(OUT, "01-login.png"))

        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "demo1234")
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        assert "Logout" in page.content(), "login failed"

        # The walkthrough now runs against a copy of the real ledger, so the
        # day's fixings are already recorded -- nothing is synthesised here.
        # (The old build wrote fixings for a hardcoded 2026-09-03 to give the
        # synthetic database something to show.)

        for slug, path, title, body, full in screens:
            if slug == "01-login":
                manifest.append({"slug": slug, "file": "01-login.png",
                                 "title": title, "body": body, "path": path.split("?")[0]})
                continue
            try:
                page.goto(BASE + path, wait_until="networkidle")
            except Exception as exc:
                print("SKIP", slug, path, exc.__class__.__name__)
                continue
            page.wait_for_timeout(350)
            action = ACTIONS.get(slug)
            if action:
                kind, arg = action
                if kind == "js":
                    page.evaluate(arg)
                elif kind == "submit":
                    page.evaluate(arg)
                    page.wait_for_load_state("networkidle")
                else:
                    page.hover(arg)
                page.wait_for_timeout(400)
            fname = slug + ".png"
            page.screenshot(path=os.path.join(OUT, fname), full_page=full)
            manifest.append({"slug": slug, "file": fname, "title": title,
                             "body": body, "path": path.split("?")[0]})
            print("captured", slug, path)

        browser.close()

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print("wrote", len(manifest), "screens")


if __name__ == "__main__":
    sys.exit(main())
