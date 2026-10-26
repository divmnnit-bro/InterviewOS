# InterviewOS — 5-Minute Live Demo Script

This script provides an exact, click-by-click narrative for demonstrating InterviewOS end-to-end to stakeholders, evaluators, and engineers.

---

## Preparation (Before Starting)
1. Ensure the backend and frontend are running:
   - Backend: `uvicorn app.main:app --port 8000` (or `docker compose up`)
   - Frontend: `npm run dev` at `http://localhost:5173` (or `http://localhost:3000` via Docker)
2. Seed the database with demo accounts:
   ```bash
   python -m app.scripts.seed_demo
   ```
3. Have two browser windows open:
   - Window 1 (Main): Regular window for Coordinator (`coordinator@interviewos.dev` / `Password123!`)
   - Window 2 (Incognito): For Candidate self-booking and Interviewer evaluation

---

## Minute 1: Coordinator Setup & Drive Overview (0:00 – 1:00)

### What to Click:
1. Open `http://localhost:5173/login`.
2. Enter email `coordinator@interviewos.dev` and password `Password123!`. Click **Sign In**.
3. Point out the dark navy/indigo aesthetic, the sidebar, the real-time notification bell, and the **Dashboard** metrics.
4. Click **Recruitment Drives** in the sidebar.
5. Click into **"Campus Placement 2026 — Engineering Drive"**.
6. Switch between the **Overview**, **Stages**, and **Candidates** tabs.

### What to Say:
> *"Welcome to InterviewOS. InterviewOS is built from the ground up for high-stakes campus recruitment and engineering hiring drives.*
> *Here in the coordinator console, a drive is defined by a recruitment window, an IANA timezone for daily quota calculations, and granular rest buffers.*
> *In the Stages tab, we have configured a multi-round pipeline: Round 1 for Technical & Algorithms requiring Python, and Round 2 for System Architecture.*
> *In the Candidates tab, four candidates are already enrolled with their availability submitted."*

---

## Minute 2: Solver Scheduling & Explainability (1:00 – 2:00)

### What to Click:
1. In the drive detail view, click the **Schedule** tab.
2. Click the **"Generate Schedule"** button. (Optionally click "Advanced Solver Settings" to reveal the CP-SAT workers, time limit, and buffer options).
3. Watch the solver progress bar finish and display the proposed schedule.
4. Toggle between **"Timeline by Room"** and **"Timeline by Interviewer"**.
5. Hover over interview blocks on the grid to show candidate and panel assignments.
6. Point out the interviewer workload badge (e.g. `2 / 4 max interviews`) showing capacity enforcement.
7. Click the **"Unscheduled Candidates"** panel or **"Explain Unscheduled"** button to show solver explainability.
8. Click **"Publish Schedule"**, review the confirmation modal, and click **"Confirm & Publish"**.

### What to Say:
> *"Now we move to the core scheduling engine powered by Google OR-Tools CP-SAT.*
> *With a single click on 'Generate Schedule', the solver analyzes candidate availability, interviewer skill tags, room capacities, and rest buffers.*
> *In milliseconds, it returns a 100% conflict-free schedule.*
> *We can review it either by Room or by Interviewer. Notice the workload cap: Sarah Chen is assigned 2 interviews against her maximum capacity of 4, ensuring zero burnout.*
> *If any candidate were unscheduled, our Explainability engine pinpoints the exact blocker and verifies how many interviews an added slot would yield.*
> *Now, we publish with optimistic concurrency protection via schedule versions."*

---

## Minute 3: Candidate Self-Booking & Calendar ICS (2:00 – 3:00)

### What to Click:
1. In the drive Candidates tab, click **"Generate Booking Links"**.
2. Select candidates, choose 48-hour expiration, and click **"Generate 4 Links"**.
3. Copy one candidate's link (or click the external link icon).
4. Switch to the **Incognito Window** and paste the link (`http://localhost:5173/book/<token>`).
5. Observe that no login is required. Free slots are displayed grouped by calendar day in the drive's timezone.
6. Select a 10:00 AM slot and click **"Confirm Booking"**.
7. Note the instant confirmation screen and click **"Download Calendar Invite (.ics)"**.

