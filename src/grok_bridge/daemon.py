"""Process manager: grok-bridge start|stop|restart."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

import uvicorn

from grok_bridge.paths import pid_path, server_log_path, state_dir
from grok_bridge.server.config import load_settings


def _configure_logging(log_file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )


def _read_pid() -> int | None:
    path = pid_path()
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_pid(pid: int) -> None:
    state_dir()
    pid_path().write_text(f"{pid}\n", encoding="utf-8")


def _clear_pid() -> None:
    path = pid_path()
    if path.is_file():
        path.unlink()


def _listen_addr(settings) -> str:
    return f"{settings.host}:{settings.port}"


def cmd_run() -> int:
    """Foreground server (used by start after backgrounding)."""
    settings = load_settings(require_token=True, require_advisor_webhook=True)
    settings.require_loopback()
    log_file = server_log_path()
    _configure_logging(log_file)
    log = logging.getLogger("grok_bridge.daemon")
    log.info(
        "starting server host=%s port=%s log=%s",
        settings.host,
        settings.port,
        log_file,
    )
    _write_pid(os.getpid())
    try:
        uvicorn.run(
            "grok_bridge.server.app:create_app",
            factory=True,
            host=settings.host,
            port=settings.port,
            log_level="info",
        )
    finally:
        if _read_pid() == os.getpid():
            _clear_pid()
    return 0


def cmd_start() -> int:
    from grok_bridge.paths import ensure_app_config, ensure_bridge_token, token_path

    app, created_dotenv, created_config = ensure_app_config()
    if created_dotenv or created_config:
        print(f"seeded appdir: {app}")
        if created_dotenv:
            print(f"  created {app / '.env'} (edit webhook secrets)")
        if created_config:
            print(f"  created {app / 'config.yaml'} (tunable knobs)")

    _token, created_token = ensure_bridge_token()
    if created_token:
        print(f"created bridge token: {token_path()}")

    settings = load_settings(require_token=True, require_advisor_webhook=True)
    settings.require_loopback()

    existing = _read_pid()
    if existing is not None and _pid_alive(existing):
        print(f"already running pid={existing}")
        print(f"listening on {_listen_addr(settings)}")
        return 0
    if existing is not None:
        _clear_pid()

    state_dir()
    log_file = server_log_path()
    log_file.touch(exist_ok=True)

    # Re-exec this module's run in a detached process
    cmd = [sys.executable, "-m", "grok_bridge.daemon", "run"]
    env = os.environ.copy()
    # Ensure package importable when installed editable
    with open(log_file, "a", encoding="utf-8") as log_fh:
        # Prefer subprocess with start_new_session for true background
        import subprocess

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
            cwd=str(Path.cwd()),
        )

    # run() also writes PID; give it a moment, then verify still alive + health
    time.sleep(0.6)
    pid = _read_pid()
    if pid is None or not _pid_alive(pid):
        # fall back: child may have exited after bind failure
        if not _pid_alive(proc.pid):
            print(
                f"failed to start; check log: {log_file}",
                file=sys.stderr,
            )
            _clear_pid()
            return 1
        pid = proc.pid
        _write_pid(pid)

    # Confirm loopback health
    try:
        import httpx

        r = httpx.get(f"http://{settings.host}:{settings.port}/health", timeout=2.0)
        if r.status_code != 200:
            raise RuntimeError(f"health HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        print(
            f"failed to start (health check): {exc}; check log: {log_file}",
            file=sys.stderr,
        )
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        _clear_pid()
        return 1

    print(f"started pid={pid}")
    print(f"listening on {_listen_addr(settings)}")
    print(f"log={log_file}")
    return 0


def cmd_stop() -> int:
    pid = _read_pid()
    if pid is None or not _pid_alive(pid):
        _clear_pid()
        print("not running")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_pid()
        print("not running")
        return 0

    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    _clear_pid()
    print(f"stopped pid={pid}")
    return 0


def cmd_restart() -> int:
    cmd_stop()
    time.sleep(0.2)
    return cmd_start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grok-bridge")
    parser.add_argument(
        "command",
        choices=("start", "stop", "restart", "run"),
        help="start|stop|restart (run is internal/foreground)",
    )
    args = parser.parse_args(argv)

    if args.command == "start":
        return cmd_start()
    if args.command == "stop":
        return cmd_stop()
    if args.command == "restart":
        return cmd_restart()
    if args.command == "run":
        return cmd_run()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
