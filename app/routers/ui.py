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
    user_id: int,
    github_id: str,
    model_id: str,
    language: str,
    trigger: str,
    code: str,
    aspects: List[str],
) -> dict:


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
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        uid = None

    if uid is None:
        uid = user_id

    if uid is None:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    row = await session.execute(select(User).where(User.id == int(uid)))
    user = row.scalar_one_or_none()
    if not user or not user.github_id:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    github_id = str(user.github_id)

    criteria: List[str] = []

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
    stmt = (
        select(Review)
        .options(joinedload(Review.meta), joinedload(Review.categories))
        .where(Review.id == review_id)
    )
    rec = (await session.execute(stmt)).unique().scalar_one_or_none()
    if not rec:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    user = await _get_current_user(request, session)

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
    user = await _get_current_user(request, session)
    effective_user_id: Optional[int] = None

    if user:
        effective_user_id = user.id
    elif user_id:
        effective_user_id = int(user_id)

    if effective_user_id is None:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    row = await session.execute(select(User).where(User.id == effective_user_id))
    effective_user = row.scalar_one_or_none()
    if not effective_user or not effective_user.github_id:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    github_id = str(effective_user.github_id)

    if criteria:
        crit_list = [c.strip() for c in criteria.split(",") if c.strip()]
    else:
        crit_list = []

    llm_payload = {
        "code": code,
        "model": model_id,
        "criteria": crit_list,
    }

    final_token: str | None = None
    access_cookie = request.cookies.get("access_token")

    if token:
        final_token = token
    elif access_cookie:
        final_token = access_cookie
    else:
        debug_url = f"{INTERNAL_API_BASE}/auth/github/debug/mint?user_id={effective_user_id}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                debug_res = await client.get(debug_url)
            if debug_res.status_code == 200:
                data = debug_res.json()
                final_token = data.get("body", {}).get("access_token")
        except Exception:
            final_token = None

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




@router.get("/ws-debug")
async def ws_debug_page(request: Request):
    return templates.TemplateResponse("ui/ws_debug.html", {"request": request})


# =====================================================================
# NEW: 모델별 통계 화면 (/ui/stats/models)
# =====================================================================

@router.get("/stats/models")
async def stats_by_model_page(
    request: Request,
    from_: str | None = None,
    to: str | None = None,
):
    params = {}
    if from_:
        params["from"] = from_
    if to:
        params["to"] = to

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{INTERNAL_API_BASE}/v1/reviews/stats/by-model",
                params=params,
            )
        data = res.json()
    except Exception as e:
        data = {"error": str(e), "data": []}

    user: Optional[User] = None
    try:
        session: AsyncSession = await get_session().__anext__()
        user = await _get_current_user(request, session)
    except Exception:
        user = None

    return templates.TemplateResponse(
        "ui/stats_models.html",
        {
            "request": request,
            "from": from_,
            "to": to,
            "items": data.get("data", []),
            "error": data.get("error"),
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# NEW: 유저별 통계 화면 (/ui/stats/users)
# =====================================================================

@router.get("/stats/users")
async def stats_by_user_page(
    request: Request,
    from_: str | None = None,
    to: str | None = None,
    model: str | None = None,
    limit: int | None = None,
):
    params = {}
    if from_:
        params["from"] = from_
    if to:
        params["to"] = to
    if model:
        params["model"] = model
    if limit:
        params["limit"] = limit

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{INTERNAL_API_BASE}/v1/reviews/stats/by-user",
                params=params,
            )
        data = res.json()
    except Exception as e:
        data = {"error": str(e), "data": []}

    user: Optional[User] = None
    try:
        session: AsyncSession = await get_session().__anext__()
        user = await _get_current_user(request, session)
    except Exception:
        user = None

    return templates.TemplateResponse(
        "ui/stats_users.html",
        {
            "request": request,
            "from": from_,
            "to": to,
            "model": model,
            "limit": limit,
            "items": data.get("data", []),
            "error": data.get("error"),
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


# =====================================================================
# NEW: Fix API 테스트 화면 (/ui/fix-test)
# =====================================================================

@router.get("/fix-test")
async def fix_test_form(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    user = await _get_current_user(request, session)

    return templates.TemplateResponse(
        "ui/fix_test.html",
        {
            "request": request,
            "fixed_code": None,           # 수정된 코드 (처음엔 없음)
            "sent_pretty": None,          # 보낸 payload 미리보기
            "status": None,               # HTTP status
            "error": None,                # 에러 메시지 있으면 표시
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )


@router.post("/fix-test")
async def fix_test_submit(
    request: Request,
    review_id: int = Form(...),
    code: str = Form(...),
):
    payload = {
        "review_id": review_id,
        "code": code,
    }

    url = f"{INTERNAL_API_BASE}/v1/fix"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload)
        status = res.status_code
        fixed_code = res.text            # 🔥 /v1/fix 가 str을 반환하므로 text 로 받기
        error = None
    except httpx.ReadTimeout:
        fixed_code = ""
        status = 504
        error = "ReadTimeout: /v1/fix 응답이 너무 오래 걸렸습니다."
    except Exception as e:
        fixed_code = ""
        status = 500
        error = str(e)

    pretty_sent = json.dumps(payload, ensure_ascii=False, indent=2)

    # 유저 정보 (헤더용)
    user: Optional[User] = None
    try:
        session: AsyncSession = await get_session().__anext__()
        user = await _get_current_user(request, session)
    except Exception:
        user = None

    return templates.TemplateResponse(
        "ui/fix_test.html",
        {
            "request": request,
            "fixed_code": fixed_code,     # 👈 여기만 보면 됨: 수정된 코드 원문
            "sent_pretty": pretty_sent,   # 어떤 payload 보냈는지 확인용
            "status": status,
            "error": error,
            "current_user_id": user.id if user else None,
            "current_user_login": user.login if user else None,
        },
    )
