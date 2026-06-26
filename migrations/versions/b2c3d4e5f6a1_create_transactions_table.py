"""create transactions table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=False),
        sa.Column("bank_id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("brokerage", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("commission", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("foreign_charge", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("stamp_duty", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("misc", sa.Numeric(), nullable=False, server_default="0"),
        sa.Column("counter_bank_id", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"]),
        sa.ForeignKeyConstraint(["counter_bank_id"], ["banks.id"]),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.ForeignKeyConstraint(["transaction_type_id"], ["transaction_types.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("transactions")
