"""add persisted weekly health reports

Revision ID: 0008_weekly_health_reports
Revises: 0007_remove_antfu_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_weekly_health_reports"
down_revision = "0007_remove_antfu_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_health_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.DateTime(), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("source_context_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_health_reports_user_week"),
    )
    op.create_index("ix_weekly_health_reports_user_id", "weekly_health_reports", ["user_id"])
    op.create_index("ix_weekly_health_reports_week_start", "weekly_health_reports", ["week_start"])


def downgrade() -> None:
    op.drop_index("ix_weekly_health_reports_week_start", table_name="weekly_health_reports")
    op.drop_index("ix_weekly_health_reports_user_id", table_name="weekly_health_reports")
    op.drop_table("weekly_health_reports")
