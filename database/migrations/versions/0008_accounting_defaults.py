"""0008 — accounting_settings: auto-posting flag + default account code columns.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_DEFAULT_ACCOUNT_COLS = [
    "default_ar_account_code",
    "default_cash_account_code",
    "default_sales_revenue_account_code",
    "default_tax_payable_account_code",
    "default_inventory_account_code",
    "default_cogs_account_code",
    "default_ap_account_code",
    "default_grn_accrual_account_code",
    "default_inventory_adjustment_account_code",
    "default_purchase_variance_account_code",
]


def upgrade() -> None:
    op.add_column(
        "accounting_settings",
        sa.Column(
            "enable_auto_posting",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    for col in _DEFAULT_ACCOUNT_COLS:
        op.add_column(
            "accounting_settings",
            sa.Column(col, sa.String(20), nullable=True),
        )


def downgrade() -> None:
    for col in reversed(_DEFAULT_ACCOUNT_COLS):
        op.drop_column("accounting_settings", col)
    op.drop_column("accounting_settings", "enable_auto_posting")
