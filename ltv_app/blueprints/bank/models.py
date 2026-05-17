from dataclasses import dataclass
from .. data_model import Model


@dataclass
class BankAccount(Model):
    table_name: str = "tbl_bank_account"

    def get_bank_refs(self):
        return [bank['ref_num'] for bank in self.db.execute(
            "SELECT * FROM tbl_bank_account ORDER BY priority;").fetchall()]
