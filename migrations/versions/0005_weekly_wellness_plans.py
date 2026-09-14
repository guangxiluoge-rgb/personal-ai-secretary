"""add weekly wellness plans

Revision ID: 0005_weekly_wellness_plans
Revises: 0004_health_gallery_metadata
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_weekly_wellness_plans"
down_revision = "0004_health_gallery_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_wellness_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.DateTime(), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("source_context_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_wellness_user_week"),
    )
    op.create_index("ix_weekly_wellness_plans_user_id", "weekly_wellness_plans", ["user_id"])
    op.create_index("ix_weekly_wellness_plans_week_start", "weekly_wellness_plans", ["week_start"])


def downgrade() -> None:
    op.drop_index("ix_weekly_wellness_plans_week_start", table_name="weekly_wellness_plans")
    op.drop_index("ix_weekly_wellness_plans_user_id", table_name="weekly_wellness_plans")
    op.drop_table("weekly_wellness_plans")
