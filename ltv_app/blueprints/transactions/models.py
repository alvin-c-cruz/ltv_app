from dataclasses import dataclass
from .. data_model import Model


@dataclass
class Transaction(Model):
    ref_num: int = None
    trade_date: str = None  # TODO: Change to datetime object
    # fixing_date: str = None  # No use yet
    value_date: str = None
    bank_ref: int = None
    code_ref: int = None
    transaction_type: str = None  # TODO: Normalization
    quantity: int = 0
    price: float = 0.0
    brokerage: float = 0.0
    commission: float = 0.0
    foreign_charge: float = 0.0
    stamp_duty: float = 0.0
    misc: float = 0.0
    comments: str = ""
    spot: float = 0.0
    ko: float = 0.0
    counter_bank_ref: int = None
    locked: int = 0
    no_charges: int = 0

    def __post_init__(self):
        self.table_name = "tbl_transaction"


def accumulate_position(transactions):
    """Weighted-average cost engine shared by position/average calculations.

    `transactions` is an ordered iterable of rows exposing quantity, price,
    brokerage, commission, foreign_charge, stamp_duty, misc.
    Returns (balance, cost_to_date, last_average) where last_average is the
    most recent non-zero average — the cost basis when a position closes.
    """
    balance = 0
    cost_to_date = 0.0
    last_average = 0.0

    for row in transactions:
        quantity = row['quantity']
        price = row['price']
        charges = row['brokerage'] + row['commission'] + row['foreign_charge'] + row['stamp_duty'] + row['misc']
        amount = quantity * price + charges

        if quantity > 0:
            if balance > 0:
                cost_to_date += amount
            elif balance == 0:
                cost_to_date += amount
            elif balance < 0:
                if balance + quantity == 0:
                    cost_to_date = 0
                elif balance + quantity < 0:
                    cost_to_date = 0
                else:
                    cost_to_date = (balance + quantity) / quantity * amount
        else:
            if balance > 0:
                if balance - abs(quantity) > 0:
                    cost_to_date -= cost_to_date * abs(quantity) / balance
                else:
                    cost_to_date = 0
            else:
                cost_to_date = 0

        balance += quantity
        if balance > 0:
            average = cost_to_date / balance
            if average != 0:
                last_average = average

    return balance, cost_to_date, last_average


def get_balance(db, bank_ref, code_ref, trade_date):
    transaction_basis = db.execute("SELECT transaction_basis FROM tbl_bank_account WHERE ref_num=?",
                                   (bank_ref,)).fetchone()[0]

    sql = ("SELECT * FROM tbl_transaction "
           + "INNER JOIN tbl_transaction_type "
           + "ON tbl_transaction_type.transaction_type = tbl_transaction.transaction_type "
           + f"WHERE tbl_transaction.bank_ref=? AND tbl_transaction.code_ref=? "
           + f"AND tbl_transaction.{transaction_basis}<=? "
           + f"ORDER BY tbl_transaction.{transaction_basis}, tbl_transaction_type.priority;")

    transactions = db.execute(sql, (bank_ref, code_ref, trade_date)).fetchall()

    balance = 0
    cost_to_date = 0

    for row in transactions:
        quantity = row['quantity']
        price = row['price']
        charges = row['brokerage'] + row['commission'] + row['foreign_charge'] + row['stamp_duty'] + row['misc']
        amount = quantity * price + charges

        if quantity > 0:

            if balance > 0:
                cost_to_date += amount
            elif balance == 0:
                cost_to_date += amount
            elif balance < 0:
                if balance + quantity == 0:
                    cost_to_date = 0
                elif balance + quantity < 0:
                    cost_to_date = 0
                else:
                    cost_to_date = (balance + quantity) / quantity * amount

        else:
            if balance > 0:
                if balance - abs(quantity) > 0:
                    cost_to_date -= cost_to_date * abs(quantity) / balance
                else:
                    cost_to_date = 0
            else:
                cost_to_date = 0

        balance += quantity

    return balance, cost_to_date


