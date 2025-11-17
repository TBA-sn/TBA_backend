# app/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from app.routers.v1.review import router as review_router
from app.routers.v1.user import router as user_router
from app.routers.ui import router as ui_router
from app.routers.v1.action_log import router as action_log_router
from app.routers.llm import router as llm_router
from app.routers.ws_debug import router as ws_debug_router

auth_router = None
try:
    from app.routers.auth import router as _auth_router
    auth_router = _auth_router
except Exception:
    try:
        from app.auth.github import router as _gh_router
        auth_router = _gh_router
    except Exception:
        auth_router = None

app = FastAPI(
    title="Code Review API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(llm_router)
app.include_router(review_router)
app.include_router(action_log_router)
app.include_router(ws_debug_router)
app.include_router(user_router)
if auth_router:
    app.include_router(auth_router)
    logging.getLogger("uvicorn.error").info("Auth router enabled.")
else:
    logging.getLogger("uvicorn.error").warning("Auth router not found. /auth/* disabled.")
app.include_router(ui_router)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/reviews", status_code=303)

@app.get("/health", tags=["meta"])
def health():
    return {"ok": True, "service": "code-review-api"}

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    wants_html = "text/html" in (request.headers.get("accept") or "")

    if exc.status_code == 401 and wants_html:
        return RedirectResponse(url="/auth/github/login", status_code=303)

    if exc.status_code == 403 and wants_html:
        return HTMLResponse("<h3>접근 권한이 없습니다.</h3>", status_code=403)

    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
