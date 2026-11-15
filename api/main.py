"""Ataraxia dashboard API.

Run from the repository root:

    uvicorn api.main:app --host 127.0.0.1 --port 8000

See api/README.md for configuration and the endpoint list.
"""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import schemas
from .auth import (
    SESSION_COOKIE,
    STATE_COOKIE,
    GuildAccess,
    SessionManager,
    csrf_protect,
    current_session,
    guild_access,
    new_token,
)
from .config import Settings, load_settings
from .db import LOG_COLUMNS, Database
from .discord_client import DiscordClient, DiscordError, is_admin

logger = logging.getLogger("ataraxia.api")
STATIC_DIR = Path(__file__).parent / "static"
TEXT_CHANNELS = ("text", "announcement")


def create_app(
    settings: Optional[Settings] = None,
    discord_transport: Optional[httpx.AsyncBaseTransport] = None,
) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.db = await Database.connect(settings.database_url, settings.db_pool_max)
        app.state.discord = DiscordClient(settings, transport=discord_transport)
        app.state.sessions = SessionManager(app.state.db, app.state.discord)
        if not settings.oauth_ready:
            logger.warning("DISCORD_CLIENT_SECRET is not set: logging in will not work")
        try:
            yield
        finally:
            await app.state.discord.close()
            await app.state.db.close()

    app = FastAPI(
        title="Ataraxia Dashboard API",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        problems = []
        for error in exc.errors():
            where = ".".join(str(p) for p in error["loc"] if p != "body")
            problems.append(f"{where}: {error['msg']}" if where else error["msg"])
        return JSONResponse({"detail": "; ".join(problems)}, status_code=422)

    @app.exception_handler(DiscordError)
    async def discord_error(request: Request, exc: DiscordError):
        logger.warning("Discord request failed: %s", exc)
        return JSONResponse(
            {"detail": "Discord is not reachable right now. Try again in a moment."}, status_code=503
        )

    def set_cookie(response, name: str, value: str, max_age: int):
        response.set_cookie(
            name, value, max_age=max_age, path=settings.cookie_path, httponly=True,
            secure=settings.cookie_secure, samesite="lax",
        )

    # ------------------------------------------------------------- general

    @app.get("/health")
    async def health(request: Request):
        try:
            ok = await request.app.state.db.ping()
        except Exception:
            ok = False
        return JSONResponse(
            {"status": "ok" if ok else "degraded", "database": ok, "login_configured": settings.oauth_ready},
            status_code=200 if ok else 503,
        )

    # ---------------------------------------------------------------- auth

    @app.get("/auth/login")
    async def login():
        if not settings.oauth_ready:
            raise HTTPException(503, "Login is not configured (DISCORD_CLIENT_SECRET is missing)")
        state = new_token()
        query = urlencode({
            "client_id": settings.client_id,
            "redirect_uri": settings.redirect_uri,
            "response_type": "code",
            "scope": "identify guilds",
            "state": state,
            "prompt": "none",
        })
        response = RedirectResponse(f"{settings.discord_authorize_url}?{query}", status_code=302)
        set_cookie(response, STATE_COOKIE, state, 600)
        return response

    @app.get("/auth/callback")
    async def callback(request: Request, code: Optional[str] = None, state: Optional[str] = None,
                       error: Optional[str] = None):
        home = f"{settings.base_url}/"
        expected = request.cookies.get(STATE_COOKIE)
        if error or not code:
            response = RedirectResponse(f"{home}?login=cancelled", status_code=302)
        elif not state or not expected or not hmac.compare_digest(state, expected):
            response = RedirectResponse(f"{home}?login=failed", status_code=302)
        else:
            try:
                tokens = await request.app.state.discord.exchange_code(code)
                user = await request.app.state.discord.get_user(tokens["access_token"])
            except DiscordError as exc:
                logger.warning("OAuth code exchange failed: %s", exc)
                response = RedirectResponse(f"{home}?login=failed", status_code=302)
            else:
                token = await request.app.state.sessions.create(user, tokens, settings.session_ttl_days)
                response = RedirectResponse(home, status_code=302)
                set_cookie(response, SESSION_COOKIE, token, settings.session_ttl_days * 86400)
        response.delete_cookie(STATE_COOKIE, path=settings.cookie_path)
        return response

    @app.post("/auth/logout", dependencies=[Depends(csrf_protect)])
    async def logout(request: Request, session: dict = Depends(current_session)):
        await request.app.state.sessions.destroy(session)
        response = JSONResponse({"ok": True})
        response.delete_cookie(SESSION_COOKIE, path=settings.cookie_path)
        return response

    # ----------------------------------------------------------------- user

    @app.get("/api/me")
    async def me(session: dict = Depends(current_session)):
        return {
            "id": str(session["user_id"]),
            "username": session["username"],
            "avatar": session["avatar"],
        }

    @app.get("/api/guilds")
    async def guilds(request: Request, session: dict = Depends(current_session)):
        """Servers the user administers. ``bot_present`` tells whether they can be configured."""
        all_guilds = await request.app.state.sessions.user_guilds(session)
        admin = [g for g in all_guilds if is_admin(g)]
        present = await request.app.state.db.tracked_guild_ids([int(g["id"]) for g in admin])
        result = [
            {"id": str(g["id"]), "name": g["name"], "icon": g.get("icon"),
             "bot_present": int(g["id"]) in present}
            for g in admin
        ]
        result.sort(key=lambda g: (not g["bot_present"], g["name"].lower()))
        return {
            "guilds": result,
            "invite_url": "https://discord.com/oauth2/authorize?"
            + urlencode({"client_id": settings.client_id, "scope": "bot applications.commands",
                         "permissions": "8"}),
        }

    # ---------------------------------------------------------------- guild

    @app.get("/api/guilds/{guild_id}")
    async def guild(access: GuildAccess = Depends(guild_access)):
        """Name, roles and channels of the server, for building pickers."""
        return access.meta

    # ------------------------------------------------------------------- XP

    @app.get("/api/guilds/{guild_id}/xp")
    async def get_xp(request: Request, access: GuildAccess = Depends(guild_access)):
        return await request.app.state.db.get_xp_settings(access.guild_id)

    @app.put("/api/guilds/{guild_id}/xp")
    async def put_xp(body: schemas.XPSettings, request: Request,
                     access: GuildAccess = Depends(guild_access)):
        await request.app.state.db.set_xp_settings(access.guild_id, body.model_dump(), access.user_id)
        return await request.app.state.db.get_xp_settings(access.guild_id)

    @app.get("/api/guilds/{guild_id}/voice-requirements")
    async def get_voice(request: Request, access: GuildAccess = Depends(guild_access)):
        return await request.app.state.db.get_voice_requirements(access.guild_id)

    @app.put("/api/guilds/{guild_id}/voice-requirements")
    async def put_voice(body: schemas.VoiceRequirements, request: Request,
                        access: GuildAccess = Depends(guild_access)):
        await request.app.state.db.set_voice_requirements(access.guild_id, body.model_dump(), access.user_id)
        return await request.app.state.db.get_voice_requirements(access.guild_id)

    # ---------------------------------------------------------- multipliers

    async def multipliers_response(request: Request, guild_id: int) -> dict[str, Any]:
        data = await request.app.state.db.get_multipliers(guild_id)
        return {kind: [{"id": str(m["id"]), "multiplier": m["multiplier"]} for m in items]
                for kind, items in data.items()}

    @app.get("/api/guilds/{guild_id}/multipliers")
    async def get_multipliers(request: Request, access: GuildAccess = Depends(guild_access)):
        return await multipliers_response(request, access.guild_id)

    @app.put("/api/guilds/{guild_id}/multipliers/{kind}/{target_id}")
    async def put_multiplier(kind: str, target_id: str, body: schemas.Multiplier, request: Request,
                             access: GuildAccess = Depends(guild_access)):
        tid = _multiplier_target(access, kind, target_id, must_exist=True)
        await request.app.state.db.set_multiplier(access.guild_id, kind, tid, body.multiplier, access.user_id)
        return await multipliers_response(request, access.guild_id)

    @app.delete("/api/guilds/{guild_id}/multipliers/{kind}/{target_id}")
    async def delete_multiplier(kind: str, target_id: str, request: Request,
                                access: GuildAccess = Depends(guild_access)):
        # Deleted channels and roles must stay removable, so no existence check here.
        tid = _multiplier_target(access, kind, target_id, must_exist=False)
        await request.app.state.db.set_multiplier(access.guild_id, kind, tid, None, access.user_id)
        return await multipliers_response(request, access.guild_id)

    # ----------------------------------------------------------------- logs

    async def logs_response(request: Request, guild_id: int) -> dict[str, Any]:
        data = await request.app.state.db.get_log_channels(guild_id)
        level = data["level"]
        result = {name: (str(value) if value else None) for name, value in data.items()}
        result["level_disabled"] = level == 0
        return result

    @app.get("/api/guilds/{guild_id}/logs")
    async def get_logs(request: Request, access: GuildAccess = Depends(guild_access)):
        return await logs_response(request, access.guild_id)

    @app.put("/api/guilds/{guild_id}/logs")
    async def put_logs(body: schemas.LogChannels, request: Request,
                       access: GuildAccess = Depends(guild_access)):
        sent = body.model_dump(exclude_unset=True)
        level_disabled = sent.pop("level_disabled", None)
        values: dict[str, Optional[int]] = {}
        for name, channel_id in sent.items():
            if name not in LOG_COLUMNS:
                continue
            values[name] = access.require_channel(channel_id, TEXT_CHANNELS) if channel_id else None
        if level_disabled:
            if values.get("level"):
                raise HTTPException(422, "level and level_disabled cannot both be set")
            values["level"] = 0  # the bot treats 0 as "announcements off"
        elif level_disabled is False and "level" not in values:
            current = await request.app.state.db.get_log_channels(access.guild_id)
            if current["level"] == 0:
                values["level"] = None
        await request.app.state.db.set_log_channels(access.guild_id, values, access.user_id)
        return await logs_response(request, access.guild_id)

    # ---------------------------------------------------------- level roles

    async def level_roles_response(request: Request, guild_id: int):
        rows = await request.app.state.db.get_level_roles(guild_id)
        return [{"level": r["level"], "role_id": str(r["role_id"])} for r in rows]

    @app.get("/api/guilds/{guild_id}/level-roles")
    async def get_level_roles(request: Request, access: GuildAccess = Depends(guild_access)):
        return await level_roles_response(request, access.guild_id)

    @app.put("/api/guilds/{guild_id}/level-roles/{level}")
    async def put_level_role(level: int, body: schemas.LevelRole, request: Request,
                             access: GuildAccess = Depends(guild_access)):
        _check_level(level)
        role_id = access.require_role(body.role_id, assignable=True)
        await request.app.state.db.set_level_role(access.guild_id, level, role_id, access.user_id)
        return await level_roles_response(request, access.guild_id)

    @app.delete("/api/guilds/{guild_id}/level-roles/{level}")
    async def delete_level_role(level: int, request: Request,
                                access: GuildAccess = Depends(guild_access)):
        _check_level(level)
        await request.app.state.db.set_level_role(access.guild_id, level, None, access.user_id)
        return await level_roles_response(request, access.guild_id)

    # ----------------------------------------------------------- auto roles

    async def auto_roles_response(request: Request, guild_id: int):
        data = await request.app.state.db.get_auto_roles(guild_id)
        return {
            "enabled": data["enabled"],
            "user_role_ids": [str(r) for r in data["user_role_ids"]],
            "bot_role_ids": [str(r) for r in data["bot_role_ids"]],
        }

    @app.get("/api/guilds/{guild_id}/auto-roles")
    async def get_auto_roles(request: Request, access: GuildAccess = Depends(guild_access)):
        return await auto_roles_response(request, access.guild_id)

    @app.put("/api/guilds/{guild_id}/auto-roles")
    async def put_auto_roles(body: schemas.AutoRoles, request: Request,
                             access: GuildAccess = Depends(guild_access)):
        user_roles = list(dict.fromkeys(access.require_role(r, assignable=True) for r in body.user_role_ids))
        bot_roles = list(dict.fromkeys(access.require_role(r, assignable=True) for r in body.bot_role_ids))
        await request.app.state.db.set_auto_roles(
            access.guild_id, body.enabled, user_roles, bot_roles, access.user_id
        )
        return await auto_roles_response(request, access.guild_id)

    # ---------------------------------------------------------- leaderboard

    @app.get("/api/guilds/{guild_id}/leaderboard")
    async def leaderboard(request: Request, access: GuildAccess = Depends(guild_access),
                          limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
        data = await request.app.state.db.get_leaderboard(access.guild_id, limit, offset)
        for entry in data["entries"]:
            entry["user_id"] = str(entry["user_id"])
        return data

    # -------------------------------------------------------------- web UI

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def _multiplier_target(access: GuildAccess, kind: str, target_id: str, must_exist: bool) -> int:
    if kind not in ("channels", "roles"):
        raise HTTPException(404, "Unknown multiplier type")
    if not target_id.isdigit() or not 15 <= len(target_id) <= 20:
        raise HTTPException(422, "Invalid ID")
    tid = int(target_id)
    if must_exist:
        if kind == "channels":
            access.require_channel(tid)
        else:
            access.require_role(tid)
    return tid


def _check_level(level: int):
    if not 1 <= level <= 1000:
        raise HTTPException(422, "level must be between 1 and 1000")


def __getattr__(name: str):
    # ``uvicorn api.main:app`` - built lazily so importing this module needs no environment.
    if name == "app":
        global app
        app = create_app()
        return app
    raise AttributeError(name)
