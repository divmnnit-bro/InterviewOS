"""Seed script for InterviewOS demo environment.

Creates:
  - Demo Coordinator: coordinator@interviewos.dev / Password123!
  - 3 Interviewers with skills, departments and availability:
      sarah.chen@interviewos.dev, marcus.vance@interviewos.dev, priya.sharma@interviewos.dev
  - 4 Candidates with availability:
      alice.walker@example.com, bob.martinez@example.com, clara.zhao@example.com, david.kim@example.com
  - 3 Rooms: Turing Lab, Hopper Boardroom, Lovelace Room
  - 1 Active Recruitment Drive with 2 stages:
      Campus Placement 2026 — Engineering Drive (Technical & Algorithms, System Architecture)
  - Enrolled candidates ready for scheduling and pipeline workflows.

Usage:
  python -m app.scripts.seed_demo
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import (
    Availability,
    Candidate,
    DriveCandidate,
    DriveCandidateStatus,
    DriveStatus,
    InterviewStage,
    Interviewer,
    RecruitmentDrive,
    Room,
    StageType,
    User,
    UserRole,
    UserStatus,
)


def seed() -> None:
    db = SessionLocal()
    try:
        print("[*] Starting InterviewOS database seed...")

        # 1. Coordinator
        coordinator = db.query(User).filter(User.email == "coordinator@interviewos.dev").first()
        if not coordinator:
            coordinator = User(
                name="Alex Rivera (Lead Coordinator)",
                email="coordinator@interviewos.dev",
                hashed_password=hash_password("Password123!"),
                role=UserRole.COORDINATOR,
                status=UserStatus.ACTIVE,
            )
            db.add(coordinator)
            db.flush()
            print("  [+] Created Coordinator: coordinator@interviewos.dev")
        else:
            print("  [-] Coordinator already exists")

        # 2. Interviewers
        interviewer_specs = [
            {
                "name": "Sarah Chen",
                "email": "sarah.chen@interviewos.dev",
                "skills": ["Python", "Algorithms", "Distributed Systems"],
                "capacity": 4,
                "department": "Platform Engineering",
            },
            {
                "name": "Marcus Vance",
                "email": "marcus.vance@interviewos.dev",
                "skills": ["React", "Frontend Architecture", "UI/UX"],
                "capacity": 4,
                "department": "Product Engineering",
            },
            {
                "name": "Priya Sharma",
                "email": "priya.sharma@interviewos.dev",
                "skills": ["System Design", "Cloud", "Leadership"],
                "capacity": 3,
                "department": "Core Infrastructure",
            },
        ]

        interviewers: list[User] = []
        for spec in interviewer_specs:
            user = db.query(User).filter(User.email == spec["email"]).first()
            if not user:
                user = User(
                    name=spec["name"],
                    email=spec["email"],
                    hashed_password=hash_password("Password123!"),
                    role=UserRole.INTERVIEWER,
                    status=UserStatus.ACTIVE,
                )
                db.add(user)
                db.flush()
                profile = Interviewer(
                    user_id=user.id,
                    skills=spec["skills"],
                    capacity=spec["capacity"],
                    department=spec["department"],
                )
                db.add(profile)
                db.flush()
                print(f"  [+] Created Interviewer: {spec['email']}")
            interviewers.append(user)

        # 3. Candidates
        candidate_specs = [
            {
                "name": "Alice Walker",
                "email": "alice.walker@example.com",
                "roll": "CS2026-001",
                "branch": "Computer Science",
            },
            {
                "name": "Bob Martinez",
                "email": "bob.martinez@example.com",
                "roll": "CS2026-002",
                "branch": "Information Technology",
            },
            {
                "name": "Clara Zhao",
                "email": "clara.zhao@example.com",
                "roll": "CS2026-003",
                "branch": "Data Science",
            },
            {
                "name": "David Kim",
                "email": "david.kim@example.com",
                "roll": "CS2026-004",
                "branch": "Software Engineering",
            },
        ]

        candidates: list[User] = []
        for spec in candidate_specs:
            user = db.query(User).filter(User.email == spec["email"]).first()
            if not user:
                user = User(
                    name=spec["name"],
                    email=spec["email"],
                    hashed_password=hash_password("Password123!"),
                    role=UserRole.CANDIDATE,
                    status=UserStatus.ACTIVE,
                )
                db.add(user)
                db.flush()
                profile = Candidate(
                    user_id=user.id,
                    roll_number=spec["roll"],
                    branch=spec["branch"],
                )
                db.add(profile)
                db.flush()
                print(f"  [+] Created Candidate: {spec['email']}")
            candidates.append(user)

        # 4. Rooms
        room_specs = [
            {"name": "Turing Lab (Room 101)", "capacity": 4, "location": "Engineering Block, Floor 1"},
            {"name": "Hopper Boardroom (Room 202)", "capacity": 6, "location": "Innovation Centre, Floor 2"},
            {"name": "Lovelace Room (Room 303)", "capacity": 4, "location": "Tech Park East, Floor 3"},
        ]
        for spec in room_specs:
            room = db.query(Room).filter(Room.name == spec["name"]).first()
            if not room:
                room = Room(name=spec["name"], capacity=spec["capacity"], location=spec["location"])
                db.add(room)
                db.flush()
                print(f"  [+] Created Room: {spec['name']}")

        # 5. Drive and Stages
        drive_title = "Campus Placement 2026 — Engineering Drive"
        drive = db.query(RecruitmentDrive).filter(RecruitmentDrive.title == drive_title).first()
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)  # midnight UTC, so 09:00-17:00 below is really 09:00-17:00 UTC
        window_start = now + timedelta(days=1, hours=9)
        window_end = now + timedelta(days=5, hours=18)

        if not drive:
            drive = RecruitmentDrive(
                title=drive_title,
                description="Annual campus recruitment drive for core software engineering roles.",
                window_start=window_start,
                window_end=window_end,
                status=DriveStatus.COLLECTING_AVAILABILITY,
                timezone="UTC",
                slot_minutes=30,
                interviewer_buffer_minutes=15,
                min_round_gap_minutes=30,
                created_by=coordinator.id,
            )
            db.add(drive)
            db.flush()
            print(f"  [+] Created Drive: {drive.title}")

            # Stages
            stage1 = InterviewStage(
                drive_id=drive.id,
                order_index=1,
                name="Round 1: Technical & Algorithms",
                stage_type=StageType.TECHNICAL,
                duration_minutes=30,
                panel_size=1,
                required_skills=["Python", "Algorithms"],
                rule={"type": "min_score", "min_score": 6.0},
            )
            stage2 = InterviewStage(
                drive_id=drive.id,
                order_index=2,
                name="Round 2: System Architecture",
                stage_type=StageType.TECHNICAL,
                duration_minutes=45,
                panel_size=1,
                required_skills=["System Design"],
                rule={"type": "min_score", "min_score": 7.0},
            )
            db.add(stage1)
            db.add(stage2)
            db.flush()
            print("  [+] Added Stage 1 and Stage 2")

            # Enroll candidates
            for cand in candidates:
                enrollment = DriveCandidate(
                    drive_id=drive.id,
                    candidate_id=cand.id,
                    status=DriveCandidateStatus.ACTIVE,
                    current_stage_id=stage1.id,
                )
                db.add(enrollment)
            db.flush()
            print(f"  [+] Enrolled {len(candidates)} candidates")

            # Seed Availability Windows within drive window
            for u in interviewers + candidates:
                for day_offset in range(1, 4):
                    day_start = now + timedelta(days=day_offset, hours=9)
                    day_end = now + timedelta(days=day_offset, hours=17)
                    avail = Availability(
                        owner_id=u.id,
                        start_time=day_start,
                        end_time=day_end,
                    )
                    db.add(avail)
            db.flush()
            print("  [+] Seeded availability windows for interviewers and candidates")

        db.commit()
        print("[✓] InterviewOS demo database seeded successfully!")
        print("\nDemo Accounts:")
        print("  - Coordinator: coordinator@interviewos.dev / Password123!")
        print("  - Interviewer: sarah.chen@interviewos.dev / Password123!")
        print("  - Interviewer: marcus.vance@interviewos.dev / Password123!")
        print("  - Interviewer: priya.sharma@interviewos.dev / Password123!")
        print("  - Candidate:   alice.walker@example.com / Password123!")
        print("  - Candidate:   bob.martinez@example.com / Password123!")

    except Exception as e:
        db.rollback()
        print(f"[!] Seed failed: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()