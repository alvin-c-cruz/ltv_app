from dataclasses import dataclass
from .. data_model import Model


@dataclass
class Stocks(Model):
    table_name: str = "tbl_code"
    ref_num: int = None
    code: str = None
    company_name: str = None
    stock_name: str = None
    yahoo_ticker: str = None
    security_code: str = None
    ccy_ref: int = None

    def get_code_refs(self):
        return [stock['ref_num'] for stock in self.db.execute("SELECT * FROM tbl_code ORDER BY code;").fetchall()]
