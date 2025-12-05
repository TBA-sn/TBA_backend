# app/routers/v1/__init__.py

from app.routers.v1.review import router as review_router
from app.routers.v1.user import router as user_router

__all__ = [
    "review_router",
    "user_router",
]