def get_transactions(db, bank_ref, code_ref, date_from, date_to):
    short_name = {
        "CB1": "Citibank A/C 1",
        "CB2": "Citibank A/C 2",
        "CB3": "Citibank A/C 3",
        "CBBH": "Citibank Berry Hill",
        "CBBH2": "Citibank Berry Hill No. 1",
        "CBSG": "Citibank Singapore A/C 1",
        "BOS": "Bank of Singapore",
        "DBPe": "DB Personal",
        "DBPL": "DB Perfect Legend",
        "SC": "Standard",
        "SHK": "Sun Hung Kai Account No. 1",
        "SHK2": "Sun Hung Kai Account No. 2",
        "MST1": "MS Titan 1",
        "MST2": "MS Titan 2",
        "MSPL": "MS Perfect Legend",
        "NSG": "Nomura Singapore",
    }

    transaction_basis = db.execute("SELECT transaction_basis FROM tbl_bank_account WHERE ref_num=?",
                                   (bank_ref,)).fetchone()[0]

    sql = ("SELECT * FROM tbl_transaction "
            + "INNER JOIN tbl_transaction_type "
            + "ON tbl_transaction_type.transaction_type = tbl_transaction.transaction_type "
            + f"WHERE tbl_transaction.bank_ref=? AND tbl_transaction.code_ref=? "
            + f"AND tbl_transaction.{transaction_basis}>=? "
            + f"AND tbl_transaction.{transaction_basis}<=? "
            + f"ORDER BY tbl_transaction.{transaction_basis}, tbl_transaction_type.priority;")

    transactions = db.execute(sql, (bank_ref, code_ref, date_from, date_to)).fetchall()

    restructured_data = []
    for trans in transactions:
        if 'Transfer' in trans['transaction_type']:
            bank_id = db.execute("SELECT bank_id FROM tbl_bank_account WHERE ref_num=?",
                                   (trans['counter_bank_ref'],)).fetchone()[0]
            if '-In' in trans['transaction_type']:
                description = f'From {short_name[bank_id]}'
            else:
                description = f'To {short_name[bank_id]}'
        else:
            description = trans['transaction_type']

        _dict = {
            'ref_num': trans['ref_num'],
            'trade_date': trans['trade_date'],
            'value_date': trans['value_date'],
            'description': description,
            'quantity': trans['quantity'],
            'price': trans['price'],
            'charges': trans['brokerage'] + trans['commission'] + trans['foreign_charge']
                          + trans['stamp_duty'] + trans['misc'],
        }

        restructured_data.append(_dict)

    return restructured_data


def _update_short_cost(balance, cost_to_date, qty, price, charges):
    amount = abs(qty) * price + charges
    if qty < 0:  # opening/deepening short
        if balance <= 0:
            cost_to_date += amount
    else:  # closing short
        if balance < 0:
            if abs(balance) - qty > 0:
                cost_to_date -= cost_to_date * qty / abs(balance)
            else:
                cost_to_date = 0.0
    return cost_to_date


def get_short_balance(db, bank_ref, code_ref, trade_date):
    """Net short position and cost basis from tbl_transaction_short as of trade_date."""
    transaction_basis = db.execute(
        "SELECT transaction_basis FROM tbl_bank_account WHERE ref_num=?",
        (bank_ref,)).fetchone()[0]

    rows = db.execute(
        "SELECT quantity, price, brokerage, commission, foreign_charge, stamp_duty, misc "
        "FROM tbl_transaction_short "
        f"WHERE bank_ref=? AND code_ref=? AND {transaction_basis}<=? "
        f"ORDER BY {transaction_basis}",
        (bank_ref, code_ref, trade_date)
    ).fetchall()

    balance = 0
    cost_to_date = 0.0
    for row in rows:
        charges = row['brokerage'] + row['commission'] + row['foreign_charge'] + row['stamp_duty'] + row['misc']
        cost_to_date = _update_short_cost(balance, cost_to_date, row['quantity'], row['price'], charges)
        balance += row['quantity']

    return balance, cost_to_date


def get_short_transactions(db, bank_ref, code_ref, date_from, date_to):
    """Short book transactions for a period from tbl_transaction_short."""
    transaction_basis = db.execute(
        "SELECT transaction_basis FROM tbl_bank_account WHERE ref_num=?",
        (bank_ref,)).fetchone()[0]

    rows = db.execute(
        "SELECT ref_num, trade_date, value_date, transaction_type, quantity, price, "
        "brokerage, commission, foreign_charge, stamp_duty, misc "
        "FROM tbl_transaction_short "
        f"WHERE bank_ref=? AND code_ref=? AND {transaction_basis}>=? AND {transaction_basis}<=? "
        f"ORDER BY {transaction_basis}",
        (bank_ref, code_ref, date_from, date_to)
    ).fetchall()

    result = []
    for row in rows:
        charges = (row['brokerage'] + row['commission'] + row['foreign_charge']
                   + row['stamp_duty'] + row['misc'])
        result.append({
            'ref_num': row['ref_num'],
            'trade_date': row['trade_date'],
            'value_date': row['value_date'],
            'description': row['transaction_type'],
            'quantity': row['quantity'],
            'price': row['price'],
            'charges': charges,
        })

    return result


@dataclass
class TransactionShort(Model):
    ref_num: int = None
    trade_date: str = None  # TODO: Change to datetime object
    # fixing_date: str = None  # No use yet
    value_date: str = None
    bank_ref: int = None
    code_ref: int = None
    transaction_type: str = None  # TODO: Normalization
    quantity: int = 0
    price: float = 0.0
    brokerage: float = 0.0
    commission: float = 0.0
    foreign_charge: float = 0.0
    stamp_duty: float = 0.0
    misc: float = 0.0
    locked: int = 0
    no_charges: int = 0

    def __post_init__(self):
        self.table_name = "tbl_transaction_short"
