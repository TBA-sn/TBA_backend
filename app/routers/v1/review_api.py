# app/routers/v1/review_api.py

from fastapi import APIRouter
from app.schemas.review import (
    ReviewAPIRequest,
    ReviewAPIResponse,
    LLMRequest,      # 이미 있는 스키마라고 가정
)
from app.services.llm_client import review_code

router = APIRouter(prefix="/api/v1", tags=["review-api"])


@router.post("/review/", response_model=ReviewAPIResponse)
async def review_endpoint(payload: ReviewAPIRequest):
    # 1) 기존 LLMRequest로 변환
    # language는 일단 "python" 하드코딩, 필요하면 프론트에서 같이 보내도록 확장
    llm_req = LLMRequest(
        code=payload.code_snippet,
        language="python",
        model=None,
        criteria=["bug", "maintainability", "style", "security"],
    )

    # 2) 로컬 LLM / LM Studio 호출
    llm_res = await review_code(llm_req)

    # 3) 카테고리 매핑: 이름을 소문자로 깔고 필요한 4개만 추출
    scores_by_category: dict[str, float] = {}
    review_details: dict[str, str] = {}

    for cat in llm_res.categories:
        key = (cat.name or "").lower()
        if key in ("bug", "maintainability", "style", "security"):
            scores_by_category[key] = float(cat.score)
            review_details[key] = cat.comment or ""

    # 4) quality_score 계산: 지정된 4개 평균, 없으면 fallback으로 global 점수 사용
    if scores_by_category:
        quality_score = sum(scores_by_category.values()) / len(scores_by_category)
    else:
        quality_score = float(llm_res.scores.get("global", 0.0))

    review_summary = llm_res.summary or "No summary provided by LLM."

    return ReviewAPIResponse(
        quality_score=quality_score,
        review_summary=review_summary,
        scores_by_category=scores_by_category,
        review_details=review_details,
    )
