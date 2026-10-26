from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.scheduler.types import (
    Anchor,
    ProposedInterview,
    ScheduleInput,
    ScheduleResult,
)
from app.scheduler.verify import verify


@dataclass(frozen=True)
class ScheduleQualityReport:
    total_requested: int
    scheduled_count: int
    unscheduled_count: int
    completion_rate: float
    hard_constraint_violations: int
    violation_details: list[str]
    interviewer_workload_variance: float
    interviewer_workload_std_dev: float
    max_interviewer_load: int
    min_interviewer_load: int
    room_utilization_percent: float
    average_candidate_wait_hours: float
    schedule_changes_count: int
    is_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requested": self.total_requested,
            "scheduled_count": self.scheduled_count,
            "unscheduled_count": self.unscheduled_count,
            "completion_rate": round(self.completion_rate, 2),
            "hard_constraint_violations": self.hard_constraint_violations,
            "violation_details": self.violation_details,
            "interviewer_workload_variance": round(self.interviewer_workload_variance, 4),
            "interviewer_workload_std_dev": round(self.interviewer_workload_std_dev, 2),
            "max_interviewer_load": self.max_interviewer_load,
            "min_interviewer_load": self.min_interviewer_load,
            "room_utilization_percent": round(self.room_utilization_percent, 2),
            "average_candidate_wait_hours": round(self.average_candidate_wait_hours, 2),
            "schedule_changes_count": self.schedule_changes_count,
            "is_verified": self.is_verified,
        }


def compute_schedule_quality(
    inp: ScheduleInput,
    result: ScheduleResult,
    anchors: dict[Any, Anchor] | None = None,
) -> ScheduleQualityReport:
    """Compute rigorous, explainable mathematical metrics assessing the quality of a schedule."""
    violations = verify(inp, result)
    hard_violations = len(violations)
    is_verified = hard_violations == 0

    total_req = len(result.interviews) + len(result.unscheduled)
    scheduled_count = len(result.interviews)
    unscheduled_count = len(result.unscheduled)
    completion_rate = (scheduled_count / total_req * 100.0) if total_req > 0 else 100.0

    # 1. Interviewer Workload Variance & Load Spread
    # Count interviews per interviewer
    all_iv_ids = [i.id for i in inp.interviewers]
    loads = {iid: 0 for iid in all_iv_ids}
    for iv in result.interviews:
        for iid in iv.interviewer_ids:
            loads[iid] = loads.get(iid, 0) + 1

    load_values = list(loads.values()) if loads else [0]
    if len(load_values) > 1:
        variance = statistics.pvariance(load_values)
        std_dev = math.sqrt(variance)
    else:
        variance = 0.0
        std_dev = 0.0

    max_load = max(load_values) if load_values else 0
    min_load = min(load_values) if load_values else 0

    # 2. Room Utilization
    # Total room capacity hours available over the horizon
    horizon_duration = inp.config.horizon_end - inp.config.horizon_start
    horizon_hours = max(horizon_duration.total_seconds() / 3600.0, 0.1)
    total_room_available_hours = len(inp.rooms) * horizon_hours

    booked_room_hours = 0.0
    for iv in result.interviews:
        duration_hr = (iv.end - iv.start).total_seconds() / 3600.0
        booked_room_hours += duration_hr

    room_utilization_percent = (
        (booked_room_hours / total_room_available_hours * 100.0)
        if total_room_available_hours > 0
        else 0.0
    )

    # 3. Candidate Waiting Time (gap between consecutive rounds)
    candidate_interviews: dict[Any, list[ProposedInterview]] = {}
    for iv in result.interviews:
        candidate_interviews.setdefault(iv.candidate_id, []).append(iv)

    gaps: list[float] = []
    for cid, iv_list in candidate_interviews.items():
        if len(iv_list) > 1:
            sorted_ivs = sorted(iv_list, key=lambda x: x.start)
            for a, b in zip(sorted_ivs, sorted_ivs[1:]):
                gap_hours = (b.start - a.end).total_seconds() / 3600.0
                if gap_hours >= 0:
                    gaps.append(gap_hours)

    avg_wait_hours = (sum(gaps) / len(gaps)) if gaps else 0.0

    # 4. Schedule Changes Count (relative to anchors if provided)
    changes_count = 0
    if anchors:
        current_map = {(iv.candidate_id, iv.stage_id): iv for iv in result.interviews}
        for (cid, sid), a in anchors.items():
            placed = current_map.get((cid, sid))
            if placed is None:
                changes_count += 1  # Dropped
            elif placed.start != a.start or placed.room_id != a.room_id or set(placed.interviewer_ids) != set(a.interviewer_ids):
                changes_count += 1  # Moved or modified

    return ScheduleQualityReport(
        total_requested=total_req,
        scheduled_count=scheduled_count,
        unscheduled_count=unscheduled_count,
        completion_rate=completion_rate,
        hard_constraint_violations=hard_violations,
        violation_details=violations,
        interviewer_workload_variance=variance,
        interviewer_workload_std_dev=std_dev,
        max_interviewer_load=max_load,
        min_interviewer_load=min_load,
        room_utilization_percent=min(room_utilization_percent, 100.0),
        average_candidate_wait_hours=avg_wait_hours,
        schedule_changes_count=changes_count,
        is_verified=is_verified,
    )


