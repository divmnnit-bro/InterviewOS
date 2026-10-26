export type UserRole = 'coordinator' | 'interviewer' | 'candidate';
export type UserStatus = 'active' | 'inactive' | 'suspended';

export interface CandidateProfile {
  roll_number?: string;
  branch?: string;
}

export interface InterviewerProfile {
  skills: string[];
  capacity: number;
  department?: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  candidate?: CandidateProfile;
  interviewer?: InterviewerProfile;
  roll_number?: string;
  branch?: string;
  skills?: string[];
  capacity?: number;
  department?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type?: string;
}

export type DriveStatus =
  | 'draft'
  | 'collecting_availability'
  | 'scheduling'
  | 'published'
  | 'completed'
  | 'cancelled';

export interface PassRule {
  min_score?: number;
  min_evaluations?: number;
  require_all_pass?: boolean;
  weights?: Record<string, number>;
  [key: string]: any;
}

export interface Stage {
  id: string;
  drive_id: string;
  order_index: number;
  name: string;
  stage_type: 'technical' | 'hr' | 'managerial' | 'system_design' | 'general';
  duration_minutes: number;
  panel_size: number;
  required_skills: string[];
  rule: PassRule;
}

export interface RecruitmentDrive {
  id: string;
  title: string;
  description?: string;
  window_start: string;
  window_end: string;
  timezone: string;
  slot_minutes: number;
  interviewer_buffer_minutes: number;
  min_round_gap_minutes: number;
  status: DriveStatus;
  created_by?: string;
  schedule_version?: number;
  stages: Stage[];
}

export type DriveCandidateStatus = 'active' | 'withdrawn' | 'selected' | 'rejected';

export interface Enrollment {
  drive_id: string;
  candidate_id: string;
  status: DriveCandidateStatus;
  current_stage_id?: string;
  candidate_name?: string;
  candidate_email?: string;
  roll_number?: string;
  branch?: string;
}

export interface Room {
  id: string;
  name: string;
  capacity: number;
  location?: string;
  is_active: boolean;
}

export interface WindowTime {
  start_time: string;
  end_time: string;
}

export interface AvailabilityOut {
  windows: WindowTime[];
}

export type InterviewStatus =
  | 'proposed'
  | 'scheduled'
  | 'confirmed'
  | 'completed'
  | 'cancelled'
  | 'no_show';

export interface Interview {
  id: string;
  drive_id: string;
  stage_id: string;
  candidate_id: string;
  room_id: string;
  start_time: string;
  end_time: string;
  status: InterviewStatus;
  version: number;
  interviewer_ids?: string[];
  candidate_name?: string;
  stage_name?: string;
  room_name?: string;
  panel?: Array<{ id: string; name: string }>;
}

export interface EvaluationCriterion {
  name: string;
  score: number;
  weight?: number;
  notes?: string;
}

export interface Evaluation {
  id: string;
  interview_id: string;
  author_id: string;
  author_name?: string;
  criteria_ratings: Record<string, number>;
  overall_score?: number;
  recommendation: 'strong_hire' | 'hire' | 'lean_hire' | 'lean_reject' | 'reject';
  feedback: string;
  created_at: string;
  updated_at?: string;
}

export interface InterviewEvaluationsOut {
  interview_id: string;
  evaluations: Evaluation[];
  can_submit: boolean;
  colleagues_hidden: boolean;
}

export interface UnscheduledReason {
  code: string;
  detail?: string;
}

export interface UnscheduledCandidate {
  candidate_id: string;
  candidate_name?: string;
  stage_id: string;
  stage_name?: string;
  reasons: UnscheduledReason[];
}

export interface ScheduleProposal {
  drive_id: string;
  schedule_version: number;
  solver_status: string;
  complete: boolean;
  interviews: Interview[];
  unscheduled: UnscheduledCandidate[];
}

export interface Blocker {
  kind: string;
  resource_id: string;
  interviews: any[];
}

export interface VerifiedFix {
  kind: string;
  description: string;
  target_id?: string;
  extra_interviews: number;
}

