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


def test_is_noise_line_matches_pg_hba_scanner_noise():
    raw = (
        'FATAL: no pg_hba.conf entry for host "1.2.3.4", '
        'user "postgres", database "postgres", no encryption'
    )
    line = log_parser.LogLine(
        timestamp=None, source="heroku-postgres", dyno="db", message=raw, raw=raw
    )
    assert log_parser.is_noise_line(line)


def test_classify_drops_pg_hba_scanner_noise_despite_fatal_keyword():
    raw = (
        "2024-05-01T12:00:00.000000+00:00 heroku-postgres[db]: FATAL: "
        'no pg_hba.conf entry for host "1.2.3.4", user "postgres", '
        'database "postgres", no encryption\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_drops_postgres_protocol_scanner_noise():
    raw = (
        "2026-07-17T23:09:40.000000+00:00 app[postgres.1953744]: FATAL:  "
        "unsupported frontend protocol 16.0: server supports 3.0 to 3.0\n"
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_drops_postgres_missing_username_scanner_noise():
    raw = (
        "2026-07-18T01:11:38.000000+00:00 app[postgres.1971921]: FATAL:  "
        "no PostgreSQL user name specified in startup packet\n"
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_drops_postgres_default_user_auth_scanner_noise():
    raw = (
        "2026-07-18T00:22:35.000000+00:00 app[postgres.1965022]: FATAL:  "
        'password authentication failed for user "postgres"\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_keeps_password_auth_failure_for_non_default_user():
    raw = (
        "2026-07-18T00:22:35.000000+00:00 app[postgres.1965022]: FATAL:  "
        'password authentication failed for user "app_prod_user"\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert len(errors) == 1


def test_classify_drops_wordpress_scanner_noise_on_web_and_router_lines():
    raw = (
        '2026-07-17T23:42:57.127429+00:00 app[web.1]: INFO:     172.202.76.205:0 - '
        '"GET /wp-includes/registration-exception.php HTTP/1.1" 404 Not Found\n'
        '2026-07-17T23:42:57.127724+00:00 heroku[router]: at=info method=GET '
        'path="/wp-includes/registration-exception.php" host=rating.maid2match.com.au '
        'status=404\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_drops_uvicorn_access_log_despite_keyword_in_path():
    raw = (
        '2026-07-17T18:49:36.131488+00:00 app[web.1]: INFO:     20.226.26.5:0 - '
        '"GET /error.php?phpshells HTTP/1.1" 404 Not Found\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_drops_router_at_info_despite_keyword_in_path():
    raw = (
        '2026-07-17T18:49:36.131827+00:00 heroku[router]: at=info method=GET '
        'path="/error.php?phpshells" host=rating.lawn.com.au status=404\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert errors == []
    assert warnings == []


def test_classify_keeps_router_at_error_lines():
    raw = (
        '2026-07-17T18:49:36.131827+00:00 heroku[router]: at=error code=H12 '
        'desc="Request timeout" method=GET path="/slow" host=rating.lawn.com.au\n'
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert len(errors) == 1


def test_classify_keeps_uvicorn_error_level_lines():
    raw = (
        "2026-07-17T18:49:36.131827+00:00 app[web.1]: ERROR:    Exception in "
        "ASGI application\n"
    )
    lines = log_parser.parse_log_text(raw)
    errors, warnings = log_parser.classify(lines, include_warnings=True)
    assert len(errors) == 1


def test_classify_drops_regional_access_boundary_noise():
    raw = (
        "2026-07-17T10:00:35.120983+00:00 app[scheduler.6392]: Regional Access "
        "Boundary HTTP request failed after retries: response_data={'error': "
        "{'code': 403, 'message': 'Permission denied on the service account.', "
        "'status': 'PERMISSION_DENIED'}}, retryable_error=False\n"
    )
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


def test_filter_since_drops_lines_older_than_cutoff():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    cutoff = datetime(2024, 5, 1, 12, 0, 3, tzinfo=timezone.utc)
    kept = log_parser.filter_since(lines, cutoff)
    assert [line.message for line in kept] == [
        "Traceback (most recent call last):",
        "WARNING: deprecated config used",
        "Request completed normally",
    ]


def test_filter_since_keeps_lines_with_no_parseable_timestamp():
    raw = "not-a-timestamp app[web.1]: mystery line\n" + SAMPLE_LOG
    lines = log_parser.parse_log_text(raw)
    cutoff = datetime(2099, 1, 1, tzinfo=timezone.utc)
    kept = log_parser.filter_since(lines, cutoff)
    assert [line.message for line in kept] == ["mystery line"]


def test_lines_after_filters_out_already_seen_lines():
    lines = log_parser.parse_log_text(SAMPLE_LOG)
    watermark_line = lines[2]  # the "ERROR: something broke" line
    kept = log_parser.lines_after(lines, watermark_line.timestamp, watermark_line.hash)
    assert [line.message for line in kept] == [
        "Traceback (most recent call last):",
        "WARNING: deprecated config used",
        "Request completed normally",
    ]
