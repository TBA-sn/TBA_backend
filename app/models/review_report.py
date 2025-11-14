from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, func, ForeignKey
from app.utils.database import Base

class ReviewReport(Base):
    __tablename__ = "review_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)

    summary: Mapped[str] = mapped_column(String(1024), nullable=True)
    global_score: Mapped[int] = mapped_column(Integer, nullable=True)
    model_score: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    reviews = relationship("Review", back_populates="report", lazy="selectin")
