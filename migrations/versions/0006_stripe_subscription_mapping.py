"""persist Stripe subscription mapping

Revision ID: 0006_stripe_subscription_mapping
Revises: 0005_weekly_wellness_plans
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_stripe_subscription_mapping"
down_revision = "0005_weekly_wellness_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("stripe_subscription_id", sa.String(length=128), nullable=True))
    op.add_column("orders", sa.Column("stripe_customer_id", sa.String(length=128), nullable=True))
    op.create_index("ix_orders_stripe_subscription_id", "orders", ["stripe_subscription_id"])
    op.create_index("ix_orders_stripe_customer_id", "orders", ["stripe_customer_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_stripe_customer_id", table_name="orders")
    op.drop_index("ix_orders_stripe_subscription_id", table_name="orders")
    op.drop_column("orders", "stripe_customer_id")
    op.drop_column("orders", "stripe_subscription_id")
