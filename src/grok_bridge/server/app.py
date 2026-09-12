"""FastAPI application: health, send, replies."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status

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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings(
        require_token=True,
        require_advisor_webhook=True,
    )
    queue = ReplyQueue(max_replies=settings.max_replies)
    app = FastAPI(title="grok-bridge", version="0.1.0")
    app.state.settings = settings
    app.state.queue = queue

    def _settings() -> Settings:
        return app.state.settings

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post(
        "/send",
        response_model=SendResponse,
        dependencies=[Depends(require_bearer)],
    )
    def send(body: SendRequest) -> SendResponse:
        cfg = _settings()
        bot = cfg.bots.get(body.bot)
        if bot is None:
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
            log.exception("webhook transport failed bot=%s", body.bot)
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
                "webhook rejected bot=%s status=%s message_id=%s",
                body.bot,
                resp.status_code,
                body.message_id,
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
        return RepliesListResponse(
            ok=True, bot=bot, replies=replies, next_since=next_since
        )

    return app
