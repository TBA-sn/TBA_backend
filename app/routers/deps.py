# app/routers/deps.py
import os
from fastapi import Header, HTTPException, status

async def require_service_token(
    x_service_token: str | None = Header(None, alias="X-Service-Token"),
) -> bool:
    expected = os.getenv("SERVICE_TOKEN")
    if not expected:
        return True
    if x_service_token == expected:
        return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid service token",
    )
