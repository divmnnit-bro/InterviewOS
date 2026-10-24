from datetime import datetime, timedelta, timezone

import pytest

from app.services.ics import IcsEvent, escape_text, fold, render_calendar

T = datetime(2026, 11, 2, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def ev(**kw):
    base = dict(uid="abc@interviewos", start=T, end=T + timedelta(minutes=30), summary="Technical round",
                stamp=datetime(2026, 10, 23, tzinfo=timezone.utc))
    base.update(kw)
    return IcsEvent(**base)


def test_times_are_converted_to_utc_and_lines_end_crlf():
    out = render_calendar([ev()])
    assert "DTSTART:20261102T043000Z" in out and "DTEND:20261102T050000Z" in out
    assert out.startswith("BEGIN:VCALENDAR\r\n") and out.endswith("END:VCALENDAR\r\n")
    assert "\n" not in out.replace("\r\n", "")


def test_text_is_escaped_and_cannot_inject_lines():
    assert escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    out = render_calendar([ev(summary="x\r\nATTENDEE:mailto:evil@example.com")])
    assert "\r\nATTENDEE" not in out


def test_long_lines_fold_at_75_octets_without_splitting_characters():
    line = "DESCRIPTION:" + "é" * 100
    folded = fold(line)
    for part in folded.split("\r\n"):
        assert len(part.encode()) <= 75
    assert folded.replace("\r\n ", "") == line


def test_cancelled_and_sequence():
    out = render_calendar([ev(cancelled=True, sequence=3)], method="CANCEL")
    assert "STATUS:CANCELLED" in out and "SEQUENCE:3" in out and "METHOD:CANCEL" in out


def test_naive_datetimes_and_bad_ranges_rejected():
    with pytest.raises(ValueError):
        render_calendar([ev(start=datetime(2026, 11, 2, 10), end=datetime(2026, 11, 2, 11))])
    with pytest.raises(ValueError):
        render_calendar([ev(end=T)])
