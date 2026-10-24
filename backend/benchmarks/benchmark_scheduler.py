#!/usr/bin/env python3
"""Scale benchmark for the interview scheduler: CP-SAT (`solve`) versus the greedy fallback.

Run from the `backend/` directory (no database needed):

    python benchmarks/benchmark_scheduler.py                       # all three tiers, both methods
    python benchmarks/benchmark_scheduler.py --tier medium         # one tier
    python benchmarks/benchmark_scheduler.py --time-limit 5        # shorter CP-SAT budget
    python benchmarks/benchmark_scheduler.py --workers 4           # parallel CP-SAT search
    python benchmarks/benchmark_scheduler.py --methods greedy      # greedy only
    python benchmarks/benchmark_scheduler.py --json results.json   # also save the numbers

Tiers (every candidate is scheduled for ALL of the tier's rounds, chained in order, which is the
hardest case the solver supports; the API normally schedules one round at a time):

    small   10 candidates,   5 interviewers, 2 rounds,  2 rooms,  2 days   comfortable
    medium  50 candidates,  20 interviewers, 3 rounds,  5 rooms,  3 days   heavily loaded
    large  160 candidates,  40 interviewers, 3 rounds, 10 rooms,  3 days   oversubscribed (stress)

The number of days is the knob that sets how tight a tier is. Large is deliberately given more
interview-hours than its rooms can hold, so some candidates cannot be placed by ANY method and
the match rate then shows how well each method uses the capacity that exists.

What is measured, per (tier, method):

    Time          validation + preparation + solving. Data generation and verification are excluded.
    Interviews    placed / requested (one request per candidate per round).
    Candidates    candidates with EVERY round placed / all candidates.
    Status        the solver's status (optimal, feasible, heuristic, unknown).
    Busiest       interviews taken by the busiest interviewer (lower = more even workload).
    Avg start     mean start of the placed interviews, in hours after the drive begins
                  (lower = earlier). These two show what CP-SAT's soft preferences buy.
    Peak MB       peak resident memory of the whole worker process, interpreter and OR-Tools import
                  included. This is what a container memory limit has to cover.
    +MB           growth of that peak over the process baseline measured before any data was built.
    Valid         the result re-checked by the independent checker (app.scheduler.verify).

Each run happens in a fresh subprocess, because peak RSS is a process-lifetime maximum: sharing one
process would let a big run inflate the number reported for every later run. Pass --no-isolate to
run in-process instead (memory figures are then cumulative and only indicative).

Both methods get byte-for-byte identical input for a given --seed. The greedy method is the same
first-fit plan that seeds CP-SAT and is returned when CP-SAT cannot finish in time, so the
comparison shows what the solver adds on top of its own starting point.

Exit status is 1 if any run failed or produced a schedule the checker rejects, otherwise 0.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import random
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make `import app...` work when this file is run directly as `python benchmarks/...`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scheduler import (  # noqa: E402
    CandidateSpec,
    InterviewerSpec,
    RoomSpec,
    ScheduleInput,
    SchedulerConfig,
    StageSpec,
    Window,
    solve,
    validate_input,
)
from app.scheduler.greedy import greedy_plan  # noqa: E402
from app.scheduler.prepare import prepare  # noqa: E402
from app.scheduler.solver import _fallback  # noqa: E402
from app.scheduler.verify import verify  # noqa: E402

try:
    import resource  # POSIX only
except ImportError:  # pragma: no cover - Windows
    resource = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- scenarios
@dataclass(frozen=True)
class Tier:
    name: str
    candidates: int
    interviewers: int
    rooms: int
    stages: int
    days: int
    time_limit: float  # default CP-SAT budget in seconds


TIERS: dict[str, Tier] = {
    "small": Tier("small", candidates=10, interviewers=5, rooms=2, stages=2, days=2, time_limit=10.0),
    "medium": Tier("medium", candidates=50, interviewers=20, rooms=5, stages=3, days=3, time_limit=20.0),
    "large": Tier("large", candidates=160, interviewers=40, rooms=10, stages=3, days=3, time_limit=30.0),
}

METHODS = ("cpsat", "greedy")
METHOD_LABEL = {"cpsat": "cp-sat", "greedy": "greedy"}

DAY0 = datetime(2026, 11, 2, tzinfo=timezone.utc)  # a Monday; the horizon starts at midnight UTC
BLOCKS = ((9, 13), (14, 18))                      # morning and afternoon working blocks (UTC hours)
SKILLS = ("algorithms", "systems", "design", "behavioral", "python")
# (stage id, name, minutes, panel size, required skills). A tier uses the first `stages` of these.
STAGE_DEFS = (
    ("coding", "Coding", 30, 1, ("algorithms",)),
    ("technical", "Technical", 45, 2, ("systems",)),
    ("hr", "HR", 30, 1, ("behavioral",)),
)
INTERVIEWER_DAILY_CAPACITY = 6
ROOM_CAPACITIES = (3, 4, 6)          # every room seats the largest panel (2) plus the candidate
CANDIDATE_BLOCK_PROBABILITY = 0.65   # chance a candidate is free in a given block
INTERVIEWER_BLOCK_PROBABILITY = 0.80
BUFFER_MINUTES = 10                  # interviewer rest after a session
ROUND_GAP_MINUTES = 30               # minimum gap between one candidate's rounds


def _window(day: int, block: int) -> Window:
    start_hour, end_hour = BLOCKS[block]
    return Window(
        DAY0 + timedelta(days=day, hours=start_hour),
        DAY0 + timedelta(days=day, hours=end_hour),
    )


def _pick_blocks(rng: random.Random, all_blocks: list[tuple[int, int]], p: float, minimum: int):
    """Each block is chosen with probability p; top up at random so at least `minimum` are chosen."""
    minimum = min(minimum, len(all_blocks))
    chosen = [b for b in all_blocks if rng.random() < p]
    if len(chosen) < minimum:
        spare = [b for b in all_blocks if b not in chosen]
        chosen += rng.sample(spare, minimum - len(chosen))
    return sorted(chosen)


def build_input(tier: Tier, seed: int, time_limit: float, workers: int) -> ScheduleInput:
    """A reproducible, realistic drive for `tier`.

    Candidates and interviewers are each free in a random subset of the morning/afternoon blocks.
    `tier.days` sets how much capacity there is for the demand, and so how tight the tier is.
    Every interviewer holds three of the five skills in rotation, so each required skill is
    covered by at least three interviewers (enough for the two-person technical panel).
    """
    rng = random.Random(f"{seed}:{tier.name}")  # str seeds are stable across processes
    all_blocks = [(d, b) for d in range(tier.days) for b in range(len(BLOCKS))]

    stages = tuple(
        StageSpec(sid, order, minutes, panel, frozenset(skills), name)
        for order, (sid, name, minutes, panel, skills) in enumerate(STAGE_DEFS[: tier.stages], start=1)
    )
    stage_ids = tuple(s.id for s in stages)

    candidates = tuple(
        CandidateSpec(
            f"cand-{n:03d}",
            stage_ids,
            tuple(
                _window(d, b)
                for d, b in _pick_blocks(rng, all_blocks, CANDIDATE_BLOCK_PROBABILITY, minimum=3)
            ),
        )
        for n in range(tier.candidates)
    )
    interviewers = tuple(
        InterviewerSpec(
            f"intv-{k:02d}",
            frozenset(SKILLS[(k + j) % len(SKILLS)] for j in range(3)),
            tuple(
                _window(d, b)
                for d, b in _pick_blocks(
                    rng, all_blocks, INTERVIEWER_BLOCK_PROBABILITY, minimum=max(1, len(all_blocks) // 2)
                )
            ),
            INTERVIEWER_DAILY_CAPACITY,
        )
        for k in range(tier.interviewers)
    )
    rooms = tuple(
        RoomSpec(f"room-{n:02d}", ROOM_CAPACITIES[n % len(ROOM_CAPACITIES)], name=f"Room {n + 1}")
        for n in range(tier.rooms)
    )
    config = SchedulerConfig(
        horizon_start=DAY0,
        horizon_end=DAY0 + timedelta(days=tier.days),
        slot_minutes=15,
        timezone="UTC",
        interviewer_buffer_minutes=BUFFER_MINUTES,
        min_round_gap_minutes=ROUND_GAP_MINUTES,
        time_limit_seconds=time_limit,
        workers=workers,
        seed=seed,
    )
    return ScheduleInput(stages, candidates, interviewers, rooms, config)


# --------------------------------------------------------------------------- measuring
def _peak_rss_mb() -> float | None:
    """Peak resident memory of this process in MB, or None where the OS does not report it."""
    if resource is None:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes, macOS reports bytes.
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def run_case(tier_name: str, method: str, seed: int, time_limit: float, workers: int) -> dict:
    """Build the drive, schedule it with `method`, and return the measurements."""
    tier = TIERS[tier_name]
    baseline = _peak_rss_mb()
    inp = build_input(tier, seed, time_limit, workers)
    requested = len(inp.candidates) * len(inp.stages)

    started = time.perf_counter()
    if method == "cpsat":
        result = solve(inp)
    else:
        # The same steps `solve` takes before building its model, then the greedy plan on its own.
        validate_input(inp)
        prep = prepare(inp)
        plan = greedy_plan(
            prep,
            {r.id: r.capacity for r in inp.rooms},
            {i.id: i.capacity_per_day for i in inp.interviewers},
        )
        result = _fallback(prep, prep.requests, plan, 0.0)
    elapsed = time.perf_counter() - started
    peak = _peak_rss_mb()

    per_candidate = Counter(iv.candidate_id for iv in result.interviews)
    complete = sum(1 for c in inp.candidates if per_candidate.get(c.id, 0) == len(c.stage_ids))
    violations = verify(inp, result)
    starts = [(iv.start - DAY0).total_seconds() / 3600 for iv in result.interviews]
    reasons = Counter(r.code.value for u in result.unscheduled for r in u.reasons)

    return {
        "tier": tier_name,
        "method": method,
        "candidates": len(inp.candidates),
        "interviewers": len(inp.interviewers),
        "rooms": len(inp.rooms),
        "stages": len(inp.stages),
        "requested": requested,
        "placed": len(result.interviews),
        "interview_match_pct": 100.0 * len(result.interviews) / requested if requested else 100.0,
        "candidates_complete": complete,
        "candidate_match_pct": 100.0 * complete / len(inp.candidates) if inp.candidates else 100.0,
        "seconds": elapsed,
        "status": result.status.value,
        "objective": result.objective,
        "busiest_load": max(result.load_per_interviewer.values(), default=0),
        "mean_start_hours": (sum(starts) / len(starts)) if starts else None,
        "violations": len(violations),
        "violation_examples": violations[:3],
        "unscheduled_reasons": dict(reasons),
        "time_limit": time_limit,
        "workers": workers,
        "peak_mb": peak,
        "delta_mb": (peak - baseline) if (peak is not None and baseline is not None) else None,
    }


def _child(conn, kwargs: dict) -> None:
    try:
        conn.send(run_case(**kwargs))
    except BaseException:  # report anything, including KeyboardInterrupt, instead of hanging the parent
        conn.send({"error": traceback.format_exc()})
    finally:
        conn.close()


def run_isolated(kwargs: dict, timeout: float) -> dict:
    """Run one case in a fresh interpreter so its peak memory is its own."""
    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child, args=(child, kwargs))
    proc.start()
    child.close()  # so the pipe reports EOF if the worker dies
    try:
        if parent.poll(timeout):
            try:
                out = parent.recv()
            except EOFError:
                out = {"error": "worker exited without a result (killed, possibly out of memory)"}
        else:
            out = {"error": f"no result after {timeout:.0f}s; worker stopped"}
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join(10)
        parent.close()
    return out


# --------------------------------------------------------------------------- reporting
def _fmt_mb(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.0f}"


def _render(headers: list[str], rows: list[list[str]], left: set[int]) -> str:
    """A plain ASCII table (no box-drawing characters, so any terminal encoding works)."""
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]

    def line(cells: list[str]) -> str:
        parts = [c.ljust(widths[i]) if i in left else c.rjust(widths[i]) for i, c in enumerate(cells)]
        return "| " + " | ".join(parts) + " |"

    rule = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    return "\n".join([rule, line(headers), rule, *(line(r) for r in rows), rule])


def print_results(results: list[dict]) -> None:
    ok = [r for r in results if "error" not in r]

    def label(r: dict) -> list[str]:
        return [r["tier"], METHOD_LABEL[r["method"]]]

    outcome_rows: list[list[str]] = []
    for r in results:
        if "error" in r:
            outcome_rows.append([*label(r), "ERROR", "-", "-", "-", "-"])
            continue
        outcome_rows.append([
            *label(r),
            f"{r['placed']}/{r['requested']} ({r['interview_match_pct']:.1f}%)",
            f"{r['candidates_complete']}/{r['candidates']} ({r['candidate_match_pct']:.1f}%)",
            f"{r['seconds']:.2f}",
            r["status"],
            "yes" if r["violations"] == 0 else f"NO ({r['violations']})",
        ])
    print("\nMatch rate, speed and validity:\n")
    print(_render(
        ["Tier", "Method", "Interviews", "Candidates", "Time (s)", "Status", "Valid"],
        outcome_rows, left={0, 1, 5},
    ))

    quality_rows = [
        [
            *label(r),
            str(r["busiest_load"]),
            "n/a" if r["mean_start_hours"] is None else f"{r['mean_start_hours']:.2f}",
            _fmt_mb(r["peak_mb"]),
            _fmt_mb(r["delta_mb"]),
        ]
        for r in ok
    ]
    if quality_rows:
        print("\nSchedule quality and memory:\n")
        print(_render(
            ["Tier", "Method", "Busiest", "Avg start (h)", "Peak MB", "+MB"],
            quality_rows, left={0, 1},
        ))

    # CP-SAT against greedy, tier by tier.
    by_key = {(r["tier"], r["method"]): r for r in results if "error" not in r}
    comparison: list[list[str]] = []
    for tier in TIERS:
        a, b = by_key.get((tier, "cpsat")), by_key.get((tier, "greedy"))
        if a is None or b is None:
            continue
        slower = f"x{a['seconds'] / b['seconds']:.1f}" if b["seconds"] > 1e-6 else "n/a"
        comparison.append([
            tier,
            f"{a['placed'] - b['placed']:+d}",
            f"{a['candidates_complete'] - b['candidates_complete']:+d}",
            f"{a['busiest_load'] - b['busiest_load']:+d}",
            f"{a['seconds'] - b['seconds']:+.2f}",
            slower,
        ])
    if comparison:
        print("\nCP-SAT minus greedy (more interviews/candidates is better; lower busiest load is better):\n")
        print(_render(
            ["Tier", "Interviews", "Candidates", "Busiest", "Extra time (s)", "Time ratio"],
            comparison,
            left={0},
        ))

    print(
        "\nTime = validation + preparation + solve; data generation and verification are excluded.\n"
        "Busiest = interviews taken by the busiest interviewer; Avg start = mean start in hours after\n"
        "the drive begins. Peak MB is the whole worker process, interpreter and OR-Tools import\n"
        "included; +MB is its growth over the baseline measured before the data was built.\n"
        "Valid = the independent checker (app.scheduler.verify) re-checked every constraint."
    )
    for r in results:
        if "error" in r:
            print(f"\n[{r['tier']} / {METHOD_LABEL[r['method']]}] failed:\n{r['error'].rstrip()}")
        elif r["violations"]:
            print(f"\n[{r['tier']} / {METHOD_LABEL[r['method']]}] checker violations (first 3):")
            for v in r["violation_examples"]:
                print(f"  - {v}")


def _positive_float(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return value


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark the CP-SAT scheduler against the greedy fallback.")
    p.add_argument("--tier", choices=[*TIERS, "all"], default="all",
                   help="which scale tier to run (default: all)")
    p.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS),
                   help="which schedulers to run (default: cpsat greedy)")
    p.add_argument("--time-limit", type=_positive_float, default=None, metavar="SECONDS",
                   help="CP-SAT time limit (default: 10 small, 20 medium, 30 large)")
    p.add_argument("--workers", type=_positive_int, default=1,
                   help="CP-SAT search workers; 1 is deterministic, more is faster on big drives (default: 1)")
    p.add_argument("--seed", type=int, default=2026,
                   help="seed for the synthetic data and the solver (default: 2026)")
    p.add_argument("--json", metavar="PATH", default=None,
                   help="also write the results to this JSON file")
    p.add_argument("--no-isolate", action="store_true",
                   help="run in this process instead of one subprocess per run (memory becomes cumulative)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tier_names = list(TIERS) if args.tier == "all" else [args.tier]

    try:
        import ortools
        ortools_version = getattr(ortools, "__version__", "unknown")
    except ImportError:
        ortools_version = "not installed"
    print(
        f"InterviewOS scheduler benchmark | python {platform.python_version()} | "
        f"ortools {ortools_version} | {platform.system()} {platform.machine()} | "
        f"{os.cpu_count()} CPUs | seed {args.seed} | workers {args.workers}"
    )
    if args.no_isolate:
        print("note: --no-isolate, so memory figures are cumulative across runs")

    results: list[dict] = []
    for name in tier_names:
        tier = TIERS[name]
        limit = args.time_limit or tier.time_limit
        for method in args.methods:
            print(
                f"running {name:<6} {METHOD_LABEL[method]:<6} "
                f"({tier.candidates} candidates, {tier.interviewers} interviewers, "
                f"{tier.stages} rounds, {tier.rooms} rooms) ...",
                flush=True,
            )
            kwargs = {
                "tier_name": name, "method": method, "seed": args.seed,
                "time_limit": limit, "workers": args.workers,
            }
            if args.no_isolate:
                try:
                    out = run_case(**kwargs)
                except Exception:
                    out = {"error": traceback.format_exc()}
            else:
                # CP-SAT may legitimately use its whole budget; allow generous room for setup.
                out = run_isolated(kwargs, timeout=(limit * 3 + 120) if method == "cpsat" else 300)
            out.setdefault("tier", name)
            out.setdefault("method", method)
            results.append(out)

    print_results(results)

    if args.json:
        payload = {
            "python": platform.python_version(),
            "ortools": ortools_version,
            "platform": platform.platform(),
            "cpus": os.cpu_count(),
            "seed": args.seed,
            "workers": args.workers,
            "results": results,
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"\nresults written to {args.json}")

    failed = any("error" in r or r.get("violations") for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
