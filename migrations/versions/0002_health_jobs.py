from alembic import op
import sqlalchemy as sa
revision = "0002_health_jobs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("health_analysis_jobs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("file_path", sa.Text(), nullable=False), sa.Column("image_type", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="pending"), sa.Column("error", sa.Text(), nullable=False, server_default=""), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("completed_at", sa.DateTime()))
    op.create_index("ix_health_analysis_jobs_user_id", "health_analysis_jobs", ["user_id"])

def downgrade():
    op.drop_table("health_analysis_jobs")
