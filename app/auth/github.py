# app/auth/github.py
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseSettings
from app.utils.database import get_session
from app.models.user import User
from app.services.auth import create_jwt
from datetime import datetime, timezone
from typing import Any, Dict
from pydantic import BaseModel
from app.schemas.common import Meta 

class Settings(BaseSettings):
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/auth/github/callback"
    class Config:
        env_file = ".env"
settings = Settings()

router = APIRouter(prefix="/auth/github", tags=["auth"])

@router.get("/login")
async def gh_login():
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        "&scope=read:user"
    )
    return {"authorize_url": url}

@router.get("/callback")
async def gh_callback(code: str, session: AsyncSession = Depends(get_session)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
            timeout=10,
        )
    if token_resp.status_code != 200:
        raise HTTPException(400, "token exchange failed")
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(400, "no access_token")

    async with httpx.AsyncClient() as client:
        me = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
    if me.status_code != 200:
        raise HTTPException(400, "github /user failed")
    data = me.json()
    gh_id = str(data["id"])
    login = data.get("login", "")
    name = data.get("name")
    avatar = data.get("avatar_url")

    q = await session.execute(select(User).where(User.github_id == gh_id))
    user = q.scalar_one_or_none()
    if user:
        user.login = login
        user.name = name
        user.avatar_url = avatar
    else:
        user = User(github_id=gh_id, login=login, name=name, avatar_url=avatar)
        session.add(user)
        await session.flush()
    await session.commit()

    token = create_jwt(user.id)
    resp = RedirectResponse(url="/ui/reviews", status_code=303)
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", secure=False, max_age=60*60*24*7, path="/")
    return resp

class DebugMintBody(BaseModel):
    access_token: str
    user: Dict[str, Any]


class DebugMintResponse(BaseModel):
    meta: Meta
    body: DebugMintBody


@router.get("/auth/github/debug/mint", response_model=DebugMintResponse)
async def debug_mint(user_id: int, session: AsyncSession = Depends(get_session)):
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token = create_access_token(user_id=user.id)

    now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    meta = Meta(
        id=None,
        version="v1",
        actor="server",
        identity=None,
        model=None,
        analysis=None,
        progress={"status": "done", "next_step": None},
        result={"result_ref": None, "error_message": None},
        audit={
            "created_at": now,
            "updated_at": now,
        },
    )

    body = DebugMintBody(
        access_token=access_token,
        user={
            "id": user.id,
            "nickname": user.nickname,
            "created_at": now.isoformat().replace("+00:00", "Z"),
        },
    )

    return DebugMintResponse(meta=meta, body=body)