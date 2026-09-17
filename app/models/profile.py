from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class UserQuestionnaire(Base):
    __tablename__ = "user_questionnaires"
    __table_args__ = (UniqueConstraint("user_id", "program_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program_key: Mapped[str] = mapped_column(String(64), default="personal_portrait_36", nullable=False)
    consented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserQuestionnaireAnswer(Base):
    __tablename__ = "user_questionnaire_answers"
    __table_args__ = (UniqueConstraint("questionnaire_id", "question_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("user_questionnaires.id", ondelete="CASCADE"), index=True)
    question_key: Mapped[str] = mapped_column(String(80), index=True)
    dimension: Mapped[str] = mapped_column(String(64), index=True)
    prompt_variant: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source: Mapped[str] = mapped_column(String(48), default="questionnaire", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
