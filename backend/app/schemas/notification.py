from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class NotificationOut(ORMModel):
    id: uuid.UUID
    type: str
    title: str
    message: str
    payload: dict[str, Any]
    is_read: bool
    created_at: datetime
