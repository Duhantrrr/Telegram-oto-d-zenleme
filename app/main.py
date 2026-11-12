"""FastAPI uygulaması: web paneli + JSON API."""
from __future__ import annotations

import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .config import load_settings
from .rules import RuleError, RuleStore
from .telegram_manager import ManagerError, TelegramManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = load_settings()
rules = RuleStore(settings.rules_file, seed_json=os.getenv("RULES_JSON", ""))
manager = TelegramManager(settings, rules)
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await manager.start()
    yield
    await manager.stop()


app = FastAPI(title="Telegram Panel", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="tgpanel",
    max_age=60 * 60 * 24 * 7,
    same_site="strict",
    https_only=settings.cookie_secure,
)


# ---- hata yakalama -------------------------------------------------
@app.exception_handler(ManagerError)
async def _manager_error(_: Request, exc: ManagerError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


@app.exception_handler(RuleError)
async def _rule_error(_: Request, exc: RuleError):
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


# ---- panel girişi --------------------------------------------------
_failed: dict[str, list[float]] = {}
MAX_FAILS, WINDOW = 5, 300


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def require_auth(request: Request) -> None:
    if not request.session.get("ok"):
        raise HTTPException(401, "Panel girişi gerekli")


class PanelLogin(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@app.post("/api/panel/login")
async def panel_login(body: PanelLogin, request: Request):
    ip = _client_ip(request)
    now = time.time()
    attempts = [t for t in _failed.get(ip, []) if now - t < WINDOW]
    if len(attempts) >= MAX_FAILS:
        raise HTTPException(429, "Çok fazla hatalı deneme. 5 dakika sonra tekrar deneyin")
    if not hmac.compare_digest(body.password.encode(), settings.panel_password.encode()):
        attempts.append(now)
        _failed[ip] = attempts
        raise HTTPException(401, "Panel şifresi hatalı")
    _failed.pop(ip, None)
    request.session["ok"] = True
    return {"ok": True}


@app.post("/api/panel/logout")
async def panel_logout(request: Request):
    request.session.clear()
    return {"ok": True}


# ---- durum / log ---------------------------------------------------
@app.get("/api/status", dependencies=[Depends(require_auth)])
async def status():
    return manager.status()


@app.get("/api/logs", dependencies=[Depends(require_auth)])
async def logs():
    return list(manager.logs)


@app.get("/api/session", dependencies=[Depends(require_auth)])
async def session_string():
    value = manager.session_string()
    if not value:
        raise HTTPException(409, "Önce Telegram hesabına giriş yapın")
    return {"session": value}


# ---- Telegram girişi -----------------------------------------------
class PhoneIn(BaseModel):
    phone: str = Field(min_length=5, max_length=32)


class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)


@app.post("/api/tg/send-code", dependencies=[Depends(require_auth)])
async def tg_send_code(body: PhoneIn):
    await manager.send_code(body.phone)
    return manager.status()


@app.post("/api/tg/verify-code", dependencies=[Depends(require_auth)])
async def tg_verify_code(body: CodeIn):
    await manager.verify_code(body.code)
    return manager.status()


@app.post("/api/tg/verify-password", dependencies=[Depends(require_auth)])
async def tg_verify_password(body: PasswordIn):
    await manager.verify_password(body.password)
    return manager.status()


@app.post("/api/tg/cancel", dependencies=[Depends(require_auth)])
async def tg_cancel():
    await manager.cancel_login()
    return manager.status()


@app.post("/api/tg/logout", dependencies=[Depends(require_auth)])
async def tg_logout():
    await manager.logout()
    return manager.status()


# ---- kurallar ------------------------------------------------------
class RuleIn(BaseModel):
    trigger: str = Field(min_length=1, max_length=4096)
    replacement: str = Field(min_length=1, max_length=4096)
    enabled: bool = True


@app.get("/api/rules", dependencies=[Depends(require_auth)])
async def list_rules():
    return [r.__dict__ for r in rules.list()]


@app.post("/api/rules", status_code=201, dependencies=[Depends(require_auth)])
async def add_rule(body: RuleIn):
    return rules.add(body.trigger, body.replacement, body.enabled).__dict__


@app.put("/api/rules/{rule_id}", dependencies=[Depends(require_auth)])
async def update_rule(rule_id: str, body: RuleIn):
    return rules.update(rule_id, body.trigger, body.replacement, body.enabled).__dict__


@app.delete("/api/rules/{rule_id}", dependencies=[Depends(require_auth)])
async def delete_rule(rule_id: str):
    rules.delete(rule_id)
    return {"ok": True}


@app.get("/api/rules/export", dependencies=[Depends(require_auth)])
async def export_rules():
    return {"json": rules.export_json()}


# ---- sayfa ---------------------------------------------------------
@app.get("/health")
async def health():
    return {"ok": True, "telegram": manager.state}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})
