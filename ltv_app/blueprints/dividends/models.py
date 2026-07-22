from dataclasses import dataclass
from ..data_model import Model


@dataclass
class CashDividends(Model):
    ref_num: int = None
    bank_id: int = None
    stock_id: int = None
    declaration_date: str = None
    ex_date: str = None
    record_date: str = None
    pay_out: str = None
    nominal: float = None
    ccy_id: int = None
    dividends_per_share: float = None
    tax: float = None
    charges: float = None
    status: str = None

    def __post_init__(self):
        self.table_name = "tbl_cash_dividends"

# class DividendsDeclaration(db.Model):
#     id = db.Column(db.Integer(), primary_key=True)
#     ex_date = db.Column(db.DateTime(), nullable=True)
#     pay_out_date = db.Column(db.DateTime(), nullable=True)
#     ccy_ref = db.Column(db.Integer())
#     dividends_per_share = db.Column(db.Float())
#     comment = db.Column(db.String(), nullable=True)
