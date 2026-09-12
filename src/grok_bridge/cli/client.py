"""HTTP client for grok-bridge-cli → localhost server."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

log = logging.getLogger("grok_bridge.cli.client")


class BridgeClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout
        log.info("client init base_url=%s timeout=%.1fs", self.base_url, timeout)

    def health(self) -> dict[str, Any]:
        url = f"{self.base_url}/health"
        log.info("client GET %s", url)
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(url)
            log.info("client health status=%s", r.status_code)
            r.raise_for_status()
            return r.json()

    def send(self, *, bot: str, message_id: str, text: str) -> tuple[int, dict[str, Any]]:
        payload = {
            "v": 1,
            "bot": bot,
            "client_id": "mini-cli",
            "message_id": message_id,
            "text": text,
            "sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        url = f"{self.base_url}/send"
        log.info(
            "client POST %s bot=%s message_id=%s text_len=%s",
            url,
            bot,
            message_id,
            len(text),
        )
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(url, headers=self._headers, json=payload)
            body = _json_body(r)
            log.info(
                "client send status=%s ok=%s error=%s",
                r.status_code,
                body.get("ok"),
                body.get("error"),
            )
            return r.status_code, body

    def replies(self, *, bot: str, since: int) -> tuple[int, dict[str, Any]]:
        url = f"{self.base_url}/replies"
        log.info("client GET %s bot=%s since=%s", url, bot, since)
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(
                url,
                headers=self._headers,
                params={"bot": bot, "since": since},
            )
            body = _json_body(r)
            count = len(body.get("replies") or []) if isinstance(body, dict) else -1
            log.info(
                "client replies status=%s count=%s next_since=%s",
                r.status_code,
                count,
                body.get("next_since") if isinstance(body, dict) else None,
            )
            return r.status_code, body


def _json_body(r: httpx.Response) -> dict[str, Any]:
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        log.warning("client non-json response status=%s preview=%s", r.status_code, r.text[:200])
        return {"ok": False, "error": "bad_response", "detail": r.text[:200]}
    if isinstance(data, dict) and isinstance(data.get("detail"), dict):
        return data["detail"]
    if isinstance(data, dict):
        return data
    return {"ok": False, "error": "bad_response", "detail": str(data)[:200]}
