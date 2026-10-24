from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WindowIn(BaseModel):
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def _check(self) -> "WindowIn":
        for v in (self.start_time, self.end_time):
            if v.tzinfo is None or v.utcoffset() is None:
                raise ValueError("datetimes must include a timezone offset")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class WindowOut(ORMModel):
    start_time: datetime
    end_time: datetime


def require_aware(v: datetime) -> datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("datetimes must include a timezone offset")
    return v


def require_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except Exception:
        raise ValueError(f"unknown timezone {name!r}")
    return name
