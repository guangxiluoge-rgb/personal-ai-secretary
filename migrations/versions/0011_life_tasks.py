"""add actionable life tasks

Revision ID: 0011_life_tasks
Revises: 0010_social_circles
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_life_tasks"
down_revision = "0010_social_circles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "life_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("task_type", sa.String(48), nullable=False, server_default="follow_up"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(48), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_life_tasks_user_id", "life_tasks", ["user_id"])
    op.create_index("ix_life_tasks_person_id", "life_tasks", ["person_id"])
    op.create_index("ix_life_tasks_conversation_id", "life_tasks", ["conversation_id"])
    op.create_index("ix_life_tasks_due_at", "life_tasks", ["due_at"])
    op.create_index("ix_life_tasks_status", "life_tasks", ["status"])


def downgrade():
    op.drop_table("life_tasks")