@dataclass(frozen=True)
class ScheduleComparison:
    added_count: int
    moved_count: int
    unchanged_count: int
    cancelled_count: int
    details: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "added_count": self.added_count,
            "moved_count": self.moved_count,
            "unchanged_count": self.unchanged_count,
            "cancelled_count": self.cancelled_count,
            "details": self.details,
        }


def compare_schedules(
    existing_interviews: list[Any],
    new_interviews: list[ProposedInterview],
) -> ScheduleComparison:
    """Compare a new/proposed schedule against an existing schedule."""
    existing_map = {
        (iv.candidate_id, iv.stage_id): iv
        for iv in existing_interviews
    }
    new_map = {
        (iv.candidate_id, iv.stage_id): iv
        for iv in new_interviews
    }

    added = 0
    moved = 0
    unchanged = 0
    cancelled = 0
    details = []

    for key, new_iv in new_map.items():
        if key not in existing_map:
            added += 1
            details.append({
                "type": "added",
                "candidate_id": str(new_iv.candidate_id),
                "stage_id": str(new_iv.stage_id),
                "start_time": new_iv.start.isoformat(),
                "room_id": str(new_iv.room_id),
            })
        else:
            old_iv = existing_map[key]
            time_changed = old_iv.start_time != new_iv.start
            room_changed = old_iv.room_id != new_iv.room_id
            old_panel = {p.interviewer_id for p in old_iv.panel if p.is_active} if hasattr(old_iv, "panel") else set()
            new_panel = set(new_iv.interviewer_ids)
            panel_changed = old_panel != new_panel

            if time_changed or room_changed or panel_changed:
                moved += 1
                details.append({
                    "type": "moved",
                    "candidate_id": str(new_iv.candidate_id),
                    "stage_id": str(new_iv.stage_id),
                    "from_start": old_iv.start_time.isoformat(),
                    "to_start": new_iv.start.isoformat(),
                    "time_changed": time_changed,
                    "room_changed": room_changed,
                    "panel_changed": panel_changed,
                })
            else:
                unchanged += 1

    for key, old_iv in existing_map.items():
        if key not in new_map:
            cancelled += 1
            details.append({
                "type": "cancelled",
                "candidate_id": str(old_iv.candidate_id),
                "stage_id": str(old_iv.stage_id),
                "start_time": old_iv.start_time.isoformat(),
            })

    return ScheduleComparison(
        added_count=added,
        moved_count=moved,
        unchanged_count=unchanged,
        cancelled_count=cancelled,
        details=details,
    )
