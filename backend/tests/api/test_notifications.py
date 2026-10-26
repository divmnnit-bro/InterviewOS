import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import (
    Interview, InterviewStatus, Notification, NotificationChannel, NotificationStatus, PanelAssignment, User,
)
from app.core.config import settings
from app.services import notifications
from app.services.notifications import SMTPEmailSender

from .conftest import T0


def confirmed_interview(db, drive, *, with_panel=True):
    """A CONFIRMED interview inserted directly, i.e. with no notifications yet."""
    from app.models import InterviewStage, User
    stage = db.scalars(select(InterviewStage).where(InterviewStage.drive_id == uuid.UUID(drive["id"]))).one()
    iv = Interview(candidate_id=uuid.UUID(drive["candidates"][0]), stage_id=stage.id, room_id=uuid.UUID(drive["room"]),
                   start_time=T0 + timedelta(hours=9), end_time=T0 + timedelta(hours=9, minutes=30),
                   status=InterviewStatus.CONFIRMED)
    if with_panel:
        interviewer = db.scalars(select(User).where(User.email == "iv0@example.com")).one()
        iv.panel = [PanelAssignment(interviewer_id=interviewer.id, start_time=iv.start_time, end_time=iv.end_time)]
    db.add(iv)
    db.commit()
    return iv


def rows_for(db, iv):
    return db.scalars(select(Notification).where(
        Notification.payload["interview_id"].as_string() == str(iv.id))).all()


def test_notify_is_idempotent(db, drive):
    iv = confirmed_interview(db, drive)
    assert notifications.notify_booking_confirmed(db, iv.id) is True
    assert notifications.notify_booking_confirmed(db, iv.id) is True
    rows = rows_for(db, iv)
    assert len(rows) == 2 and {r.status for r in rows} == {NotificationStatus.SENT}   # candidate + panelist


def test_backfill_creates_notifications_a_crash_would_have_lost(db, drive):
    iv = confirmed_interview(db, drive)
    assert rows_for(db, iv) == []
    assert notifications.backfill_missing(db) >= 1      # (>= : a shared dev database may hold other cases)
    assert len(rows_for(db, iv)) == 2
    notifications.backfill_missing(db)
    assert len(rows_for(db, iv)) == 2                   # running it again creates no duplicates


def test_smtp_alerts_are_queued_only_when_configured(db, drive, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_FROM", "alerts@example.test")
    iv = confirmed_interview(db, drive)
    assert notifications.notify_booking_confirmed(db, iv.id) is True
    rows = rows_for(db, iv)
    assert len(rows) == 4
    assert sum(row.channel == NotificationChannel.EMAIL and row.status == NotificationStatus.PENDING for row in rows) == 2
    assert notifications.notify_booking_confirmed(db, iv.id) is True
    assert len(rows_for(db, iv)) == 4


def test_smtp_sender_uses_tls_and_resolved_recipient(db, drive, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_FROM", "alerts@example.test")
    monkeypatch.setattr(settings, "SMTP_USE_SSL", False)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", True)
    monkeypatch.setattr(settings, "SMTP_USERNAME", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    user = db.scalars(select(User).where(User.email == "c0@example.com")).one()
    notification = Notification(
        user_id=user.id, type="booking_confirmed", title="Interview confirmed",
        message="Your interview is confirmed.", payload={}, channel=NotificationChannel.EMAIL,
        status=NotificationStatus.PENDING,
    )
    calls = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls["connection"] = (host, port, timeout)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def starttls(self, **kwargs):
            calls["tls"] = True
        def send_message(self, message):
            calls["to"] = message["To"]
            calls["subject"] = message["Subject"]

    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", FakeSMTP)
    SMTPEmailSender(db).send(notification)
    assert calls["connection"][:2] == ("smtp.test", 587)
    assert calls["tls"] is True
    assert calls["to"] == user.email
    assert calls["subject"] == "Interview confirmed"


def test_a_failed_notification_never_touches_the_booking(db, drive, monkeypatch):
    iv = confirmed_interview(db, drive)
    monkeypatch.setattr(notifications, "_lock_interview_notifications",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db hiccup")))
    assert notifications.notify_booking_confirmed(db, iv.id) is False
    db.refresh(iv)
    assert iv.status == InterviewStatus.CONFIRMED


class Flaky:
    def __init__(self, fail_times):
        self.fail_times, self.calls = fail_times, 0

    def send(self, n):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("smtp down")


def pending_email(db, user_id):
    n = Notification(user_id=user_id, type="x", title="t", message="m", payload={},
                     channel=NotificationChannel.EMAIL, status=NotificationStatus.PENDING)
    db.add(n)
    db.commit()
    return n


def test_retry_with_backoff_then_success(db, drive):
    n = pending_email(db, uuid.UUID(drive["candidates"][0]))
    sender = Flaky(fail_times=2)
    senders = {NotificationChannel.EMAIL: sender}
    t = datetime.now(timezone.utc)

    assert notifications.deliver_pending(db, senders, now=t)["failed"] == 1
    assert (n.status, n.attempts) == (NotificationStatus.FAILED, 1) and "smtp down" in n.last_error
    assert notifications.deliver_pending(db, senders, now=t)["waiting"] == 1          # too soon to retry
    assert sender.calls == 1
    assert notifications.deliver_pending(db, senders, now=t + timedelta(hours=2))["failed"] == 1
    assert notifications.deliver_pending(db, senders, now=t + timedelta(hours=4))["sent"] == 1
    assert n.status == NotificationStatus.SENT and n.attempts == 3 and n.last_error is None


def test_gives_up_after_max_attempts_and_ignores_unregistered_channels(db, drive):
    uid = uuid.UUID(drive["candidates"][0])
    dead = pending_email(db, uid)
    sender = Flaky(fail_times=99)
    t = datetime.now(timezone.utc)
    for i in range(notifications.MAX_ATTEMPTS + 2):
        notifications.deliver_pending(db, {NotificationChannel.EMAIL: sender}, now=t + timedelta(hours=3 * (i + 1)))
    assert sender.calls == notifications.MAX_ATTEMPTS and dead.status == NotificationStatus.FAILED
    other = Notification(user_id=uid, type="x", title="t", message="m", payload={},
                         channel=NotificationChannel.CALENDAR, status=NotificationStatus.PENDING)
    db.add(other)
    db.commit()
    notifications.deliver_pending(db, {NotificationChannel.EMAIL: sender})
    assert (other.status, other.attempts) == (NotificationStatus.PENDING, 0)
