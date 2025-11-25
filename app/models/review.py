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

    model = Column(String(255), nullable=False)      # 사용한 LLM 모델 이름
    trigger = Column(String(50), nullable=False)     # 'manual', 'save', 'commit' 등
    language = Column(String(50), nullable=True)     # 'python', 'typescript' 등

    # ===== 점수 & 요약 =====
    quality_score = Column(Integer, nullable=False)  # 0~100 (전체 품질 점수)
    summary = Column(Text, nullable=False)           # review_summary

    # scores_by_category (8개로 확장)
    score_bug = Column(Integer, nullable=False)
    score_maintainability = Column(Integer, nullable=False)
    score_style = Column(Integer, nullable=False)
    score_security = Column(Integer, nullable=False)

    # 카테고리별 코멘트 (선택)
    comment_bug = Column(Text, nullable=True)
    comment_maintainability = Column(Text, nullable=True)
    comment_style = Column(Text, nullable=True)
    comment_security = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default="done")  # 'done', 'processing' 등

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

    issue_id = Column(String(50), nullable=True)          # "E501", "B101" 등
    issue_category = Column(String(100), nullable=False)  # "line_too_long" 등
    issue_severity = Column(String(10), nullable=False)   # "HIGH", "MEDIUM", "LOW"

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
