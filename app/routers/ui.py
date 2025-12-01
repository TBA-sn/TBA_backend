# app/routers/ui.py
from uuid import uuid4
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.utils.database import get_session
from app.models.review import Review, ReviewMeta
from app.models.action_log import ActionLog
from app.models.user import User
from app.routers.auth import get_current_user_id_from_cookie
from app.schemas.common import Meta as MetaSchema
import httpx
import os

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates")

INTERNAL_API_BASE: str = os.getenv("INTERNAL_API_BASE", "http://127.0.0.1:8000")


# =====================================================================
# 공통 유저 조회
# =====================================================================

async def _get_current_user(
    request: Request,
    session: AsyncSession,
) -> Optional[User]:
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        return None

    if not uid:
        return None

    row = await session.execute(select(User).where(User.id == uid))
    return row.scalar_one_or_none()


# =====================================================================
# /v1/reviews/request 로 넘길 payload 빌드
# =====================================================================

def build_code_request_payload(
    *,
    user_id: int,        # 의미상 남겨둠 (현재는 사용 안 함)
    github_id: str,
    model_id: str,
    language: str,
    trigger: str,
    code: str,
    aspects: List[str],
) -> dict:
    """
    /v1/reviews/request 에 맞춘 envelope(meta + body) 생성
    Meta 스키마(app.schemas.common.Meta)에 정확히 맞춘다.
    """

    meta_obj = MetaSchema(
        github_id=github_id,
        review_id=None,
        version="v1",
        actor="web",
        language=language,
        trigger=trigger,
        code_fingerprint=None,
        model=model_id,
        result=None,
        audit=None,
    )

    body = {
        "snippet": {
            "code": code,
        },
    }

    return {
        "meta": meta_obj.model_dump(mode="json"),
        "body": body,
    }


# =====================================================================
# 리뷰 폼
# =====================================================================

