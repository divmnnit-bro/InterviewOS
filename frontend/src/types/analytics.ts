export interface AnalyticsOverview {
  total_drives: number;
  active_drives: number;
  completed_drives: number;
  total_candidates_registered: number;
  total_candidates_enrolled: number;
  total_interviews_scheduled: number;
  total_interviews_completed: number;
  global_completion_rate: number;
  total_evaluations_submitted: number;
  average_score_across_all_evaluations?: number | null;
  pending_evaluations_count: number;
  upcoming_interviews: Array<{
    interview_id: string;
    drive_id: string;
    drive_title: string;
    stage_name: string;
    candidate_name: string;
    room_name?: string | null;
    start_time: string;
    end_time: string;
  }>;
  recent_activity: Array<{ action: string; entity_type: string; timestamp: string }>;
  generated_at: string;
}

export interface DriveStageAnalytics {
  stage_id: string;
  stage_name: string;
  order_index: number;
  stage_type: string;
  candidates_count: number;
  passed_count: number;
  failed_count: number;
  pending_count: number;
  conversion_rate: number;
}

export interface DriveAnalytics {
  drive_id: string;
  drive_title: string;
  drive_status: string;
  timezone: string;
  window_start: string;
  window_end: string;
  total_enrolled: number;
  active_in_pipeline: number;
  selected_count: number;
  rejected_count: number;
  withdrawn_count: number;
  overall_selection_rate: number;
  interview_completion_rate: number;
  total_interviews: number;
  completed_interviews: number;
  cancelled_interviews: number;
  pending_feedback_count: number;
  stage_funnel: DriveStageAnalytics[];
  average_stage_duration_hours: number;
  room_utilization_percent: number;
  rescue_operations_count: number;
  generated_at: string;
}

export interface StageAnalytics {
  stage_id: string;
  stage_name: string;
  order_index: number;
  stage_type: string;
  duration_minutes: number;
  panel_size: number;
  total_candidates_entered: number;
  conversion_rate: number;
  dropoff_rate: number;
  average_score?: number | null;
  min_score?: number | null;
  max_score?: number | null;
  median_score?: number | null;
  interviews_completed: number;
  interviews_scheduled: number;
}

export interface InterviewerAnalytics {
  interviewer_id: string;
  name: string;
  email: string;
  department: string;
  capacity_per_day: number;
  skills: string[];
  total_assigned_interviews: number;
  completed_interviews: number;
  pending_evaluations: number;
  utilization_rate: number;
  average_score_given?: number | null;
  evaluator_calibration: string;
}

export interface InterviewersAnalytics {
  total_interviewers: number;
  interviewers: InterviewerAnalytics[];
  generated_at: string;
}
