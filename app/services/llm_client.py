# app/services/llm_client.py
from app.schemas.review import LLMRequest, LLMResponse, CategoryResult


async def review_code(llm_req: LLMRequest) -> LLMResponse:
    """
    LLM 서버 호출 래퍼.
    지금은 개발용 더미 응답을 반환하고,
    나중에 httpx로 실제 LLM 엔드포인트 호출 로직을 여기 안에 넣으면 됨.
    """
    # TODO: 여기다가 실제 LLM API 호출(httpx) 붙이기
    # llm_req.model, llm_req.input, llm_req.criteria 사용

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
            comment="새 기능 추가 시 조건문 분기가 늘어날 여지가 있어, 전략 패턴 등으로 분리하면 좋습니다.",
        ),
        CategoryResult(
            name="유연성",
            score=70,
            comment="하드코딩된 상수와 직접 의존성이 있어, 설정 값/인터페이스로 분리하면 더 유연해집니다.",
        ),
        CategoryResult(
            name="간결성",
            score=80,
            comment="불필요한 중복 로직이 일부 존재하지만, 전반적으로는 과한 장황함 없이 정리되어 있습니다.",
        ),
        CategoryResult(
            name="재사용성",
            score=75,
            comment="반복되는 로직을 유틸 함수나 공통 모듈로 추출하면 여러 곳에서 재사용하기 좋습니다.",
        ),
        CategoryResult(
            name="테스트 용이성",
            score=68,
            comment="의존성 주입이 부족해 단위 테스트 작성이 어렵고, 인터페이스 분리와 mocking 구조가 도움이 됩니다.",
        ),
    ]

    dummy_summary = (
        "전반적으로 구조와 가독성은 양호하지만, 재사용성과 테스트 용이성을 위한 "
        "의존성 분리·모듈화 리팩터링 여지가 있습니다."
    )

    return LLMResponse(
        scores=dummy_scores,
        categories=dummy_categories,
        summary=dummy_summary,
    )
