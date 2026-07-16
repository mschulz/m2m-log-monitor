from datetime import datetime, timezone
from unittest.mock import patch

import state_store


class FakeCursor:
    def __init__(self, table):
        self.table = table
        self._last_result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("CREATE TABLE"):
            return
        if normalized.startswith("ALTER TABLE"):
            return
        if normalized.startswith("SELECT"):
            app_name = params[0]
            row = self.table.get(app_name)
            self._last_result = (
                (row["last_ts"], row["last_hash"], row["had_errors"]) if row else None
            )
            return
        if normalized.startswith("INSERT"):
            app_name, last_ts, last_hash, had_errors = params
            self.table[app_name] = {
                "last_ts": last_ts,
                "last_hash": last_hash,
                "had_errors": had_errors,
            }
            return
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchone(self):
        return self._last_result


class FakeConnection:
    def __init__(self, table):
        self.table = table

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def cursor(self):
        return FakeCursor(self.table)

    def commit(self):
        pass


def _make_fake_connect(table):
    def fake_connect(dsn):
        return FakeConnection(table)

    return fake_connect


def test_get_last_state_returns_none_when_unseen():
    table = {}
    with patch("state_store.psycopg.connect", _make_fake_connect(table)):
        last_ts, last_hash, had_errors = state_store.get_last_state("some-app")
    assert last_ts is None
    assert last_hash is None
    assert had_errors is False


def test_set_then_get_last_state_round_trips():
    table = {}
    ts = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    with patch("state_store.psycopg.connect", _make_fake_connect(table)):
        state_store.set_last_state("some-app", ts, "abc123", True)
        last_ts, last_hash, had_errors = state_store.get_last_state("some-app")
    assert last_ts == ts
    assert last_hash == "abc123"
    assert had_errors is True


def test_set_last_state_overwrites_previous_value():
    table = {}
    ts1 = datetime(2024, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2024, 5, 1, 18, 0, 0, tzinfo=timezone.utc)
    with patch("state_store.psycopg.connect", _make_fake_connect(table)):
        state_store.set_last_state("some-app", ts1, "hash1", True)
        state_store.set_last_state("some-app", ts2, "hash2", False)
        last_ts, last_hash, had_errors = state_store.get_last_state("some-app")
    assert last_ts == ts2
    assert last_hash == "hash2"
    assert had_errors is False


def test_ensure_schema_runs_create_table_without_error():
    table = {}
    with patch("state_store.psycopg.connect", _make_fake_connect(table)):
        state_store.ensure_schema()
