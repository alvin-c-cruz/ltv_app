"""Assemble the screens captured by demo_capture.py into a walkthrough PDF.

Reads demo/shots/ and writes demo/ltv_app_demo.pdf at the workspace root.
"""
import argparse
import base64
import json
import os

from playwright.sync_api import sync_playwright

PROFILES = {
    "live": {
        "dir": "demo",
        "pdf": "ltv_app_demo.pdf",
        "note": (
            "<b>Confidential.</b> Every figure, account name, contract and holding in "
            "this document is live data from the production ledger as it stood on "
            "4 September 2026. It is a point-in-time snapshot, not a live view, and it "
            "is not a statement of account. Circulate only to people already entitled "
            "to see these positions."
        ),
        "callout": (
            "<b>About this snapshot.</b> The figures are read from a copy of the "
            "production database taken on the date above; the live database is opened "
            "read-only and never written to. The workbooks shown beside five of the "
            "screens are the application's own exports, unedited."
        ),
    },
    "sample": {
        "dir": "demo_sample",
        "pdf": "ltv_app_demo_sample.pdf",
        "note": (
            "<b>Illustrative data.</b> The account names, contracts, holdings and "
            "figures in this document are illustrative, dated 3 September 2026. They "
            "are not real positions, and no live account data appears anywhere in it. "
            "Ticker symbols are real listed securities; the prices shown against them "
            "are simulated."
        ),
        "callout": "",
    },
}

DEMO = None
SHOTS = None
OUT_HTML = None
OUT_PDF = None
COVER_NOTE = None
CLOSING_NOTE = None

CSS = """
:root {
  --nav-bg: #0c1a2e; --accent: #b8941f; --accent-light: #f8f0dc;
  --bg: #f3f0e8; --border: #dbd5c5; --text: #1a2236; --muted: #7a6e5e;
  --gold: #e6c96a;
}
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', Arial, sans-serif; color: var(--text);
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.page {
  width: 297mm; height: 210mm; page-break-after: always; position: relative;
  overflow: hidden; background: #ffffff;
}
.page:last-child { page-break-after: auto; }

/* ---------- cover ---------- */
.cover { background: var(--nav-bg); color: #fff; padding: 30mm 26mm; }
.cover .brand {
  font-size: 15pt; letter-spacing: .42em; font-weight: 700; color: var(--gold);
}
.cover h1 { font-size: 38pt; line-height: 1.08; margin: 14mm 0 0; font-weight: 600; }
.cover .sub { font-size: 15pt; color: #9fb0c6; margin-top: 6mm; font-weight: 300; }
.cover .rule { width: 46mm; height: 3px; background: var(--accent); margin: 12mm 0; }
.cover .meta { font-size: 20pt; color: #8fa1ba; line-height: 2; }
.cover .meta b { color: #dfe7f1; font-weight: 600; }
.cover .note {
  position: absolute; left: 26mm; right: 26mm; bottom: 18mm;
  font-size: 8.5pt; color: #7e90a8; border-top: 1px solid #24344f; padding-top: 5mm;
}

/* ---------- contents ---------- */
.contents { padding: 20mm 24mm 16mm; background: var(--bg); }
.contents h2 { font-size: 20pt; margin: 0 0 3mm; font-weight: 600; }
.contents .lede { font-size: 10pt; color: var(--muted); margin: 0 0 8mm; max-width: 200mm;
                  line-height: 1.6; }
.toc { column-count: 2; column-gap: 14mm; }
.toc-item {
  break-inside: avoid; display: flex; gap: 4mm; align-items: baseline;
  padding: 1.7mm 0; border-bottom: 1px solid var(--border); font-size: 9.5pt;
}
.toc-num { color: var(--accent); font-weight: 700; min-width: 8mm; font-size: 8.5pt; }
.toc-title { flex: 1; }
.toc-path { color: var(--muted); font-family: Consolas, monospace; font-size: 7.5pt; }

/* ---------- screen pages ---------- */
.screen { display: flex; background: var(--bg); }
.side {
  width: 78mm; flex: none; background: var(--nav-bg); color: #dfe7f1;
  padding: 16mm 11mm; display: flex; flex-direction: column;
}
.side .num {
  font-size: 8pt; letter-spacing: .22em; color: var(--gold); font-weight: 700;
  margin-bottom: 5mm;
}
.side h3 { font-size: 16pt; line-height: 1.22; margin: 0 0 6mm; font-weight: 600; color: #fff; }
.side .bar { width: 18mm; height: 2px; background: var(--accent); margin-bottom: 6mm; }
.side p { font-size: 9pt; line-height: 1.72; color: #a9bbd1; margin: 0; }
.side .path {
  margin-top: auto; font-family: Consolas, monospace; font-size: 8pt;
  color: var(--gold); border-top: 1px solid #24344f; padding-top: 4mm;
}
.shot {
  flex: 1; padding: 11mm 11mm 9mm; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.shot img {
  max-width: 100%; max-height: 100%; object-fit: contain;
  border: 1px solid var(--border); box-shadow: 0 2px 10px rgba(12,26,46,.14);
  background: #fff;
}
.shot.dual { gap: 6mm; }
.shot.dual .frame {
  flex: 1; min-height: 0; width: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.shot.dual .frame img { max-height: 100%; }
.shot .cap {
  font-size: 6.5pt; letter-spacing: .18em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 1.6mm; align-self: flex-start;
}
.folio {
  position: absolute; right: 9mm; bottom: 5mm; font-size: 7.5pt; color: var(--muted);
}

/* ---------- closing ---------- */
.closing { padding: 20mm 26mm; background: var(--bg); }
.closing h2 { font-size: 20pt; margin: 0 0 8mm; font-weight: 600; }
.cols { display: flex; gap: 12mm; }
.col { flex: 1; }
.col h4 {
  font-size: 9pt; letter-spacing: .14em; text-transform: uppercase;
  color: var(--accent); margin: 0 0 4mm;
}
.col ul { margin: 0; padding-left: 5mm; font-size: 9.5pt; line-height: 1.85; color: #33405c; }
.col p { font-size: 9.5pt; line-height: 1.8; color: #33405c; margin: 0 0 4mm; }
code {
  font-family: Consolas, monospace; font-size: 8.5pt; background: #e8e3d6;
  padding: .5mm 1.5mm; border-radius: 2px;
}
/* ---------- what it replaced ---------- */
.savings { padding: 20mm 26mm; background: var(--bg); }
.savings h2 { font-size: 20pt; margin: 0 0 4mm; font-weight: 600; }
.savings .lede {
  font-size: 10.5pt; line-height: 1.75; color: #4c5876; margin: 0 0 10mm;
  max-width: 200mm;
}
.savings table { border-collapse: collapse; width: 100%; }
.savings th {
  text-align: left; font-size: 7.5pt; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); font-weight: 600; padding: 0 8mm 2.5mm 0;
  border-bottom: 1px solid var(--border);
}
.savings td {
  padding: 4mm 8mm 4mm 0; border-bottom: 1px solid #e6e1d4; vertical-align: baseline;
}
.savings td.task { font-size: 11pt; font-weight: 600; color: #1a2236; width: 52mm; }
.savings td.was { font-size: 9.5pt; color: #6b5f4c; }
.savings td.now {
  font-size: 15pt; font-weight: 600; color: var(--accent); white-space: nowrap;
  width: 30mm;
}
.savings td.fold { font-size: 9.5pt; color: #7a6e5e; white-space: nowrap; }
.savings .total {
  margin-top: 11mm; border-left: 3px solid var(--accent); background: var(--accent-light);
  padding: 6mm 8mm; color: #4a3f28; font-size: 9.5pt; line-height: 1.7;
}
.savings .total .big {
  font-size: 15pt; font-weight: 600; color: #4a3f28; margin-bottom: 3mm;
}
.callout {
  margin-top: 6mm; border-left: 3px solid var(--accent); background: var(--accent-light);
  padding: 4mm 7mm; font-size: 8.5pt; line-height: 1.65; color: #4a3f28;
}
"""


