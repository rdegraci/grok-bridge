"""Filesystem locations for PID, server log, and CLI session logs."""

from __future__ import annotations

from pathlib import Path


def state_dir() -> Path:
    path = Path.home() / ".grok-bridge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pid_path() -> Path:
    return state_dir() / "grok-bridge.pid"


def server_log_path() -> Path:
    return state_dir() / "grok-bridge.log"


def cli_logs_dir() -> Path:
    path = state_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
