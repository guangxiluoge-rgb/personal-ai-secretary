from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LifeTask(Base):
    __tablename__ = "life_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    task_type: Mapped[str] = mapped_column(String(48), default="follow_up")
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(24), default="open")
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(48), default="manual")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
