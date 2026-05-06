#!/usr/bin/env python3
"""Initialise la base Postgres de l'agent vocal (idempotent)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

DSN = os.environ.get("PG_DSN", "postgresql://depanmagic:depanmagic@postgres:5432/depanmagic")
SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def main() -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    print(f"Application du schéma sur {DSN}…")
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(sql)
    print("OK")


if __name__ == "__main__":
    try:
        main()
    except psycopg.OperationalError as exc:
        print(f"Connexion Postgres impossible : {exc}", file=sys.stderr)
        sys.exit(1)
