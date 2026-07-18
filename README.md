# m2m-log-monitor

A scheduled health check for a fleet of Heroku apps. Every 6 hours it checks
each app for maintenance mode, crashed/down dynos, and new error/warning
lines in the logs, then posts a summary to Slack.

## Features

- Reports new error log lines (and optionally warnings) since the last run
- Alerts on crashed or down dynos
- Skips apps entirely while they're in maintenance mode
- Filters out known-noisy log lines (e.g. scanner traffic) so reports stay
  actionable
- Sends a "resolved" message when a previously-erroring app comes back clean
- Posts findings to a Slack channel via an Incoming Webhook

The list of monitored apps lives in `config.py` (`MONITORED_APPS`).

## How it works

This is a standalone script, not a server — it runs to completion and exits.
It's intended to be invoked on a schedule (e.g. Heroku Scheduler) rather than
run continuously. Each run walks every app in `MONITORED_APPS`, checks its
health and logs, and sends at most one Slack message per app.

## Requirements

- Python 3.13
- A Heroku account/API key with access to every monitored app
- A Postgres database (for tracking what's already been reported)
- A Slack Incoming Webhook

## Setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in real values
```

Environment variables are loaded from `.env` automatically via
`python-dotenv`; `.env` is gitignored so real secrets never get committed.

| Var | Required | Purpose |
|---|---|---|
| `HEROKU_API_KEY` | yes | `heroku auth:token`, from an account with access to every app in `MONITORED_APPS` |
| `DATABASE_URL` | yes (unless `DRY_RUN`) | Postgres connection string used to track what's already been reported |
| `SLACK_WEBHOOK_URL` | yes (unless `DRY_RUN`) | Incoming Webhook URL for the target Slack channel |
| `REPORT_WARNINGS` | no | `true` to also report warning lines (default `false`) |
| `LOG_SESSION_LINES` | no | Log lines fetched per app per run (default `1500`) |
| `LOG_LOOKBACK_HOURS` | no | Only report lines from within this many hours of now (default `6`) |
| `DRY_RUN` | no | `true` to print Slack messages instead of sending, and skip the database (default `false`) |

## Running

```bash
python main.py
```

To try it out locally without sending real Slack messages or touching the
database:

```bash
DATABASE_URL= DRY_RUN=true python main.py
```

## Deploying to Heroku

```bash
heroku create m2m-log-monitor
heroku addons:create heroku-postgresql:mini
heroku addons:create scheduler:standard
heroku config:set HEROKU_API_KEY=... SLACK_WEBHOOK_URL=...
git push heroku main
```

Then open the scheduler dashboard and add a job:

```bash
heroku addons:open scheduler
```

- Command: `python main.py`
- Frequency: every 6 hours

## Tests

```bash
pip install pytest
pytest
```
