from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, Text, DateTime, func, ForeignKey, JSON
from app.utils.database import Base

class Review(Base):
    __tablename__ = "review"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), onupdate="CASCADE", nullable=True)
    model_id: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
