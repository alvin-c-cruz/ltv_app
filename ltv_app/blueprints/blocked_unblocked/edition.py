"""The Blocked Unblocked edition's figures as of one date, from the ledger.

One row per account and position: an account's long holding of a stock, or its short. Every printed page of the
edition is drawn from these rows (spec docs/superpowers/specs/2026-11-02-blocked-unblocked-design.md, sections 3
and 7, approved 6 Nov 2026):

- holdings count every row traded on or before the date, in every account, so the day's fixings are in (D7c);
- shorts come from the Short Book, the average rounded to 4 dp as the Short Book page shows it (ruling 12);
- shares to block are the days of the live decumulators' periods ending after the date, flagged or not (ruling 6);
- a long row blocks min(to block, shares); a short row blocks nothing and is carried as Short (F6);
- a position nobody holds, with a live contract still running, keeps its row and reads 0 (rulings of 4 and 6 Nov);
- prices are the date's close, else the latest before it, unless a price set is supplied for the build (ruling 4).

Contract status is today's, not the date's: a contract knocked out since the date is no longer counted.
"""
from dataclasses import dataclass, field

from ..term_sheet.models import _to_int
from ..transactions.models import accumulate_position, accumulate_short_position, get_short_average

LONG, SHORT = "Long", "Short"
SHORT_TYPES = ("Sell (Short)", "Buy (Pay Short)")
CHARGES = ("brokerage", "commission", "foreign_charge", "stamp_duty", "misc")
BASIS_COLUMNS = ("trade_date", "value_date")


@dataclass
class EditionRow:
    bank_ref: int
    bank_id: str
    bank_name: str
    code_ref: int
    code: str
    stock_name: str
    ccy: str
    side: str
    shares: float
    average: float
    to_block: float = 0
    close: float | None = None
    close_from: str = ""

    @property
    def cost(self):
        return self.shares * self.average

    @property
    def blocked(self):
        return 0 if self.side == SHORT else max(0, min(self.to_block, self.shares))

    @property
    def unblocked(self):
        return 0 if self.side == SHORT else self.shares - self.blocked

    @property
    def short(self):
        return self.shares if self.side == SHORT else 0

    @property
    def market(self):
        return None if self.close is None else self.shares * self.close

    @property
    def gain(self):
        return None if self.close is None else self.market - self.cost

    @property
    def gain_pct(self):
        if self.close is None:
            return None
        return self.gain / abs(self.cost) if self.cost else 0.0

    @property
    def key(self):
        """The workbook's own key for the position: '175:HK', or '(S) 175:HK' for a short."""
        code = (self.code.lstrip("0") or "0") if self.code.isdigit() else self.code
        suffix = "HK" if self.ccy == "HKD" else self.ccy
        return f"{'(S) ' if self.side == SHORT else ''}{code}:{suffix}"


@dataclass
class Edition:
    as_of: str
    rows: list
    price_label: str
    unpriced: list = field(default_factory=list)


