# app/services/llm_client.py

import asyncio
from typing import Dict, Any

from app.services.ai_client import CodeReviewerClient
from app.schemas.review import LLMRequest, LLMQualityResponse, ScoresByCategory

AI_ENGINE_URL = "http://18.205.229.159:8001/v1"
client = CodeReviewerClient(vllm_url=AI_ENGINE_URL)


async def review_code(req: LLMRequest) -> LLMQualityResponse:
    raw = await asyncio.to_thread(client.get_review, req.code)

    quality_score = int(raw.get("quality_score", 0))
    review_summary = raw.get("review_summary", "") or ""

    scores_raw: Dict[str, Any] = raw.get("scores_by_category") or {}
    scores = ScoresByCategory(
        bug=int(scores_raw.get("bug", 0)),
        maintainability=int(scores_raw.get("maintainability", 0)),
        style=int(scores_raw.get("style", 0)),
        security=int(scores_raw.get("security", 0)),
    )

    review_details = raw.get("review_details") or {}

    return LLMQualityResponse(
        quality_score=quality_score,
        review_summary=review_summary,
        scores_by_category=scores,
        review_details=review_details,
    )


async def fix_code(
    code_snippet: str,
    review_summary: str,
    review_details: Dict[str, Any],
) -> str:
    fixed_code = await asyncio.to_thread(
        client.get_fix,
        code_snippet,
        review_summary,
        review_details,
    )
    return fixed_code
