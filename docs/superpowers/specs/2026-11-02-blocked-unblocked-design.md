# Blocked Unblocked from the app — design

Date: 2026-11-02
Status: Draft. Pending Alvin on D7a (output), D7b (workbook faults) and D7c (Shares Blocked basis).
Work order: `app-docs/bug-reports/2026-10-30-blocked-unblocked-from-the-app.md` (outside this repository). Its
evidence folder holds the 27 Oct and 30 Oct editions, the two PDFs Alvin printed, and the root session's scripts.

This spec contains no client figures. Every share count, cost, price or total it refers to is in the work order or
its evidence, and the harness in section 8 works them out at runtime.

## 1. Goal and scope

Alvin builds a weekly workbook, `<date> Blocked Unblocked.xlsm`, by hand. Per account and stock it shows the shares
held, their cost and average, the shares that must stay blocked for live decumulators (and the rest, unblocked), and
market value against cost. He prints two PDFs from it:

- **Blocked Unblocked**: the `Blocked Unblocked` sheet, 2 pages.
- **Market vs Average**: `Market vs Average`, `Market vs Average (2)`, `PAGE 3` and one `PAGE 3 - <account>` page for
  each account holding shares, 9 pages on 30 Oct.

Alvin (30 Oct): "format and page break is important".

**In scope.** The app builds the edition for a given date from its own database: the printed sheets with their
exact print layout, Filter Active Stocks applied in Python, and a data sheet the figures can be tied against.

**Out of scope.**
- The working sheets nobody prints: `Claude Log`, `Closing`, `2333.hk`, `Stocks`, `Loan`, `Online`,
  `Online (SHORT)`, `Blocked Shares`, `Summary-Equities`. Section 7 says what the app keeps of them.
- The VBA module: the app does its work itself.
- The Yahoo download: closes come from `tbl_stock_price` (section 3).
- Any change to how holdings, shorts or decumulator schedules are recorded.

## 2. Approach chosen, and why

Two spikes were run on copies of the evidence and of the ledger. Their scripts and full outputs are in the task
report (`.superpowers/sdd/2026-11-02-inbox-and-open-items/task-14-report.md`, local only).

### 2.1 Template route: fill the existing workbook

openpyxl 3.1.5, `load_workbook(..., keep_vba=True).save(...)`, on copies of both editions. Excel COM, read-only,
compared each pair before and after the round trip.

What survived:
- `xl/vbaProject.bin`, so the macro is kept.
- Every print setting Excel reads back, on all ten printed sheets: print area, paper, orientation, zoom, fit-to,
  margins, print titles, manual row and column breaks, hidden rows and columns, and the page count. All were identical
  before and after.
- The printed output. Exported to PDF, the Market vs Average set (9 pages) was pixel-identical. The Blocked Unblocked
  pages were the same 2 pages, with about 0.2% of pixels moved by a text-baseline hint openpyxl drops
  (`x14ac:dyDescent` on each row). The difference can't be seen at reading size.
- After a full recalculation, the values and formulas inside every printed print area were identical, apart from one
  cell holding a single space (`Blocked Unblocked!A1`). The error-cell count was unchanged on every sheet.
- Comments, conditional formats, merged cells and the 54 defined names.

What was lost:
- Both DrawingML parts:
  - the **Filter Active Stocks button** on `Blocked Unblocked` (W1:Y2, outside the print area);
  - the pasted web controls and images on `Closing`, which isn't printed.
- The 18 `printerSettings*.bin` parts. These matter for old editions: the 27 Oct edition stores paper as driver
  form 10001, which prints 13 × 8.5 in on the current printer, not Legal. Alvin's 30 Oct save sets paper 5 and the
  zoom of 78 itself, so a template must be that save or a later one.
- `xl/metadata.xml`. The column A counter formulas on `Blocked Unblocked` lose their dynamic-array flag and come back as
  legacy array formulas. They give the same values.
- `calcChain.xml` and the web-extension task pane. Shared strings are rewritten as inline strings. All harmless.
- openpyxl writes formulas without cached values, so the file holds no numbers until Excel recalculates it.

