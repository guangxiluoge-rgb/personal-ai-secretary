"""add adaptive profile questionnaire

Revision ID: 0012_profile_questionnaire
Revises: 0011_life_tasks
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_profile_questionnaire"
down_revision = "0011_life_tasks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "profile_questionnaires",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="paused"),
        sa.Column("version", sa.String(32), nullable=False, server_default="aron-inspired-v1"),
        sa.Column("consent_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_profile_questionnaires_user_id", "profile_questionnaires", ["user_id"])

    op.create_table(
        "profile_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("questionnaire_id", sa.Integer(), sa.ForeignKey("profile_questionnaires.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_key", sa.String(64), nullable=False),
        sa.Column("dimension", sa.String(64), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("round_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("questionnaire_id", "question_key"),
    )
    op.create_index("ix_profile_answers_questionnaire_id", "profile_answers", ["questionnaire_id"])
    op.create_index("ix_profile_answers_user_id", "profile_answers", ["user_id"])
    op.create_index("ix_profile_answers_question_key", "profile_answers", ["question_key"])
    op.create_index("ix_profile_answers_dimension", "profile_answers", ["dimension"])

    op.create_table(
        "profile_facts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("source_answer_id", sa.Integer(), sa.ForeignKey("profile_answers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_profile_facts_user_id", "profile_facts", ["user_id"])
    op.create_index("ix_profile_facts_dimension", "profile_facts", ["dimension"])
    op.create_index("ix_profile_facts_source_answer_id", "profile_facts", ["source_answer_id"])


def downgrade():
    op.drop_table("profile_facts")
    op.drop_table("profile_answers")
    op.drop_table("profile_questionnaires")
