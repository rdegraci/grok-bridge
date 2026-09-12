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


def _configure_logging() -> None:
    """Log to stderr only (daemon start redirects stderr into the log file)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )
    # Keep noisy libraries down so failures stay readable
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def _tail_text(path: Path, max_lines: int = 40) -> str:
    if not path.is_file():
        return f"(no log file yet at {path})"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(could not read log: {exc})"
    if not lines:
        return "(log file is empty)"
    return "\n".join(lines[-max_lines:])


def _explain_health_failure(exc: BaseException, listen: str) -> str:
    text = str(exc).lower()
    if "connect" in text or "refused" in text or "10061" in text:
        return (
            f"Nothing is listening on {listen} yet "
            f"(connection refused). The background process likely crashed "
            f"during startup (bad install, import error, port in use, or "
            f"missing webhook config)."
        )
    if "timed out" in text or "timeout" in text:
        return f"Timed out waiting for http://{listen}/health."
    return f"Health check failed against http://{listen}/health: {exc}"


def _print_start_failure(title: str, detail: str, log_file: Path) -> None:
    print(f"ERROR: {title}", file=sys.stderr)
    print(detail, file=sys.stderr)
    print(f"Server log: {log_file}", file=sys.stderr)
    print("---- last log lines ----", file=sys.stderr)
    print(_tail_text(log_file), file=sys.stderr)
    print("---- end log ----", file=sys.stderr)


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


def _say(msg: str) -> None:
    """Always-visible startup breadcrumb (stderr + flush → server log)."""
    print(msg, file=sys.stderr, flush=True)


def _uvicorn_log_config() -> dict:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(asctime)s %(levelprefix)s %(message)s",
                "use_colors": False,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
                "use_colors": False,
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
            "grok_bridge": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }


def cmd_run() -> int:
    """Foreground server (used by start after backgrounding)."""
    # Logging first so every later failure is visible in the redirected log.
    _configure_logging()
    _say(f"daemon run: begin pid={os.getpid()} python={sys.executable}")

    try:
        _say("daemon run: loading settings (.env, token, config.yaml)")
        settings = load_settings(require_token=True, require_advisor_webhook=True)
        settings.require_loopback()
    except SystemExit as exc:
        _say(f"daemon run: settings failed: {exc}")
        raise
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("grok_bridge.daemon").exception("settings load failed")
        _say(f"daemon run: settings crashed: {exc}")
        raise

    bots = ",".join(sorted(settings.bots)) or "(none)"
    log_file = server_log_path()
    _say(
        f"daemon run: settings ok host={settings.host} port={settings.port} "
        f"bots={bots} log={log_file}"
    )
    _write_pid(os.getpid())
    _say(f"daemon run: wrote pid file {pid_path()}")
    _say(
        f"daemon run: launching uvicorn on http://{settings.host}:{settings.port}"
    )

    try:
        uvicorn.run(
            "grok_bridge.server.app:create_app",
            factory=True,
            host=settings.host,
            port=settings.port,
            log_level="info",
            log_config=_uvicorn_log_config(),
            access_log=True,
        )
        _say("daemon run: uvicorn exited normally")
    except OSError as exc:
        _say(
            f"daemon run: bind/listen failed on {settings.host}:{settings.port}: {exc}"
        )
        logging.getLogger("grok_bridge.daemon").exception("uvicorn OSError")
        raise
    except Exception as exc:  # noqa: BLE001
        _say(f"daemon run: uvicorn crashed: {exc}")
        logging.getLogger("grok_bridge.daemon").exception("uvicorn crashed")
        raise
    finally:
        if _read_pid() == os.getpid():
            _clear_pid()
            _say("daemon run: cleared pid file")
    return 0


def cmd_start() -> int:
    from grok_bridge.paths import ensure_app_config, ensure_bridge_token, token_path

    print("start: begin", flush=True)
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
    else:
        print(f"start: using existing token file {token_path()}", flush=True)

    print("start: loading settings", flush=True)
    settings = load_settings(require_token=True, require_advisor_webhook=True)
    settings.require_loopback()
    print(
        f"start: settings host={settings.host} port={settings.port} "
        f"bots={','.join(settings.bots) or '(none)'}",
        flush=True,
    )

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
    with open(log_file, "a", encoding="utf-8") as log_fh:
        print(
            f"\n--- grok-bridge start {time.strftime('%Y-%m-%dT%H:%M:%S')} "
            f"python={sys.executable} listen={_listen_addr(settings)} ---",
            file=log_fh,
            flush=True,
        )
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

    # Wait for listen (import/bind can take >0.6s on cold start)
    listen = _listen_addr(settings)
    pid = None
    last_exc: BaseException | None = None
    import httpx

    for attempt in range(20):
        time.sleep(0.25)
        pid = _read_pid()
        alive = _pid_alive(proc.pid)
        print(
            f"start wait attempt={attempt + 1}/20 pid_file={pid} "
            f"child_alive={alive} listen={listen}",
            file=sys.stderr,
            flush=True,
        )
        with open(log_file, "a", encoding="utf-8") as log_fh:
            print(
                f"start wait attempt={attempt + 1}/20 pid_file={pid} "
                f"child_alive={alive} listen={listen}",
                file=log_fh,
                flush=True,
            )
        if pid is None and not alive:
            _print_start_failure(
                "bridge process exited immediately",
                "The background server died before it could listen. "
                "Common causes: wrong Python env, missing package install "
                "(`pip install -e .`), or webhook/.env config error.",
                log_file,
            )
            _clear_pid()
            return 1
        if pid is None and alive:
            pid = proc.pid
            _write_pid(pid)
            print(f"start wait: adopted child pid={pid}", file=sys.stderr, flush=True)
        try:
            r = httpx.get(f"http://{settings.host}:{settings.port}/health", timeout=1.0)
            print(
                f"start wait health status={r.status_code}",
                file=sys.stderr,
                flush=True,
            )
            if r.status_code == 200:
                last_exc = None
                break
            last_exc = RuntimeError(f"health HTTP {r.status_code}: {r.text[:200]}")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print(
                f"start wait health error: {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
    else:
        # loop exhausted without break
        if pid is not None and _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        _print_start_failure(
            "bridge did not become healthy",
            _explain_health_failure(last_exc or RuntimeError("unknown"), listen),
            log_file,
        )
        _clear_pid()
        return 1

    print(f"started pid={pid}")
    print(f"listening on {listen}")
    print(f"log={log_file}")
    return 0


def cmd_stop() -> int:
    print("stop: begin", flush=True)
    pid = _read_pid()
    if pid is None or not _pid_alive(pid):
        _clear_pid()
        print("not running")
        return 0
    print(f"stop: sending SIGTERM to pid={pid}", flush=True)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_pid()
        print("not running")
        return 0

    for i in range(50):
        if not _pid_alive(pid):
            print(f"stop: process exited after {(i + 1) * 0.1:.1f}s", flush=True)
            break
        time.sleep(0.1)
    else:
        print(f"stop: still alive, sending SIGKILL to pid={pid}", flush=True)
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
