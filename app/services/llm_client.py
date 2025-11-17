# app/services/llm_client.py
import json
import httpx

from app.schemas.review import LLMRequest, LLMResponse, CategoryResult
from app.routers.ws_debug import ws_manager  # WebSocket manager

LLM_API_URL = "http://18.205.229.159:8001/v1/completions"
DEFAULT_MODEL = "TheBloke/CodeLlama-13B-Instruct-AWQ"


def build_prompt_from_request(req: LLMRequest) -> str:
    code = getattr(req, "code", None) or getattr(req, "input", None)
    language = getattr(req, "language", None)
    criteria = getattr(req, "criteria", []) or []

    criteria_text = ", ".join(criteria) if criteria else "전반적인 품질"

    return f"""
당신은 코드 리뷰 전문가입니다.
아래 {language or "알 수 없는 언어"} 코드를 {criteria_text} 관점에서 분석하세요.

1. scores: 전체(global) 점수와 모델(model) 점수를 0~100 사이 정수로 줍니다.
2. categories: 각 평가 항목별로 name, score, comment를 제공합니다.
3. summary: 전체 요약을 한국어로 3~4문장 내로 작성합니다.

반드시 JSON 형식만 출력하세요.

분석할 코드는 다음과 같습니다:

```code
{code}
""".strip()
def build_dummy_llm_response() -> LLMResponse:
    dummy_scores = {"global": 82, "model": 76}
    dummy_categories = [
        CategoryResult(
            name="유지보수성",
            score=78,
            comment="모듈 분리가 다소 부족해서 수정 시 영향 범위 파악이 어려울 수 있습니다.",
        ),
        CategoryResult(
            name="가독성",
            score=85,
            comment="함수와 변수 이름이 역할을 잘 드러내며, 전반적으로 코드 흐름이 명확합니다.",
        ),
        CategoryResult(
            name="확장성",
            score=72,
            comment="새 기능 추가 시 조건문 분기가 늘어날 여지가 있어 전략 패턴 분리가 도움이 됩니다.",
        ),
        CategoryResult(
            name="유연성",
            score=70,
            comment="하드코딩된 상수를 설정 값으로 분리하면 더 유연합니다.",
        ),
        CategoryResult(
            name="간결성",
            score=80,
            comment="불필요한 중복 로직이 일부 존재합니다.",
        ),
        CategoryResult(
            name="재사용성",
            score=75,
            comment="공통 로직을 유틸 함수로 추출하면 좋습니다.",
        ),
        CategoryResult(
            name="테스트 용이성",
            score=68,
            comment="의존성 분리와 mocking 구조가 필요합니다.",
        ),
    ]

    dummy_summary = (
        "전반적으로 구조와 가독성이 양호하지만, 모듈화와 의존성 관리 측면에서 "
        "개선 여지가 있는 코드입니다."
    )

    return LLMResponse(
        scores=dummy_scores,
        categories=dummy_categories,
        summary=dummy_summary,
    )
async def review_code(llm_req: LLMRequest) -> LLMResponse:
    model = getattr(llm_req, "model", None) or DEFAULT_MODEL
    prompt = getattr(llm_req, "prompt", None) or build_prompt_from_request(llm_req)

    # Step 3 WebSocket 로그
    if ws_manager:
        try:
            await ws_manager.broadcast(
                {
                    "event": "llm_request_sent",
                    "step": 3,
                    "payload": {"model": model, "has_prompt": bool(prompt)},
                }
            )
        except Exception:
            pass

    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": 0.01,
        "max_tokens": 2048,
    }

    fallback = False

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(LLM_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw_text = ""
        if isinstance(data, dict) and "choices" in data:
            choices = data.get("choices") or []
            if choices:
                raw_text = (choices[0].get("text") or "").strip()
        else:
            raw_text = json.dumps(data, ensure_ascii=False)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            fallback = True
        else:
            scores_dict = parsed.get("scores", {})
            categories_raw = parsed.get("categories", [])
            summary = parsed.get("summary", "")

            categories = [
                CategoryResult(
                    name=c.get("name", ""),
                    score=c.get("score", 0),
                    comment=c.get("comment", ""),
                )
                for c in categories_raw
            ]

            llm_resp = LLMResponse(
                scores=scores_dict,
                categories=categories,
                summary=summary,
            )

    except Exception:
        fallback = True

    if fallback:
        llm_resp = build_dummy_llm_response()

    # Step 4 WebSocket 로그
    if ws_manager:
        try:
            await ws_manager.broadcast(
                {
                    "event": "llm_response_received",
                    "step": 4,
                    "payload": {
                        "model": model,
                        "scores": llm_resp.scores,
                        "category_count": len(llm_resp.categories),
                        "fallback": fallback,
                    },
                }
            )
        except Exception:
            pass

    return llm_resp
