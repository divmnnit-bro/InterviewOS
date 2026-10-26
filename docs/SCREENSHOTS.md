# InterviewOS — Visual Tour & Screenshot Catalog

This catalog documents the primary user interfaces across stages F1 through F8 of InterviewOS.

---

### 1. F1: Authentication & Role-Based Entry
- **Path**: `/login`, `/register`, `/not-allowed`
- **File**: `docs/screenshots/01_login_and_auth.png`
- **Features**:
  - Dark-mode glassmorphic theme with indigo/violet accents.
  - Role-specific authentication with automatic routing to `/coordinator`, `/interviewer`, or `/candidate`.
  - Candidate public self-registration with roll number and branch fields.
  - Notification bell with unread badge and 30-second background polling.

---

### 2. F2: Coordinator Setup & Drive Management
- **Path**: `/coordinator/drives`, `/coordinator/drives/:id`, `/coordinator/people`, `/coordinator/rooms`
- **File**: `docs/screenshots/02_coordinator_setup_drives.png`
- **Features**:
  - Directory tables with instant client-side and server-side filtering.
  - Drive creation and configuration: IANA timezone picker, slot minutes (5–60 min), interviewer rest buffer, minimum round gap.
  - Multi-stage pipeline builder: order index, duration, panel size, skill tags, pass rules.
  - Multi-candidate search and batch enrolment with withdrawal safeguards.
  - Locked-field indicators for published drives preventing race conditions.

---

### 3. F3: Interactive Availability Matrix
- **Path**: `/candidate/availability`, `/interviewer/availability`, `/coordinator/people/:id/availability`, `/coordinator/rooms/:id/availability`
- **File**: `docs/screenshots/03_availability_calendar.png`
- **Features**:
  - 7-day interactive week calendar with hour grid.
  - Drive-window background highlight showing the active recruitment boundary.
  - Window overlap auto-merging (`mergeOverlappingWindows`) and drive-window boundary clipping.
  - Room availability banner explaining the "No windows means open the entire drive" rule.
  - Interviewer profile card displaying skill tags and maximum daily interview capacity.

---

### 4. F4: Scheduling Console & Timelines
- **Path**: `/coordinator/drives/:id` (Schedule Tab)
- **File**: `docs/screenshots/04_schedule_console_timeline.png`
- **Features**:
  - CP-SAT solver execution with progress indicator and advanced solver configuration drawer.
  - Dual timeline visualizations: **Timeline by Room** and **Timeline by Interviewer**.
  - 30-minute block scaling, color-coded stage badges, and session details on hover.
  - Interviewer daily workload counter vs configured daily capacity limit badge.
  - Compare-and-swap publish with `expected_version` and 409 stale version detection.
  - One-click `.ics` calendar invitation download per scheduled session.

---

### 5. F4: Unscheduled Candidates & Solver Explainability
- **Path**: `/coordinator/drives/:id` (Schedule Tab > Unscheduled Drawer)
- **File**: `docs/screenshots/05_schedule_explain_unscheduled.png`
- **Features**:
  - Plain-language summary of unplaced candidates.
  - Explain solver integration (`POST /schedule/explain`).
  - Diagnostic breakdown: Primary blocker (interviewer capacity, room shortage, or no overlapping window), best near-miss slot, and verified fixes with exact extra interview yields.

---

### 6. F5: Candidate Self-Booking & Booking Links
- **Path**: `/book/:token`, `/candidate`
- **File**: `docs/screenshots/06_booking_modal_and_public_page.png`
- **Features**:
  - Coordinator batch booking links generator with configurable TTL hours and copy-to-clipboard.
  - Public booking portal (`/book/:token`) without login requirements.
  - Real-time slot grouping by calendar day in the drive's local timezone.
  - Idempotent booking submission (`Idempotency-Key` header with replay tolerance).
  - Slot conflict handling (instant 409 alert and list refresh).
  - Post-booking confirmation card with instant `.ics` calendar export.

---

### 7. F6: Interviewer Evaluation & Anti-Anchoring Form
- **Path**: `/interviewer`, `/interviewer/interviews`
- **File**: `docs/screenshots/07_interviewer_evaluation_modal.png`
- **Features**:
  - Start-time gating: evaluation submission disabled before interview start time.
  - Real rubric criteria sliders (0 to 10 scale) with live average score calculation.
  - Overall recommendation picker (Strong Hire, Hire, Weak Hire, Hold, Reject).
  - Dynamic 201 Create vs 200 Revision detection.
  - Anti-anchoring colleague feedback protection: hides peer reviews until own evaluation is submitted.

---

### 8. F7: Pipeline Kanban & Decision Dossier
- **Path**: `/coordinator/drives/:id` (Pipeline Tab)
- **File**: `docs/screenshots/08_pipeline_kanban_board.png`
- **Features**:
  - Multi-column Kanban board grouped by interview stage plus end states (Selected, Rejected).
  - Table view alternative toggle with stage and status filters.
  - Candidate Dossier modal showing historical interview performance and scored evaluations.
  - Progression decisions: Advance to next stage or Reject with audited override justification.
  - "Go to Schedule" shortcut immediately following candidate advancement.

---

### 9. F7: Ripple Rescue Disruption Console
- **Path**: `/coordinator/drives/:id` (Rescue Tab)
- **File**: `docs/screenshots/09_ripple_rescue_disruption_repair.png`
- **Features**:
  - Disruption specification: Interviewer Out, Room Closed, or Candidate Reschedule.
  - High-impact preview diff: before vs after comparison of slot, room, and panelist.
  - Direct hit vs collateral shift categorization with visual tags.
  - Dropped sessions panel with root-cause explanations.
  - Safe apply transaction requiring matching `expected_version` and `plan_fingerprint`.
