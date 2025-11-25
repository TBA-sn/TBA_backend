# app/services/llm_normalizer.py
from typing import Dict, Any

from app.schemas.review import LLMQualityResponse, ScoresByCategory


def normalize_llm_raw_to_quality_response(raw: Dict[str, Any]) -> LLMQualityResponse:
   
    raw_scores: Dict[str, Any] = raw.get("scores_by_category", {}) or {}
    raw_details: Dict[str, Any] = raw.get("review_details", {}) or {}

    scores = ScoresByCategory(
        bug=int(raw_scores.get("bug", 0)),
        maintainability=int(raw_scores.get("maintainability", 0)),
        style=int(raw_scores.get("style", 0)),
        security=int(raw_scores.get("security", 0)),
    )

    return LLMQualityResponse(
        quality_score=int(raw["quality_score"]),
        review_summary=str(raw["review_summary"]),
        scores_by_category=scores,
        # 카테고리별 코멘트 dict 그대로 유지 (bug, maintainability, style, security)
        review_details={k: str(v) for k, v in raw_details.items()},
    )
