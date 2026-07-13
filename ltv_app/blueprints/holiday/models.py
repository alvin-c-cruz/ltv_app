from dataclasses import dataclass
from .. data_model import Model


@dataclass
class Holiday(Model):
    table_name: str = "tbl_holiday"
    ref_num: int = None
    ccy_ref: int = None
    holi_date: str = ""

    def list_holidays(self, date_from, date_to):
        date_from = str(date_from)[:10]
        date_to = str(date_to)[:10]
        sql = f"SELECT * FROM {self.table_name} WHERE holi_date>=? AND holi_date<=? ORDER BY ccy_ref, holi_date;"
        return self.db.execute(sql, (date_from, date_to)).fetchall()
