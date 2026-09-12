"""HTTP client for grok-bridge-cli → localhost server."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


class BridgeClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(f"{self.base_url}/health")
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
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(
                f"{self.base_url}/send",
                headers=self._headers,
                json=payload,
            )
            return r.status_code, _json_body(r)

    def replies(self, *, bot: str, since: int) -> tuple[int, dict[str, Any]]:
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(
                f"{self.base_url}/replies",
                headers=self._headers,
                params={"bot": bot, "since": since},
            )
            return r.status_code, _json_body(r)


def _json_body(r: httpx.Response) -> dict[str, Any]:
    try:
        data = r.json()
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "bad_response", "detail": r.text[:200]}
    if isinstance(data, dict) and isinstance(data.get("detail"), dict):
        return data["detail"]
    if isinstance(data, dict):
        return data
    return {"ok": False, "error": "bad_response", "detail": str(data)[:200]}
