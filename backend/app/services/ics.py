"""iCalendar (RFC 5545) export. Pure: plain values in, text out."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

PRODID = "-//InterviewOS//Interview Scheduling//EN"


@dataclass(frozen=True)
class IcsEvent:
    uid: str
    start: datetime
    end: datetime
    summary: str
    description: str = ""
    location: str = ""
    sequence: int = 0          # raise when the event changes so calendars update it
    cancelled: bool = False
    stamp: datetime | None = None


def _utc(dt: datetime) -> str:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("ICS datetimes must be timezone-aware")
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def escape_text(value: str) -> str:
    """Escape a TEXT value. Newlines become \\n, which also stops header/line injection."""
    return (
        value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    )


def fold(line: str) -> str:
    """Fold to 75 octets per line (continuations start with one space), never splitting a character."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    cur = b""
    limit = 75
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > limit:
            parts.append(cur.decode("utf-8"))
            cur, limit = b, 74            # continuation lines lose one octet to the leading space
        else:
            cur += b
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def render_calendar(events: list[IcsEvent], *, method: str = "PUBLISH") -> str:
    now = datetime.now(timezone.utc)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", f"METHOD:{method}"]
    for e in events:
        if e.end <= e.start:
            raise ValueError("event must end after it starts")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{escape_text(e.uid)}",
            f"DTSTAMP:{_utc(e.stamp or now)}",
            f"DTSTART:{_utc(e.start)}",
            f"DTEND:{_utc(e.end)}",
            f"SUMMARY:{escape_text(e.summary)}",
        ]
        if e.description:
            lines.append(f"DESCRIPTION:{escape_text(e.description)}")
        if e.location:
            lines.append(f"LOCATION:{escape_text(e.location)}")
        lines += [
            f"SEQUENCE:{e.sequence}",
            f"STATUS:{'CANCELLED' if e.cancelled else 'CONFIRMED'}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"
