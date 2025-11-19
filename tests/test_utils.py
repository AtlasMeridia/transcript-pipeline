import os
from pathlib import Path

from src.utils import (
    sanitize_filename,
    format_timestamp,
    ensure_output_path,
    retry_with_backoff,
    format_duration,
)


def test_sanitize_filename_basic():
    assert sanitize_filename("Simple Title") == "simple-title"


def test_sanitize_filename_strips_bad_chars_and_truncates():
    title = "A*Very/Strange:Title?" * 20
    slug = sanitize_filename(title, max_length=50)
    assert "/" not in slug
    assert "*" not in slug
    assert len(slug) <= 50
    assert slug != ""


def test_sanitize_filename_empty_fallback():
    assert sanitize_filename("!!!") == "untitled"


def test_format_timestamp():
    assert format_timestamp(0) == "[00:00:00]"
    assert format_timestamp(65) == "[00:01:05]"
    assert format_timestamp(3661) == "[01:01:01]"


def test_ensure_output_path_within_directory(tmp_path):
    base = tmp_path / "out"
    path = ensure_output_path(str(base), "file.txt")
    assert path.parent == base
    assert path.name == "file.txt"
    assert base.exists()


def test_ensure_output_path_rejects_escape(tmp_path):
    base = tmp_path / "out"
    # Path that tries to escape the base directory
    filename = "../evil.txt"
    try:
        ensure_output_path(str(base), filename)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for escaping path")


def test_retry_with_backoff_success():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("temporary")
        return "ok"

    result = retry_with_backoff(flaky, max_retries=3, initial_delay=0.01)
    assert result == "ok"
    assert calls["count"] == 2


def test_retry_with_backoff_exhausts():
    def always_fail():
        raise RuntimeError("fail")

    try:
        retry_with_backoff(always_fail, max_retries=2, initial_delay=0.01)
    except RuntimeError:
        return
    raise AssertionError("Expected RuntimeError after retries")


def test_format_duration_various():
    assert format_duration(0) == "0s"
    assert format_duration(59) == "59s"
    assert format_duration(60) == "1m"
    assert format_duration(61) == "1m 1s"
    assert format_duration(3600) == "1h"
    assert format_duration(3661) == "1h 1m 1s"


