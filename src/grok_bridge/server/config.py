"""Load settings from Application Support .env and config.yaml."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv

from grok_bridge.paths import (
    app_dir,
    config_path,
    dotenv_path,
    ensure_app_config,
    ensure_bridge_token,
    token_path,
)

log = logging.getLogger("grok_bridge.config")

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


@dataclass(frozen=True)
class BotConfig:
    name: str
    webhook_url: str
    webhook_auth: str


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 18787
    auth_token: str = ""
    base_url: str = "http://127.0.0.1:18787"
    poll_interval_sec: float = 1.5
    reply_timeout_sec: float = 90.0
    max_replies: int = 500
    bots: dict[str, BotConfig] = field(default_factory=dict)
    app_dir: Path = field(default_factory=app_dir)

    def require_loopback(self) -> None:
        if self.host not in LOOPBACK_HOSTS:
            raise ValueError(
                f"Bind host must be loopback (127.0.0.1 / ::1), got {self.host!r}"
            )


def _safe_url_host(url: str) -> str:
    try:
        return urlparse(url).netloc or "(no-host)"
    except Exception:  # noqa: BLE001
        return "(bad-url)"


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        log.info("config yaml missing path=%s", path)
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    log.info("config yaml loaded path=%s keys=%s", path, sorted(data.keys()))
    return data


def load_settings(*, require_token: bool = True, require_advisor_webhook: bool = False) -> Settings:
    log.info(
        "load_settings: begin require_token=%s require_advisor_webhook=%s",
        require_token,
        require_advisor_webhook,
    )
    app, created_dotenv, created_config = ensure_app_config()
    log.info(
        "load_settings: appdir=%s created_dotenv=%s created_config=%s",
        app,
        created_dotenv,
        created_config,
    )

    token, created_token = ensure_bridge_token()
    log.info(
        "load_settings: token path=%s created=%s present=%s len=%s",
        token_path(),
        created_token,
        bool(token),
        len(token) if token else 0,
    )

    env_file = dotenv_path()
    log.info("load_settings: loading dotenv path=%s exists=%s", env_file, env_file.is_file())
    load_dotenv(env_file, override=False)
    load_dotenv(override=False)

    raw = _load_yaml(config_path())

    server = raw.get("server") or {}
    cli = raw.get("cli") or {}
    queue = raw.get("queue") or {}

    host = str(server.get("host") or os.environ.get("GROK_BRIDGE_HOST") or "127.0.0.1")
    port = int(server.get("port") or os.environ.get("GROK_BRIDGE_PORT") or 18787)
    base_url = str(cli.get("base_url") or f"http://{host}:{port}")
    poll_interval_sec = float(cli.get("poll_interval_sec") or 1.5)
    reply_timeout_sec = float(cli.get("reply_timeout_sec") or 90)
    max_replies = int(queue.get("max_replies") or 500)
    log.info(
        "load_settings: resolved host=%s port=%s base_url=%s "
        "poll=%.2fs timeout=%.1fs max_replies=%s",
        host,
        port,
        base_url,
        poll_interval_sec,
        reply_timeout_sec,
        max_replies,
    )

    if require_token and not token:
        log.error("load_settings: token missing path=%s", token_path())
        raise SystemExit(
            f"GROK_BRIDGE_TOKEN could not be loaded from {token_path()}."
        )

    bots: dict[str, BotConfig] = {}
    advisor_url = (os.environ.get("GROK_BRIDGE_ADVISOR_WEBHOOK_URL") or "").strip()
    advisor_auth = (os.environ.get("GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH") or "").strip()
    log.info(
        "load_settings: advisor webhook url_set=%s auth_set=%s host=%s placeholder=%s",
        bool(advisor_url),
        bool(advisor_auth),
        _safe_url_host(advisor_url) if advisor_url else "(none)",
        ("example.invalid" in advisor_url) or advisor_auth == "CHANGE_ME_SENDER_KEY",
    )
    if (
        advisor_url
        and advisor_auth
        and "example.invalid" not in advisor_url
        and advisor_auth != "CHANGE_ME_SENDER_KEY"
    ):
        bots["advisor"] = BotConfig(
            name="advisor",
            webhook_url=advisor_url,
            webhook_auth=advisor_auth,
        )
        log.info("load_settings: advisor bot configured")
    elif require_advisor_webhook:
        log.error("load_settings: advisor webhook required but missing/placeholder")
        raise SystemExit(
            "Advisor webhook missing or still placeholder values. Set "
            "GROK_BRIDGE_ADVISOR_WEBHOOK_URL and GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH in "
            f"{dotenv_path()}."
        )
    else:
        log.warning("load_settings: advisor webhook not configured (ok for CLI-only)")

    settings = Settings(
        host=host,
        port=port,
        auth_token=token,
        base_url=base_url.rstrip("/"),
        poll_interval_sec=poll_interval_sec,
        reply_timeout_sec=reply_timeout_sec,
        max_replies=max_replies,
        bots=bots,
        app_dir=app,
    )
    settings.require_loopback()
    log.info(
        "load_settings: done bots=%s app_dir=%s",
        ",".join(sorted(settings.bots)) or "(none)",
        settings.app_dir,
    )
    return settings
