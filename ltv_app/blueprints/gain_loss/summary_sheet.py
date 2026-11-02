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
    ws.print_area = f"A1:F{conversion_total}"   # ends on the conversion TOTAL, as the template's did

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
