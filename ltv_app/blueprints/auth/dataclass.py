from dataclasses import dataclass
from .. data_model import Model


@dataclass
class User(Model):
    id: int = None
    username: str = ""
    email: str = ""
    password: str = ""
    level: int = 5  # Levels: 1=admin; 2=audit; 3=accountant; 4=bookkeeper; 5=viewer
    role: str = 'staff'  # Roles: staff, superuser

    def __post_init__(self):
        self.table_name = "tbl_user"
