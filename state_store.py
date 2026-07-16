"""Postgres-backed per-app watermark storage.

Stores, for each monitored app, the timestamp and content hash of the newest
log line seen on the previous run, so the next run only reports genuinely new
lines instead of re-alerting on the same overlapping buffer. Also tracks
whether the last run reported any errors, so a run that comes back clean
after a prior error run can be reported as resolved.
"""
import psycopg

import config

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS seen_state (
    app_name TEXT PRIMARY KEY,
    last_ts TIMESTAMPTZ,
    last_hash TEXT,
    had_errors BOOLEAN NOT NULL DEFAULT FALSE
)
"""

_ADD_HAD_ERRORS_COLUMN_SQL = """
ALTER TABLE seen_state
    ADD COLUMN IF NOT EXISTS had_errors BOOLEAN NOT NULL DEFAULT FALSE
"""


def _connect():
    return psycopg.connect(config.DATABASE_URL)


def ensure_schema():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
            cur.execute(_ADD_HAD_ERRORS_COLUMN_SQL)
        conn.commit()


def get_last_state(app_name):
    """Return (last_ts, last_hash, had_errors) for the app, or (None, None, False) if unseen."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_ts, last_hash, had_errors FROM seen_state WHERE app_name = %s",
                (app_name,),
            )
            row = cur.fetchone()
    if row is None:
        return None, None, False
    return row[0], row[1], row[2]


def set_last_state(app_name, last_ts, last_hash, had_errors):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO seen_state (app_name, last_ts, last_hash, had_errors)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (app_name)
                DO UPDATE SET last_ts = EXCLUDED.last_ts,
                              last_hash = EXCLUDED.last_hash,
                              had_errors = EXCLUDED.had_errors
                """,
                (app_name, last_ts, last_hash, had_errors),
            )
        conn.commit()
