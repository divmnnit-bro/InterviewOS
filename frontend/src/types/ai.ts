export interface CodingQuestion {
  title: string;
  description: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  constraints: string[];
  sample_inputs_outputs: Array<{ input: string; output: string; explanation?: string }>;
  expected_concepts: string[];
  edge_cases: string[];
  evaluation_rubric: Record<string, string>;
}

export interface SystemDesignScenario {
  title: string;
  problem_statement: string;
  functional_requirements: string[];
  non_functional_requirements: string[];
  scalability_concerns: string[];
  evaluation_criteria: Record<string, string>;
}

export interface BehavioralQuestion {
  question: string;
  competency: string;
  expected_indicators: string[];
  red_flags: string[];
}

export interface RubricTemplate {
  criteria: Array<{
    name: string;
    description: string;
    weight: number;
    scoring_levels: Record<string, string>;
  }>;
}

export interface InterviewKitResponse {
  kit_id?: string;
  drive_id?: string;
  stage_name?: string;
  topic?: string;
  difficulty?: string;
  job_id?: string;
  is_ai_generated: boolean;
  provider_used?: string;
  model_used?: string;
  coding_questions: CodingQuestion[];
  system_design_scenarios: SystemDesignScenario[];
  behavioral_questions: BehavioralQuestion[];
  rubric_template: RubricTemplate;
}

export interface CandidateCounts {
  total_enrolled: number;
  active_in_pipeline: number;
  selected: number;
  rejected: number;
  withdrawn: number;
}

export interface UpcomingRound {
  stage_id: string;
  stage_name: string;
  order_index: number;
  scheduled_interviews: number;
  completed_interviews: number;
}

export interface MissingFeedbackItem {
  interview_id: string;
  candidate_id: string;
  candidate_name: string;
  interviewer_id: string;
  interviewer_name: string;
  stage_name: string;
  scheduled_time: string;
}

export interface DriveBriefResponse {
  drive_id: string;
  drive_title: string;
  drive_status: string;
  candidate_counts: CandidateCounts;
  upcoming_rounds: UpcomingRound[];
  missing_feedback: MissingFeedbackItem[];
  scheduling_conflicts_and_risks: string[];
  pending_actions: string[];
  executive_summary: string;
  is_ai_generated: boolean;
  provider_used?: string;
}

export interface RoundEvaluationSummary {
  stage_name: string;
  order_index: number;
  score?: number | null;
  recommendation?: string;
  interviewer_name?: string | null;
  key_feedback?: string | null;
}

export interface CandidateSummaryResponse {
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  drive_id: string;
  drive_title: string;
  pipeline_status: string;
  current_stage_name?: string | null;
  average_score?: number | null;
  evaluations_count: number;
  completed_rounds: RoundEvaluationSummary[];
  recurring_strengths: string[];
  recurring_weaknesses: string[];
  recommendation_synthesis: string;
  progression_readiness: string;
  disclaimer: string;
  is_ai_generated: boolean;
  provider_used: string;
}

export interface AskRecruitmentDataResponse {
  question: string;
  answer: string;
  data_points: Array<Record<string, string | number | null>>;
  data_points_analyzed: number;
  suggested_followups: string[];
  intent: string;
  is_ai_generated: boolean;
  provider_used: string;
}
