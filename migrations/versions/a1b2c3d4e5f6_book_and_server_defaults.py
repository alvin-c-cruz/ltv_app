"""add book to transaction_types + server_default backfill

Revision ID: a1b2c3d4e5f6
Revises: 98c3b03d0462
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '98c3b03d0462'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transaction_types") as batch:
        batch.add_column(sa.Column("book", sa.String(length=10), nullable=False, server_default="long"))
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default="0")
    with op.batch_alter_table("currencies") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default="0")
    with op.batch_alter_table("banks") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default="0")
    with op.batch_alter_table("holidays") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
    with op.batch_alter_table("stocks") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=sa.text("1"))
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(length=20), existing_nullable=False, server_default="user")
        batch.alter_column("failed_logins", existing_type=sa.Integer(), existing_nullable=False, server_default="0")


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.alter_column("failed_logins", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("role", existing_type=sa.String(length=20), existing_nullable=False, server_default=None)
    with op.batch_alter_table("stocks") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("holidays") as batch:
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("banks") as batch:
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("currencies") as batch:
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("transaction_types") as batch:
        batch.alter_column("priority", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
        batch.alter_column("is_active", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
        batch.drop_column("book")
