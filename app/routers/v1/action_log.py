# app/routers/v1/action_log.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.database import get_session
from app.models.action_log import ActionLog
from app.schemas.action_log import ActionLogOut, ActionLogList
from app.routers.auth import get_current_user_id

router = APIRouter(prefix="/v1", tags=["action-log"])

@router.get("/action-logs", response_model=ActionLogList, summary="액션 로그 목록")
async def list_action_logs(
    session: AsyncSession = Depends(get_session),
    _uid: int = Depends(get_current_user_id),
    user_id: Optional[int] = Query(None, description="해당 유저의 로그만"),
    case_id: Optional[str] = Query(None, description="보통 review id 문자열"),
    action: Optional[str] = Query(None, description="예: REVIEW_REQUEST"),
    since: Optional[datetime] = Query(None, description="이 시간 이후"),
    until: Optional[datetime] = Query(None, description="이 시간 이전"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(ActionLog)

    if user_id is not None:
        stmt = stmt.where(ActionLog.user_id == user_id)
    if case_id:
        stmt = stmt.where(ActionLog.case_id == case_id)
    if action:
        stmt = stmt.where(ActionLog.action == action)
    if since:
        stmt = stmt.where(ActionLog.timestamp >= since)
    if until:
        stmt = stmt.where(ActionLog.timestamp <= until)

    stmt = stmt.order_by(ActionLog.timestamp.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return ActionLogList(items=rows)


@router.get("/reviews/{review_id}/logs", response_model=ActionLogList, summary="특정 리뷰의 액션 로그")
async def list_review_logs(
    review_id: int,
    session: AsyncSession = Depends(get_session),
    _uid: int = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = (
        select(ActionLog)
        .where(ActionLog.case_id == str(review_id))
        .order_by(ActionLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return ActionLogList(items=rows)


@router.get("/action-logs/{log_id}", response_model=ActionLogOut, summary="액션 로그 단건 조회")
async def get_action_log(
    log_id: str,
    session: AsyncSession = Depends(get_session),
    _uid: int = Depends(get_current_user_id),
):
    row = (await session.execute(
        select(ActionLog).where(ActionLog.log_id == log_id)
    )).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="action_log not found")

    return row