def data_uri(path):
    with open(path, "rb") as fh:
        return "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")


def shot_block(m):
    """The screen capture, plus the workbook it generates when one was captured.

    Pages carrying a sample report (2026-09-04 review) show both: the app screen
    on top, the Excel output it produces underneath.
    """
    screen = data_uri(os.path.join(SHOTS, m["file"]))
    report = os.path.join(SHOTS, m["slug"] + "-report.png")
    if not os.path.exists(report):
        return '<div class="shot"><img src="{0}"></div>'.format(screen)
    return (
        '<div class="shot dual">'
        '<div class="frame"><div class="cap">In the app</div><img src="{0}"></div>'
        '<div class="frame"><div class="cap">The workbook it generates</div>'
        '<img src="{1}"></div>'
        '</div>'
    ).format(screen, data_uri(report))


def build_html(manifest):
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<style>", CSS, "</style></head><body>"]

    # cover
    parts.append("""
<div class="page cover">
  <div class="brand">L T V</div>
  <h1>Stock Management<br>System</h1>
  <div class="sub">A guided walkthrough of the day-to-day application</div>
  <div class="rule"></div>
  <div class="meta">
    <div>Version <b>4.0.25</b></div>
    <div>Developed by <b>Alvin C. Cruz</b></div>
  </div>
  <div class="note">""" + COVER_NOTE + """</div>
</div>""")

    # contents
    toc = "".join(
        "<div class='toc-item'><span class='toc-num'>{:02d}</span>"
        "<span class='toc-title'>{}</span>"
        "<span class='toc-path'>{}</span></div>".format(i, m["title"], m["path"])
        for i, m in enumerate(manifest, start=1)
    )
    parts.append("""
<div class="page contents">
  <h2>What the system does</h2>
  <p class="lede">
    LTV tracks one portfolio's equity holdings across several bank and broker
    accounts, and the accumulator / decumulator contracts written against them. Each
    trading day it prices the live contracts against the day's closes, works out the
    shares fixed, writes them into the ledger, and moves them through review, charging
    and locking. Positions, margin and every report are derived from that one ledger.
    The pages below follow that day in order.
  </p>
  <div class="toc">""" + toc + """</div>
</div>""")

    for i, m in enumerate(manifest, start=1):
        parts.append("""
<div class="page screen">
  <div class="side">
    <div class="num">{num:02d} &nbsp;/&nbsp; {total}</div>
    <h3>{title}</h3>
    <div class="bar"></div>
    <p>{body}</p>
    <div class="path">{path}</div>
  </div>
  {shot}
  <div class="folio">{num} of {total}</div>
</div>""".format(num=i, total=len(manifest), title=m["title"], body=m["body"],
                 path=m["path"], shot=shot_block(m)))

    parts.append("""
<div class="page savings">
  <h2>From hours to seconds</h2>
  <p class="lede">
    When this work began in 2018 the reporting day was done by hand &mdash; the notebook
    written out longhand, the day's trades transcribed, the holdings report assembled a
    line at a time. Those deliverables are unchanged in form; what changed is how long
    they take. The times on the right are measured end to end against the current ledger
    of roughly 28,000 transactions.
  </p>
  <table>
    <tr><th>Deliverable</th><th>By hand</th><th>Now</th><th>Faster by</th></tr>
    <tr><td class="task">Notebook</td>
        <td class="was">Written out longhand &mdash; one to two hours</td>
        <td class="now">0.4 s</td><td class="fold">~13,000&times;</td></tr>
    <tr><td class="task">Trades Done</td>
        <td class="was">Several minutes of transcription</td>
        <td class="now">0.04 s</td><td class="fold">~7,000&times;</td></tr>
    <tr><td class="task">LTV Stocks report</td>
        <td class="was">Over an hour</td>
        <td class="now">1.0 s</td><td class="fold">~3,600&times;</td></tr>
    <tr><td class="task">Realised gain / loss</td>
        <td class="was">Two hours of processing before it could be printed</td>
        <td class="now">2.2 s</td><td class="fold">~3,300&times;</td></tr>
  </table>
  <div class="total">
    <div class="big">About four and a half hours of manual work &rarr; under four seconds.</div>
    Taken together the four deliverables above account for the better part of a working
    day. The application produces all four, from the same ledger, in the time it takes to
    read this sentence &mdash; and produces them the same way every time.
  </div>
</div>""")

    parts.append("""
<div class="page closing">
  <h2>Behind the screens</h2>
  <div class="cols">
    <div class="col">
      <h4>How it is built</h4>
      <p>A Flask application of roughly thirty blueprints over a single SQLite
      database, deployed on PythonAnywhere. Data access is raw <code>sqlite3</code>
      through one connection per request — no ORM — with a small dataclass base
      supplying <code>save()</code> / <code>get()</code> / <code>all()</code>.</p>
      <p>Every Excel deliverable is produced with <code>openpyxl</code> at request
      time. The report endpoints are backed by declared indexes created at start-up,
      which is what keeps the two largest reports inside the host's request limit.</p>
    </div>
    <div class="col">
      <h4>How access is controlled</h4>
      <p>Authentication is default-deny. A <code>before_request</code> hook demands an
      authenticated user for every endpoint except an explicit two-entry allowlist, so
      a newly added blueprint is private the moment it is registered and publishing one
      takes a deliberate, reviewable edit.</p>
      <p>Two roles: staff run the daily workflow; superusers can additionally lock and
      unlock records, manage users and inspect uploads.</p>
    </div>
    <div class="col">
      <h4>The daily cycle</h4>
      <ul>
        <li>Load the day's closing prices</li>
        <li>Generate fixings from the live contracts</li>
        <li>Record them into the ledger</li>
        <li>Review against the broker advices</li>
        <li>Apply charges</li>
        <li>Lock the day</li>
        <li>Export the notebook and reports</li>
      </ul>
    </div>
  </div>
  """ + (('<div class="callout">' + CLOSING_NOTE + '</div>') if CLOSING_NOTE else "") + """
</div>""")

    parts.append("</body></html>")
    return "".join(parts)


def main():
    global DEMO, SHOTS, OUT_HTML, OUT_PDF, COVER_NOTE, CLOSING_NOTE
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(PROFILES), default="live")
    args = parser.parse_args()
    prof = PROFILES[args.profile]

    DEMO = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", prof["dir"]))
    SHOTS = os.path.join(DEMO, "shots")
    OUT_HTML = os.path.join(DEMO, "demo.html")
    OUT_PDF = os.path.join(DEMO, prof["pdf"])
    COVER_NOTE = prof["note"]
    CLOSING_NOTE = prof["callout"]

    with open(os.path.join(SHOTS, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)

    html = build_html(manifest)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto("file:///" + OUT_HTML.replace("\\", "/"), wait_until="load")
        page.wait_for_timeout(1500)
        page.pdf(path=OUT_PDF, width="297mm", height="210mm",
                 print_background=True, margin={"top": "0", "bottom": "0",
                                                "left": "0", "right": "0"})
        browser.close()

    print("wrote", OUT_PDF, "({:.1f} MB)".format(os.path.getsize(OUT_PDF) / 1e6))


if __name__ == "__main__":
    main()
