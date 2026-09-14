"""add health gallery intake metadata

Revision ID: 0004_health_gallery_metadata
Revises: 0003_admin_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_health_gallery_metadata"
down_revision = "0003_admin_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "health_analysis_jobs",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="gallery"),
    )
    op.add_column(
        "health_analysis_jobs",
        sa.Column("client_sha256", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_health_analysis_jobs_client_sha256",
        "health_analysis_jobs",
        ["client_sha256"],
    )


def downgrade():
    op.drop_index("ix_health_analysis_jobs_client_sha256", table_name="health_analysis_jobs")
    op.drop_column("health_analysis_jobs", "client_sha256")
    op.drop_column("health_analysis_jobs", "source")
