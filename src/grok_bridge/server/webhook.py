"""Outbound POST to Grok Bot webhook routines."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from grok_bridge.server.config import BotConfig

log = logging.getLogger("grok_bridge.webhook")


def post_webhook(bot: BotConfig, payload: dict[str, Any], *, timeout: float = 30.0) -> httpx.Response:
    """POST JSON body with Authorization: Bearer (confirmed 2026-09-11)."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {bot.webhook_auth}",
        "User-Agent": "grok-bridge/0.1",
    }
    log.info(
        "webhook POST bot=%s url_host=%s message_id=%s",
        bot.name,
        httpx.URL(bot.webhook_url).host,
        payload.get("message_id"),
    )
    with httpx.Client(timeout=timeout) as client:
        return client.post(bot.webhook_url, json=payload, headers=headers)
