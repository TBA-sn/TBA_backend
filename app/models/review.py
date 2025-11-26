# app/models/review.py
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.utils.database import Base


class Review(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    model = Column(String(255), nullable=False)
    trigger = Column(String(50), nullable=False)
    language = Column(String(50), nullable=True)

    quality_score = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False)

    score_bug = Column(Integer, nullable=False)
    score_maintainability = Column(Integer, nullable=False)
    score_style = Column(Integer, nullable=False)
    score_security = Column(Integer, nullable=False)

    comment_bug = Column(Text, nullable=True)
    comment_maintainability = Column(Text, nullable=True)
    comment_style = Column(Text, nullable=True)
    comment_security = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    details = relationship(
        "ReviewDetail",
        back_populates="review",
        cascade="all, delete-orphan",
    )


class ReviewDetail(Base):
    __tablename__ = "review_detail"

    id = Column(BigInteger, primary_key=True, index=True)
    review_id = Column(
        BigInteger,
        ForeignKey("review.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    issue_id = Column(String(50), nullable=True)
    issue_category = Column(String(100), nullable=False)
    issue_severity = Column(String(10), nullable=False)

    issue_summary = Column(String(255), nullable=False)
    issue_details = Column(Text, nullable=True)

    issue_line_number = Column(Integer, nullable=True)
    issue_column_number = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    review = relationship("Review", back_populates="details")
