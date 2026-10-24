"""Self-booking. The `/booking/{token}` routes need no login: the signed link is the credential."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator
from app.core.security import decode_booking_token
from app.db.database import get_db
from app.models import Room
from app.schemas.booking import (
    BookedOut,
    ConfirmRequest,
    IssueLinksOut,
    IssueLinksRequest,
    LinkOut,
    OffersOut,
    SkippedOut,
    SlotOut,
)
from app.services import booking as svc
from app.services.errors import InvalidLink
from app.services.interviews import booked_out, ics_for

router = APIRouter(tags=["booking"])

_KEY_RE = re.compile(r"^[A-Za-z0-9_.:\-]{8,64}$")


def _claims(token: str):
    claims = decode_booking_token(token)
    if claims is None:
        raise InvalidLink("this booking link is not valid or has expired")
    return claims


@router.post("/drives/{drive_id}/booking-links", response_model=IssueLinksOut,
             dependencies=[Depends(require_coordinator)])
def issue_links(drive_id: uuid.UUID, body: IssueLinksRequest, db: Session = Depends(get_db)) -> IssueLinksOut:
    """Create booking links for candidates who still need a slot in their current round."""
    links, skipped = svc.issue_links(db, drive_id, body.candidate_ids, body.ttl_hours)
    return IssueLinksOut(
        links=[LinkOut(candidate_id=l.candidate_id, token=l.token, path=f"/booking/{l.token}") for l in links],
        skipped=[SkippedOut(**s) for s in skipped],
    )


@router.get("/booking/{token}", response_model=OffersOut)
def slots(token: str, limit: int = Query(50, ge=1, le=200), after: datetime | None = None,
          db: Session = Depends(get_db)) -> OffersOut:
    """Free slots right now. Offers are a convenience: booking rechecks everything."""
    claims = _claims(token)
    drive, booked, offers = svc.offers_for(db, claims, limit=limit, after=after)
    stage = next(s for s in drive.stages if s.id == claims.stage_id)
    return OffersOut(
        stage_name=stage.name, duration_minutes=stage.duration_minutes, timezone=drive.timezone,
        booked=booked_out(booked) if booked else None,
        slots=[SlotOut(start=o.start, end=o.end) for o in offers],
    )


@router.post("/booking/{token}/confirm", response_model=BookedOut)
def confirm(token: str, body: ConfirmRequest, response: Response,
            idempotency_key: str = Header(..., alias="Idempotency-Key"),
            db: Session = Depends(get_db)) -> BookedOut:
    """Book a slot. Retrying with the same Idempotency-Key and slot returns the same interview (200)."""
    if not _KEY_RE.match(idempotency_key):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Idempotency-Key must be 8-64 characters: letters, digits, _ . : -")
    iv, created = svc.book(db, _claims(token), body.start, idempotency_key)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return booked_out(iv)


@router.get("/booking/{token}/ics")
def booking_ics(token: str, db: Session = Depends(get_db)) -> Response:
    claims = _claims(token)
    iv = svc.existing_booking(db, claims)
    if iv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "nothing is booked for this link yet")
    return Response(ics_for(iv), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="interview.ics"'})
