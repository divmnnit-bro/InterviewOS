from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, WindowIn, WindowOut


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    capacity: int = Field(gt=0, le=500)
    location: str | None = Field(default=None, max_length=160)


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    capacity: int | None = Field(default=None, gt=0, le=500)
    location: str | None = Field(default=None, max_length=160)
    is_active: bool | None = None


class RoomOut(ORMModel):
    id: uuid.UUID
    name: str
    capacity: int
    location: str | None
    is_active: bool


class AvailabilityReplace(BaseModel):
    """Replaces ALL windows. For a room, an empty list means open the whole drive window."""

    windows: list[WindowIn] = Field(max_length=500)


class AvailabilityOut(BaseModel):
    windows: list[WindowOut]
