"""会話履歴をプロセスメモリに保持するシンプルなセッションストア。

- session_id をキーに直近 N メッセージを保持する。
- TTL を超えたセッションは get/set の際に削除する。
- 単一プロセス前提。Cloud Run などで複数インスタンスにスケールさせる場合は
  Firestore / Redis 等の外部ストレージに差し替えること。
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Literal, TypedDict

MAX_MESSAGES = 20  # user + assistant 合計でこの数を超えたら古いものから捨てる
TTL_SECONDS = 60 * 60  # 1 時間アクセスのないセッションは破棄


class StoredMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class _SessionEntry(TypedDict):
    messages: list[StoredMessage]
    updated_at: float


class SessionStore:
    def __init__(self, max_messages: int = MAX_MESSAGES, ttl_seconds: int = TTL_SECONDS) -> None:
        self._max_messages = max_messages
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, _SessionEntry] = {}
        self._lock = threading.Lock()

    def _is_expired(self, entry: _SessionEntry, now: float) -> bool:
        return now - entry["updated_at"] > self._ttl_seconds

    def _purge_expired(self, now: float) -> None:
        expired = [sid for sid, e in self._sessions.items() if self._is_expired(e, now)]
        for sid in expired:
            self._sessions.pop(sid, None)

    def ensure_session(self, session_id: str | None) -> str:
        """session_id を返す。未指定 / 期限切れなら新規発行する。"""
        now = time.time()
        with self._lock:
            self._purge_expired(now)
            if session_id and session_id in self._sessions:
                return session_id
            new_id = session_id or str(uuid.uuid4())
            self._sessions[new_id] = {"messages": [], "updated_at": now}
            return new_id

    def get_messages(self, session_id: str) -> list[StoredMessage]:
        now = time.time()
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None or self._is_expired(entry, now):
                self._sessions.pop(session_id, None)
                return []
            return list(entry["messages"])

    def append(self, session_id: str, role: Literal["user", "assistant"], content: str) -> None:
        if not content:
            return
        now = time.time()
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None or self._is_expired(entry, now):
                entry = {"messages": [], "updated_at": now}
                self._sessions[session_id] = entry
            entry["messages"].append({"role": role, "content": content})
            if len(entry["messages"]) > self._max_messages:
                entry["messages"] = entry["messages"][-self._max_messages :]
            entry["updated_at"] = now

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


session_store = SessionStore()
