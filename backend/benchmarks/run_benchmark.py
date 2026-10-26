"""InterviewOS Scheduling Engine Benchmark.

Executes and benchmarks the OR-Tools CP-SAT scheduler across Small, Medium, and Large drive sizes,
measuring wall clock solve time, solver status, scheduled vs unscheduled counts, and quality metrics.

Usage:
  python benchmarks/run_benchmark.py
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from app.scheduler import (
    CandidateSpec,
    InterviewerSpec,
    RoomSpec,
    ScheduleInput,
    SchedulerConfig,
    StageSpec,
    Window,
    solve,
)
from app.scheduler.quality import compute_schedule_quality
from app.scheduler.types import SolveStatus

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)


def generate_benchmark_dataset(num_candidates: int, num_interviewers: int, num_rooms: int, num_stages: int) -> ScheduleInput:
    stages = tuple(
        StageSpec(
            id=f"stage_{s}",
            order_index=s + 1,
            name=f"Round {s + 1}",
            duration_minutes=30,
            panel_size=1,
            required_skills=frozenset(["python"]) if s == 0 else frozenset(["system_design"]),
        )
        for s in range(num_stages)
    )

    stage_ids = tuple(s.id for s in stages)
    horizon_days = max(2, (num_candidates * num_stages) // (num_rooms * 8) + 1)
    horizon_end = T0 + timedelta(days=horizon_days, hours=8)

    candidates = []
    for c in range(num_candidates):
        day_offset = c % horizon_days
        w_start = T0 + timedelta(days=day_offset)
        w_end = w_start + timedelta(hours=8)
        candidates.append(CandidateSpec(
            id=f"cand_{c}",
            stage_ids=stage_ids,
            availability=(Window(w_start, w_end),),
        ))

    interviewers = []
    for i in range(num_interviewers):
        skills = frozenset(["python", "system_design"])
        windows = tuple(
            Window(T0 + timedelta(days=d), T0 + timedelta(days=d, hours=8))
            for d in range(horizon_days)
        )
        interviewers.append(InterviewerSpec(
            id=f"ivr_{i}",
            skills=skills,
            availability=windows,
            capacity_per_day=6,
        ))

    rooms = tuple(
        RoomSpec(id=f"room_{r}", capacity=3, name=f"Room {r + 1}")
        for r in range(num_rooms)
    )

    cfg = SchedulerConfig(
        horizon_start=T0,
        horizon_end=horizon_end,
        slot_minutes=15,
        time_limit_seconds=20.0,
        workers=2,
    )

    return ScheduleInput(
        stages=stages,
        candidates=tuple(candidates),
        interviewers=tuple(interviewers),
        rooms=rooms,
        config=cfg,
    )


def run_benchmarks():
    scenarios = [
        ("Small Drive", 10, 4, 2, 2),
        ("Medium Drive", 50, 10, 4, 2),
        ("Large Drive", 120, 20, 8, 2),
    ]

    print("=" * 78)
    print(" INTERVIEWOS SCHEDULING ENGINE BENCHMARK SUITE (OR-TOOLS CP-SAT)")
    print("=" * 78)
    print(f"{'Scenario':<16} | {'Candidates':<10} | {'Status':<10} | {'Time (s)':<10} | {'Scheduled':<12} | {'Verified':<8}")
    print("-" * 78)

    for name, c_count, i_count, r_count, s_count in scenarios:
        inp = generate_benchmark_dataset(c_count, i_count, r_count, s_count)
        total_requests = len(inp.candidates) * len(inp.stages)

        t_start = time.perf_counter()
        result = solve(inp)
        elapsed = time.perf_counter() - t_start

        quality = compute_schedule_quality(inp, result)
        status_str = result.status.value.upper()
        sched_ratio = f"{len(result.interviews)}/{total_requests}"
        verified_str = "YES" if quality.is_verified else "NO"

        print(f"{name:<16} | {c_count:<10} | {status_str:<10} | {elapsed:<10.3f} | {sched_ratio:<12} | {verified_str:<8}")
        print(f"  -> Quality: Workload Variance={quality.interviewer_workload_variance:.2f}, Room Util={quality.room_utilization_percent:.1f}%, Hard Violations={quality.hard_constraint_violations}")

    print("=" * 78)


if __name__ == "__main__":
    run_benchmarks()
