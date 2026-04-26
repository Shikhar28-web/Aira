"""
Lightweight SQLite data layer for Aira.

Tables:
- users
- companions
- chats
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any


_DB_PATH = os.getenv(
    "AIRA_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "aira.db"),
)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Create all required tables if they do not exist."""
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS companions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                style TEXT,
                language TEXT,
                voice_type TEXT,
                profile_voice_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_companions_user
            ON companions(user_id)
            """
        )
        conn.execute("DROP INDEX IF EXISTS idx_companions_user_unique")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                companion_id INTEGER,
                conversation_id INTEGER,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                message TEXT NOT NULL,
                emotion TEXT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (companion_id) REFERENCES companions(id) ON DELETE SET NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )

        # Backward-compatible migration for existing DBs.
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(chats)").fetchall()
        }
        if "conversation_id" not in cols:
            conn.execute("ALTER TABLE chats ADD COLUMN conversation_id INTEGER")

        companion_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(companions)").fetchall()
        }
        if "voice_type" not in companion_cols:
            conn.execute("ALTER TABLE companions ADD COLUMN voice_type TEXT")
        if "profile_voice_id" not in companion_cols:
            conn.execute("ALTER TABLE companions ADD COLUMN profile_voice_id TEXT")


def create_user(username: str, password_hash: str) -> int | None:
    """Create a user and return the new user id; returns None if username exists."""
    try:
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None


def get_user(username: str) -> dict[str, Any] | None:
    """Fetch a user by username."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def get_companion_profile(user_id: int) -> dict[str, Any] | None:
    """Fetch companion profile for a user (one companion per user)."""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, name, style, language, voice_type, profile_voice_id
            FROM companions
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_companions(user_id: int) -> list[dict[str, Any]]:
    """Fetch all companions for a user."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, style, language, voice_type, profile_voice_id
            FROM companions
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_companion(
    user_id: int,
    name: str,
    style: str,
    language: str,
    voice_type: str | None = None,
    profile_voice_id: str | None = None,
) -> dict[str, Any]:
    """Create a companion profile for user and return it."""
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO companions (user_id, name, style, language, voice_type, profile_voice_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, style, language, voice_type, profile_voice_id),
        )
        cid = int(cur.lastrowid)
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, name, style, language, voice_type, profile_voice_id
            FROM companions
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (cid, user_id),
        ).fetchone()
    return dict(row) if row else {
        "id": cid,
        "user_id": user_id,
        "name": name,
        "style": style,
        "language": language,
        "voice_type": voice_type,
        "profile_voice_id": profile_voice_id,
    }


def get_companion_by_id(user_id: int, companion_id: int) -> dict[str, Any] | None:
    """Fetch one companion by id scoped to a user."""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, name, style, language, voice_type, profile_voice_id
            FROM companions
            WHERE user_id = ? AND id = ?
            LIMIT 1
            """,
            (user_id, companion_id),
        ).fetchone()
    return dict(row) if row else None


def update_companion(
    user_id: int,
    companion_id: int,
    name: str,
    style: str,
    language: str,
    voice_type: str | None,
    profile_voice_id: str | None,
) -> dict[str, Any] | None:
    """Update a companion and return the updated row."""
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE companions
            SET name = ?, style = ?, language = ?, voice_type = ?, profile_voice_id = ?
            WHERE user_id = ? AND id = ?
            """,
            (name, style, language, voice_type, profile_voice_id, user_id, companion_id),
        )
    return get_companion_by_id(user_id, companion_id)


def delete_companion(user_id: int, companion_id: int) -> bool:
    """Delete a companion owned by user. Returns True if deleted."""
    with _get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM companions WHERE user_id = ? AND id = ?",
            (user_id, companion_id),
        )
        return cur.rowcount > 0


def upsert_companion_profile(
    user_id: int,
    name: str,
    style: str,
    language: str,
) -> dict[str, Any]:
    """Create or update the first companion profile for a user."""
    with _get_conn() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM companions
            WHERE user_id = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE companions
                SET name = ?, style = ?, language = ?
                WHERE id = ?
                """,
                (name, style, language, int(existing["id"])),
            )
        else:
            conn.execute(
                """
                INSERT INTO companions (user_id, name, style, language, voice_type, profile_voice_id)
                VALUES (?, ?, ?, ?, NULL, NULL)
                """,
                (user_id, name, style, language),
            )

    profile = get_companion_profile(user_id)
    return profile or {
        "id": None,
        "user_id": user_id,
        "name": name,
        "style": style,
        "language": language,
    }


def save_message(
    user_id: int,
    companion_id: int | None,
    role: str,
    message: str,
    emotion: str | None = None,
    conversation_id: int | None = None,
) -> int:
    """Persist one chat message and return inserted message id."""
    with _get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO chats (user_id, companion_id, conversation_id, role, message, emotion)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, companion_id, conversation_id, role, message, emotion),
        )
        return int(cur.lastrowid)


def create_conversation(user_id: int, title: str) -> int:
    """Create a new conversation for user and return conversation id."""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return int(cur.lastrowid)


def get_conversations(user_id: int) -> list[dict[str, Any]]:
    """Return all conversations for a user (newest first)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages(user_id: int, conversation_id: int) -> list[dict[str, Any]]:
    """Return messages for one conversation (oldest first)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, companion_id, conversation_id, role, message, emotion, timestamp
            FROM chats
            WHERE user_id = ? AND conversation_id = ?
            ORDER BY id ASC
            """,
            (user_id, conversation_id),
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages_by_companion(user_id: int, companion_id: int) -> list[dict[str, Any]]:
    """Return messages for one companion (oldest first)."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, companion_id, role, message, emotion, timestamp
            FROM chats
            WHERE user_id = ? AND companion_id = ?
            ORDER BY id ASC
            """,
            (user_id, companion_id),
        ).fetchall()
    return [dict(r) for r in rows]


def get_chat_history(user_id: int, companion_id: int | None) -> list[dict[str, Any]]:
    """Return chat history ordered by insertion time (oldest first)."""
    with _get_conn() as conn:
        if companion_id is None:
            rows = conn.execute(
                """
                SELECT id, user_id, companion_id, role, message, emotion, timestamp
                FROM chats
                WHERE user_id = ? AND companion_id IS NULL
                ORDER BY id ASC
                """,
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, user_id, companion_id, role, message, emotion, timestamp
                FROM chats
                WHERE user_id = ? AND companion_id = ?
                ORDER BY id ASC
                """,
                (user_id, companion_id),
            ).fetchall()
    return [dict(r) for r in rows]
