# app/services/llm_normalizer.py
from typing import Dict, Any

from app.schemas.review import LLMQualityResponse, ScoresByCategory


def normalize_llm_raw_to_quality_response(raw: Dict[str, Any]) -> LLMQualityResponse:
    """
    LLM 원시 응답(raw JSON)을 LLMQualityResponse로 정규화.

    - 지금은 bug / maintainability / style / security 4개만 오지만
      내부 스키마는 8개(Bug~Testing)를 강제로 가지도록 맞춰 줌.
    - 안 오는 카테고리는 0점으로 채움.
    """
    raw_scores: Dict[str, Any] = raw.get("scores_by_category", {}) or {}
    raw_details: Dict[str, Any] = raw.get("review_details", {}) or {}

    scores = ScoresByCategory(
        bug=int(raw_scores.get("bug", 0)),
        performance=int(raw_scores.get("performance", 0)),
        maintainability=int(raw_scores.get("maintainability", 0)),
        style=int(raw_scores.get("style", 0)),
        docs=int(raw_scores.get("docs", 0)),
        dependency=int(raw_scores.get("dependency", 0)),
        security=int(raw_scores.get("security", 0)),
        testing=int(raw_scores.get("testing", 0)),
    )

    return LLMQualityResponse(
        quality_score=int(raw["quality_score"]),
        review_summary=str(raw["review_summary"]),
        scores_by_category=scores,
        # 카테고리별 코멘트 dict 그대로 유지 (bug, maintainability, style, security)
        review_details={k: str(v) for k, v in raw_details.items()},
    )
