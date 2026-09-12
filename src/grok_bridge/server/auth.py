"""Bearer token auth for bridge HTTP routes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from grok_bridge.server.config import Settings, load_settings

log = logging.getLogger("grok_bridge.auth")

_bearer = HTTPBearer(auto_error=False)
_settings_cache: Settings | None = None


def get_settings() -> Settings:
    global _settings_cache
    if _settings_cache is None:
        log.info("auth settings cache miss — loading")
        _settings_cache = load_settings(
            require_token=True, require_advisor_webhook=False
        )
    return _settings_cache


def require_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if credentials is None:
        log.warning("auth rejected: missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "error": "unauthorized"},
        )
    if credentials.scheme.lower() != "bearer":
        log.warning("auth rejected: scheme=%s (expected bearer)", credentials.scheme)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "error": "unauthorized"},
        )
    if credentials.credentials != settings.auth_token:
        log.warning(
            "auth rejected: bearer token mismatch presented_len=%s expected_len=%s",
            len(credentials.credentials or ""),
            len(settings.auth_token or ""),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "error": "unauthorized"},
        )
    log.debug("auth ok")
