# app/models/review.py
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.utils.database import Base


class ReviewMeta(Base):
    __tablename__ = "review_meta"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(String(32), nullable=True, index=True)
    version = Column(String(10), nullable=False, server_default="v1")
    language = Column(String(50), nullable=False, server_default="python")
    trigger = Column(String(32), nullable=False, server_default="manual")
    code_fingerprint = Column(String(128), nullable=True)
    model = Column(String(255), nullable=True)
    audit = Column(DateTime(timezone=True), nullable=True)

    reviews = relationship(
        "Review",
        back_populates="meta",
        cascade="all, delete-orphan",
    )


class Review(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True, index=True)
    meta_id = Column(
        Integer,
        ForeignKey("review_meta.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quality_score = Column(Float, nullable=False)
    summary = Column(Text, nullable=False)
    code = Column(Text, nullable=True)

    meta = relationship("ReviewMeta", back_populates="reviews")

    categories = relationship(
        "ReviewCategoryResult",
        back_populates="review",
        cascade="all, delete-orphan",
    )



class ReviewCategoryResult(Base):
    __tablename__ = "review_category_result"

    id = Column(Integer, primary_key=True, index=True)

    review_id = Column(
        Integer,
        ForeignKey("review.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category = Column(String(50), nullable=False, index=True)

    score = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)


    review = relationship("Review", back_populates="categories")
