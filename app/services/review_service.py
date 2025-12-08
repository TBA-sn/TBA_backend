# app/services/review_service.py

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review, ReviewMeta, ReviewCategoryResult
from app.schemas.review import LLMQualityResponse


async def save_review_result(
    session: AsyncSession,
    *,
    github_id: Optional[str],
    model: str,
    trigger: str,
    language: Optional[str],
    llm_result: LLMQualityResponse,
    code_fingerprint: Optional[str] = None,
    raw_code: Optional[str] = None,
) -> Review:

    now = datetime.now(timezone.utc)

    meta = ReviewMeta(
        github_id=github_id,
        version="v1",
        language=language or "unknown",
        trigger=trigger or "manual",
        code_fingerprint=code_fingerprint,
        model=model,
        audit=now,
    )
    session.add(meta)
    await session.flush()

    review = Review(
        meta_id=meta.id,
        quality_score=float(llm_result.quality_score),
        summary=llm_result.review_summary,
        code=raw_code,
    )
    session.add(review)
    await session.flush()

    scores = llm_result.scores_by_category.model_dump()
    comments = llm_result.review_details or {}

    for category_name, score in scores.items():
        category_row = ReviewCategoryResult(
            review_id=review.id,
            category=category_name,
            score=float(score),
            comment=comments.get(category_name),
        )
        session.add(category_row)

    return review
