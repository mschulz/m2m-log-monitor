"""Configuration for the Heroku multi-app log monitor."""
import os

from dotenv import load_dotenv

load_dotenv()

MONITORED_APPS = [
    "lca-booking-system",
    "lca-klaviyo-addresses",
    "lca-launch27",
    "lca-proxy",
    "m2m-booking-system",
    "m2m-bookings-mcp",
    "m2m-forecast-bookings",
    "m2m-hubspot",
    "m2m-klaviyo-addresses",
    "m2m-launch27",
    "m2m-lead-data",
    "m2m-new-sales",
    "m2m-pays",
    "m2m-proxy",
    "m2m-ratings",
    "m2m-sales-data",
    "m2m-sales-report",
    "m2m-sandbox-proxy",
    "m2m-staff-retention",
    "m2m-team-details",
    "m2m-time-sheets",
    "m2m-zip2location",
    "m2mnz-bookings-mcp",
    "m2mnz-proxy",
    "m2mnz-sales-report",
    "m2mnz-team-details",
    "mlc-lead-data",
    "mlc-ratings",
    "mlc-zip2location",
]

SLACK_CHANNEL_NAME = "#m2m-system-alerts"

HEROKU_API_KEY = os.environ.get("HEROKU_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

REPORT_WARNINGS = os.environ.get("REPORT_WARNINGS", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

DRY_RUN = os.environ.get("DRY_RUN", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

LOG_SESSION_LINES = int(os.environ.get("LOG_SESSION_LINES", "1500"))

DOWN_DYNO_STATES = {"crashed", "down"}

HEROKU_API_BASE = "https://api.heroku.com"
HEROKU_ACCEPT_HEADER = "application/vnd.heroku+json; version=3"

HTTP_TIMEOUT_SECONDS = 30
