"""Filesystem locations for app config, PID, and logs."""

from __future__ import annotations

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


def _read_example(name: str) -> bytes:
    """Read packaged example, then repo-root example."""
    try:
        base = resources.files("grok_bridge") / "examples" / name
        return base.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, TypeError, AttributeError, OSError):
        pass

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / name
        if candidate.is_file():
            return candidate.read_bytes()
    raise FileNotFoundError(f"Could not find example file {name!r}")


def ensure_app_config() -> tuple[Path, bool, bool]:
    """
    Ensure Application Support appdir has .env and config.yaml.

    Copies from dot_env.example / config.yaml.example when missing.
    Returns (app_dir, created_dotenv, created_config).
    """
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

    cfg_dest = config_path()
    if not cfg_dest.exists():
        cfg_dest.write_bytes(_read_example("config.yaml.example"))
        created_config = True

    return dest_dir, created_dotenv, created_config
