"""Pydantic request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SendRequest(BaseModel):
    v: int = 1
    bot: str
    client_id: str = "mini-cli"
    message_id: str
    text: str = Field(min_length=1)
    sent_at: str | None = None


class SendResponse(BaseModel):
    ok: bool
    bot: str | None = None
    message_id: str | None = None
    webhook_status: int | None = None
    error: str | None = None
    detail: str | None = None


class ReplyIn(BaseModel):
    v: int = 1
    bot: str
    in_reply_to: str | None = None
    message_id: str
    text: str = Field(min_length=1)
    sent_at: str | None = None


class ReplyOut(BaseModel):
    seq: int
    v: int = 1
    bot: str
    in_reply_to: str | None = None
    message_id: str
    text: str
    sent_at: str | None = None


class RepliesListResponse(BaseModel):
    ok: bool = True
    bot: str
    replies: list[ReplyOut]
    next_since: int


class ReplyStoredResponse(BaseModel):
    ok: bool = True
    seq: int


class HealthResponse(BaseModel):
    ok: bool = True
    v: int = 1


class ErrorBody(BaseModel):
    ok: bool = False
    error: str
    detail: str | None = None
    webhook_status: int | None = None
    extra: dict[str, Any] | None = None
