"""In-memory reply queue with monotonic seq and bot filter."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class StoredReply:
    seq: int
    v: int
    bot: str
    in_reply_to: str | None
    message_id: str
    text: str
    sent_at: str | None


class ReplyQueue:
    def __init__(self, max_replies: int = 500) -> None:
        self._max = max(1, max_replies)
        self._lock = threading.Lock()
        self._items: list[StoredReply] = []
        self._next_seq = 1

    def append(
        self,
        *,
        bot: str,
        message_id: str,
        text: str,
        in_reply_to: str | None = None,
        sent_at: str | None = None,
        v: int = 1,
    ) -> int:
        with self._lock:
            seq = self._next_seq
            self._next_seq += 1
            self._items.append(
                StoredReply(
                    seq=seq,
                    v=v,
                    bot=bot,
                    in_reply_to=in_reply_to,
                    message_id=message_id,
                    text=text,
                    sent_at=sent_at,
                )
            )
            while len(self._items) > self._max:
                self._items.pop(0)
            return seq

    def list_since(self, bot: str, since: int, limit: int = 50) -> tuple[list[StoredReply], int]:
        limit = max(1, min(limit, 100))
        with self._lock:
            matched = [r for r in self._items if r.bot == bot and r.seq > since]
            matched = matched[:limit]
            next_since = matched[-1].seq if matched else since
            return list(matched), next_since