@router.get("/review")
async def review_form(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(request, session)

    ctx = {
        "request": request,
        "current_user_id": user.id if user else None,
        "current_user_login": user.login if user else None,
    }
    return templates.TemplateResponse("ui/review_form.html", ctx)


@router.post("/review")
async def review_submit(
    request: Request,
    user_id: int | None = Form(None),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    # 1) 유저 ID 결정 (쿠키 우선, 없으면 폼의 user_id)
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        uid = None

    if uid is None:
        uid = user_id

    if uid is None:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    # 2) DB에서 github_id 조회
    row = await session.execute(select(User).where(User.id == int(uid)))
    user = row.scalar_one_or_none()
    if not user or not user.github_id:
        # 깃허브 로그인 안 돼 있거나 github_id 없는 경우 다시 로그인으로
        return RedirectResponse(url="/auth/github/login", status_code=303)

    github_id = str(user.github_id)

    # 3) criteria/aspects (지금은 체크박스 같은 거 없으니까 빈 리스트)
    criteria: List[str] = []

    # 4) /v1/reviews/request 로 보낼 payload 생성
    payload = build_code_request_payload(
        user_id=int(uid),
        github_id=github_id,
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        aspects=criteria,
    )

    url = f"{INTERNAL_API_BASE}/v1/reviews/request"

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, json=payload)

    if res.status_code != 200:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    body = res.json()
    resp_body = body.get("body") or {}
    review_id = resp_body.get("review_id")

    if not review_id:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    return RedirectResponse(url=f"/ui/review/{review_id}", status_code=303)


# =====================================================================
# 리뷰 상세
# =====================================================================

@router.get("/review/{review_id}")
async def review_detail(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    일단은 ORM Review 그대로 가져와서 템플릿에 넘김.
    (Review 모델에 없는 필드는 Jinja에서 그냥 빈 값으로 떨어지니까 에러 안 남)
    나중에 필요하면 /v1/reviews/{id} API를 불러서 quality / category_rows 채워도 됨.
    """
    stmt = (
        select(Review)
        .options(joinedload(Review.meta), joinedload(Review.categories))
        .where(Review.id == review_id)
    )
    rec = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not rec:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    user = await _get_current_user(request, session)

    # 현재는 quality / category_rows 안 채우고, 템플릿에서 fallback 로직 사용
    return templates.TemplateResponse(
        "ui/review_detail.html",
        {
            "request": request,
            "rec": rec,
            "quality": None,
            "category_rows": None,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# 리뷰 목록
# =====================================================================

@router.get("/reviews")
async def review_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: int | None = None,
):
    """
    ReviewMeta.audit 기준으로 최신순 정렬해서 리뷰 목록 조회
    """
    stmt = (
        select(Review)
        .join(ReviewMeta, Review.meta_id == ReviewMeta.id)
        .options(joinedload(Review.meta))
        .order_by(ReviewMeta.audit.desc())
    )

    rows = (await session.execute(stmt)).unique().scalars().all()
    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/review_list.html",
        {
            "request": request,
            "rows": rows,
            "user_id": user_id,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# API 테스트 화면 (/ui/api-test)
# =====================================================================

@router.get("/api-test")
async def api_test_form(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/api_test.html",
        {
            "request": request,
            "resp": None,
            "sent_pretty": None,
            "llm_payload_pretty": None,
            "used_authorization": False,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


@router.post("/api-test")
async def api_test_submit(
    request: Request,
    user_id: str = Form(""),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
    token: str | None = Form(None),
    criteria: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
):
    # 1) 현재 로그인 유저 확인
    user = await _get_current_user(request, session)
    effective_user_id: Optional[int] = None

    if user:
        effective_user_id = user.id
    elif user_id:
        effective_user_id = int(user_id)

    if effective_user_id is None:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    # 2) DB에서 github_id 조회
    row = await session.execute(select(User).where(User.id == effective_user_id))
    effective_user = row.scalar_one_or_none()
    if not effective_user or not effective_user.github_id:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    github_id = str(effective_user.github_id)

    # criteria 문자열 → 리스트
    if criteria:
        crit_list = [c.strip() for c in criteria.split(",") if c.strip()]
    else:
        crit_list = []

    # LLM 디버깅용 payload (화면에 보여주는 용도)
    llm_payload = {
        "code": code,
        "model": model_id,
        "criteria": crit_list,
    }

    # 3) Authorization 토큰 결정
    final_token: str | None = None
    access_cookie = request.cookies.get("access_token")

    if token:
        final_token = token
    elif access_cookie:
        final_token = access_cookie
    else:
        # 디버그용 토큰 발급 엔드포인트 호출
        debug_url = f"{INTERNAL_API_BASE}/auth/github/debug/mint?user_id={effective_user_id}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                debug_res = await client.get(debug_url)
            if debug_res.status_code == 200:
                data = debug_res.json()
                final_token = data.get("body", {}).get("access_token")
        except Exception:
            final_token = None

    # 4) /v1/reviews/request 에 보낼 최종 payload
    payload = build_code_request_payload(
        user_id=effective_user_id,
        github_id=github_id,
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        aspects=crit_list,
    )

    url = f"{INTERNAL_API_BASE}/v1/reviews/request"
    headers = {"Content-Type": "application/json"}

    if final_token:
        headers["Authorization"] = f"Bearer {final_token}"

    cookies = {}
    if access_cookie:
        cookies["access_token"] = access_cookie

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, headers=headers, cookies=cookies, json=payload)
        try:
            body = res.json()
        except Exception:
            body = {"raw": res.text}
        status = res.status_code
    except httpx.ReadTimeout:
        res = None
        body = {
            "error": "ReadTimeout: /v1/reviews/request 응답이 너무 오래 걸렸습니다."
        }
        status = 504

    pretty_resp = json.dumps(body, ensure_ascii=False, indent=2)
    pretty_sent = json.dumps(payload, ensure_ascii=False, indent=2)
    llm_payload_pretty = json.dumps(llm_payload, ensure_ascii=False, indent=2)

    return templates.TemplateResponse(
        "ui/api_test.html",
        {
            "request": request,
            "resp": {"status": status, "json": body, "pretty": pretty_resp},
            "sent": payload,
            "sent_pretty": pretty_sent,
            "llm_payload_pretty": llm_payload_pretty,
            "used_authorization": bool(final_token),
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# 리뷰 로그
# =====================================================================

@router.get("/review/{review_id}/logs")
async def review_logs(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(ActionLog)
        .where(ActionLog.event_name == "REVIEW_REQUEST")
        .order_by(ActionLog.timestamp.desc())
    )
    logs = (await session.execute(stmt)).scalars().all()

    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/review_logs.html",
        {
            "request": request,
            "review_id": review_id,
            "logs": logs,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


@router.get("/ws-debug")
async def ws_debug_page(request: Request):
    return templates.TemplateResponse("ui/ws_debug.html", {"request": request})
