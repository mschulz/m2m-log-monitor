"""Parsing and classification of Heroku Logplex log output.

A Heroku log session returns plain text, one record per line, in the same
format `heroku logs` prints, e.g.:

    2024-05-01T12:00:00.123456+00:00 app[web.1]: Something happened
    2024-05-01T12:00:00.654321+00:00 heroku[web.1]: State changed from up to crashed
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re

LINE_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+"
    r"(?P<source>[^\[\s]+)\[(?P<dyno>[^\]]+)\]:\s*"
    r"(?P<message>.*)$"
)

ERROR_RE = re.compile(
    r"\b(error|err|exception|traceback|critical|fatal)\b", re.IGNORECASE
)
WARNING_RE = re.compile(r"\b(warn|warning)\b", re.IGNORECASE)


@dataclass(frozen=True)
class LogLine:
    timestamp: datetime | None
    source: str
    dyno: str
    message: str
    raw: str

    @property
    def hash(self):
        return hashlib.sha256(self.raw.encode("utf-8", errors="replace")).hexdigest()


def _parse_timestamp(raw_timestamp):
    try:
        text = raw_timestamp
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def parse_log_text(raw_text):
    """Parse raw Logplex text into a list of LogLine records, in file order.

    Lines that don't match the expected `source[dyno]: message` shape are
    skipped (e.g. blank lines, partial frames) rather than raising.
    """
    lines = []
    for raw_line in raw_text.splitlines():
        if not raw_line.strip():
            continue
        match = LINE_RE.match(raw_line)
        if not match:
            continue
        lines.append(
            LogLine(
                timestamp=_parse_timestamp(match.group("timestamp")),
                source=match.group("source"),
                dyno=match.group("dyno"),
                message=match.group("message"),
                raw=raw_line,
            )
        )
    return lines


def is_error_line(line: LogLine) -> bool:
    return bool(ERROR_RE.search(line.message))


def is_warning_line(line: LogLine) -> bool:
    return bool(WARNING_RE.search(line.message))


def classify(lines, include_warnings):
    """Split lines into (errors, warnings) preserving order.

    A line matching both patterns is counted only as an error. `warnings` is
    always `[]` when `include_warnings` is False.
    """
    errors = []
    warnings = []
    for line in lines:
        if is_error_line(line):
            errors.append(line)
        elif include_warnings and is_warning_line(line):
            warnings.append(line)
    return errors, warnings


def newest_line(lines):
    """Return the line with the latest timestamp, breaking ties by list order.

    Falls back to the last line in the list if none have a parseable
    timestamp (so the watermark still advances).
    """
    timestamped = [line for line in lines if line.timestamp is not None]
    if not timestamped:
        return lines[-1] if lines else None
    return max(timestamped, key=lambda line: line.timestamp)


def filter_since(lines, cutoff):
    """Return only lines at or after `cutoff`; lines with no parseable timestamp are kept.

    Bounds how far back a report can reach after a watermark reset or a
    first-ever run, so results aren't dominated by log lines from days
    earlier still sitting in Heroku's rolling log buffer.
    """
    return [line for line in lines if line.timestamp is None or line.timestamp >= cutoff]


def lines_after(lines, after_timestamp, after_hash):
    """Return lines newer than the given watermark.

    `after_timestamp` may be None (no prior watermark -> return all lines).
    Lines with no parseable timestamp are always included, since they can't
    be reliably compared against the watermark.
    """
    if after_timestamp is None:
        return list(lines)
    kept = []
    for line in lines:
        if line.timestamp is None:
            kept.append(line)
            continue
        if line.timestamp > after_timestamp:
            kept.append(line)
        elif line.timestamp == after_timestamp and line.hash != after_hash:
            kept.append(line)
    return kept
