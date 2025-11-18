# app/services/llm_client.py
import os
import logging
from typing import Dict, Any, List

import httpx

from app.schemas.review import LLMRequest, LLMResponse, CategoryResult
from app.routers.ws_debug import ws_manager  # WebSocket manager

logger = logging.getLogger(__name__)

# 🔧 LLM 품질 API 엔드포인트 (서버: 8001)
#   .env 에서 덮어쓰면 됨:
#   LLM_QUALITY_API_URL=http://18.205.229.159:8001/api/v1/review/
LLM_QUALITY_API_URL = os.getenv(
    "LLM_QUALITY_API_URL",
    "http://18.205.229.159:8001/api/v1/review/",
).rstrip("/")

# --------------------------------------------------------
# 더미 응답 (LLM 서버 죽었을 때만 사용)
# --------------------------------------------------------
def build_dummy_llm_response() -> LLMResponse:
    dummy_scores = {"global": 50.0, "model": 50.0}
    dummy_categories = [
        CategoryResult(
            name="bug",
            score=50.0,
            comment="LLM 서버 호출 실패로 더미 결과를 반환했습니다.",
        ),
        CategoryResult(
            name="maintainability",
            score=50.0,
            comment="LLM 서버가 응답하지 않아 실제 평가는 수행되지 않았습니다.",
        ),
    ]
    dummy_summary = "LLM 서버 오류로 인해 실제 코드 리뷰 대신 더미 결과를 반환했습니다."

    return LLMResponse(
        scores=dummy_scores,
        categories=dummy_categories,
        summary=dummy_summary,
    )


# --------------------------------------------------------
# 핵심 함수: 8000 → 8001 품질 API 호출
# --------------------------------------------------------
async def review_code(llm_req: LLMRequest) -> LLMResponse:

    # 1) 코드 추출
    code = getattr(llm_req, "code", None) or getattr(llm_req, "input", None)
    if not code:
        logger.error("[LLM] 코드가 비어서 리뷰를 수행할 수 없습니다.")
        return build_dummy_llm_response()

    # WebSocket 디버그 로그
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

    # 2) 요청 payload (문제에서 준 스펙 그대로)
    request_payload: Dict[str, Any] = {
        "code_snippet": code,
    }

    fallback = False
    data: Dict[str, Any] | None = None

    # 3) HTTP 호출
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{LLM_QUALITY_API_URL}/", json=request_payload)
        # 상태 코드 확인
        if resp.status_code >= 400:
            fallback = True
            logger.error(
                f"[LLM] quality API HTTP {resp.status_code} 에러: {resp.text}"
            )
        else:
            # JSON 파싱
            data = resp.json()
            logger.info(f"[LLM] quality API response: {data}")
            # 디버그용 원본 출력 (터미널에서 바로 보려고)
            print("[LLM] RAW RESPONSE:", data)
    except Exception as e:
        logger.error(f"[LLM] quality API 호출 실패: {e}")
        fallback = True

    # 4) 응답 파싱 → 내부 LLMResponse 로 변환
    if not fallback and isinstance(data, dict):
        try:
            quality_score = float(data.get("quality_score", 0.0))
            review_summary = (data.get("review_summary") or "").strip()

            scores_by_category_raw = data.get("scores_by_category") or {}
            review_details = data.get("review_details") or {}

            scores_dict = {
                "global": quality_score,
                "model": quality_score,
            }

            categories: List[CategoryResult] = []

            # dict 형태: { "bug": 70.0, ... }
            if isinstance(scores_by_category_raw, dict):
                for name, score in scores_by_category_raw.items():
                    name_str = str(name)
                    try:
                        score_val = float(score)
                    except Exception:
                        score_val = 0.0
                    comment = ""
                    if isinstance(review_details, dict):
                        comment = review_details.get(name_str, "") or ""
                    categories.append(
                        CategoryResult(
                            name=name_str,
                            score=score_val,
                            comment=comment,
                        )
                    )

            # list 형태: [ {"name": "...", "score": ...}, ... ] 도 지원
            elif isinstance(scores_by_category_raw, list):
                for item in scores_by_category_raw:
                    if not isinstance(item, dict):
                        continue
                    name_str = str(item.get("name", ""))
                    try:
                        score_val = float(item.get("score", 0.0))
                    except Exception:
                        score_val = 0.0
                    comment = item.get("comment") or ""
                    if not comment and isinstance(review_details, dict):
                        comment = review_details.get(name_str, "") or ""
                    categories.append(
                        CategoryResult(
                            name=name_str,
                            score=score_val,
                            comment=comment,
                        )
                    )

            # 파싱된 걸로 최종 LLMResponse 생성
            llm_resp = LLMResponse(
                scores=scores_dict,
                categories=categories,
                summary=review_summary or "LLM 품질 API에서 요약을 제공하지 않았습니다.",
            )
        except Exception as e:
            # 파싱만 실패했으면 그냥 더미로 폴백
            logger.error(f"[LLM] 응답 파싱 중 오류: {e}")
            fallback = True
            llm_resp = build_dummy_llm_response()
    else:
        llm_resp = build_dummy_llm_response()

    # WebSocket 디버그 로그
    if ws_manager:
        try:
            await ws_manager.broadcast(
                {
                    "event": "llm_response_received",
                    "step": 4,
                    "payload": {
                        "from": "quality_api",
                        "scores": llm_resp.scores,
                        "category_count": len(llm_resp.categories),
                        "fallback": fallback,
                    },
                }
            )
        except Exception:
            pass

    return llm_resp
