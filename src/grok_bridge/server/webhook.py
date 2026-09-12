"""Outbound POST to Grok Bot webhook routines."""

from __future__ import annotations

import logging
import time
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
    host = httpx.URL(bot.webhook_url).host
    text = payload.get("text") or ""
    log.info(
        "webhook POST begin bot=%s host=%s message_id=%s text_len=%s timeout=%.1fs",
        bot.name,
        host,
        payload.get("message_id"),
        len(str(text)),
        timeout,
    )
    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(bot.webhook_url, json=payload, headers=headers)
    except Exception:
        elapsed = time.monotonic() - started
        log.exception(
            "webhook POST transport error bot=%s host=%s elapsed=%.3fs",
            bot.name,
            host,
            elapsed,
        )
        raise
    elapsed = time.monotonic() - started
    log.info(
        "webhook POST done bot=%s host=%s status=%s elapsed=%.3fs body_len=%s",
        bot.name,
        host,
        resp.status_code,
        elapsed,
        len(resp.content or b""),
    )
    if resp.status_code >= 400:
        log.warning(
            "webhook POST non-success status=%s preview=%s",
            resp.status_code,
            (resp.text or "")[:300],
        )
    return resp
