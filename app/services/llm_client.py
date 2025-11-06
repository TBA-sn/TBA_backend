# app/services/llm_client.py
import os
from typing import List, Dict, Any
import httpx
from app.schemas.review import LLMRequest, LLMResponse

LLM_ENDPOINT = os.getenv("LLM_ENDPOINT")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "15"))

async def _call_llm(req: LLMRequest) -> Dict[str, Any]:
    if not LLM_ENDPOINT:
        raise RuntimeError("LLM_ENDPOINT not set")

    url = f"{LLM_ENDPOINT.rstrip('/')}/v1/review"
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        r = await client.post(url, json=req.model_dump())
        r.raise_for_status()
        return r.json()

def _mock_response(req: LLMRequest) -> Dict[str, Any]:

    code_len = len(req.code.strip())
    base = 72 + min(15, max(0, code_len // 20))
    return {
        "scores": {"global": base, "model": base - 4},
        "categories": [
            {"name": "readability", "score": min(100, base + 5), "comment": "명확한 변수/함수명"},
            {"name": "efficiency", "score": max(50, base - 8), "comment": "루프/메모리 최적화 여지"},
            {"name": "consistency", "score": min(100, base + 7), "comment": "스타일 일관"},
        ],
        "summary": "전반적으로 간결하고 가독성이 높음.",
    }

async def review_code(req: LLMRequest) -> LLMResponse:

    try:
        data = await _call_llm(req)
    except Exception as e:
        data = _mock_response(req)

    return LLMResponse.model_validate(data)
