"""In-app notifications, saved AFTER the booking commits, with retry.

A booking is never rolled back because a notification failed. Instead:
  * `notify_booking_confirmed` runs after the commit; on any error it logs and returns False.
  * `backfill_missing` finds confirmed interviews that never got a notification (a crash between
    the commit and the notification) and creates them, so delivery is at-least-once.
  * `deliver_pending` sends rows that are pending or failed through a per-channel `Sender`, counting
    attempts, backing off between tries, and giving up after `max_attempts`. Rows for a channel with
    no registered sender are left alone.
In-app rows are written already `sent`: being in the table IS delivery.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Interview,
    InterviewStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
)

log = logging.getLogger(__name__)

BOOKING_CONFIRMED = "booking_confirmed"
MAX_ATTEMPTS = 5


class Sender(Protocol):
    def send(self, notification: Notification) -> None:  # raise to signal failure
        ...


class InAppSender:
    def send(self, notification: Notification) -> None:
        return None


DEFAULT_SENDERS: dict[NotificationChannel, Sender] = {NotificationChannel.IN_APP: InAppSender()}


def _lock_interview_notifications(db: Session, interview_id: uuid.UUID) -> None:
    """Serialise notification creation per interview, so a retry or sweep cannot create duplicates."""
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"notify:{interview_id}", 0))))


def notify_booking_confirmed(db: Session, interview_id: uuid.UUID) -> bool:
    """Create the in-app notifications for a confirmed interview. Safe to call twice."""
    try:
        _lock_interview_notifications(db, interview_id)
        iv = db.get(Interview, interview_id, populate_existing=True)
        if iv is None or iv.status != InterviewStatus.CONFIRMED:
            db.rollback()
            return False
        tz = ZoneInfo(iv.stage.drive.timezone)
        when = iv.start_time.astimezone(tz).strftime("%a %d %b %Y, %H:%M")
        room = iv.room.name if iv.room else "to be announced"
        recipients = {iv.candidate_id: ("Interview confirmed",
                                        f"Your {iv.stage.name} interview is confirmed for {when} ({tz.key}), room: {room}.")}
        for pa in iv.panel:
            if pa.is_active:
                recipients[pa.interviewer_id] = (
                    "New interview on your calendar",
                    f"You are on the panel for a {iv.stage.name} interview on {when} ({tz.key}), room: {room}.")
        already = set(db.scalars(
            select(Notification.user_id).where(
                Notification.type == BOOKING_CONFIRMED,
                Notification.channel == NotificationChannel.IN_APP,
                Notification.payload["interview_id"].as_string() == str(iv.id),
            )
        ))
        now = datetime.now(timezone.utc)
        for uid, (title, message) in recipients.items():
            if uid in already:
                continue
            db.add(Notification(
                user_id=uid, type=BOOKING_CONFIRMED, title=title, message=message,
                payload={"interview_id": str(iv.id), "start": iv.start_time.isoformat(),
                         "end": iv.end_time.isoformat()},
                channel=NotificationChannel.IN_APP, status=NotificationStatus.SENT,
                attempts=1, sent_at=now,
            ))
        db.commit()
        return True
    except Exception:
        db.rollback()
        log.exception("could not create notifications for interview %s (the booking stands)", interview_id)
        return False


def backfill_missing(db: Session, limit: int = 100) -> int:
    """Notify confirmed interviews whose candidate has no booking notification yet."""
    has_note = (
        select(Notification.id)
        .where(
            Notification.type == BOOKING_CONFIRMED,
            Notification.user_id == Interview.candidate_id,
            Notification.payload["interview_id"].as_string() == cast(Interview.id, String),
        )
        .exists()
    )
    ids = list(db.scalars(
        select(Interview.id).where(Interview.status == InterviewStatus.CONFIRMED, ~has_note).limit(limit)
    ))
    db.rollback()
    return sum(1 for i in ids if notify_booking_confirmed(db, i))


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * 2 ** max(attempts - 1, 0), 3600))


def deliver_pending(
    db: Session, senders: dict[NotificationChannel, Sender] | None = None, *,
    now: datetime | None = None, batch: int = 50, max_attempts: int = MAX_ATTEMPTS,
) -> dict[str, int]:
    """Try to send pending/failed notifications. Returns counts. Safe to run from several workers."""
    senders = DEFAULT_SENDERS if senders is None else senders
    now = now or datetime.now(timezone.utc)
    stats = {"sent": 0, "failed": 0, "waiting": 0}
    if not senders:
        return stats
    rows = db.scalars(
        select(Notification)
        .where(
            Notification.channel.in_(list(senders)),
            or_(Notification.status == NotificationStatus.PENDING,
                Notification.status == NotificationStatus.FAILED),
            Notification.attempts < max_attempts,
        )
        .order_by(Notification.status, Notification.updated_at)
        .limit(batch)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    ).all()
    for n in rows:
        if n.status == NotificationStatus.FAILED and now - n.updated_at < _backoff(n.attempts):
            stats["waiting"] += 1
            continue
        n.attempts += 1
        try:
            senders[n.channel].send(n)
            n.status, n.sent_at, n.last_error = NotificationStatus.SENT, now, None
            stats["sent"] += 1
        except Exception as exc:  # a sender outage must never raise out of the worker
            n.status, n.last_error = NotificationStatus.FAILED, str(exc)[:500]
            stats["failed"] += 1
    db.commit()
    return stats
