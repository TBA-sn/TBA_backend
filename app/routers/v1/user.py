# app/routers/v1/user.py (요지)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.utils.database import get_session
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserStoreCodeUpdate
from app.routers.auth import get_current_user_id_from_cookie

router = APIRouter(prefix="/v1/users", tags=["user"])

@router.post("", response_model=UserOut)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session)):
    u = User(
        github_id=payload.github_id,
        login=payload.login,
        name=payload.name,
        avatar_url=payload.avatar_url,
        store_code=False,
    )
    session.add(u)
    await session.flush()
    await session.commit()
    return u

@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return rows

@router.get("/me", response_model=UserOut)
async def get_me(
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id_from_cookie),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user

@router.patch("/me/store-code", response_model=UserOut)
async def update_my_store_code(
    payload: UserStoreCodeUpdate,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(get_current_user_id_from_cookie),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    user.store_code = payload.store_code

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user