# app/routers/llm/__init__.py
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_session
from app.routers.auth import get_current_user_id
from app.routers.deps import require_service_token

from app.models.review import Review



from app.schemas.analysis import (
    AnalysisRequestIn,
    AnalysisRequestAck,
    AnalysisCallbackIn,
    AnalysisStoredOut,
)
from app.schemas.review import LLMRequest, LLMQualityResponse
from app.services.llm_clientt import review_code

router = APIRouter(prefix="/v1/analysis/llm", tags=["analysis-llm"])




@router.post("/request", response_model=AnalysisRequestAck, summary="코드 분석 요청(LLM로 전달)")
async def analysis_llm_request(
    body: AnalysisRequestIn,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id),
):
    case_id = body.case_id or f"c-{uuid4().hex}"
    await session.commit()

    if body.direct:
        llm_res: LLMQualityResponse = await review_code(
            LLMRequest(code=body.code, model=body.model, criteria=criteria)
        )
        rev = Review(
            user_id=user_id,
            model_id=body.model,
            language="unknown",
            trigger="direct",
            code=body.code,
            result=llm_res.model_dump(),
            summary=llm_res.review_summary,
        )
        session.add(rev)
        await session.flush()
        await session.commit()
        return AnalysisRequestAck(case_id=case_id, status="requested_direct")

    return AnalysisRequestAck(case_id=case_id, status="requested")


@router.post("/callback", response_model=AnalysisStoredOut, summary="LLM 결과 콜백(저장)")
async def analysis_llm_callback(
    body: AnalysisCallbackIn,
    session: AsyncSession = Depends(get_session),
    _svc_ok: bool = Depends(require_service_token),
):
    llm_res = body.llm_response
    rev = Review(
        user_id=None,
        model_id="unknown",
        language="unknown",
        trigger="callback",
        code="",
        result=llm_res.model_dump(),
        summary=llm_res.review_summary,
    )
    session.add(rev)
    await session.flush()
    await session.commit()
    return AnalysisStoredOut(case_id=body.case_id, review_id=rev.id, status="stored")
