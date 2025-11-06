import os, time, jwt, httpx
from typing import Any, Dict

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT = os.getenv("GITHUB_REDIRECT", "http://localhost:3000/auth/github/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")

def github_login_url(state: str = "native") -> str:
    base = "https://github.com/login/oauth/authorize"
    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT,
        "scope": "read:user user:email",
        "state": state,
        "allow_signup": "true",
    }
    from urllib.parse import urlencode
    return f"{base}?{urlencode(params)}"

async def exchange_code_for_token(code: str) -> str:
    if not GITHUB_CLIENT_SECRET:
        raise RuntimeError("GITHUB_CLIENT_SECRET missing")
    url = "https://github.com/login/oauth/access_token"
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT,
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers={"Accept": "application/json"}, json=payload)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(data.get("error_description") or "github oauth error")
        return data["access_token"]

async def fetch_github_me(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.github.com/user",
                             headers={"Authorization": f"Bearer {access_token}",
                                      "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        return r.json()

def create_jwt(user_id: int) -> str:
    payload = {"sub": str(user_id), "iat": int(time.time())}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_jwt(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
