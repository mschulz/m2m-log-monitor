"""Postgres-backed per-app watermark storage.

Stores, for each monitored app, the timestamp and content hash of the newest
log line seen on the previous run, so the next run only reports genuinely new
lines instead of re-alerting on the same overlapping buffer.
"""
import psycopg

import config

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS seen_state (
    app_name TEXT PRIMARY KEY,
    last_ts TIMESTAMPTZ,
    last_hash TEXT
)
"""


def _connect():
    return psycopg.connect(config.DATABASE_URL)


def ensure_schema():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        conn.commit()


def get_last_state(app_name):
    """Return (last_ts, last_hash) for the app, or (None, None) if unseen."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_ts, last_hash FROM seen_state WHERE app_name = %s",
                (app_name,),
            )
            row = cur.fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def set_last_state(app_name, last_ts, last_hash):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO seen_state (app_name, last_ts, last_hash)
                VALUES (%s, %s, %s)
                ON CONFLICT (app_name)
                DO UPDATE SET last_ts = EXCLUDED.last_ts,
                              last_hash = EXCLUDED.last_hash
                """,
                (app_name, last_ts, last_hash),
            )
        conn.commit()
