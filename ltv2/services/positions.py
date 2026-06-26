"""Pure position/P&L engine for the ltv2 trading ledger.

No Flask, no SQLAlchemy session. Folds an ordered list of transaction dicts
into per-(bank_id, stock_id, book) PositionState objects.

Transaction dict keys:
    bank_id: int
    stock_id: int
    book: str                 # "long" | "short"
    behavior_category: str    # increase|decrease|transfer_in|transfer_out|dividend|neutral
    quantity: Decimal         # positive magnitude; direction inferred
    price: Decimal            # per share
    charges: Decimal          # total charges
    sort_date: datetime.date  # effective date (caller resolves trade vs value)
    priority: int             # transaction_type.priority, tiebreaker
"""
from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal(0)

_DELTA_SIGN = {
    ("long", "increase"): 1,
    ("long", "decrease"): -1,
    ("long", "dividend"): 1,
    ("long", "transfer_in"): 1,
    ("long", "transfer_out"): -1,
    ("short", "increase"): -1,
    ("short", "decrease"): 1,
}


@dataclass
class PositionState:
    balance: Decimal = ZERO
    cost_basis: Decimal = ZERO
    realized_pnl: Decimal = ZERO

    @property
    def average(self) -> Decimal:
        return self.cost_basis / self.balance if self.balance != ZERO else ZERO


def _signed_delta(book, behavior, qty):
    if behavior == "neutral":
        return ZERO
    try:
        sign = _DELTA_SIGN[(book, behavior)]
    except KeyError:
        raise ValueError(f"unsupported (book, behavior): ({book!r}, {behavior!r})")
    return Decimal(sign) * qty


def _sign(value):
    return Decimal(1) if value > ZERO else Decimal(-1)


def _apply(state, txn):
    behavior = txn["behavior_category"]
    qty = txn["quantity"]
    price = txn["price"]
    charges = txn["charges"]

    d = _signed_delta(txn["book"], behavior, qty)
    if d == ZERO:
        return

    bal = state.balance
    # Case 1: opening or adding (flat, or delta same sign as balance)
    if bal == ZERO or (d > ZERO) == (bal > ZERO):
        sign_new = _sign(d)
        opening_cost = sign_new * (qty * price) + charges
        state.cost_basis += opening_cost
        state.balance += d
        return

    abs_bal = -bal if bal < ZERO else bal
    # Case 2: reduce without crossing zero
    if qty <= abs_bal:
        sign_bal = _sign(bal)
        closing_cash = sign_bal * (qty * price) - charges
        released = (qty / abs_bal) * state.cost_basis
        state.realized_pnl += closing_cash - released
        state.cost_basis -= released
        state.balance += d
        return

    # Case 3: zero-crossing (close fully, then open the remainder)
    close_qty = abs_bal
    open_qty = qty - close_qty
    charges_close = charges * (close_qty / qty)
    charges_open = charges * (open_qty / qty)

    # Step A: close the existing position fully
    sign_bal = _sign(bal)
    closing_cash = sign_bal * (close_qty * price) - charges_close
    released = state.cost_basis
    state.realized_pnl += closing_cash - released
    state.cost_basis = ZERO
    state.balance = ZERO

    # Step B: open the remainder in the new direction
    sign_new = _sign(d)
    state.cost_basis = sign_new * (open_qty * price) + charges_open
    state.balance = sign_new * open_qty


def compute_position(transactions):
    ordered = sorted(transactions, key=lambda t: (t["sort_date"], t["priority"]))
    positions = {}
    for txn in ordered:
        key = (txn["bank_id"], txn["stock_id"], txn["book"])
        state = positions.setdefault(key, PositionState())
        _apply(state, txn)
    return positions
