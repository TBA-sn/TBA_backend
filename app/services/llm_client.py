# app/services/llm_client.py
import os
import logging
from typing import Dict, Any

import httpx

from app.schemas.review import LLMRequest, LLMQualityResponse, ScoresByCategory
from app.routers.ws_debug import ws_manager

logger = logging.getLogger(__name__)

LLM_QUALITY_API_URL = os.getenv(
    "LLM_QUALITY_API_URL",
    "http://18.205.229.159:8002/api/v1/review/",
).rstrip("/")


async def review_code(llm_req: LLMRequest) -> LLMQualityResponse:
    code = getattr(llm_req, "code", None) or getattr(llm_req, "input", None)
    if not code:
        logger.error("[LLM] 코드가 비어서 리뷰를 수행할 수 없습니다.")
        raise ValueError("LLM review_code: code is empty")

    if ws_manager:
        try:
            await ws_manager.broadcast(
                {
                    "event": "llm_request_sent",
                    "step": 3,
                    "payload": {
                        "target": "quality_api",
                        "url": f"{LLM_QUALITY_API_URL}/",
                        "has_code": bool(code),
                    },
                }
            )
        except Exception:
            pass

    request_payload: Dict[str, Any] = {
        "code_snippet": code,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{LLM_QUALITY_API_URL}/", json=request_payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[LLM] quality API response: {data}")
        print("[LLM] RAW RESPONSE:", data)
    except Exception as e:
        logger.error(f"[LLM] quality API 호출 실패: {e}")
        raise

    try:
        raw_scores = data.get("scores_by_category") or {}
        scores = ScoresByCategory(
            bug=int(raw_scores.get("bug", 0)),
            maintainability=int(raw_scores.get("maintainability", 0)),
            style=int(raw_scores.get("style", 0)),
            security=int(raw_scores.get("security", 0)),
        )

        raw_details = data.get("review_details") or {}
        if not isinstance(raw_details, dict):
            raw_details = {}

        review_details: Dict[str, str] = {
            str(k).lower(): str(v) for k, v in raw_details.items()
        }

        quality_score = int(data.get("quality_score", 0))
        summary_raw = (data.get("review_summary") or "").strip()
        review_summary = (
            summary_raw or "LLM 품질 API에서 요약을 제공하지 않았습니다."
        )

        llm_resp = LLMQualityResponse(
            quality_score=quality_score,
            review_summary=review_summary,
            scores_by_category=scores,
            review_details=review_details,
        )

    except Exception as e:
        logger.error(f"[LLM] 응답 파싱 중 오류: {e}")
        raise

    if ws_manager:
        try:
            await ws_manager.broadcast(
                {
                    "event": "llm_response_received",
                    "step": 4,
                    "payload": {
                        "from": "quality_api",
                        "quality_score": llm_resp.quality_score,
                        "category_count": 8,
                        "detail_count": len(llm_resp.review_details),
                        "fallback": False,
                    },
                }
            )
        except Exception:
            pass

    return llm_resp
