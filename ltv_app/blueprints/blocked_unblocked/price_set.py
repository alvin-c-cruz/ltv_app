"""A price set Alvin supplies for one build of the edition.

His own prices win (ruling of 4 Nov 2026), but they are intraday quotes as often as closes, so they are used for that
build only and never written to tbl_stock_price, which the fixings and the notebook read as the day's close
(spec section 9, question 3, ruled 6 Nov)."""
import csv
import io
import math
import re
from dataclasses import dataclass, field

LINE = re.compile(r"^([^\s,;]+)[\s,;]+(.+)$")


@dataclass
class PriceSet:
    prices: dict = field(default_factory=dict)   # code_ref -> price
    skipped: list = field(default_factory=list)  # what could not be read, as given


def _number(text):
    try:
        value = float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def read_price_set(db, csv_bytes=None, text=None):
    """Prices from a Yahoo portfolio CSV (its Symbol and Current Price columns, the file stock_price's upload reads)
    and from pasted lines of 'code price' (a comma, semicolon, tab or spaces between; the code as tbl_code has it,
    with or without its leading zeros, or its Yahoo ticker). A later entry for the same stock wins."""
    by_ticker = {str(r["yahoo_ticker"]).strip().upper(): r["ref_num"] for r in db.execute(
        "SELECT ref_num, yahoo_ticker FROM tbl_code WHERE yahoo_ticker IS NOT NULL AND yahoo_ticker != ''")}
    by_code = {}
    for r in db.execute("SELECT ref_num, code FROM tbl_code"):
        code = str(r["code"]).strip().upper()
        by_code[code] = r["ref_num"]
        if code.isdigit():
            by_code.setdefault(code.lstrip("0") or "0", r["ref_num"])

    result = PriceSet()
    if csv_bytes:
        try:
            reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
            fields = reader.fieldnames
            if not fields or "Symbol" not in fields or "Current Price" not in fields:
                result.skipped.append("the file is not a Yahoo portfolio CSV (no Symbol and Current Price columns)")
            else:
                for row in reader:
                    symbol = (row.get("Symbol") or "").strip()
                    ref = by_ticker.get(symbol.upper())
                    price = _number(row.get("Current Price"))
                    if ref is None or price is None:
                        result.skipped.append(symbol or "a row with no symbol")
                        continue
                    result.prices[ref] = price
        except (UnicodeDecodeError, csv.Error):
            result.skipped.append("the file could not be read as a CSV")

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = LINE.match(line)
        token = match.group(1).upper() if match else ""
        ref = by_code.get(token) or by_code.get(token.lstrip("0") or "0") or by_ticker.get(token)
        price = _number(match.group(2)) if match else None
        if ref is None or price is None:
            result.skipped.append(line)
            continue
        result.prices[ref] = price
    return result
