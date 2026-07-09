from dataclasses import dataclass
from .. data_model import Model


@dataclass
class Currency(Model):
    table_name: str = "tbl_currency"
