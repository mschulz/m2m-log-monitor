"""Thin wrapper around the Heroku Platform API v3."""
import requests

import config


class HerokuApiError(Exception):
    """Raised when a Heroku Platform API call fails."""


def _headers():
    return {
        "Authorization": f"Bearer {config.HEROKU_API_KEY}",
        "Accept": config.HEROKU_ACCEPT_HEADER,
    }


def _get(path):
    url = f"{config.HEROKU_API_BASE}{path}"
    try:
        response = requests.get(
            url, headers=_headers(), timeout=config.HTTP_TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise HerokuApiError(f"GET {path} failed: {exc}") from exc
    if not response.ok:
        raise HerokuApiError(
            f"GET {path} returned {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def _post(path, json_body=None):
    url = f"{config.HEROKU_API_BASE}{path}"
    try:
        response = requests.post(
            url,
            headers=_headers(),
            json=json_body or {},
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise HerokuApiError(f"POST {path} failed: {exc}") from exc
    if not response.ok:
        raise HerokuApiError(
            f"POST {path} returned {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def get_maintenance_mode(app_name):
    """Return True if the app currently has maintenance mode enabled."""
    data = _get(f"/apps/{app_name}")
    return bool(data.get("maintenance"))


def get_dynos(app_name):
    """Return the list of dyno dicts currently known for the app."""
    return _get(f"/apps/{app_name}/dynos")


def create_log_session(app_name, lines=None):
    """Create a Logplex log session and return its (temporary) URL."""
    body = {
        "lines": lines or config.LOG_SESSION_LINES,
        "tail": False,
    }
    data = _post(f"/apps/{app_name}/log-sessions", body)
    logplex_url = data.get("logplex_url")
    if not logplex_url:
        raise HerokuApiError(f"log-session response missing logplex_url: {data}")
    return logplex_url


def fetch_log_text(logplex_url):
    """Fetch the raw log text from a Logplex session URL."""
    try:
        response = requests.get(logplex_url, timeout=config.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise HerokuApiError(f"GET logplex session failed: {exc}") from exc
    if not response.ok:
        raise HerokuApiError(
            f"GET logplex session returned {response.status_code}: "
            f"{response.text[:500]}"
        )
    return response.text
