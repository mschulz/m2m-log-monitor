from datetime import datetime, timezone

import log_parser

SAMPLE_LOG = """\
2024-05-01T12:00:00.000000+00:00 heroku[web.1]: State changed from starting to up
2024-05-01T12:00:01.000000+00:00 app[web.1]: Listening on port 12345
2024-05-01T12:00:02.000000+00:00 app[web.1]: ERROR: something broke
2024-05-01T12:00:03.000000+00:00 app[web.1]: Traceback (most recent call last):
2024-05-01T12:00:04.000000+00:00 app[web.1]: WARNING: deprecated config used
2024-05-01T12:00:05.000000+00:00 app[web.1]: Request completed normally
"""


def test_parse_log_text_extracts_all_well_formed_lines():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    assert len(lines) == 6
    assert lines[0].source == "heroku"
    assert lines[0].dyno == "web.1"
    assert lines[1].message == "Listening on port 12345"


def test_parse_log_text_skips_blank_and_malformed_lines():
    raw = "\n\nnot a log line\n" + SAMPLE_LOG
    lines = log_parser.parse_log_text(raw)
    assert len(lines) == 6


def test_classify_finds_errors_and_ignores_warnings_when_disabled():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    errors, warnings = log_parser.classify(lines, include_warnings=False)
    assert len(errors) == 2
    assert warnings == []
    assert "ERROR" in errors[0].message
    assert "Traceback" in errors[1].message


def test_classify_includes_warnings_when_enabled():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert len(errors) == 2
    assert len(warnings) == 1
    assert "WARNING" in warnings[0].message


def test_classify_has_no_false_positive_on_ordinary_lines():
    raw = "2024-05-01T12:00:00.000000+00:00 app[web.1]: Request completed normally\n"
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_newest_line_picks_latest_timestamp():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    newest = log_parser.newest_line(lines)
    assert newest.message == "Request completed normally"
    assert newest.timestamp == datetime(2024, 5, 1, 12, 0, 5, tzinfo=timezone.utc)


def test_lines_after_with_no_watermark_returns_all():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    kept = log_parser.lines_after(lines, None, None)
    assert len(kept) == len(lines)


def test_lines_after_filters_out_already_seen_lines():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    watermark_line = lines[2]  # the "ERROR: something broke" line
    kept = log_parser.lines_after(lines, watermark_line.timestamp, watermark_line.hash)
    assert [line.message for line in kept] == [
        "Traceback (most recent call last):",
        "WARNING: deprecated config used",
        "Request completed normally",
    ]
