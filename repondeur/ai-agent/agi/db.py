"""Helpers Postgres pour persister les appels et leurs tours."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

DB_DSN = os.environ.get(
    "PG_DSN",
    "postgresql://depanmagic:depanmagic@localhost:5432/depanmagic",
)


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(DB_DSN, row_factory=dict_row) as conn:
        yield conn


def open_call(asterisk_uid: str, caller_number: str | None) -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO calls (asterisk_uid, caller_number)
            VALUES (%s, %s)
            ON CONFLICT (asterisk_uid) DO UPDATE SET caller_number = EXCLUDED.caller_number
            RETURNING id
            """,
            (asterisk_uid, caller_number),
        )
        row = cur.fetchone()
        conn.commit()
        return row["id"]


def append_turn(
    call_id: int,
    turn_index: int,
    role: str,
    content: str,
    stt_confidence: float | None = None,
    latency_ms: int | None = None,
) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO call_turns (call_id, turn_index, role, content, stt_confidence, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (call_id, turn_index, role, content, stt_confidence, latency_ms),
        )
        conn.commit()


def close_call(call_id: int, outcome: str, summary: str | None, handoff_to: str | None) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE calls
            SET ended_at = NOW(), outcome = %s, summary = %s, handoff_to = %s
            WHERE id = %s
            """,
            (outcome, summary, handoff_to, call_id),
        )
        conn.commit()


def previous_call_summary(caller_number: str) -> str | None:
    """Retourne le résumé du dernier appel terminé de ce numéro, s'il y en a un."""
    if not caller_number:
        return None
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT summary
            FROM calls
            WHERE caller_number = %s AND ended_at IS NOT NULL AND summary IS NOT NULL
            ORDER BY ended_at DESC
            LIMIT 1
            """,
            (caller_number,),
        )
        row = cur.fetchone()
        return row["summary"] if row else None