The round trip is safe for printing. The template route still fails on everything around it:
1. **The app would compute every figure anyway.** Filter Active Stocks hides rows by their values, and openpyxl can't
   evaluate the formula chain (`Online` → `Equities` → `Summary-Equities` → the printed sheets). The app would need to
   duplicate that chain in Python or drive Excel, and the app has no Excel automation.
2. **The template is client data.** It is a 20-sheet workbook full of figures and account names, so it can't go in
   `instance/excel_templates/`, which this public repository tracks. It would have to be read from Alvin's Dropbox or an
   untracked file, and would drift from edition to edition.
3. **Fixed rows.** `Blocked Unblocked` has one 3-row block for each stock in a fixed list, and the other sheets hide
   rows by hand. A new stock, or an account starting to hold shares, needs inserted rows or a copied sheet. openpyxl
   does both poorly: `insert_rows` moves no merges, conditional formats or formula references, and `copy_worksheet`
   drops print setup, conditional formats and comments.
4. **The faults stay.** The section 6 faults live in the template's formulas and would be carried on silently.
5. Each save also loses the button and the dynamic-array metadata.

### 2.2 Native route: build the sheets (the notebook's way)

The spike built a skeleton of `Blocked Unblocked` only, with openpyxl, from a copy of the ledger through the app's own
functions (`create_app({"DATABASE": <copy>, "LOGIN_DISABLED": True})`). Both halves had bank and non-bank sections in
the 3-row block shape. It set Legal (5), landscape, zoom 75, the work order's margins, a manual row break before the
BLOCKED half, and hidden columns B G H I J M, and hid rows by the Python filter (section 4).

Excel COM read the result back with:
- paper 5, landscape, zoom 75, and the manual break exactly at the chosen row;
- hidden columns B G H I J M, and the hidden rows the filter chose;
- **2 pages**. The PDF export was two 14 × 8.5 in pages, one half on each.

Its inputs equalled the evidence's own reads: every holding and every shares-to-block line. After the filter, each
half showed the same stocks as Alvin's 14:18 save.

The spike didn't attempt fonts, fills, header colours, merges or the grey zero-cells. These are ordinary openpyxl
styling, and the notebook already does them from a template.

### 2.3 Decision

**Build natively from a figure-free style template.** `create_notebook.py` does the same: it loads
`instance/excel_templates/notebook.xlsx`, writes its rows, then sets `print_area` and `paperSize` in code.

- **Template:** `instance/excel_templates/blocked_unblocked.xlsx` (tracked, so it must stay figure-free).
  - It holds one sheet for each printed kind: `Blocked Unblocked`, `Market vs Average`, `Market vs Average (2)` and
    `PAGE 3`.
  - Each has its header rows and one prototype row for each row kind: stock block rows, section header, section
    footer, the totals, and the PAGE 3 group rows.
  - It holds no figures, no account names or numbers, and no stock list. Those come from the database at runtime.
- **Builder:** copies a prototype row's styles, heights and merges for each row it writes (the notebook copies styles
  with `copy()` the same way).
  - It writes **values**, totals included, all computed in Python. The file is then correct without a recalculation,
    and the harness can read it with openpyxl.
  - It sets every print setting in section 5 in code, so a re-saved template can't undo them (as the notebook does for
    its paper size).
  - The account pages are written from the `PAGE 3` prototype, one for each account that holds shares.
- **Rows match the macro, the look matches the PDFs.** The 14:15 PDFs were printed before Alvin ran Filter Active
  Stocks; his 14:18 save is after it. The `Blocked Unblocked` PDF therefore shows the 27 Oct filter state: a
  zero-share block with `#DIV/0!` on each page and gaps in the column A numbering. So the app's rows follow the macro
  (the 14:18 save), and its fonts, fills, borders, number formats and page breaks follow the PDFs.

## 3. Inputs

Work order section 1 names five input areas. Each maps to existing code as follows.

