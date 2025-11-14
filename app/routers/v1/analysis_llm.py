# app/routers/v1/analysis_llm.py
from fastapi import APIRouter, BackgroundTasks
from app.schemas.analysis import LLMAnalysisRequest
from app.schemas.analysis import LLMCallbackRequest
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.database import get_session
from app.models.review import Review

router = APIRouter(prefix="/v1/analysis/llm", tags=["analysis-llm"])


@router.post("/request")
async def request_llm_analysis(
    payload: LLMAnalysisRequest,
    background_tasks: BackgroundTasks,
):
    # TODO: 여기서 큐/워커로 전달 (예: Redis/Kafka 등)
    # 일단 202만 리턴하거나, 간단한 ack 리턴
    return {
        "status": "accepted",
        "model": payload.request.model,
    }

@router.post("/callback")
async def llm_callback(
    payload: LLMCallbackRequest,
    session: AsyncSession = Depends(get_session),
):
    # TODO: correlation_id -> review_id 매핑 테이블 갖고 있으면 여기서 찾아서 Review update
    # 일단은 로깅만 한다고 가정
    # 예: aspect_scores / rationales 를 review_result 테이블에 저장 등
    return {"status": "ok"}