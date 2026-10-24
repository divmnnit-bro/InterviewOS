from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_coordinator
from app.db.database import get_db
from app.models import Availability, Interviewer, Room, RoomAvailability, User, UserRole
from app.schemas.common import WindowOut
from app.schemas.room import AvailabilityOut, AvailabilityReplace, RoomCreate, RoomOut, RoomUpdate

router = APIRouter(tags=["rooms and availability"])


def _commit(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message)


def _room(db: Session, room_id: uuid.UUID) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "room not found")
    return room


# ---------------------------------------------------------------- rooms


@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_coordinator)])
def create_room(body: RoomCreate, db: Session = Depends(get_db)) -> Room:
    room = Room(**body.model_dump())
    db.add(room)
    _commit(db, "a room with that name already exists")
    return room


@router.get("/rooms", response_model=list[RoomOut], dependencies=[Depends(require_coordinator)])
def list_rooms(db: Session = Depends(get_db)) -> list[Room]:
    return list(db.scalars(select(Room).order_by(Room.name)))


@router.patch("/rooms/{room_id}", response_model=RoomOut, dependencies=[Depends(require_coordinator)])
def update_room(room_id: uuid.UUID, body: RoomUpdate, db: Session = Depends(get_db)) -> Room:
    room = _room(db, room_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None or k == "location":
            setattr(room, k, v)
    _commit(db, "a room with that name already exists")
    return room


@router.get("/rooms/{room_id}/availability", response_model=AvailabilityOut,
            dependencies=[Depends(require_coordinator)])
def read_room_availability(room_id: uuid.UUID, db: Session = Depends(get_db)) -> AvailabilityOut:
    _room(db, room_id)
    rows = db.scalars(select(RoomAvailability).where(RoomAvailability.room_id == room_id)
                      .order_by(RoomAvailability.start_time))
    return AvailabilityOut(windows=[WindowOut.model_validate(r) for r in rows])


@router.put("/rooms/{room_id}/availability", response_model=AvailabilityOut,
            dependencies=[Depends(require_coordinator)])
def replace_room_availability(room_id: uuid.UUID, body: AvailabilityReplace,
                              db: Session = Depends(get_db)) -> AvailabilityOut:
    """Replace every window. No windows at all means the room is open for the whole drive."""
    _room(db, room_id)
    db.execute(delete(RoomAvailability).where(RoomAvailability.room_id == room_id))
    db.add_all(RoomAvailability(room_id=room_id, start_time=w.start_time, end_time=w.end_time)
               for w in body.windows)
    db.commit()
    return AvailabilityOut(windows=[WindowOut(start_time=w.start_time, end_time=w.end_time)
                                    for w in sorted(body.windows, key=lambda w: w.start_time)])


# ------------------------------------------------- candidate / interviewer availability


def _owner_check(db: Session, user_id: uuid.UUID, actor: User) -> User:
    """Coordinators may edit anyone's availability; everyone else only their own."""
    if actor.role != UserRole.COORDINATOR and actor.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "you can only edit your own availability")
    target = db.get(User, user_id)
    if target is None or target.role == UserRole.COORDINATOR:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return target


@router.get("/users/{user_id}/availability", response_model=AvailabilityOut)
def read_availability(user_id: uuid.UUID, db: Session = Depends(get_db),
                      actor: User = Depends(get_current_user)) -> AvailabilityOut:
    _owner_check(db, user_id, actor)
    rows = db.scalars(select(Availability).where(Availability.owner_id == user_id)
                      .order_by(Availability.start_time))
    return AvailabilityOut(windows=[WindowOut.model_validate(r) for r in rows])


@router.put("/users/{user_id}/availability", response_model=AvailabilityOut)
def replace_availability(user_id: uuid.UUID, body: AvailabilityReplace, db: Session = Depends(get_db),
                         actor: User = Depends(get_current_user)) -> AvailabilityOut:
    """Replace every availability window for a candidate or interviewer."""
    _owner_check(db, user_id, actor)
    db.execute(delete(Availability).where(Availability.owner_id == user_id))
    db.add_all(Availability(owner_id=user_id, start_time=w.start_time, end_time=w.end_time)
               for w in body.windows)
    db.commit()
    return AvailabilityOut(windows=[WindowOut(start_time=w.start_time, end_time=w.end_time)
                                    for w in sorted(body.windows, key=lambda w: w.start_time)])
