from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_coordinator
from app.db.database import get_db
from app.models import User
from app.schemas.analytics import (
    AnalyticsOverviewOut,
    DriveAnalyticsOut,
    InterviewersAnalyticsOut,
    StagesAnalyticsOut,
)
from app.services import analytics as analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_coordinator)])


@router.get("/overview", response_model=AnalyticsOverviewOut)
def get_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
    refresh: Annotated[bool, Query(description="Force refresh cache")] = False,
    drive_id: Annotated[uuid.UUID | None, Query(description="Limit upcoming interviews to a drive")] = None,
) -> AnalyticsOverviewOut:
    """Get global platform analytics overview across all recruitment drives."""
    return analytics_service.get_overview_analytics(db, force_refresh=refresh, drive_id=drive_id)


@router.get("/drives/{drive_id}", response_model=DriveAnalyticsOut)
def get_drive_analytics(
    drive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
    refresh: Annotated[bool, Query(description="Force refresh cache")] = False,
) -> DriveAnalyticsOut:
    """Get detailed progression funnel, interview completion, and room utilization for a drive."""
    return analytics_service.get_drive_analytics(db, drive_id, force_refresh=refresh)


@router.get("/stages/{drive_id}", response_model=StagesAnalyticsOut)
def get_stages_analytics(
    drive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
    refresh: Annotated[bool, Query(description="Force refresh cache")] = False,
) -> StagesAnalyticsOut:
    """Get stage-by-stage conversion, dropoff rates, and score distributions."""
    return analytics_service.get_stages_analytics(db, drive_id, force_refresh=refresh)


@router.get("/interviewers", response_model=InterviewersAnalyticsOut)
def get_interviewers_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_coordinator),
    refresh: Annotated[bool, Query(description="Force refresh cache")] = False,
) -> InterviewersAnalyticsOut:
    """Get interviewer workload distribution, capacity utilization, and calibration."""
    return analytics_service.get_interviewers_analytics(db, force_refresh=refresh)
