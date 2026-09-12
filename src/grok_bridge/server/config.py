"""Load settings from Application Support .env and config.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from grok_bridge.paths import (
    app_dir,
    config_path,
    dotenv_path,
    ensure_app_config,
)

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


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a mapping: {path}")
    return data


def load_settings(*, require_token: bool = True, require_advisor_webhook: bool = False) -> Settings:
    app, created_dotenv, created_config = ensure_app_config()

    # Prefer Application Support; allow process env to override after load
    load_dotenv(dotenv_path(), override=False)
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

    token = (os.environ.get("GROK_BRIDGE_TOKEN") or "").strip()
    if require_token and (not token or token == "CHANGE_ME"):
        hint = ""
        if created_dotenv or created_config:
            hint = f" Fresh example files were created in {app}."
        raise SystemExit(
            f"GROK_BRIDGE_TOKEN is not set (or still CHANGE_ME). "
            f"Edit {dotenv_path()} and set a real token.{hint}"
        )

    bots: dict[str, BotConfig] = {}
    advisor_url = (os.environ.get("GROK_BRIDGE_ADVISOR_WEBHOOK_URL") or "").strip()
    advisor_auth = (os.environ.get("GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH") or "").strip()
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
    elif require_advisor_webhook:
        raise SystemExit(
            "Advisor webhook missing or still placeholder values. Set "
            "GROK_BRIDGE_ADVISOR_WEBHOOK_URL and GROK_BRIDGE_ADVISOR_WEBHOOK_AUTH in "
            f"{dotenv_path()}."
        )

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
    return settings
