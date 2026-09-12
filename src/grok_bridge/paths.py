"""Filesystem locations for app config, PID, logs, and bridge token."""

from __future__ import annotations

import os
import secrets
import sys
from importlib import resources
from pathlib import Path


def app_dir() -> Path:
    """macOS Application Support appdir; ~/.grok-bridge elsewhere."""
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "grok-bridge"
    else:
        path = Path.home() / ".grok-bridge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_home() -> Path:
    """XDG-style config dir for the auto-generated bridge token."""
    path = Path.home() / ".config" / "grok-bridge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def token_path() -> Path:
    return config_home() / "token"


def ensure_bridge_token() -> tuple[str, bool]:
    """
    Ensure ~/.config/grok-bridge/token exists; load into GROK_BRIDGE_TOKEN.

    Generates a random token on first use. Returns (token, created).
    """
    import logging

    log = logging.getLogger("grok_bridge.paths")
    path = token_path()
    created = False
    if not path.is_file() or not path.read_text(encoding="utf-8").strip():
        token = secrets.token_urlsafe(32)
        path.write_text(token + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        created = True
        log.info("token created path=%s len=%s", path, len(token))
    else:
        token = path.read_text(encoding="utf-8").strip()
        log.info("token loaded path=%s len=%s", path, len(token))
    os.environ["GROK_BRIDGE_TOKEN"] = token
    return token, created


def state_dir() -> Path:
    return app_dir()


def dotenv_path() -> Path:
    return app_dir() / ".env"


def config_path() -> Path:
    return app_dir() / "config.yaml"


def pid_path() -> Path:
    return state_dir() / "grok-bridge.pid"


def server_log_path() -> Path:
    return state_dir() / "grok-bridge.log"


def cli_logs_dir() -> Path:
    path = state_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cli_history_path() -> Path:
    """Persistent readline history for grok-bridge-cli."""
    return state_dir() / "cli-history"


def _read_example(name: str) -> bytes:
    """Read packaged example under grok_bridge/examples/."""
    try:
        base = resources.files("grok_bridge") / "examples" / name
        return base.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, TypeError, AttributeError, OSError):
        pass

    # Editable / source-tree fallback
    here = Path(__file__).resolve().parent
    candidate = here / "examples" / name
    if candidate.is_file():
        return candidate.read_bytes()
    raise FileNotFoundError(f"Could not find packaged example {name!r}")


def ensure_app_config() -> tuple[Path, bool, bool]:
    """
    Ensure Application Support appdir has .env and config.yaml.

    Copies from packaged examples/dot_env.example and
    examples/config.yaml.example when missing.
    Returns (app_dir, created_dotenv, created_config).
    """
    import logging

    log = logging.getLogger("grok_bridge.paths")
    dest_dir = app_dir()
    created_dotenv = False
    created_config = False

    env_dest = dotenv_path()
    if not env_dest.exists():
        env_dest.write_bytes(_read_example("dot_env.example"))
        try:
            env_dest.chmod(0o600)
        except OSError:
            pass
        created_dotenv = True
        log.info("seeded dotenv path=%s", env_dest)
    else:
        log.info("dotenv exists path=%s", env_dest)

    cfg_dest = config_path()
    if not cfg_dest.exists():
        cfg_dest.write_bytes(_read_example("config.yaml.example"))
        created_config = True
        log.info("seeded config.yaml path=%s", cfg_dest)
    else:
        log.info("config.yaml exists path=%s", cfg_dest)

    return dest_dir, created_dotenv, created_config
