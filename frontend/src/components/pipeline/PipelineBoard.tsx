import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Kanban,
  Table as TableIcon,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ShieldAlert,
  AlertTriangle,
  Users,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import {
  PipelineStatusResponse,
  PipelineCandidate,
  CandidateStageDecision,
  DecisionOut,
} from '@/types/api';
import { Card, Button, Badge, Spinner, Modal, FormField, Textarea, Input } from '@/components/ui';

export interface PipelineBoardProps {
  driveId: string;
  driveTitle?: string;
  onGoToSchedule?: () => void;
}

export const PipelineBoard: React.FC<PipelineBoardProps> = ({
  driveId,
  onGoToSchedule,
}) => {
  const queryClient = useQueryClient();

  const [viewType, setViewType] = useState<'kanban' | 'table'>('kanban');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedCandidate, setSelectedCandidate] = useState<PipelineCandidate | null>(null);

  // Decision Modal State
  const [decisionType, setDecisionType] = useState<'advance' | 'reject'>('advance');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [isOverride, setIsOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const { data: pipelineData, isLoading, refetch } = useQuery<PipelineStatusResponse>({
    queryKey: ['drive-pipeline', driveId, statusFilter],
    queryFn: () =>
      apiClient<PipelineStatusResponse>(
        `/drives/${driveId}/pipeline${
          statusFilter !== 'all' ? `?status=${statusFilter}` : ''
        }`
      ),
    enabled: !!driveId,
  });

  const advanceMutation = useMutation({
    mutationFn: (body: CandidateStageDecision) =>
      apiClient.post<DecisionOut>(
        `/drives/${driveId}/candidates/${selectedCandidate?.candidate_id}/advance`,
        body
      ),
    onSuccess: () => {
      setDecisionError(null);
      setSelectedCandidate(null);
      setIsOverride(false);
      setOverrideReason('');
      setDecisionNotes('');
      queryClient.invalidateQueries({ queryKey: ['drive-pipeline', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
      refetch();
    },
    onError: (err: any) => {
      if (err.status === 409 && !isOverride) {
        // Pass rule not met or evidence missing -> suggest override
        setDecisionError(
          `${err.message}. You can apply an Audited Override if you wish to bypass this requirement.`
        );
      } else {
        setDecisionError(err.message || 'Failed to advance candidate.');
      }
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (body: CandidateStageDecision) =>
      apiClient.post<DecisionOut>(
        `/drives/${driveId}/candidates/${selectedCandidate?.candidate_id}/reject`,
        body
      ),
    onSuccess: () => {
      setDecisionError(null);
      setSelectedCandidate(null);
      setDecisionNotes('');
      queryClient.invalidateQueries({ queryKey: ['drive-pipeline', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
      refetch();
    },
    onError: (err: any) => {
      setDecisionError(err.message || 'Failed to reject candidate.');
    },
  });

  const handleDecisionSubmit = () => {
    if (!selectedCandidate) return;

    // Current candidate stage id
    const stageId =
      selectedCandidate.current_stage_id ||
      (selectedCandidate.stages.length > 0 ? selectedCandidate.stages[0].stage_id : null);

    if (!stageId) return;

    if (decisionType === 'advance') {
      if (isOverride && (!overrideReason || overrideReason.trim().length < 10)) {
        setDecisionError('Audit override reason must be at least 10 characters.');
        return;
      }
      advanceMutation.mutate({
        stage_id: stageId,
        notes: decisionNotes.trim() || undefined,
        override: isOverride,
        override_reason: isOverride ? overrideReason.trim() : undefined,
      });
    } else {
      rejectMutation.mutate({
        stage_id: stageId,
        notes: decisionNotes.trim() || undefined,
        override: false,
      });
    }
  };

  const stages = pipelineData?.stages || [];
  const candidates = pipelineData?.candidates || [];

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <Card className="p-4 bg-slate-900/90 border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Kanban className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">Candidate Pipeline Board</h3>
              <p className="text-xs text-slate-400">
                Multi-stage tracking, interview rubric scores, and progression decisions.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300 focus:outline-none"
            >
              <option value="all">All Candidates</option>
              <option value="active">Active Only</option>
              <option value="selected">Selected</option>
              <option value="rejected">Rejected</option>
              <option value="withdrawn">Withdrawn</option>
            </select>

            {/* View Switcher */}
            <div className="flex items-center gap-1 p-1 bg-slate-950 border border-slate-800 rounded-lg">
              <button
                onClick={() => setViewType('kanban')}
                className={`p-1.5 rounded text-xs transition-colors ${
                  viewType === 'kanban'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title="Kanban Board View"
              >
                <Kanban className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setViewType('table')}
                className={`p-1.5 rounded text-xs transition-colors ${
                  viewType === 'table'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                title="Table View"
              >
                <TableIcon className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* Main Board Content */}
      {isLoading ? (
        <Card className="p-12 text-center bg-slate-900/60 border-slate-800">
          <Spinner size="lg" className="mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Loading candidate pipeline...</p>
        </Card>
      ) : candidates.length === 0 ? (
        <Card className="p-12 text-center bg-slate-900/60 border-slate-800">
          <Users className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-200">No Candidates in Pipeline</h3>
          <p className="text-xs text-slate-400 mt-1">
            Enrol applicants from the Candidates tab to populate the pipeline board.
          </p>
        </Card>
      ) : viewType === 'kanban' ? (
        /* KANBAN BOARD */
        <div className="flex gap-4 overflow-x-auto pb-4 items-start min-h-[550px]">
          {stages.map((stage) => {
            const stageCandidates = candidates.filter(
              (c) =>
                c.status === 'active' &&
                (c.current_stage_id === stage.stage_id ||
                  (!c.current_stage_id && stage.order_index === 0))
            );

            return (
              <div
                key={stage.stage_id}
                className="w-80 shrink-0 bg-slate-900/80 border border-slate-800 rounded-2xl p-3 space-y-3"
              >
                {/* Column Header */}
                <div className="flex items-center justify-between px-2 pt-1">
                  <div>
                    <h4 className="text-xs font-bold text-slate-200 truncate uppercase tracking-wider">
                      {stage.order_index + 1}. {stage.name}
                    </h4>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {stageCandidates.length} candidate{stageCandidates.length !== 1 ? 's' : ''} here
                    </span>
                  </div>
                  <Badge variant="brand" size="sm">
                    {stage.passed} Passed
                  </Badge>
                </div>

                {/* Candidate Cards */}
                <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
                  {stageCandidates.map((cand) => {
                    const currentStageProgress = cand.stages.find(
                      (s) => s.stage_id === stage.stage_id
                    );

                    return (
                      <div
                        key={cand.candidate_id}
                        onClick={() => setSelectedCandidate(cand)}
                        className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-900/90 transition-all cursor-pointer space-y-2.5 shadow-sm group"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h5 className="text-xs font-bold text-slate-200 group-hover:text-indigo-300 transition-colors">
                              {cand.name}
                            </h5>
                            <p className="text-[10px] text-slate-500 truncate">{cand.email}</p>
                          </div>
                          <Badge
                            variant={
                              currentStageProgress?.state === 'awaiting_decision'
                                ? 'warning'
                                : currentStageProgress?.state === 'interviewing'
                                ? 'brand'
                                : 'neutral'
                            }
                            size="sm"
                          >
                            {currentStageProgress?.state?.replace('_', ' ') || 'Pending'}
                          </Badge>
                        </div>

                        {/* Progress Stats */}
                        {currentStageProgress && (
                          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800/60">
                            <span>
                              Evals: <strong>{currentStageProgress.evaluations}</strong>
                            </span>
                            {currentStageProgress.average_score !== null && (
                              <span className="text-indigo-300 font-bold">
                                Avg: {currentStageProgress.average_score} / 10
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* Selected Column */}
          <div className="w-80 shrink-0 bg-slate-900/80 border border-slate-800 rounded-2xl p-3 space-y-3">
            <div className="flex items-center justify-between px-2 pt-1">
              <div>
                <h4 className="text-xs font-bold text-emerald-300 uppercase tracking-wider">
                  Selected / Hired
                </h4>
                <span className="text-[11px] text-slate-500 font-mono">
                  {candidates.filter((c) => c.status === 'selected').length} candidates
                </span>
              </div>
              <Badge variant="success" size="sm">
                Completed
              </Badge>
            </div>
            <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
              {candidates
                .filter((c) => c.status === 'selected')
                .map((cand) => (
                  <div
                    key={cand.candidate_id}
                    onClick={() => setSelectedCandidate(cand)}
                    className="p-3.5 rounded-xl bg-slate-950 border border-emerald-500/20 hover:border-emerald-500/40 cursor-pointer space-y-1.5 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <h5 className="text-xs font-bold text-emerald-200">{cand.name}</h5>
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    </div>
                    <p className="text-[10px] text-slate-500">{cand.email}</p>
                  </div>
                ))}
            </div>
          </div>

          {/* Rejected Column */}
          <div className="w-80 shrink-0 bg-slate-900/80 border border-slate-800 rounded-2xl p-3 space-y-3">
            <div className="flex items-center justify-between px-2 pt-1">
              <div>
                <h4 className="text-xs font-bold text-rose-300 uppercase tracking-wider">
                  Rejected
                </h4>
                <span className="text-[11px] text-slate-500 font-mono">
                  {candidates.filter((c) => c.status === 'rejected').length} candidates
                </span>
              </div>
              <Badge variant="danger" size="sm">
                Archived
              </Badge>
            </div>
            <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
              {candidates
                .filter((c) => c.status === 'rejected')
                .map((cand) => (
                  <div
                    key={cand.candidate_id}
                    onClick={() => setSelectedCandidate(cand)}
                    className="p-3.5 rounded-xl bg-slate-950 border border-rose-500/20 hover:border-rose-500/40 cursor-pointer space-y-1.5 transition-all opacity-80"
                  >
                    <div className="flex items-center justify-between">
                      <h5 className="text-xs font-bold text-rose-200">{cand.name}</h5>
                      <XCircle className="w-4 h-4 text-rose-400" />
                    </div>
                    <p className="text-[10px] text-slate-500">{cand.email}</p>
                  </div>
                ))}
            </div>
          </div>
        </div>
      ) : (
        /* TABLE VIEW */
        <Card className="p-0 bg-slate-900/90 border-slate-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950 border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3">Candidate</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Current Round</th>
                  <th className="px-5 py-3">Stage Progress</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-200">
                {candidates.map((cand) => {
                  const currStage = stages.find((s) => s.stage_id === cand.current_stage_id);
                  return (
                    <tr
                      key={cand.candidate_id}
                      onClick={() => setSelectedCandidate(cand)}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                    >
                      <td className="px-5 py-3.5">
                        <p className="font-semibold text-slate-100">{cand.name}</p>
                        <p className="text-xs text-slate-500">{cand.email}</p>
                      </td>
                      <td className="px-5 py-3.5">
                        <Badge
                          variant={
                            cand.status === 'selected'
                              ? 'success'
                              : cand.status === 'rejected'
                              ? 'danger'
                              : 'brand'
                          }
                        >
                          {cand.status}
                        </Badge>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-300">
                        {currStage?.name || 'Round 1'}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex gap-1.5">
                          {cand.stages.map((stg) => (
                            <span
                              key={stg.stage_id}
                              className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                                stg.state === 'passed'
                                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                  : stg.state === 'rejected'
                                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                  : stg.state === 'awaiting_decision'
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                  : 'bg-slate-800 text-slate-500'
                              }`}
                              title={`${stg.name}: ${stg.state}`}
                            >
                              R{stg.order_index + 1}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedCandidate(cand);
                          }}
                          className="text-indigo-400 hover:text-indigo-300"
                        >
                          Decide / View
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Candidate Detail & Decision Modal */}
      {selectedCandidate && (
        <Modal
          isOpen={!!selectedCandidate}
          onClose={() => {
            setSelectedCandidate(null);
            setDecisionError(null);
            setIsOverride(false);
          }}
          title={`Candidate Dossier: ${selectedCandidate.name}`}
          maxWidth="lg"
        >
          <div className="space-y-5">
            {/* Candidate Header */}
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
              <div>
                <h4 className="text-base font-bold text-slate-100">{selectedCandidate.name}</h4>
                <p className="text-xs text-slate-400">{selectedCandidate.email}</p>
              </div>
              <Badge
                variant={
                  selectedCandidate.status === 'selected'
                    ? 'success'
                    : selectedCandidate.status === 'rejected'
                    ? 'danger'
                    : 'brand'
                }
              >
                Status: {selectedCandidate.status}
              </Badge>
            </div>

            {/* Error / Conflict Alert */}
            {decisionError && (
              <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="text-xs text-rose-200/90 leading-relaxed">
                  <p>{decisionError}</p>
                  {!isOverride && decisionType === 'advance' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setIsOverride(true)}
                      className="mt-2 border-rose-500/40 text-rose-300 hover:bg-rose-500/10 text-xs"
                    >
                      <ShieldAlert className="w-3.5 h-3.5 mr-1" />
                      Proceed with Audited Override
                    </Button>
                  )}
                </div>
              </div>
            )}

            {/* Stage-by-Stage History & Evaluations */}
            <div className="space-y-3">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Stage Evaluation History
              </label>
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {selectedCandidate.stages.map((stg) => (
                  <div
                    key={stg.stage_id}
                    className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-200">
                          {stg.order_index + 1}. {stg.name}
                        </span>
                        <Badge
                          variant={
                            stg.state === 'passed'
                              ? 'success'
                              : stg.state === 'rejected'
                              ? 'danger'
                              : stg.state === 'awaiting_decision'
                              ? 'warning'
                              : 'neutral'
                          }
                          size="sm"
                        >
                          {stg.state}
                        </Badge>
                      </div>
                      <div className="text-xs font-mono text-slate-400">
                        {stg.average_score !== null ? (
                          <span className="text-indigo-300 font-bold">
                            Score: {stg.average_score} / 10
                          </span>
                        ) : (
                          'No scores yet'
                        )}
                      </div>
                    </div>

                    <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800/40">
                      <span>Submitted Evaluations: {stg.evaluations}</span>
                      {stg.rule_met !== null && (
                        <span>
                          Pass Rule Met:{' '}
                          <strong
                            className={stg.rule_met ? 'text-emerald-400' : 'text-rose-400'}
                          >
                            {stg.rule_met ? 'Yes' : 'No'}
                          </strong>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Decision Controls (if active) */}
            {selectedCandidate.status === 'active' && (
              <div className="space-y-4 pt-3 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                    Coordinator Decision
                  </label>
                  <div className="flex items-center gap-1.5 p-1 bg-slate-950 rounded-lg border border-slate-800">
                    <button
                      type="button"
                      onClick={() => {
                        setDecisionType('advance');
                        setIsOverride(false);
                      }}
                      className={`px-3 py-1 text-xs font-medium rounded ${
                        decisionType === 'advance'
                          ? 'bg-emerald-600 text-white'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Advance Candidate
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDecisionType('reject');
                        setIsOverride(false);
                      }}
                      className={`px-3 py-1 text-xs font-medium rounded ${
                        decisionType === 'reject'
                          ? 'bg-rose-600 text-white'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Reject Candidate
                    </button>
                  </div>
                </div>

                <FormField label="Decision Notes">
                  <Textarea
                    placeholder="Enter coordinator rationale or board deliberation notes..."
                    rows={2}
                    value={decisionNotes}
                    onChange={(e) => setDecisionNotes(e.target.value)}
                    className="text-xs"
                  />
                </FormField>

                {/* Audit Override Block */}
                {isOverride && (
                  <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-amber-400" />
                      <h5 className="text-xs font-bold text-amber-300">
                        Audited Override Justification (Permanent Log)
                      </h5>
                    </div>
                    <p className="text-[11px] text-amber-200/80">
                      Bypassing missing feedback or sub-threshold scores is logged in the immutable audit trail.
                    </p>
                    <Input
                      placeholder="Explain reason for override (min 10 characters)..."
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      className="text-xs bg-slate-950 border-amber-500/40 text-amber-100"
                    />
                  </div>
                )}

                <div className="flex items-center justify-between pt-2">
                  {onGoToSchedule && (
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedCandidate(null);
                        onGoToSchedule();
                      }}
                      className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                    >
                      <span>Go to Schedule Console</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                  <div className="flex gap-2 ml-auto">
                    <Button variant="ghost" onClick={() => setSelectedCandidate(null)}>
                      Cancel
                    </Button>
                    <Button
                      variant={decisionType === 'advance' ? 'primary' : 'danger'}
                      onClick={handleDecisionSubmit}
                      disabled={advanceMutation.isPending || rejectMutation.isPending}
                      className={decisionType === 'advance' ? 'bg-emerald-600 hover:bg-emerald-500' : ''}
                    >
                      {advanceMutation.isPending || rejectMutation.isPending ? (
                        <>
                          <Spinner size="sm" className="mr-2" />
                          Processing...
                        </>
                      ) : decisionType === 'advance' ? (
                        <>
                          <CheckCircle2 className="w-4 h-4 mr-1.5" />
                          {isOverride ? 'Apply Override & Advance' : 'Advance Candidate'}
                        </>
                      ) : (
                        <>
                          <XCircle className="w-4 h-4 mr-1.5" />
                          Confirm Rejection
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
