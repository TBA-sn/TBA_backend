# app/routers/ui.py
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.utils.database import get_session
from app.schemas.review import LLMRequest
from app.models.review import Review
from app.models.action_log import ActionLog
from app.services.llm_client import review_code
from app.routers.auth import get_current_user_id_from_cookie
import json
import httpx
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/review")
async def review_form(request: Request):
    return templates.TemplateResponse("ui/review_form.html", {"request": request})

@router.post("/review")
async def review_submit(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: int | None = Form(None),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
):
    try:
        uid = get_current_user_id_from_cookie(request)
    except Exception:
        uid = user_id

    llm_res = await review_code(LLMRequest(code=code, model=model_id))

    rec = Review(
        user_id=uid,
        model_id=model_id,
        language=language,
        trigger=trigger,
        code=code,
        result=llm_res.model_dump(),
        summary=llm_res.summary,
    )
    session.add(rec)
    await session.flush()

    session.add(ActionLog(
        log_id=f"lg-{uuid4().hex}",
        user_id=uid,             
        case_id=str(rec.id),
        action="REVIEW_REQUEST",
    ))
    await session.commit()

    return RedirectResponse(url=f"/ui/review/{rec.id}", status_code=303)

@router.get("/review/{review_id}")
async def review_detail(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Review).where(Review.id == review_id)
    rec = (await session.execute(stmt)).scalar_one_or_none()
    if not rec:
        return RedirectResponse(url="/ui/reviews", status_code=303)

    return templates.TemplateResponse("ui/review_detail.html", {
        "request": request,
        "rec": rec,
    })

@router.get("/reviews")
async def review_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user_id: int | None = None,
):
    stmt = select(Review).order_by(Review.id.desc())
    if user_id is not None:
        stmt = stmt.where(Review.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    return templates.TemplateResponse("ui/review_list.html", {
        "request": request,
        "rows": rows,
        "user_id": user_id,
    })

@router.get("/api-test")
async def api_test_form(request: Request):
    return templates.TemplateResponse("ui/api_test.html", {"request": request, "resp": None})

@router.post("/api-test")
async def api_test_submit(
    request: Request,
    user_id: str = Form(...),
    model_id: str = Form(...),
    language: str = Form(...),
    trigger: str = Form(...),
    code: str = Form(...),
    token: str | None = Form(None),
    criteria: str = Form("readability,efficiency,consistency"),
):
    crit_list = [c.strip() for c in criteria.split(",") if c.strip()]
    llm_payload = {"code": code, "model": model_id, "criteria": crit_list}

    auth_header = None
    if token:
        auth_header = f"Bearer {token}"
    else:
        try:
            from app.routers.auth import get_current_user_id_from_cookie
            _ = get_current_user_id_from_cookie(request)
        except Exception:
            pass

    payload = {
        "user_id": user_id,
        "model_id": model_id,
        "code": code,
        "language": language,
        "trigger": trigger,
    }

    url = "http://localhost:8000/v1/reviews/request"
    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header

    cookies = {}
    access_cookie = request.cookies.get("access_token")
    if access_cookie:
        cookies["access_token"] = access_cookie

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, headers=headers, cookies=cookies, json=payload)

    try:
        body = res.json()
    except Exception:
        body = {"raw": res.text}

    pretty_resp = json.dumps(body, ensure_ascii=False, indent=2)
    pretty_sent = json.dumps(payload, ensure_ascii=False, indent=2)
    llm_payload_pretty = json.dumps(llm_payload, ensure_ascii=False, indent=2)

    return templates.TemplateResponse(
        "ui/api_test.html",
        {
            "request": request,
            "resp": {
                "status": res.status_code,
                "json": body,
                "pretty": pretty_resp,
            },
            "sent": payload,
            "sent_pretty": pretty_sent,
            "llm_payload_pretty": llm_payload_pretty,
            "used_authorization": bool(auth_header) or bool(access_cookie),
        },
    )

@router.get("/review/{review_id}/logs")
async def review_logs(
    review_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(ActionLog)
        .where(ActionLog.case_id == str(review_id))
        .order_by(ActionLog.timestamp.desc())
    )
    logs = (await session.execute(stmt)).scalars().all()

    return templates.TemplateResponse("ui/review_logs.html", {
        "request": request,
        "review_id": review_id,
        "logs": logs,
    })