def long_positions(db, as_of):
    """{(bank_ref, code_ref): (shares, average)} for every account and stock with a long-book row traded on or
    before as_of. Replayed in the account's own basis order, then the type's priority, as the portfolio report
    replays them; the edition selects on trade date so the day's fixings count."""
    pairs = db.execute(
        "SELECT DISTINCT t.bank_ref, t.code_ref, b.transaction_basis FROM tbl_transaction t "
        "JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "WHERE t.trade_date <= ? AND t.transaction_type NOT IN (?, ?)", (as_of,) + SHORT_TYPES).fetchall()
    positions = {}
    for pair in pairs:
        basis = pair["transaction_basis"]
        if basis not in BASIS_COLUMNS:
            raise ValueError(f"account {pair['bank_ref']}: unknown transaction_basis {basis!r}")
        rows = db.execute(
            "SELECT t.* FROM tbl_transaction t "
            "JOIN tbl_transaction_type tt ON tt.transaction_type = t.transaction_type "
            "WHERE t.bank_ref=? AND t.code_ref=? AND t.trade_date<=? AND t.transaction_type NOT IN (?, ?) "
            f"ORDER BY t.{basis}, tt.priority, t.ref_num",
            (pair["bank_ref"], pair["code_ref"], as_of) + SHORT_TYPES).fetchall()
        shares, cost, _ = accumulate_position(rows)
        positions[(pair["bank_ref"], pair["code_ref"])] = (shares, cost / shares if shares else 0.0)
    return positions


def short_positions(db, as_of):
    """{(bank_ref, code_ref): (shares, average)} for every open short on as_of (shares < 0): the Short Book
    replayed in trade date and entry order, as the Short Book page does."""
    pairs = db.execute("SELECT DISTINCT bank_ref, code_ref FROM tbl_transaction_short WHERE trade_date <= ?",
                       (as_of,)).fetchall()
    positions = {}
    for pair in pairs:
        rows = db.execute(
            "SELECT * FROM tbl_transaction_short WHERE bank_ref=? AND code_ref=? AND trade_date<=? "
            "ORDER BY trade_date, ref_num", (pair["bank_ref"], pair["code_ref"], as_of)).fetchall()
        balance, _ = accumulate_short_position([{**dict(r), **{k: r[k] or 0 for k in CHARGES}} for r in rows])
        if balance < 0:
            average = get_short_average(db, pair["bank_ref"], pair["code_ref"], as_of)
            positions[(pair["bank_ref"], pair["code_ref"])] = (balance,
                                                               round(average, 4) if average is not None else 0.0)
    return positions


def shares_to_block(db, as_of):
    """{(bank_ref, code_ref): shares} still to deliver on live decumulators traded on or before as_of: daily shares
    times the days of the periods ending after as_of, doubled when geared. A period ending on or before as_of counts
    as received, flagged or not; one ending after it is still to come, flagged or not (ruling 6)."""
    to_block = {}
    contracts = db.execute(
        "SELECT ref_num, bank_ref, code_ref, daily_shares, leveraged FROM tbl_stock_contract "
        "WHERE status='active' AND transaction_type='DECU' AND trade_date<=?", (as_of,)).fetchall()
    for c in contracts:
        days = sum(_to_int(p["days"]) for p in db.execute(
            "SELECT days FROM tbl_stock_contract_period WHERE contract_ref=? AND end_date>?", (c["ref_num"], as_of)))
        shares = _to_int(c["daily_shares"]) * days * (2 if c["leveraged"] == "Yes" else 1)
        key = (c["bank_ref"], c["code_ref"])
        to_block[key] = to_block.get(key, 0) + shares
    return to_block


def live_contract_pairs(db, as_of):
    """Accounts and stocks with a live contract, accumulator or decumulator, still running after as_of."""
    return {(r["bank_ref"], r["code_ref"]) for r in db.execute(
        "SELECT DISTINCT c.bank_ref, c.code_ref FROM tbl_stock_contract c "
        "JOIN tbl_stock_contract_period p ON p.contract_ref = c.ref_num "
        "WHERE c.status='active' AND c.trade_date<=? AND p.end_date>?", (as_of, as_of))}


def closes(db, code_refs, as_of):
    """{code_ref: (price, date)}: the close on as_of, else the latest before it, as
    fixings.download_fixings.get_closing_price takes it."""
    out = {}
    for code_ref in code_refs:
        row = db.execute(
            "SELECT closing_price, trade_date FROM tbl_stock_price WHERE code_ref=? AND trade_date<=? "
            "AND closing_price IS NOT NULL ORDER BY trade_date DESC LIMIT 1", (code_ref, as_of)).fetchone()
        if row:
            out[code_ref] = (row["closing_price"], row["trade_date"])
    return out


def build_edition(db, as_of, prices=None, price_label=""):
    """Every row of the edition as of as_of. prices, {code_ref: price}, is a set supplied for this build: it wins
    over the stored closes for its codes and is never written anywhere (ruling 4)."""
    longs = long_positions(db, as_of)
    shorts = short_positions(db, as_of)
    to_block = shares_to_block(db, as_of)
    live = live_contract_pairs(db, as_of)

    keys = {pair + (LONG,) for pair, (shares, _) in longs.items() if shares}
    keys |= {pair + (LONG,) for pair in live}
    keys |= {pair + (LONG,) for pair, shares in to_block.items() if shares}
    keys |= {pair + (SHORT,) for pair in shorts}

    banks = {r["ref_num"]: r for r in db.execute(
        "SELECT ref_num, bank_id, bank_name, priority FROM tbl_bank_account")}
    codes = {r["ref_num"]: r for r in db.execute(
        "SELECT c.ref_num, c.code, c.stock_name, cur.ccy_id FROM tbl_code c "
        "LEFT JOIN tbl_currency cur ON cur.ref_num = c.ccy_ref")}
    stored = closes(db, {code_ref for _, code_ref, _ in keys}, as_of)

    rows = []
    for bank_ref, code_ref, side in keys:
        shares, average = (shorts if side == SHORT else longs).get((bank_ref, code_ref), (0, 0.0))
        if prices and code_ref in prices:
            close, close_from = prices[code_ref], price_label or "supplied"
        else:
            close, close_from = stored.get(code_ref, (None, ""))
        bank, code = banks[bank_ref], codes[code_ref]
        rows.append(EditionRow(
            bank_ref=bank_ref, bank_id=bank["bank_id"], bank_name=bank["bank_name"],
            code_ref=code_ref, code=str(code["code"]), stock_name=code["stock_name"], ccy=code["ccy_id"] or "HKD",
            side=side, shares=shares, average=average,
            to_block=to_block.get((bank_ref, code_ref), 0) if side == LONG else 0,
            close=close, close_from=close_from))
    rows.sort(key=lambda r: (banks[r.bank_ref]["priority"] or 0, r.code, r.side != LONG))
    return Edition(as_of=as_of, rows=rows,
                   price_label=(price_label or "supplied") if prices else f"closes on or before {as_of}",
                   unpriced=sorted({r.code for r in rows if r.close is None}))
