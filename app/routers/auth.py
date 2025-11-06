# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.responses import RedirectResponse
from app.utils.database import get_session
from app.models.user import User
from fastapi import Cookie

from app.services.auth import (
    github_login_url, exchange_code_for_token,
    fetch_github_me, create_jwt, decode_jwt,
)

router = APIRouter(prefix="/auth/github", tags=["auth"])

@router.get("/login")
async def gh_login(state: str = "native"):
    return {"authorize_url": github_login_url(state)}

@router.get("/callback")
async def gh_callback(code: str, state: str = "native", session: AsyncSession = Depends(get_session)):
    access_token = await exchange_code_for_token(code)
    me = await fetch_github_me(access_token)

    q = await session.execute(select(User).where(User.github_id == str(me["id"])))
    user = q.scalar_one_or_none()
    if not user:
        user = User(
            github_id=str(me["id"]),
            login=me.get("login", ""),
            name=me.get("name"),
            avatar_url=me.get("avatar_url"),
        )
        session.add(user)
        await session.flush()
    await session.commit()

    token = create_jwt(user.id)

    resp = RedirectResponse(url="/admin/users", status_code=303)
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60*60*24*7,
        path="/",
    )
    return resp

def get_current_user_id(request: Request) -> int:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = decode_jwt(auth.split(" ", 1)[1])
    return int(payload["sub"])

def get_current_user_id_from_cookie(request: Request, access_token: str | None = Cookie(default=None)) -> int:
    auth = request.headers.get("Authorization", "")
    token = None
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(401, "missing token (cookie or bearer)")

    payload = decode_jwt(token)
    return int(payload["sub"])

@router.post("/logout")
async def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("access_token", path="/")
    return resp

@router.get("/debug/mint")
def mint_debug_token(user_id: int):
    from app.services.auth import create_jwt
    return {"token": create_jwt(user_id)}
