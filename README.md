# m2m-log-monitor

Standalone Python 3.13 program that checks a fleet of Heroku apps every 6
hours for:

- Error log lines (always reported)
- Warning log lines (only if `REPORT_WARNINGS=true`)
- Crashed/down dynos
- Skips apps entirely while they're in maintenance mode

Findings are posted to the `#m2m-system-alerts` Slack channel via an
Incoming Webhook.

The list of monitored apps lives in `config.py` (`MONITORED_APPS`).

## How it works

Each run, for every app in `MONITORED_APPS`:

1. Check maintenance mode (`maintenance` field on `GET /apps/{app}`). If
   enabled, skip the app entirely for this run.
2. Check dyno states (`GET /apps/{app}/dynos`). Any dyno in `crashed` or
   `down` state triggers a Slack alert.
3. Open a Logplex log session (`POST /apps/{app}/log-sessions`) and fetch the
   recent log buffer.
4. Compare against the last-seen watermark stored in Postgres (timestamp +
   line hash of the newest line from the previous run) to find genuinely new
   lines, then drop anything older than `LOG_LOOKBACK_HOURS` (default 6,
   matching the Scheduler cadence) so a missing/reset watermark can't dredge
   up days-old errors still sitting in the log buffer. Remaining lines are
   classified as error/warning by keyword, after dropping known-noisy lines
   (e.g. `no pg_hba.conf entry for host` from internet port-scanners hitting
   Heroku Postgres addons) that would otherwise match the error keywords —
   see `log_parser.NOISE_PATTERNS`.
5. Post one batched Slack message per app with any new error/warning lines
   found, and advance the watermark. If the app had errors last run and this
   run comes back clean, post a "resolved" message instead.

**Known limitation:** Heroku's log-session API returns a rolling buffer, not
a true time-range query. A very high-volume dyno could produce enough log
output to roll past 6 hours of history between runs, and those lines would
never be seen. This is an accepted tradeoff, not something this program works
around.

## Local setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in real values
```

Environment variables are loaded from `.env` automatically via
`python-dotenv` (see `.env.example` for the full list); it's gitignored so
real secrets never get committed. Required environment variables:

| Var | Required | Purpose |
|---|---|---|
| `HEROKU_API_KEY` | yes | `heroku auth:token`, from an account with access to every app in `MONITORED_APPS` |
| `DATABASE_URL` | yes (unless `DRY_RUN`) | Postgres connection string for watermark storage |
| `SLACK_WEBHOOK_URL` | yes (unless `DRY_RUN`) | Incoming Webhook URL for `#m2m-system-alerts` |
| `REPORT_WARNINGS` | no | `true` to also report warning lines (default `false`) |
| `LOG_SESSION_LINES` | no | Log lines fetched per app per run (default `1500`) |
| `LOG_LOOKBACK_HOURS` | no | Only report lines from within this many hours of now (default `6`) |
| `DRY_RUN` | no | `true` to print Slack payloads instead of sending, and skip the DB (default `false`) |

Dry run locally against real Heroku apps without touching Slack or Postgres:

```bash
DATABASE_URL= HEROKU_API_KEY=... DRY_RUN=true python main.py
```

`DRY_RUN=true` only suppresses the Slack POST (prints instead); it does
**not** skip Postgres writes. If `.env` has a real `DATABASE_URL`, override
it to empty for the dry run so the production watermark table isn't
mutated — the app already treats a missing `DATABASE_URL` as "run without
a state store" (see `main.check_app`'s `has_state_store` check).

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
- Frequency: Every 6 hours

## Tests

```bash
pip install pytest
pytest
```
