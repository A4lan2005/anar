"""Neon PostgreSQL persistence for session state and workbook blobs."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def db_enabled() -> bool:
    return bool(DATABASE_URL.strip())


@contextmanager
def _connection():
    if not db_enabled():
        raise RuntimeError("DATABASE_URL is not set")
    import psycopg

    with psycopg.connect(DATABASE_URL) as conn:
        conn.autocommit = True
        yield conn


def init_schema() -> None:
    if not db_enabled():
        return
    from pathlib import Path

    sql = (Path(__file__).resolve().parent.parent / "schema.sql").read_text(encoding="utf-8")
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def ensure_session(session_id: str, source_filename: str | None = None) -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_sessions (id, source_filename)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (session_id, source_filename),
            )


def session_exists(session_id: str) -> bool:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM user_sessions WHERE id = %s", (session_id,))
            return cur.fetchone() is not None


def get_global_idx(session_id: str) -> int:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT global_idx FROM user_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0


def set_global_idx(session_id: str, global_idx: int) -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_sessions
                SET global_idx = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (global_idx, session_id),
            )


def set_source_filename(session_id: str, filename: str) -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE user_sessions
                SET source_filename = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (filename, session_id),
            )


def save_blob(session_id: str, blob_key: str, data: bytes) -> None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO session_blobs (session_id, blob_key, data, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (session_id, blob_key)
                DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """,
                (session_id, blob_key, data),
            )
            cur.execute(
                "UPDATE user_sessions SET updated_at = NOW() WHERE id = %s",
                (session_id,),
            )


def load_blob(session_id: str, blob_key: str) -> bytes | None:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM session_blobs WHERE session_id = %s AND blob_key = %s",
                (session_id, blob_key),
            )
            row = cur.fetchone()
            return bytes(row[0]) if row else None


def save_json(session_id: str, blob_key: str, data: Any) -> None:
    save_blob(session_id, blob_key, json.dumps(data, ensure_ascii=False).encode("utf-8"))


def load_json(session_id: str, blob_key: str, default: Any = None) -> Any:
    raw = load_blob(session_id, blob_key)
    if raw is None:
        return default
    return json.loads(raw.decode("utf-8"))


def list_blob_keys(session_id: str) -> list[str]:
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT blob_key FROM session_blobs WHERE session_id = %s ORDER BY blob_key",
                (session_id,),
            )
            return [row[0] for row in cur.fetchall()]


def delete_blobs(session_id: str, blob_keys: list[str]) -> None:
    if not blob_keys:
        return
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM session_blobs WHERE session_id = %s AND blob_key = ANY(%s)",
                (session_id, blob_keys),
            )


def validate_session_id(session_id: str) -> bool:
    try:
        UUID(session_id)
        return True
    except ValueError:
        return False
