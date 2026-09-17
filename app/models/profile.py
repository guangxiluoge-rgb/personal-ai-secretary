from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ProfileQuestionnaire(Base):
    __tablename__ = "profile_questionnaires"
    __table_args__ = (UniqueConstraint("user_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="paused")
    version: Mapped[str] = mapped_column(String(32), default="aron-inspired-v1")
    consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ProfileAnswer(Base):
    __tablename__ = "profile_answers"
    __table_args__ = (UniqueConstraint("questionnaire_id", "question_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("profile_questionnaires.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_key: Mapped[str] = mapped_column(String(64), index=True)
    dimension: Mapped[str] = mapped_column(String(64), index=True)
    answer: Mapped[str] = mapped_column(Text)
    round_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProfileFact(Base):
    __tablename__ = "profile_facts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(120))
    statement: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(default=0.5)
    source_answer_id: Mapped[int | None] = mapped_column(ForeignKey("profile_answers.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
