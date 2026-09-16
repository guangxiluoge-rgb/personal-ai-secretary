"""add social circle tables

Revision ID: 0010_social_circles
Revises: 0009_life_os_context
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_social_circles"
down_revision = "0009_life_os_context"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "social_circles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("visibility", sa.String(24), nullable=False, server_default="private"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_social_circles_user_id", "social_circles", ["user_id"])

    op.create_table(
        "social_circle_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("circle_id", sa.Integer(), sa.ForeignKey("social_circles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("tags", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("circle_id", "person_id", name="uq_social_circle_member"),
    )
    op.create_index("ix_social_circle_members_circle_id", "social_circle_members", ["circle_id"])
    op.create_index("ix_social_circle_members_person_id", "social_circle_members", ["person_id"])

    op.create_table(
        "social_circle_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("circle_id", sa.Integer(), sa.ForeignKey("social_circles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("last_interaction_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_social_circle_topics_circle_id", "social_circle_topics", ["circle_id"])

    op.create_table(
        "social_circle_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("circle_id", sa.Integer(), sa.ForeignKey("social_circles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("social_circle_topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source", sa.String(48), nullable=False, server_default="manual"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_social_circle_events_circle_id", "social_circle_events", ["circle_id"])
    op.create_index("ix_social_circle_events_person_id", "social_circle_events", ["person_id"])
    op.create_index("ix_social_circle_events_topic_id", "social_circle_events", ["topic_id"])


def downgrade():
    op.drop_table("social_circle_events")
    op.drop_table("social_circle_topics")
    op.drop_table("social_circle_members")
    op.drop_table("social_circles")
