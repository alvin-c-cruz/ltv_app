from dataclasses import dataclass, field
from datetime import date


@dataclass
class Model:
    db: any = field(repr=False)
    table_name: str = field(repr=False, default="")

    def fields(self):
        _list = []

        def d_type(name, field_type):
            if field_type == int:
                return 'INTEGER'
            if field_type == float:
                return 'FLOAT'
            if field_type == str:
                return 'TEXT'
            if field_type == bool:
                return 'BOOLEAN'
            if field_type == date:
                return 'TIMESTAMP'

        data_fields = self.__dataclass_fields__

        for key in data_fields:
            if key[0] != '_':
                field = data_fields[key]

                name = field.name

                if name in ('db', 'table_name'):
                    continue
                field_dict = {'name': name, "datatype": d_type(name, field.type)}
                if field.default == 'primary_key': field_dict["primary_key"] = True

                _list.append(field_dict)

        return _list

    def save(self):
        if self.ref_num:
            fields = [f'{field["name"]}=?' for field in self.fields()]
            values = [getattr(self, field['name']) for field in self.fields()]

            self.db.execute(f"UPDATE {self.table_name} set {', '.join(fields)} WHERE ref_num={self.ref_num};", values)

        else:
            fields = [field['name'] for field in self.fields() if field['name'] != 'ref_num']
            field_values = ["?" for field in self.fields() if field['name'] != 'ref_num']
            values = []
            for field in self.fields():
                if field['name'] == 'ref_num': continue
                values.append(getattr(self, field['name']))

            sql = f"INSERT INTO {self.table_name} ({', '.join(fields)}) VALUES ({', '.join(field_values)});"
            self.db.execute(sql, values)
            self.ref_num = self.db.execute("SELECT last_insert_rowid();").fetchone()[0]

        self.db.commit()

    def get(self, **filter):
        clause = [f'{key}=?' for key in filter]
        record = self.db.execute(f'SELECT * FROM {self.table_name} WHERE {", ".join(clause)};',
                                 tuple(filter.values())).fetchone()

        for field in self.fields():
            if record:
                setattr(self, field['name'], record[field['name']])
            else:
                setattr(self, field['name'], None)

    def all(self, fields=None, order_by=None, **filter_by):
        sql = f"SELECT {', '.join(fields)}  " if fields else "SELECT * "
        sql += f"FROM {self.table_name}  "
        if filter_by:
            sql += f"WHERE {'AND '.join([f'{key}=?' for key in filter_by])}"
        if order_by:
            sql += f"ORDER BY {', '.join(order_by)}"
        sql += ";"

        result = self.db.execute(sql, tuple(filter_by.values())).fetchall() if filter_by \
            else self.db.execute(sql).fetchall()

        return result

    def delete(self, ref_num=None):
        if ref_num is None:
            ref_num = self.ref_num

        sql = f"DELETE FROM {self.table_name} WHERE ref_num={ref_num};"
        self.db.execute(sql)
        self.db.commit()
