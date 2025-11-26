# app/services/review_service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.schemas.review import LLMQualityResponse


async def save_review_result(
    session: AsyncSession,
    *,
    user_id: int,
    model: str,
    trigger: str,
    language: str | None,
    llm_result: LLMQualityResponse,
) -> Review:
    s = llm_result.scores_by_category
    d = llm_result.review_details or {}

    r = Review(
        user_id=user_id,
        model=model,
        trigger=trigger,
        language=language,
        quality_score=llm_result.quality_score,
        summary=llm_result.review_summary,
        score_bug=s.bug,
        score_maintainability=s.maintainability,
        score_style=s.style,
        score_security=s.security,
        comment_bug=d.get("bug"),
        comment_maintainability=d.get("maintainability"),
        comment_style=d.get("style"),
        comment_security=d.get("security"),
    )

    session.add(r)
    await session.commit()
    await session.refresh(r)

    return r