export interface ExplanationItem {
  candidate_id: string;
  stage_id: string;
  reason_codes: string[];
  summary: string;
  best_slot?: string;
  blockers: Blocker[];
  fixes: VerifiedFix[];
}

export interface ExplainOut {
  drive_id: string;
  schedule_version: number;
  solver_status: string;
  complete: boolean;
  scheduled: number;
  unscheduled_count: number;
  explanations: ExplanationItem[];
  what_ifs: any[];
  budget_exhausted: boolean;
}

export interface RescueDisruption {
  kind: 'interviewer' | 'room' | 'candidate';
  resource_id: string;
  start_time: string;
  end_time: string;
  implicit?: boolean;
}

export interface Placement {
  start_time: string;
  end_time: string;
  room_id: string;
  interviewer_ids: string[];
}

export interface RescueMove {
  interview_id: string;
  candidate_id: string;
  stage_id: string;
  old: Placement;
  new: Placement;
  changes: string[];
  directly_affected: boolean;
  notifies_candidate: boolean;
}

export interface RescueDropped {
  interview_id: string;
  candidate_id: string;
  stage_id: string;
  reasons: UnscheduledReason[];
}

export interface RescuePlan {
  drive_id: string;
  schedule_version: number;
  solver_status: string;
  fully_repaired: boolean;
  plan_fingerprint: string;
  disruptions: RescueDisruption[];
  affected: string[];
  moves: RescueMove[];
  collateral_count: number;
  dropped: RescueDropped[];
  needs_manual: string[];
  unchanged: string[];
  candidates_to_notify: string[];
  interviewers_to_notify: string[];
}

export type RescuePlanOut = RescuePlan;
export type DisruptionIn = RescueDisruption;

export interface RescueRequest {
  disruptions: RescueDisruption[];
  options?: any;
}

export interface RescueApplyRequest {
  disruptions: RescueDisruption[];
  expected_version: number;
  plan_fingerprint: string;
  options?: any;
}

export interface RescueApplyOut extends RescuePlan {
  applied: boolean;
  new_schedule_version: number;
  moved_count: number;
  cancelled_count: number;
  notifications_created: number;
}

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  message: string;
  channel: 'in_app' | 'email';
  is_read: boolean;
  created_at: string;
}

export interface SlotOffer {
  start: string;
  end: string;
}

export interface BookingOffers {
  stage_name: string;
  duration_minutes: number;
  timezone: string;
  booked?: {
    id: string;
    start: string;
    end: string;
    room_name?: string;
  } | null;
  slots: SlotOffer[];
}

export interface CandidateStageDecision {
  stage_id: string;
  notes?: string;
  override?: boolean;
  override_reason?: string;
}

export interface DecisionOut {
  drive_id: string;
  candidate_id: string;
  outcome: 'advanced' | 'selected' | 'rejected';
  status: DriveCandidateStatus;
  from_stage_id: string;
  current_stage_id?: string | null;
  average_score?: number | null;
  rule_met?: boolean | null;
  override_used: boolean;
  cancelled_interviews?: number;
}

export interface StageProgress {
  stage_id: string;
  order_index: number;
  name: string;
  state: 'not_reached' | 'pending' | 'interviewing' | 'awaiting_decision' | 'passed' | 'rejected' | 'withdrawn';
  interview_id?: string | null;
  interview_status?: string | null;
  evaluations: number;
  average_score?: number | null;
  rule_met?: boolean | null;
}

export interface PipelineCandidate {
  candidate_id: string;
  name: string;
  email: string;
  status: DriveCandidateStatus;
  current_stage_id?: string | null;
  stages: StageProgress[];
}

export interface PipelineStageSummary {
  stage_id: string;
  order_index: number;
  name: string;
  candidates_here: number;
  awaiting_decision: number;
  passed: number;
  rejected: number;
}

export interface PipelineStatusResponse {
  drive_id: string;
  title: string;
  status_counts: Record<string, number>;
  stages: PipelineStageSummary[];
  candidates: PipelineCandidate[];
}
