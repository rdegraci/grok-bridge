"""Interactive chat client: grok-bridge-cli."""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from grok_bridge.cli.client import BridgeClient
from grok_bridge.paths import cli_logs_dir
from grok_bridge.server.config import load_settings

log = logging.getLogger("grok_bridge.cli")


def _truncate(text: str, limit: int = 200) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _setup_session_log() -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = cli_logs_dir() / f"cli-{ts}-{os.getpid()}.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
        ],
        force=True,
    )
    # Also keep warnings on stderr lightly
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.WARNING)
    stderr.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logging.getLogger().addHandler(stderr)
    return path


def _print_session_log_path(path: Path | None) -> None:
    if path is not None:
        print(f"Session log: {path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    session_log: Path | None = None
    try:
        settings = load_settings(require_token=True, require_advisor_webhook=False)
        session_log = _setup_session_log()
        log.info("session start base_url=%s", settings.base_url)

        client = BridgeClient(settings.base_url, settings.auth_token)
        try:
            client.health()
        except Exception as exc:  # noqa: BLE001
            print(
                f"Cannot reach bridge server at {settings.base_url} "
                f"(is it started? try: grok-bridge start) ({exc})",
                file=sys.stderr,
            )
            log.exception("health check failed")
            return 1

        active_bot: str | None = None
        cursors: dict[str, int] = {}

        print("grok-bridge-cli — /chat <bot>, /status, /quit")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue

            if line in {"/quit", "/exit"}:
                break

            if line.startswith("/chat"):
                parts = line.split(maxsplit=1)
                if len(parts) < 2 or not parts[1].strip():
                    print("Usage: /chat <bot>")
                    continue
                bot = parts[1].strip().lower()
                active_bot = bot
                cursors.setdefault(bot, 0)
                log.info("chat switch bot=%s since=%s", bot, cursors[bot])
                print(f"[{bot}] connected")
                # Drain unread
                try:
                    status, data = client.replies(bot=bot, since=cursors[bot])
                    if status == 200 and data.get("ok"):
                        for reply in data.get("replies") or []:
                            print(f"[{bot}] {reply.get('text', '')}")
                            log.info(
                                "drained reply seq=%s in_reply_to=%s",
                                reply.get("seq"),
                                reply.get("in_reply_to"),
                            )
                        cursors[bot] = int(data.get("next_since", cursors[bot]))
                except Exception as exc:  # noqa: BLE001
                    print(f"Error reading replies: {exc}", file=sys.stderr)
                    log.exception("drain failed")
                continue

            if line == "/status":
                print(f"active_bot={active_bot or '(none)'}")
                print(f"base_url={settings.base_url}")
                print(f"cursors={cursors}")
                print(f"session_log={session_log}")
                continue

            if line.startswith("/"):
                print("Unknown command. Try /chat, /status, /quit")
                continue

            if not active_bot:
                print("Use /chat <bot> first.")
                continue

            message_id = str(uuid.uuid4())
            log.info(
                "send bot=%s message_id=%s text=%s",
                active_bot,
                message_id,
                _truncate(line),
            )
            try:
                status, data = client.send(
                    bot=active_bot, message_id=message_id, text=line
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"Cannot reach bridge server at {settings.base_url} "
                    f"(is it started? try: grok-bridge start)",
                    file=sys.stderr,
                )
                log.exception("send failed: %s", exc)
                continue

            if status >= 400 or not data.get("ok", True):
                wh = data.get("webhook_status") or data.get("detail") or data
                err = data.get("error") or "send_failed"
                if err == "webhook_rejected" or status == 502:
                    print(f"Webhook rejected (HTTP {data.get('webhook_status', status)})")
                elif err == "unknown_bot":
                    print(f"Unknown bot: {active_bot}")
                else:
                    print(f"Send failed: {err} {wh}")
                log.warning("send error status=%s data=%s", status, data)
                continue

            deadline = time.monotonic() + settings.reply_timeout_sec
            matched = False
            while time.monotonic() < deadline:
                try:
                    status, data = client.replies(
                        bot=active_bot, since=cursors.get(active_bot, 0)
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"Poll error: {exc}", file=sys.stderr)
                    log.exception("poll failed")
                    break

                if status != 200:
                    log.warning("poll status=%s data=%s", status, data)
                    time.sleep(settings.poll_interval_sec)
                    continue

                replies = data.get("replies") or []
                log.debug(
                    "poll since=%s count=%s next_since=%s",
                    cursors.get(active_bot, 0),
                    len(replies),
                    data.get("next_since"),
                )
                for reply in replies:
                    text = reply.get("text", "")
                    print(f"[{active_bot}] {text}")
                    log.info(
                        "got reply seq=%s in_reply_to=%s text=%s",
                        reply.get("seq"),
                        reply.get("in_reply_to"),
                        _truncate(text),
                    )
                    if reply.get("in_reply_to") == message_id or not reply.get(
                        "in_reply_to"
                    ):
                        matched = True
                cursors[active_bot] = int(
                    data.get("next_since", cursors.get(active_bot, 0))
                )
                if matched:
                    break
                time.sleep(settings.poll_interval_sec)

            if not matched:
                n = int(settings.reply_timeout_sec)
                print(
                    f"No reply within {n}s. Check Grok Bot app and that the "
                    "agent can POST /replies."
                )
                log.warning("timeout waiting for message_id=%s", message_id)

        log.info("session end")
        return 0
    finally:
        _print_session_log_path(session_log)


if __name__ == "__main__":
    raise SystemExit(main())
