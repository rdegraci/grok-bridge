"""FastAPI application: health, send, replies."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from grok_bridge.server.auth import get_settings, require_bearer
from grok_bridge.server.config import Settings, load_settings
from grok_bridge.server.models import (
    HealthResponse,
    RepliesListResponse,
    ReplyIn,
    ReplyOut,
    ReplyStoredResponse,
    SendRequest,
    SendResponse,
)
from grok_bridge.server.queue import ReplyQueue
from grok_bridge.server.webhook import post_webhook

log = logging.getLogger("grok_bridge.server")


def _truncate(text: str, limit: int = 120) -> str:
    text = (text or "").replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def create_app(settings: Settings | None = None) -> FastAPI:
    log.info("create_app: begin")
    if settings is None:
        log.info("create_app: loading settings")
        settings = load_settings(
            require_token=True,
            require_advisor_webhook=True,
        )
    log.info(
        "create_app: building app host=%s port=%s bots=%s max_replies=%s",
        settings.host,
        settings.port,
        ",".join(sorted(settings.bots)) or "(none)",
        settings.max_replies,
    )
    queue = ReplyQueue(max_replies=settings.max_replies)
    app = FastAPI(title="grok-bridge", version="0.1.0")
    app.state.settings = settings
    app.state.queue = queue

    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.monotonic()
        log.info(
            "http request begin method=%s path=%s client=%s",
            request.method,
            request.url.path,
            request.client.host if request.client else "?",
        )
        try:
            response = await call_next(request)
        except Exception:
            log.exception(
                "http request crashed method=%s path=%s",
                request.method,
                request.url.path,
            )
            raise
        elapsed = time.monotonic() - started
        log.info(
            "http request end method=%s path=%s status=%s elapsed=%.3fs",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    @app.on_event("startup")
    def _on_startup() -> None:
        log.info(
            "READY host=%s port=%s routes=/health,/send,/replies bots=%s",
            settings.host,
            settings.port,
            ",".join(sorted(settings.bots)) or "(none)",
        )

    @app.on_event("shutdown")
    def _on_shutdown() -> None:
        log.info("shutdown: server stopping")

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        log.warning(
            "validation failed method=%s path=%s errors=%s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "ok": False,
                "error": "validation_error",
                "detail": exc.errors(),
            },
        )

    def _settings() -> Settings:
        return app.state.settings

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        log.info("health ok")
        return HealthResponse()

    @app.post(
        "/send",
        response_model=SendResponse,
        dependencies=[Depends(require_bearer)],
    )
    def send(body: SendRequest) -> SendResponse:
        cfg = _settings()
        log.info(
            "send begin bot=%s client_id=%s message_id=%s text=%s",
            body.bot,
            body.client_id,
            body.message_id,
            _truncate(body.text),
        )
        bot = cfg.bots.get(body.bot)
        if bot is None:
            log.warning(
                "send unknown_bot bot=%s known=%s",
                body.bot,
                sorted(cfg.bots.keys()),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"ok": False, "error": "unknown_bot", "detail": body.bot},
            )
        sent_at = body.sent_at or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        payload = {
            "v": body.v,
            "bot": body.bot,
            "client_id": body.client_id,
            "message_id": body.message_id,
            "text": body.text,
            "sent_at": sent_at,
        }
        try:
            resp = post_webhook(bot, payload)
        except Exception as exc:  # noqa: BLE001
            log.exception("send webhook transport failed bot=%s", body.bot)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "ok": False,
                    "error": "webhook_rejected",
                    "detail": str(exc)[:200],
                },
            ) from exc

        if resp.status_code >= 400:
            log.warning(
                "send webhook rejected bot=%s status=%s message_id=%s preview=%s",
                body.bot,
                resp.status_code,
                body.message_id,
                (resp.text or "")[:300],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "ok": False,
                    "error": "webhook_rejected",
                    "webhook_status": resp.status_code,
                    "detail": "upstream rejected webhook",
                },
            )

        log.info(
            "send ok bot=%s message_id=%s webhook_status=%s",
            body.bot,
            body.message_id,
            resp.status_code,
        )
        return SendResponse(
            ok=True,
            bot=body.bot,
            message_id=body.message_id,
            webhook_status=resp.status_code,
        )

    @app.post(
        "/replies",
        response_model=ReplyStoredResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_bearer)],
    )
    def post_reply(body: ReplyIn) -> ReplyStoredResponse:
        log.info(
            "reply begin bot=%s message_id=%s in_reply_to=%s text=%s",
            body.bot,
            body.message_id,
            body.in_reply_to,
            _truncate(body.text),
        )
        if not body.in_reply_to:
            log.warning("reply missing in_reply_to message_id=%s", body.message_id)
        q: ReplyQueue = app.state.queue
        seq = q.append(
            bot=body.bot,
            message_id=body.message_id,
            text=body.text,
            in_reply_to=body.in_reply_to,
            sent_at=body.sent_at,
            v=body.v,
        )
        log.info(
            "reply stored seq=%s bot=%s in_reply_to=%s message_id=%s",
            seq,
            body.bot,
            body.in_reply_to,
            body.message_id,
        )
        return ReplyStoredResponse(ok=True, seq=seq)

    @app.get(
        "/replies",
        response_model=RepliesListResponse,
        dependencies=[Depends(require_bearer)],
    )
    def get_replies(
        bot: Annotated[str, Query(min_length=1)],
        since: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> RepliesListResponse:
        log.info("replies list begin bot=%s since=%s limit=%s", bot, since, limit)
        q: ReplyQueue = app.state.queue
        items, next_since = q.list_since(bot, since, limit=limit)
        replies = [
            ReplyOut(
                seq=r.seq,
                v=r.v,
                bot=r.bot,
                in_reply_to=r.in_reply_to,
                message_id=r.message_id,
                text=r.text,
                sent_at=r.sent_at,
            )
            for r in items
        ]
        log.info(
            "replies list done bot=%s count=%s next_since=%s",
            bot,
            len(replies),
            next_since,
        )
        return RepliesListResponse(
            ok=True, bot=bot, replies=replies, next_since=next_since
        )

    log.info("create_app: routes registered, returning app")
    return app
