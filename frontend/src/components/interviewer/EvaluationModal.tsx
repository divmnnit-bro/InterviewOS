import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Award,
  Sparkles,
  Lock,
  AlertCircle,
  Plus,
  Trash2,
  Users,
  MessageSquare,
  Clock,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import { Button, Modal, Badge, Spinner, FormField, Textarea, Input } from '@/components/ui';
import { useAuth } from '@/context/AuthContext';

export interface EvaluationModalProps {
  interviewId: string;
  candidateName: string;
  stageName: string;
  driveTitle: string;
  startTime: string;
  endTime: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmitted?: () => void;
}

export type RecommendationType = 'strong_hire' | 'hire' | 'no_hire' | 'strong_no_hire';

export interface EvaluationRead {
  id: string;
  interview_id: string;
  interviewer_id: string;
  score: number;
  rubric: Record<string, number>;
  feedback: string | null;
  recommendation: RecommendationType | null;
  submitted_at: string;
  updated_at: string;
}

export interface InterviewEvaluationsOut {
  interview_id: string;
  visibility: 'all' | 'own_only';
  panel_size: number;
  submitted_count: number;
  evaluations: EvaluationRead[];
}

export const EvaluationModal: React.FC<EvaluationModalProps> = ({
  interviewId,
  candidateName,
  stageName,
  driveTitle,
  startTime,
  endTime,
  isOpen,
  onClose,
  onSubmitted,
}) => {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<'evaluate' | 'colleagues'>('evaluate');
  const [rubric, setRubric] = useState<Record<string, number | undefined>>({
    'Problem Solving': undefined,
    'Technical Competence': undefined,
    Communication: undefined,
    'Culture & Values': undefined,
  });
  const [newCriterionName, setNewCriterionName] = useState('');
  const [manualScore, setManualScore] = useState<string>('');
  const [recommendation, setRecommendation] = useState<RecommendationType | ''>('');
  const [feedback, setFeedback] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  // Check if interview has started
  const now = new Date();
  const start = new Date(startTime);
  const hasStarted = now >= start;

  // Query existing evaluations
  const { data: evData, isLoading: isEvLoading, refetch } = useQuery<InterviewEvaluationsOut>({
    queryKey: ['interview-evaluations', interviewId],
    queryFn: () => apiClient<InterviewEvaluationsOut>(`/interviews/${interviewId}/evaluations`),
    enabled: isOpen && !!interviewId,
  });

  // Calculate default score from rubric mean
  const rubricValues = Object.values(rubric).filter((rating): rating is number => typeof rating === 'number');
  const rubricValid = rubricValues.every((rating) => Number.isFinite(rating) && rating >= 0 && rating <= 10);
  const computedAverage =
    rubricValues.length > 0 && rubricValid
      ? Number((rubricValues.reduce((a, b) => a + b, 0) / rubricValues.length).toFixed(2))
      : null;

  const effectiveScore = manualScore.trim() !== '' ? Number(manualScore) : computedAverage;
  const manualScoreValid = manualScore.trim() === '' || (Number.isFinite(Number(manualScore)) && Number(manualScore) >= 0 && Number(manualScore) <= 10);
  const hasScore = manualScore.trim() !== '' || rubricValues.length > 0;

  // Check if author has already submitted
  const ownEvaluation = evData?.evaluations?.find((e) => e.interviewer_id === user?.id);
  const isRevision = !!ownEvaluation;

  useEffect(() => {
    if (ownEvaluation) {
      if (ownEvaluation.rubric && Object.keys(ownEvaluation.rubric).length > 0) {
        setRubric(ownEvaluation.rubric);
      }
      if (ownEvaluation.score !== undefined) {
        setManualScore(String(ownEvaluation.score));
      }
      if (ownEvaluation.recommendation) {
        setRecommendation(ownEvaluation.recommendation);
      }
      if (ownEvaluation.feedback) {
        setFeedback(ownEvaluation.feedback);
      }
    }
  }, [ownEvaluation]);

  const submitMutation = useMutation({
    mutationFn: async () => {
      const ratedRubric = Object.fromEntries(
        Object.entries(rubric).filter((entry): entry is [string, number] => typeof entry[1] === 'number')
      );
      if (!recommendation) throw new Error('Choose a recommendation before submitting.');
      if (manualScore.trim() !== '' && !manualScoreValid) {
        throw new Error('Overall score must be a number from 0 to 10.');
      }
      if (!rubricValid) {
        throw new Error('Each rubric rating must be a number from 0 to 10.');
      }
      if (!hasScore) {
        throw new Error('Rate at least one rubric criterion or enter an overall score.');
      }
      const payload: any = {
        rubric: ratedRubric,
        recommendation,
        feedback: feedback.trim() || null,
      };
      if (manualScore.trim() !== '') {
        payload.score = Number(manualScore);
      }
      return await apiClient.post<EvaluationRead>(
        `/interviews/${interviewId}/evaluations`,
        payload
      );
    },
    onSuccess: () => {
      setValidationError(null);
      queryClient.invalidateQueries({ queryKey: ['interview-evaluations', interviewId] });
      queryClient.invalidateQueries({ queryKey: ['my-interviews'] });
      refetch();
      if (onSubmitted) onSubmitted();
      onClose();
    },
    onError: (err: any) => {
      setValidationError(err.message || 'Failed to submit evaluation.');
    },
  });

  const handleRatingChange = (criterion: string, value: number | undefined) => {
    setRubric((prev) => ({ ...prev, [criterion]: value }));
  };

  const handleAddCriterion = () => {
    const trimmed = newCriterionName.trim();
    if (!trimmed) return;
    if (Object.keys(rubric).length >= 20) {
      setValidationError('Maximum 20 rubric criteria allowed.');
      return;
    }
    setRubric((prev) => ({ ...prev, [trimmed]: undefined }));
    setNewCriterionName('');
  };

  const handleRemoveCriterion = (criterion: string) => {
    setRubric((prev) => {
      const next = { ...prev };
      delete next[criterion];
      return next;
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Candidate Evaluation"
      maxWidth="lg"
    >
      <div className="space-y-5">
        {/* Header Summary */}
        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-400">
              {driveTitle}
            </span>
            <h3 className="text-base font-bold text-slate-100">{candidateName}</h3>
            <p className="text-xs text-slate-400 mt-0.5">Round: {stageName}</p>
          </div>
          <div className="flex flex-col items-start sm:items-end gap-1 text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-500" />
              {new Date(startTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} -{' '}
              {new Date(endTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
            {isRevision ? (
              <Badge variant="warning">Revision Mode</Badge>
            ) : (
              <Badge variant="brand">New Submission</Badge>
            )}
          </div>
        </div>

        {/* Start Time Guard Warning */}
        {!hasStarted && (
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-200/90 leading-relaxed">
              <strong>Interview has not started yet.</strong> Evaluations open once the interview begins at{' '}
              <span className="font-mono font-bold text-amber-300">
                {new Date(startTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              . You can review the criteria in advance.
            </div>
          </div>
        )}

        {/* Error alert */}
        {validationError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <p className="text-xs text-rose-200/90 leading-relaxed">{validationError}</p>
          </div>
        )}

        {/* Tab Switcher */}
        <div className="flex border-b border-slate-800">
          <button
            type="button"
            onClick={() => setActiveTab('evaluate')}
            className={`px-4 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'evaluate'
                ? 'border-indigo-500 text-indigo-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Award className="w-3.5 h-3.5" />
            My Evaluation
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('colleagues')}
            className={`px-4 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'colleagues'
                ? 'border-indigo-500 text-indigo-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            Colleagues' Feedback
            {evData?.visibility === 'own_only' && <Lock className="w-3 h-3 text-amber-400 ml-1" />}
          </button>
        </div>

        {/* TAB 1: EVALUATION FORM */}
        {activeTab === 'evaluate' && (
          <div className="space-y-5">
            {/* Rubric Criteria List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Rubric Criteria Ratings (0 to 10)
                </label>
                <span className="text-xs text-indigo-300 font-mono font-bold">
                  Average: {computedAverage === null ? (rubricValues.length ? 'Check ratings' : 'Not rated') : `${computedAverage} / 10`}
                </span>
              </div>

              <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
                {Object.entries(rubric).map(([name, rating]) => (
                  <div
                    key={name}
                    className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between gap-3"
                  >
                    <span className="text-xs font-medium text-slate-200 flex-1">{name}</span>
                    <div className="flex items-center gap-3">
                      <Input
                        type="number"
                        min="0"
                        max="10"
                        step="0.5"
                        placeholder="Not rated"
                        value={rating ?? ''}
                        onChange={(e) => handleRatingChange(name, e.target.value === '' ? undefined : Number(e.target.value))}
                        aria-label={`${name} rating out of 10`}
                        error={rating !== undefined && (!Number.isFinite(rating) || rating < 0 || rating > 10) ? 'Enter 0 to 10' : undefined}
                        className="w-28 sm:w-36 text-center"
                      />
                      {Object.keys(rubric).length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveCriterion(name)}
                          className="text-slate-500 hover:text-rose-400 p-1 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Add Custom Criterion */}
              <div className="flex items-center gap-2 pt-1">
                <Input
                  placeholder="Add custom criterion (e.g. Code Cleanliness)"
                  value={newCriterionName}
                  onChange={(e) => setNewCriterionName(e.target.value)}
                  className="text-xs"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAddCriterion}
                  disabled={!newCriterionName.trim()}
                  className="shrink-0 border-slate-700 text-slate-300"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" />
                  Add
                </Button>
              </div>
            </div>

            {/* Overall Score Override & Recommendation */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Overall Score (optional override, 0-10)">
                <Input
                  type="number"
                  min="0"
                  max="10"
                  step="0.1"
                  placeholder={computedAverage === null ? 'Rate a criterion to calculate' : `Calculated: ${computedAverage}`}
                  value={manualScore}
                  onChange={(e) => setManualScore(e.target.value)}
                  error={!manualScoreValid ? 'Enter a number from 0 to 10' : undefined}
                />
              </FormField>

              <FormField label="Recommendation" required>
                <select
                  value={recommendation}
                  onChange={(e) => setRecommendation(e.target.value as RecommendationType)}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select recommendation</option>
                  <option value="strong_hire">Strong Hire</option>
                  <option value="hire">Hire</option>
                  <option value="no_hire">No Hire</option>
                  <option value="strong_no_hire">Strong No Hire</option>
                </select>
              </FormField>
            </div>

            {/* Written Feedback */}
            <FormField label="Written Feedback & Justification">
              <Textarea
                placeholder="Share your structured observations, code quality notes, technical strengths, and improvement areas..."
                rows={4}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                className="text-xs"
              />
            </FormField>

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <div className="text-xs text-slate-400">
                Effective Score:{' '}
                <strong className="text-indigo-300 font-mono font-bold">
                  {effectiveScore === null || !Number.isFinite(effectiveScore) ? 'Not rated' : `${effectiveScore} / 10`}
                </strong>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={onClose}>
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending || !hasStarted || !recommendation || !hasScore || !manualScoreValid || !rubricValid}
                  className="bg-indigo-600 hover:bg-indigo-500"
                >
                  {submitMutation.isPending ? (
                    <>
                      <Spinner size="sm" className="mr-2" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-1.5" />
                      {isRevision ? 'Update Evaluation (Revise)' : 'Submit Evaluation'}
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: COLLEAGUES' FEEDBACK */}
        {activeTab === 'colleagues' && (
          <div className="space-y-4">
            {isEvLoading ? (
              <div className="py-10 text-center">
                <Spinner size="md" className="mx-auto" />
              </div>
            ) : evData?.visibility === 'own_only' ? (
              /* Locked State */
              <div className="p-8 text-center rounded-2xl bg-amber-500/5 border border-amber-500/20 space-y-3">
                <div className="w-12 h-12 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto">
                  <Lock className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-bold text-amber-200">Colleagues' Feedback is Locked</h4>
                <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                  To prevent cognitive anchoring and ensure unbiased scoring, InterviewOS reveals panel feedback only after you submit your own evaluation.
                </p>
                <div className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setActiveTab('evaluate')}
                    className="border-amber-500/30 text-amber-300 hover:bg-amber-500/10"
                  >
                    Go to My Evaluation Form
                  </Button>
                </div>
              </div>
            ) : evData?.evaluations?.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                No colleagues have submitted evaluations yet.
              </div>
            ) : (
              /* Unlocked Colleagues Submissions */
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {evData?.evaluations.map((ev, i) => (
                  <div
                    key={ev.id || i}
                    className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-200">
                          Panelist #{i + 1}
                        </span>
                        <Badge
                          variant={
                            ev.recommendation === 'strong_hire' || ev.recommendation === 'hire'
                              ? 'success'
                              : ev.recommendation === 'no_hire' || ev.recommendation === 'strong_no_hire'
                              ? 'danger'
                              : 'warning'
                          }
                          size="sm"
                        >
                          {ev.recommendation?.replace('_', ' ')}
                        </Badge>
                      </div>
                      <span className="text-xs font-mono font-bold text-indigo-300">
                        Score: {ev.score} / 10
                      </span>
                    </div>

                    {ev.rubric && Object.keys(ev.rubric).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {Object.entries(ev.rubric).map(([crit, rat]) => (
                          <span
                            key={crit}
                            className="text-[11px] px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-slate-300 font-mono"
                          >
                            {crit}: <strong>{rat}</strong>
                          </span>
                        ))}
                      </div>
                    )}

                    {ev.feedback && (
                      <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/60 text-xs text-slate-300 italic flex items-start gap-2">
                        <MessageSquare className="w-3.5 h-3.5 text-slate-500 shrink-0 mt-0.5" />
                        <span>"{ev.feedback}"</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