### What to Say:
> *"InterviewOS supports both automated batch scheduling and self-booking.*
> *Here, the coordinator generated secure, single-use booking tokens.*
> *In our incognito window, the candidate opens their private booking portal—no login friction.*
> *All available slots are grouped by date in the drive's local timezone.*
> *When the candidate confirms, an Idempotency-Key guarantees double clicks never cause duplicate bookings.*
> *And if another candidate claimed the slot milliseconds earlier, the system handles the 409 conflict gracefully and refreshes available times."*

---

## Minute 4: Interviewer Area & Anti-Anchoring Evaluation (3:00 – 4:00)

### What to Click:
1. In the Incognito Window, navigate to `http://localhost:5173/login`.
2. Sign in as Interviewer `sarah.chen@interviewos.dev` / `Password123!`.
3. Review the **Interviewer Dashboard** showing today's assigned sessions and daily workload.
4. Click **"My Interviews"** in the sidebar.
5. Click **"Evaluate"** on an interview card to open the evaluation modal.
6. Interact with the rubric criteria sliders (0 to 10 scale). Watch the computed mean score update live.
7. Select recommendation: **"Strong Hire"** and type detailed feedback: *"Demonstrated excellent proficiency in distributed algorithms and concurrency patterns."*
8. Point out the **"Colleagues' Feedback"** section: it displays a locked state explaining that peer reviews are hidden until own evaluation is submitted.
9. Click **"Submit Evaluation"** (returns 201 Created).

### What to Say:
> *"Now we switch hats to Sarah Chen, one of our technical interviewers.*
> *Her dashboard displays her upcoming agenda and direct .ics calendar downloads.*
> *Opening the evaluation form, we see the real rubric criteria from the stage configuration.*
> *As Sarah grades each criterion, the overall score calculates dynamically.*
> *Notice our anti-anchoring cognitive safeguard: Sarah cannot see any co-panelists' ratings until she has committed her own feedback.*
> *Once submitted, the record is locked in with full audit integrity."*

---

## Minute 5: Pipeline Progression & Ripple Rescue (4:00 – 5:00)

### What to Click:
1. Switch back to the **Coordinator Window**.
2. Go to the drive's **Pipeline** tab.
3. Review the Kanban board: candidates distributed across "Round 1: Technical & Algorithms", "Round 2: System Architecture", and "Selected".
4. Click on Alice Walker's card to open the **Candidate Dossier**.
5. Review Sarah Chen's submitted evaluation and score.
6. Click **"Advance Candidate"** to promote Alice to Round 2.
7. Click the **Rescue** tab on the drive.
8. Under "Disruption Event", select **Interviewer Unavailable**, pick `Marcus Vance`, and set the time range.
9. Click **"Preview Rescue Plan"**.
10. Review the before-and-after diff: showing moved sessions, affected rooms, and collateral vs direct impacts.
11. Click **"Apply Rescue Repair"** to execute the atomic schedule repair.

### What to Say:
> *"Back in the Coordinator console, the Pipeline board shows candidate movement in real time.*
> *Opening Alice's dossier, we see Sarah's glowing evaluation. With one click, the coordinator advances Alice to Round 2.*
> *Finally, what happens when disaster strikes on interview day? An interviewer falls sick or an emergency arises.*
> *Instead of manually calling and rescheduling dozens of sessions, we use Ripple Rescue.*
> *We declare Marcus Vance unavailable for the afternoon. Ripple Rescue calculates the minimal-impact topological repair plan.*
> *It shows exactly which sessions shift, flags collateral impacts, and when applied with version fingerprint verification, repairs the entire schedule without double bookings.*
> *From setup to solver, booking, evaluation, pipeline, and rescue—InterviewOS completes the entire recruitment lifecycle."*
