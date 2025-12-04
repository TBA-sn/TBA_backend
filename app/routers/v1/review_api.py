# app/routers/v1/review_api.py

from typing import Dict, List

from fastapi import APIRouter

from app.schemas.review import (
    ReviewAPIRequest,
    ReviewAPIResponse,
    LLMRequest,
    LLMQualityResponse,
    ScoresByCategory,
    IssueSeverity,
)
from app.services.llm_client import review_code

router = APIRouter(prefix="/api/v1", tags=["review-api"])


@router.post("/review/", response_model=ReviewAPIResponse)
async def review_endpoint(payload: ReviewAPIRequest) -> ReviewAPIResponse:
    llm_req = LLMRequest(
        code=payload.code_snippet,
        language="python",
        model=None,
        criteria=[
            "Bug",
            "Maintainability",
            "Style",
            "Security",
        ],
    )

    llm_res: LLMQualityResponse = await review_code(llm_req)

    s: ScoresByCategory = llm_res.scores_by_category
    scores_by_category: Dict[str, float] = {
        "bug": float(s.bug),
        "maintainability": float(s.maintainability),
        "style": float(s.style),
        "security": float(s.security),
    }

    review_details_list: List[LLMReviewDetail] = []
    for category, text in (llm_res.review_details or {}).items():
        cat = str(category)
        comment = str(text)
        review_details_list.append(
            LLMReviewDetail(
                issue_id=cat,
                issue_category=cat,
                issue_severity=IssueSeverity.MEDIUM,
                issue_summary=comment,
                issue_details=comment,
                issue_line_number=0,
                issue_column_number=None,
            )
        )

    return ReviewAPIResponse(
        quality_score=float(llm_res.quality_score or 0.0),
        review_summary=llm_res.review_summary
        or "LLM 품질 API에서 요약을 제공하지 않았습니다.",
        scores_by_category=scores_by_category,
        review_details=review_details_list,
    )
