"""
SQLite persistence layer
=========================
Stores research sessions so the Streamlit UI can show history, resume a past
thread, and reload its transcript + plan + generated files.

Design notes
------------
- One row per *thread* (a LangGraph `thread_id`) in `sessions`.
- One row per *message* in `messages`, linked by `session_id`.
- One row per *todo snapshot* in `todo_snapshots` — we store the latest
  write_todos payload per session so the sidebar can show "last known plan"
  without replaying the whole transcript.
- This file deliberately uses the standard-library `sqlite3` module only —
  no ORM — so the project stays dependency-light and the schema is easy to
  read in an interview.
- All functions are safe to call from a Streamlit script (which re-executes
  top-to-bottom on every interaction): each call opens and closes its own
  connection rather than holding one open across reruns.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "research_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,   -- == LangGraph thread_id
    title           TEXT NOT NULL,      -- first user query, truncated
    model           TEXT NOT NULL,
    backend         TEXT NOT NULL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'  -- active | completed | error
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role            TEXT NOT NULL,      -- user | assistant
    content         TEXT NOT NULL,
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS todo_snapshots (
    session_id      TEXT PRIMARY KEY REFERENCES sessions(session_id) ON DELETE CASCADE,
    todos_json      TEXT NOT NULL,      -- latest write_todos payload, as JSON
    updated_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""


def init_db() -> None:
    """Create the database file and schema if they don't exist yet."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class SessionRecord:
    session_id: str
    title: str
    model: str
    backend: str
    created_at: float
    updated_at: float
    status: str = "active"


@dataclass
class MessageRecord:
    role: str
    content: str
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
def create_session(session_id: str, title: str, model: str, backend: str) -> None:
    now = time.time()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions "
            "(session_id, title, model, backend, created_at, updated_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active')",
            (session_id, title[:120], model, backend, now, now),
        )


def touch_session(session_id: str, status: str = "active") -> None:
    """Bump updated_at (and optionally status) — call after each agent turn."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET updated_at = ?, status = ? WHERE session_id = ?",
            (time.time(), status, session_id),
        )


def list_sessions(limit: int = 50) -> list[SessionRecord]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [SessionRecord(**dict(r)) for r in rows]


def get_session(session_id: str) -> Optional[SessionRecord]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return SessionRecord(**dict(row)) if row else None


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def add_message(session_id: str, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, time.time()),
        )


def get_messages(session_id: str) -> list[MessageRecord]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [MessageRecord(**dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Todo snapshots (latest plan state per session)
# ---------------------------------------------------------------------------
def save_todo_snapshot(session_id: str, todos: list[dict[str, Any]]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO todo_snapshots (session_id, todos_json, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "todos_json = excluded.todos_json, updated_at = excluded.updated_at",
            (session_id, json.dumps(todos), time.time()),
        )


def get_todo_snapshot(session_id: str) -> list[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT todos_json FROM todo_snapshots WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return json.loads(row["todos_json"]) if row else []
