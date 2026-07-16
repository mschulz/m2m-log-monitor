# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A standalone Python script (not a long-running server) that Heroku Scheduler
invokes every 6 hours. Each run walks the fleet of apps in
`config.MONITORED_APPS`, checks each one's maintenance mode / dyno health /
recent logs, and posts findings to Slack. There is no web framework, queue,
or persistent process — `main.py` runs to completion and exits.

## Commands

```bash
# setup
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# tests
pytest
pytest tests/test_log_parser.py
pytest tests/test_log_parser.py::test_classify_finds_errors_and_ignores_warnings_when_disabled

# local dry run against real Heroku apps (no Slack sends, prints instead)
DRY_RUN=true python main.py
```

Config is read from environment variables, loaded from a local `.env` via
`python-dotenv` if present (see `.env.example`). `DATABASE_URL` unset skips
the Postgres watermark store entirely — useful for a dry run that shouldn't
mutate the production `seen_state` table (the same table the real Scheduler
job writes to).

## Architecture

Five modules, each a thin, independently-testable layer; `main.py` wires
them together with no business logic of its own beyond the per-app loop:

- **`config.py`** — all environment/env-derived values (`MONITORED_APPS`,
  API keys, feature flags). Every other module imports this rather than
  reading `os.environ` directly.
- **`heroku_client.py`** — Heroku Platform API v3 wrapper (`_get`/`_post`
  helpers, `HerokuApiError`). Maintenance mode is a field on the app
  resource itself (`GET /apps/{app}`), not a separate endpoint.
- **`log_parser.py`** — pure functions, no I/O. Parses Logplex's
  `source[dyno]: message` text format into `LogLine` records, classifies
  error/warning lines by keyword regex, and computes the "newest line"
  watermark. `LogLine.hash` (sha256 of the raw line) plus timestamp is what
  makes de-duplication exact even when two lines share a timestamp.
- **`state_store.py`** — Postgres-backed watermark persistence (one row per
  app: last-seen timestamp + hash). `psycopg.connect` is the only thing
  tests mock (see `tests/test_state_store.py`'s `FakeConnection`/
  `FakeCursor`) — there's no ORM.
- **`slack_notifier.py`** — all outbound Slack messages go through
  `_post_to_slack`, which is the single `DRY_RUN` gate (prints instead of
  POSTing). Long error/warning reports are chunked to stay under Slack's
  message size limit (`_MAX_CHUNK_CHARS`).

### Per-app flow (`main.check_app`)

1. Maintenance mode check → skip app entirely if enabled.
2. Dyno state check → alert (but don't skip) if any dyno is `crashed`/`down`.
3. Fetch the last watermark from `state_store` (skipped if `DATABASE_URL` is
   unset — the app then re-reports the whole log buffer every run).
4. Open a Logplex log session and fetch text, parse it, filter to lines
   after the watermark, classify into errors/warnings.
5. Send one batched Slack report if there's anything new, then advance the
   watermark to the newest line's (timestamp, hash).

A failure anywhere in this flow for one app (`HerokuApiError` or anything
else) is caught in `main.main()`, reported via `send_check_failure`, and
does not stop the run for remaining apps.

**Known limitation:** Heroku's log-session API returns a rolling buffer, not
a true time-range query. A very high-volume dyno can produce enough output
to roll past 6 hours between runs, and those lines are silently missed —
accepted tradeoff, not a bug to "fix" by re-architecting around it.
