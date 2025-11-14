# app/routers/v1/analysis.py
from fastapi import APIRouter
from app.schemas.review import LLMAnalysisRequest, LLMAnalysisResponse
from app.services.llm_client import review_code  # 또는 별도 함수
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends
from app.utils.database import get_session
from app.models.review import Review

router = APIRouter(prefix="/v1/analysis", tags=["analysis"])

@router.post("/llm/request", response_model=LLMAnalysisResponse)
async def llm_analysis(req: LLMAnalysisRequest):
    # 여기서는 aspect 1개 기준으로 LLM 호출
    # 구현은 네 llm_client 구조에 맞게
    res = await review_code(...)  # pseudo

    return LLMAnalysisResponse(
        aspect=req.aspect,
        score=res.score,
        comment=res.comment,
        model=res.model_id,
    )

@router.post("/llm/callback")
async def llm_callback(
    body: LLMCallbackBody,
    session: AsyncSession = Depends(get_session),
):
    # TODO: review_id 기준으로 부분 결과 저장 (categories에 append 등)
    stmt = select(Review).where(Review.id == body.review_id)
    rec = (await session.execute(stmt)).scalar_one_or_none()
    if not rec:
        return {"ok": False, "message": "review not found"}

    # rec.categories_json 업데이트 등 (구현은 DB 스키마에 맞게)
    # ...

    return {"ok": True, "message": "analysis accepted"}