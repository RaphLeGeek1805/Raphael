#!/usr/bin/env python3
"""CLI de revue qualité : liste les derniers appels et leur transcription."""
from __future__ import annotations

import argparse
import os
import textwrap
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

DSN = os.environ.get("PG_DSN", "postgresql://depanmagic:depanmagic@postgres:5432/depanmagic")


def main() -> None:
    parser = argparse.ArgumentParser(description="Revue des appels DEPANMAGIC AI.")
    parser.add_argument("--limit", type=int, default=10, help="Nombre d'appels à afficher.")
    parser.add_argument("--since", help="Date YYYY-MM-DD (filtre appels >= cette date).")
    parser.add_argument("--call-id", type=int, help="Affiche le détail d'un appel précis.")
    args = parser.parse_args()

    with psycopg.connect(DSN, row_factory=dict_row) as conn, conn.cursor() as cur:
        if args.call_id:
            _print_detail(cur, args.call_id)
        else:
            _print_list(cur, limit=args.limit, since=args.since)


def _print_list(cur, limit: int, since: str | None) -> None:
    where = ""
    params: list = []
    if since:
        where = "WHERE started_at >= %s"
        params.append(datetime.fromisoformat(since))
    params.append(limit)
    cur.execute(
        f"""
        SELECT id, asterisk_uid, caller_number, started_at, ended_at, outcome, handoff_to, summary
        FROM calls
        {where}
        ORDER BY started_at DESC
        LIMIT %s
        """,
        params,
    )
    rows = cur.fetchall()
    if not rows:
        print("Aucun appel.")
        return
    for r in rows:
        dur = ""
        if r["ended_at"]:
            dur = f" ({(r['ended_at'] - r['started_at']).total_seconds():.0f}s)"
        print(f"#{r['id']:<5} {r['started_at']:%Y-%m-%d %H:%M}{dur}  "
              f"{(r['caller_number'] or 'inconnu'):<15} "
              f"outcome={r['outcome'] or '?':<18} "
              f"handoff={r['handoff_to'] or '-':<10}")
        if r["summary"]:
            print(textwrap.indent(textwrap.fill(r["summary"], 100), "       "))
        print()


def _print_detail(cur, call_id: int) -> None:
    cur.execute("SELECT * FROM calls WHERE id = %s", (call_id,))
    call = cur.fetchone()
    if not call:
        print(f"Appel #{call_id} introuvable.")
        return
    print(f"=== Appel #{call_id} ===")
    print(f"  uid       : {call['asterisk_uid']}")
    print(f"  appelant  : {call['caller_number']}")
    print(f"  période   : {call['started_at']} → {call['ended_at']}")
    print(f"  outcome   : {call['outcome']}")
    print(f"  handoff   : {call['handoff_to']}")
    print(f"  résumé    : {call['summary']}")
    print()

    cur.execute(
        "SELECT turn_index, role, content, stt_confidence, latency_ms "
        "FROM call_turns WHERE call_id = %s ORDER BY turn_index",
        (call_id,),
    )
    for t in cur.fetchall():
        prefix = "👤" if t["role"] == "user" else "🤖"
        meta = ""
        if t["stt_confidence"] is not None:
            meta += f" conf={t['stt_confidence']:.2f}"
        if t["latency_ms"] is not None:
            meta += f" {t['latency_ms']}ms"
        print(f"{prefix} t{t['turn_index']:02d}{meta}")
        print(textwrap.indent(textwrap.fill(t["content"], 90), "    "))
        print()


if __name__ == "__main__":
    main()