| Input (work order §1) | Fed in the workbook | App source | Edition-date rule |
|---|---|---|---|
| Holdings: shares and cost per account and stock | `Online` D, K, E → `Equities` C, D | Weighted-average engine `transactions/models.py: accumulate_position`. Row selection like `portfolio/extensions/create_excel.py: GetData.get_transactions`, ordered like it (account's `transaction_basis`, then `tbl_transaction_type.priority`). Exclude `Sell (Short)` / `Buy (Pay Short)` as `stock_position/views.py: get_stock_positions` does. | Rows with **`trade_date` ≤ D** in every account, so the day's fixings count. Spike on the 30 Oct ledger: equal to the 30 Oct build's all-transactions read on every pair. Selecting on the account's own basis (`GetData(report_date=D)`, the settled view) leaves out the fixings that settle after D. Ordering by `trade_date` instead of the basis column changes the cost on some pairs, so keep the basis order. |
| Shorts: shares (negative) and average | `Online (SHORT)` J, K and the matching `Online` rows | `tbl_transaction_short` through `transactions/models.py: accumulate_short_position` (balance and cost) and `get_short_average(db, bank_ref, code_ref, D)`. `bank/views.py: gather_short_position_bulk` lists the open shorts (it needs a date filter added). The page Alvin reads is `/bank/<id>/<code>/short` (`short_transaction_list`). | Rows with `trade_date` ≤ D, ordered `trade_date, ref_num`, as the Short Book is. The edition carries the average **rounded to 4 dp**, as that page shows it (open question 4). |
| Shares to block | `Blocked Shares` H → `Equities` J, I | `stock_position/views.py: get_blocked_unblocked(db)`, keyed by `bank_id` and code. It uses the same formula as `block_unblock/views.py: home`: active DECU contracts, `daily_shares × remaining_days`, doubled when leveraged, with `remaining_days` from `term_sheet.StockContract.get_schedules`. Clamp with `split_blocked_unblocked(shares, to_block)`. | **Shares blocked = min(shares to block, holdings on the rule above)**. Pending Alvin (D7c), below. Shares to block itself is live state (the periods' `received` flags), not dated (open question 2). |
| Closing prices | `Closing` D (price), L2 (market time), the `^HSI` row | `tbl_stock_price (code_ref, trade_date, closing_price)` through `ltv_stocks/legacy_port/stock_price.py: get_stock_price(db, code_ref, D)`. When D has no close, take the latest close before D, as `fixings/extensions/download_fixings.py: get_closing_price` does. Loaded today from Alvin's Yahoo CSV by `stock_price/views.py: upload_yahoo_csv`, keyed on `tbl_code.yahoo_ticker`. | The edition day's own close (work order §3). Spike: for every code printed on 30 Oct, and for `^HSI` (`Market vs Average` P1), the 29 Oct close in `tbl_stock_price` equals the edition's `Closing` sheet. `^HSCE` is on `Closing` only and no printed formula uses it, so it isn't needed. The market time (`Market vs Average` L4 ← `Closing` L2) isn't stored anywhere (open question 3). |
| Edition date | `Market vs Average` D4 → `Equities` A1, `Blocked Unblocked` Q2, the date cells of the other printed sheets | A form field, a `DateField` defaulting to `tz.ph_today` as `portfolio/forms.py: Form.report_date` does. | "A Friday report is up to Friday only" (26 Oct). Every input above is taken as of D. |

**Pending Alvin (D7c): Shares Blocked basis.** The 30 Oct edition used holdings including that day's fixings, so
blocked = min(to block, holdings on `trade_date` ≤ D). `/block-unblock/`'s own Excel uses the settled basis
(`transactions/models.py: get_balance` at today's date, on the account's `transaction_basis`). That basis leaves the
day's fixings out, and gives different blocked figures on the pairs the work order's section 3 lists.
**Recommended default:** keep the edition's basis (fixings included).
- It is the basis Alvin set for holdings ("up to october 27 fixings").
- Both halves of the page then rest on one holdings figure, so unblocked + blocked = holdings on every row.
- It reproduces the 30 Oct edition he printed.

**Layout data the template held.** These items aren't inputs in section 1's sense, but the build needs them and today
they live only in the workbook:
- the account columns of `Blocked Unblocked`, with their order and header labels;
- which stocks are in the BANKS and NON-BANKS sections, and the row order;
- the stock display names;
- the `PAGE 3` groups (sections I to IV, Group A, Group B);
- the bank families in the `Market vs Average (2)` columns.

Account names and ids come from `tbl_bank_account` (`bank_id`, `bank_name`, `report_label`, `priority`). The rest needs
a home (open question 1).

## 4. Filter Active Stocks, in Python

The macro (`FilterActiveStocks`, in the work order's `vba_source.bas`) runs on `Blocked Unblocked` in three steps. The
builder does the same while it writes, so no macro and no button are needed:

1. **Start with every row visible.** The macro unhides rows 5 to the last. The builder writes all rows visible. The only
   rows hidden by layout are each half's spacer row under the title (template row 3).
2. **Hide each stock block with no position.** A block is three rows: the `Shares` row (B = code, D = `"Shares"`), the
   `HKD` row, and a thin spacer. The macro hides all three when the `Shares` row's sum over E:S is 0. S is the total of
   E:R, so this is the same as "the account cells sum to 0". The builder applies the same test to the figures it
   computed.
   - Keep the macro's sum test rather than "every cell is 0", so the harness matches the macro.
   - The two differ only on a row mixing long and short positions that cancel (open question 5).
3. **Hide each section left with no visible stock**, from its header row (B empty, C = section label, D empty,
   E = first account name) through its footer rows, up to the next header.

The column A counter follows the template's formula, `INDIRECT("A"&ROW()-3)+IF(S<>0,1,0)`. Within each half it is the
running count of blocks whose total is non-zero, so once the filter has run it numbers the visible blocks 1, 2, 3 and
so on. The builder writes these numbers as values.

`Market vs Average` and `PAGE 3` have no macro. Their hidden rows are template rows Alvin hid by hand. The builder
writes a row only for each code held, long or short, in any account on D. That is what the 30 Oct pages show, and the
harness checks it.

## 5. The print layout to reproduce

The work order's section 2 table gives these settings, read through Excel COM from Alvin's 14:18 save:
- printer `Microsoft Print to PDF`;
- paper **5, Legal 8.5 × 14 in, landscape**, on every printed sheet;
- no headers or footers, no gridlines, page order down then over, not centred;
- margins, in inches: left 0.118, right 0.079, bottom 0.118, header and footer 0.315;
- top margin 0.394 on `Blocked Unblocked` and 0.63 on the others;
- zoom in force on every sheet, not fit-to-page (`pageSetUpPr fitToPage` off).

### Blocked Unblocked (PDF 1, 2 pages)

- **Print setup:**
  - print area `A1:V<last row>`, zoom 75;
  - a **manual row break before the BLOCKED title row** (row 172 in the template);
  - hidden columns **B G H I J M**: the code column, and the account columns CB2, CB3, CBBH, CBBH2 and SC;
  - hidden rows from section 4.
- **Page 1, UNBLOCKED:**
  - title row (height 23.25): `UNBLOCKED` in C, `*NOTE: HKD is based on Ave. Cost` in K, the edition date in Q;
  - then the BANKS section and the NON-BANKS section;
  - then the two `BANK + NON-BANK … TOTAL` rows.
- **Page 2, BLOCKED:** the same layout, plus the two `GRAND TOTAL` rows (blocked + unblocked).
- **Section header row** (height 35.25):
  - the section label in C;
  - the account names in E:R, in the template's order: BOS, NSG, CB2, CB3, CBBH, CBBH2, DBPe, DBPL, SC, SHK, SHK2,
    MST1, MST2, MSPL;
  - `TOTAL` in S and `Ave. Cost` in U.
- **Stock block, three rows:**
  - `Shares` (height 15.75): the counter in A, the name in C, `Shares` in D and T, the units in E:R, the total in S,
    the average cost in U, and the name again in V. A, B, C, U and V are merged over the `Shares` and `HKD` rows;
  - `HKD` (height 15.95): units × account average in E:R, and the total in S;
  - a spacer (height 2.45) with a thick bottom border.
- **Section footer:** `<section> UNBLOCK|BLOCK SHARES TOTAL:` and `HKD TOTAL:`.
- **Zero cells** are filled grey and print blank. Negatives (the short rows) are red in parentheses.
- Column widths, fonts (Calibri 11 to 22), fills and the header colour per account follow the PDF.
- The spike placed the manual break, hid the columns and reached 2 pages with openpyxl alone.

### Market vs Average set (PDF 2, 9 pages on 30 Oct)

These sheets use print titles `$A:$D`. Their row height is 17.25, and they mix Calibri and Times New Roman.

| Sheet | Print area | Zoom | Breaks | Hidden columns |
|---|---|---|---|---|
| `Market vs Average` | `A1:Q70` | 78 | manual column break at R | C F R–AA |
| `Market vs Average (2)` | `R1:AX69` | 78 | none | C R–Y AA AB AD–AG AI–AQ AS AT |
| `PAGE 3` | `A1:Q78` | 78 | manual column break at V | C O–U W X Z–AC AE AF AH–AM AO AP |
| `PAGE 3 - <account>` (one each) | `A1:Q78` | 78 | the same as `PAGE 3` | the same as `PAGE 3` |

Each sheet prints one page.

- **`Market vs Average`.** Each non-bank stock held gets a row:
  - Code, Shares, Ave., Total Cost, % of, Market, Market Value, Gain/Loss %, Gain/Loss and % Distribution;
  - then the sub-total and the HKD GRAND-TOTAL.
  - D4 is the edition date. Above the Market column, L4 holds the market time (from `Closing` L2) and L5 is `=D4`.
    P1 holds `^HSI`.
- **`Market vs Average (2)`.** The gain or loss of the same rows broken down by bank family: Nomura Singapore, BOS,
  Deutsche Bank, Morgan Stanley and SHK Private.
  - Its print area starts at R, and print titles repeat A:D.
  - The page title in A1 is therefore cut at column D in the PDF. That is the target look.
- **`PAGE 3`, from top to bottom:**
  - the HKD GRAND-TOTAL;
  - sections I. BANKS, II. (one stock), III. Group A and IV. Group B, each with shares, % of total, cost, market %,
    market value and gain/loss;
  - the Group A and Group B stock tables with their sub-totals;
  - Total Non Bank Shares, NON-BANK SUB-TOTAL and HKD GRAND-TOTAL.
- **`PAGE 3 - <account>`:**
  - the `PAGE 3` layout for one account, from `bank_pages.py` in the work order's evidence;
  - the account id in B2 and the account name right-aligned in the merged I1:N1;
  - % of Total and Gain/Loss % taken over the account's own totals;
  - the cross-bank breakdown P:AW left empty;
  - one page for each account holding shares on D, in `tbl_bank_account.priority` order;
  - the sum of the account pages equals `PAGE 3` on every figure.

**Page-for-page check.** The harness (section 8) reads every printed sheet back through Excel COM and compares it with
the table above: print area, paper, orientation, zoom, manual breaks, hidden columns, and page count. It also compares
the visible rows with the 14:18 save. The exported PDFs must have the PDFs' page count and page size: 2 pages and
9 pages, all Legal landscape.

## 6. Known workbook faults

The work order's section 4 lists these. None is copied into the app silently. Each recommendation names what changes
on the printed pages.

- **F1. `Equities` F, "Market", reads column K of `Market vs Average`, which is empty.** The price is in L. So
  F = 0 and G = −1 on every row, in both editions. *Pending Alvin (D7b).*
  - **Recommended:** fix it. The data sheet carries the edition's close and (F − D) / D.
  - Nothing printed changes, because `Equities` isn't printed.
- **F2. `PAGE 3` D50: a row carries another stock's code, so it is priced as that stock** (the account pages inherit
  this). *Pending Alvin (D7b).*
  - **Recommended:** fix it. Each row is priced by its own code from `tbl_code`.
  - That row's market value and gain/loss change on `PAGE 3` and the account pages that hold it.
- **F3. `PAGE 3` E64, "Total Non Bank Shares", double-counts the E45/E61 subtotals** (the account pages inherit this).
  *Pending Alvin (D7b).*
  - **Recommended:** fix it. Count each stock row once.
  - The printed total changes.
- **F4. `PAGE 3` O28 and O52:O55 hold pasted `#N/A`.** *Pending Alvin (D7b).*
  - **Recommended:** fix it. Compute these % cells like the rest of the column. `bank_pages.py` already does this on
    the account pages.
  - Printed `#N/A` cells become percentages.
- **F5. The `PAGE 3` row 67 grand total leaves out section II.** The top HKD GRAND-TOTAL includes it, so the page
  shows two different grand totals. *Pending Alvin (D7b).*
  - **Recommended:** make the bottom grand total I + II + III + IV, equal to the top one. Keep NON-BANK SUB-TOTAL as
    the groups listed beneath.
- **F6. The `Equities` "Blocked" column shows the two short rows as negatives.** `I = IF(J>C, C, J)` with C < 0 and
  J = 0 makes a short count as blocked. Its total therefore falls below Σ min(to block, holdings) over the long rows.
  *Pending Alvin (D7b).*
  - **Recommended:** the data sheet's Blocked figure is min(to block, holdings) on long rows only, and a short row
    carries its shares in its own Short column.
  - The printed BLOCKED page keeps the short block where the 30 Oct edition printed it, in red as a negative, so the
    printed pages don't change.

The work order speaks of five faults. The list above has six because it splits the four `PAGE 3` items. Alvin can rule
on them one by one.

The harness ties the built figures to the evidence except where a ruling changes them. A fixed fault is checked
against the corrected rule, computed at runtime, not against the evidence cell.

## 7. Output

**Pending Alvin (D7a):** the `.xlsm`, an `.xlsx`, the two PDFs, or all of them.

**Recommended default:** **one `.xlsx`**, `<date> Blocked Unblocked.xlsx`, downloaded from a new page the way the
portfolio report is (`workbook_download.send_workbook`). Alvin prints the two PDFs from Excel with the print setup
already in place. It holds:
- the printed sheets in workbook order: `Market vs Average`, `Market vs Average (2)`, `PAGE 3`, the account pages, and
  `Blocked Unblocked`;
- one data sheet, `Equities` (not printed). It has a row per account and code with shares, average, cost, to block,
  blocked, unblocked, short, close (with its date), market value and gain/loss. Everything printed derives from it, and
  the harness ties it.

Why this default:
- No macro is left to run, so `.xlsm` buys nothing, and an `.xlsx` can't carry code.
- Alvin said the PDFs are "just a sample of how the report should be", so they aren't a deliverable.
- PDFs from the app would need Excel automation in the app (pywin32 isn't in its venv), or another renderer, and none
  of those reproduce Excel's page breaks exactly.
- If he later wants the PDFs, add an Excel-COM export that runs only on the local production machine. It would have to
  sit outside the request cycle.

The working sheets (`Closing`, `Online`, `Online (SHORT)`, `Blocked Shares`, `Summary-Equities`, `Loan`, `2333.hk`,
`Stocks`, `Claude Log`) are left out. `Equities` and the closes in it cover what the printed pages need. Whether he
still uses `Loan` and `2333.hk` is open question 6.

## 8. Harness

`scripts/verify_blocked_unblocked.py` (app venv, openpyxl) and `scripts/verify_blocked_unblocked_print.py` (a Python
that has pywin32, Excel COM). Both follow the rules for committed harnesses: no figure in the source, expected values
worked out at runtime, and no values printed on failure, only the sheet, cell address, account id and code. They
print `PASS`/`FAIL` per case.

**Setup.**
- Copy `clients/ltv/backups/LTV Stocks 2026-10-30-1355.db` to a temp file (sqlite backup API, source opened
  `mode=ro`).
- Boot `create_app({"DATABASE": <temp>, "LOGIN_DISABLED": True})`.
- Build the edition for D = 2026-10-30 into a temp folder.
- The reference is Alvin's 14:18 save. Pass its path as an argument, copy it to the temp folder first, and read it
  with `data_only=True`. Never write beside it.
- The 30 Oct 13:55 ledger reproduced the 14:08 inputs the edition was built from, every holding and every
  shares-to-block line (spike, section 2.2).

**Cases.**
1. **Inputs, recomputed independently.** Run a second SQL path (the work order's `calc.py` method, not the builder's
   functions) for holdings on `trade_date` ≤ D, to block and shorts. It must equal the builder's inputs pair by pair.
2. **Equities.**
   - The set of (account, code) rows equals the reference's `Equities` rows with non-zero shares (K, B).
   - On each row, shares = reference C and average = reference D to 1e-6.
   - Blocked = reference I, except on short rows if F6 is ruled as recommended. Then blocked = min(to block, shares)
     computed at runtime.
3. **PAGE 3 and the account pages.**
   - The set of account pages equals the reference's `PAGE 3 - *` sheets.
   - Each account page's shares and averages equal the reference page's.
   - Every figure cell of `PAGE 3` equals the sum of the account pages (the work order's tie).
   - `PAGE 3` equals the reference outside the cells a D7b ruling changes. Those are checked against the ruling's rule.
4. **Blocked Unblocked.**
   - The visible blocks, as (half, section, code), equal the reference's visible blocks: the 14:18 save, after the
     macro.
   - The account cells of each visible `Shares` row equal the reference's E:R.
   - Section 4's three steps, run over the reference's own values, reproduce its hidden rows.
5. **Closes.**
   - Every printed code's close equals the reference `Closing` price for the same date (29 Oct on the 30 Oct build).
   - Figures that depend on closes are compared only where both sides used the same close date, as the work order
     allows.
6. **Print layout** (Excel COM, read-only, hidden, `Quit()` in `finally`). For every printed sheet, compare against
   the section 5 table:
   - paper 5, landscape, zoom, print area, manual breaks;
   - hidden columns, the visible-row count against the reference, and `PageSetup.Pages.Count`.
   - Export both PDFs to temp and check 2 and 9 pages of 14 × 8.5 in.

Page counts depend on the active printer's metrics. On this machine the Legal setting gave the same counts on the
current default printer as the work order recorded under `Microsoft Print to PDF`. The harness reports the printer it
ran with.

## 9. Open questions

1. **Where the layout data lives** (section 3, last paragraph): the section order, BANKS/NON-BANKS membership, display
   names, the `PAGE 3` groups, and the bank families of `Market vs Average (2)`.
   - Today they live only in the workbook.
   - A stock list in this public repository would describe the client's portfolio.
   - **Proposed:** a small table, or a JSON file under `instance/` (untracked), seeded from the 30 Oct edition. It would
     be editable when a new stock or account appears.
2. **Shares to block "as of D".** `remaining_days` counts the periods not yet marked `received` at build time. An
   edition built after D (Friday's report run on Monday) would count fixings received after D as already delivered.
   - **Proposed:** count a period as received only when its end date is ≤ D, as `calc.py`'s RECEIVED_THRU option does.
   - Alvin to confirm.
3. **Market time and close date in the header** (`Market vs Average` L4/L5). `tbl_stock_price` has no time. The
   30 Oct edition printed the Yahoo time in L4 and the edition date in L5 (`=D4`), over 29 Oct closes.
   - **Proposed:** L5 shows the date of the close actually used, and L4 stays empty, rather than invent a time.
4. **Short average precision.**
   - The edition carries the Short Book's 4-dp average, so a short row's HKD differs slightly from full precision.
   - **Proposed:** round to 4 dp, as the Short Book page shows, so the figures tie to the edition.
5. **Filter edge case.** The macro hides a block whose account cells sum to 0. A row holding cancelling positions would
   be hidden.
   - **Proposed:** keep the macro's test, for parity.
6. **The working sheets.** Does Alvin still use `Loan`, `2333.hk` or `Online`? If so, the app should carry them in the
   output.
7. **When to run.** The closes for D land in `tbl_stock_price` only after Alvin's 4:30 PM upload.
   - **Proposed:** before the upload, the page builds the edition with the previous close and says so on the page.
   - Alternatively it refuses until D's closes are in. Alvin to choose.
