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
) -> Review:
    """
    LLM 결과를 기반으로 다음을 저장한다:
      - review_meta
      - review
      - review_category_result (bug / maintainability / style / security)
    그리고 Review 객체를 반환한다.
    """

    now = datetime.now(timezone.utc)

    # 1) Meta 생성
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
    await session.flush()  # meta.id 확보

    # 2) Review 생성
    review = Review(
        meta_id=meta.id,
        quality_score=float(llm_result.quality_score),
        summary=llm_result.review_summary,
    )
    session.add(review)
    await session.flush()  # review.id 확보

    # 3) 카테고리별 점수/코멘트 생성
    scores = llm_result.scores_by_category.model_dump()
    comments = llm_result.review_details or {}

    for category_name, score in scores.items():
        category_row = ReviewCategoryResult(
            review_id=review.id,
            category=category_name,              # "bug" / "maintainability" / "style" / "security"
            score=float(score),
            comment=comments.get(category_name),
        )
        session.add(category_row)

    # 여기서는 commit 안 한다. (라우터에서 ActionLog까지 묶어서 commit 할 것)
    return review
