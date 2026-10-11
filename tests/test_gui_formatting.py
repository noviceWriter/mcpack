from datetime import datetime, timedelta, timezone

from mcpack.gui.formatting import (
    format_count,
    format_duration,
    format_relative,
    format_size,
    fuzzy_score,
    project_url,
)
from mcpack.i18n import set_language


def test_format_count():
    assert format_count(999) == "999"
    assert format_count(1500) == "1.5K"
    assert format_count(2_300_000) == "2.3M"


def test_format_size():
    assert format_size(None) == "—"
    assert format_size(512) == "512 B"
    assert format_size(2048) == "2.0 KB"
    assert format_size(5 * 1024 * 1024) == "5.0 MB"


def test_format_duration():
    assert format_duration(None) == "—"
    assert format_duration(65) == "01:05"
    assert format_duration(3725) == "1:02:05"


def test_format_relative():
    set_language("en")
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert format_relative(now - timedelta(seconds=10), now=now) == "just now"
    assert format_relative(now - timedelta(minutes=5), now=now) == "5 min ago"
    assert format_relative(now - timedelta(hours=3), now=now) == "3 h ago"
    set_language("tr")


def test_fuzzy_score_orders_substring_first():
    assert fuzzy_score("", "anything") == 0
    assert fuzzy_score("xyz", "Library") is None
    assert fuzzy_score("lib", "Library") < fuzzy_score("lby", "Library")


def test_project_url():
    assert project_url("modrinth", "AANobbMI", "sodium") == "https://modrinth.com/project/sodium"
    assert project_url("curseforge", "238222").endswith("/projects/238222")
    assert project_url("unknown", "x") is None
