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
        score_performance=s.performance,
        score_maintainability=s.maintainability,
        score_style=s.style,
        score_docs=s.docs,
        score_dependency=s.dependency,
        score_security=s.security,
        score_testing=s.testing,
        comment_bug=d.get("bug"),
        comment_performance=d.get("performance"),
        comment_maintainability=d.get("maintainability"),
        comment_style=d.get("style"),
        comment_docs=d.get("docs"),
        comment_dependency=d.get("dependency"),
        comment_security=d.get("security"),
        comment_testing=d.get("testing"),
        status="done",
    )

    session.add(r)
    await session.commit()
    await session.refresh(r)

    return r
