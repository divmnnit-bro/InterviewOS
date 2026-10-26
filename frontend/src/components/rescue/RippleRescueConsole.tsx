import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  LifeBuoy,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Send,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import {
  RescuePlanOut,
  RescueApplyOut,
  RescueRequest,
  RescueApplyRequest,
  DisruptionIn,
  RescueMove,
  RescueDropped,
} from '@/types/api';
import { Card, Button, Badge, Spinner, FormField, Select, Input } from '@/components/ui';
import { formatTimeUTC } from '@/lib/timelineMath';

export interface RippleRescueConsoleProps {
  driveId: string;
  driveTitle?: string;
  scheduleVersion: number;
  users?: Array<{ id: string; name: string; role: string; department?: string }>;
  rooms?: Array<{ id: string; name: string }>;
  onRescueApplied?: () => void;
}

export const RippleRescueConsole: React.FC<RippleRescueConsoleProps> = ({
  driveId,
  scheduleVersion,
  users = [],
  rooms = [],
  onRescueApplied,
}) => {
  const queryClient = useQueryClient();

  // Disruption Form State
  const [disruptionKind, setDisruptionKind] = useState<'interviewer' | 'room' | 'candidate'>('interviewer');
  const [resourceId, setResourceId] = useState<string>('');
  const [startTime, setStartTime] = useState<string>('2026-11-02T09:00');
  const [endTime, setEndTime] = useState<string>('2026-11-02T13:00');

  // Plan State
  const [previewPlan, setPreviewPlan] = useState<RescuePlanOut | null>(null);
  const [applyResult, setApplyResult] = useState<RescueApplyOut | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [staleConflict, setStaleConflict] = useState<boolean>(false);

  const interviewers = users.filter((u) => u.role === 'interviewer');
  const candidates = users.filter((u) => u.role === 'candidate');

  const resourceMap = new Map([
    ...users.map((u) => [u.id, u.name] as [string, string]),
    ...rooms.map((r) => [r.id, r.name] as [string, string]),
  ]);

  // Preview Mutation
  const previewMutation = useMutation({
    mutationFn: (body: RescueRequest) =>
      apiClient.post<RescuePlanOut>(`/drives/${driveId}/rescue/preview`, body),
    onSuccess: (data) => {
      setPreviewPlan(data);
      setApplyResult(null);
      setErrorMessage(null);
      setStaleConflict(false);
    },
    onError: (err: any) => {
      setErrorMessage(err.message || 'Failed to preview rescue plan.');
    },
  });

  // Apply Mutation
  const applyMutation = useMutation({
    mutationFn: (body: RescueApplyRequest) =>
      apiClient.post<RescueApplyOut>(`/drives/${driveId}/rescue/apply`, body),
    onSuccess: (data) => {
      setApplyResult(data);
      setPreviewPlan(null);
      setErrorMessage(null);
      setStaleConflict(false);
      queryClient.invalidateQueries({ queryKey: ['drive-interviews', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
      if (onRescueApplied) onRescueApplied();
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setStaleConflict(true);
        setErrorMessage(
          'The schedule version or appointments changed since this preview was generated. Please preview the rescue again.'
        );
      } else {
        setErrorMessage(err.message || 'Failed to apply rescue plan.');
      }
    },
  });

  const handlePreview = () => {
    if (!resourceId) {
      setErrorMessage('Please select the affected resource.');
      return;
    }

    const disruption: DisruptionIn = {
      kind: disruptionKind,
      resource_id: resourceId,
      start_time: `${startTime}:00Z`,
      end_time: `${endTime}:00Z`,
    };

    previewMutation.mutate({
      disruptions: [disruption],
    });
  };

  const handleApply = () => {
    if (!previewPlan) return;

    const disruption: DisruptionIn = {
      kind: disruptionKind,
      resource_id: resourceId,
      start_time: `${startTime}:00Z`,
      end_time: `${endTime}:00Z`,
    };

    applyMutation.mutate({
      disruptions: [disruption],
      expected_version: previewPlan.schedule_version,
      plan_fingerprint: previewPlan.plan_fingerprint,
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <Card className="p-5 bg-slate-900/90 border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
              <LifeBuoy className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-100">Ripple Rescue Engine</h3>
                <Badge variant="neutral">Schedule v{scheduleVersion}</Badge>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Atomic disruption repair for unavailable interviewers, closed rooms, or missing candidates.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Error or Stale Conflict Alert */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 text-rose-400 mt-0.5 shrink-0" />
            <div>
              <h4 className="text-sm font-semibold text-rose-300">
                {staleConflict ? 'Version or State Conflict' : 'Rescue Error'}
              </h4>
              <p className="text-xs text-rose-200/80 mt-0.5">{errorMessage}</p>
            </div>
          </div>
          {staleConflict && (
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreview}
              className="border-rose-500/40 text-rose-300 hover:bg-rose-500/10 shrink-0"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              Preview Again
            </Button>
          )}
        </div>
      )}

      {/* Success Banner */}
      {applyResult && (
        <div className="p-5 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 space-y-3">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
            <h4 className="text-base font-bold text-emerald-200">
              Ripple Rescue Successfully Applied! (New Version: v{applyResult.new_schedule_version})
            </h4>
          </div>
          <p className="text-xs text-emerald-200/80 leading-relaxed">
            All moves have been committed atomically to the database. {applyResult.moved_count} interview(s) rescheduled,{' '}
            {applyResult.cancelled_count} cancelled, and {applyResult.notifications_created} notification(s) sent out.
          </p>
        </div>
      )}

      {/* Grid: Disruption Form & Live Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Form: Disruption Inputs */}
        <Card className="p-5 bg-slate-900 border-slate-800 space-y-4">
          <h4 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            Describe Disruption
          </h4>

          <FormField label="Disruption Kind" required>
            <Select
              value={disruptionKind}
              onChange={(e) => {
                setDisruptionKind(e.target.value as any);
                setResourceId('');
              }}
            >
              <option value="interviewer">Interviewer Out (Emergency / Sick)</option>
              <option value="room">Room Closed (Maintenance / Audio Issue)</option>
              <option value="candidate">Candidate Reschedule Request</option>
            </Select>
          </FormField>

          <FormField
            label={
              disruptionKind === 'interviewer'
                ? 'Select Interviewer'
                : disruptionKind === 'room'
                ? 'Select Room'
                : 'Select Candidate'
            }
            required
          >
            <Select
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
            >
              <option value="">-- Choose resource --</option>
              {disruptionKind === 'interviewer' &&
                interviewers.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name} {i.department ? `(${i.department})` : ''}
                  </option>
                ))}
              {disruptionKind === 'room' &&
                rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              {disruptionKind === 'candidate' &&
                candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </Select>
          </FormField>

          <div className="space-y-3">
            <FormField label="Start Time (UTC)">
              <Input
                type="datetime-local"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </FormField>

            <FormField label="End Time (UTC)">
              <Input
                type="datetime-local"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </FormField>
          </div>

          <div className="pt-3 border-t border-slate-800">
            <Button
              variant="primary"
              className="w-full bg-rose-600 hover:bg-rose-500"
              onClick={handlePreview}
              disabled={previewMutation.isPending || !resourceId}
            >
              {previewMutation.isPending ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Calculating Repair...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-1.5" />
                  Preview Rescue Plan
                </>
              )}
            </Button>
          </div>
        </Card>

        {/* Live Preview Display (Span 2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {!previewPlan && !applyResult && (
            <Card className="p-12 text-center bg-slate-900/50 border-slate-800">
              <LifeBuoy className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <h4 className="text-base font-semibold text-slate-300">No Rescue Preview Generated</h4>
              <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
                Select an affected resource and time range on the left, then click "Preview Rescue Plan" to view proposed repairs before applying changes.
              </p>
            </Card>
          )}

          {previewPlan && (
            <div className="space-y-4">
              {/* Summary Stats */}
              <Card className="p-5 bg-slate-900 border-indigo-500/30 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-base font-bold text-slate-100">Proposed Rescue Plan</h4>
                      <Badge
                        variant={previewPlan.fully_repaired ? 'success' : 'warning'}
                      >
                        {previewPlan.fully_repaired ? 'Fully Repaired' : 'Partial Repair'}
                      </Badge>
                      <Badge variant="neutral">Solver: {previewPlan.solver_status}</Badge>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Target Schedule Version: v{previewPlan.schedule_version}
                    </p>
                  </div>

                  <Button
                    variant="primary"
                    onClick={handleApply}
                    disabled={applyMutation.isPending}
                    className="bg-emerald-600 hover:bg-emerald-500"
                  >
                    {applyMutation.isPending ? (
                      <>
                        <Spinner size="sm" className="mr-2" />
                        Applying Changes...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4 mr-1.5" />
                        Apply Repair Plan
                      </>
                    )}
                  </Button>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">Total Moves:</span>
                    <p className="text-lg font-bold text-indigo-300 font-mono mt-0.5">
                      {previewPlan.moves.length}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">Collateral Moves:</span>
                    <p className="text-lg font-bold text-amber-300 font-mono mt-0.5">
                      {previewPlan.collateral_count}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">Dropped / Cancelled:</span>
                    <p className="text-lg font-bold text-rose-300 font-mono mt-0.5">
                      {previewPlan.dropped.length}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <span className="text-slate-400">People to Notify:</span>
                    <p className="text-lg font-bold text-emerald-300 font-mono mt-0.5">
                      {previewPlan.candidates_to_notify.length +
                        previewPlan.interviewers_to_notify.length}
                    </p>
                  </div>
                </div>
              </Card>

              {/* Moves List (Before & After) */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
                  <span>Rescheduled Sessions ({previewPlan.moves.length})</span>
                  {previewPlan.moves.length === 0 && (
                    <span className="text-emerald-400 normal-case font-normal">
                      No interviews needed to be moved!
                    </span>
                  )}
                </label>

                {previewPlan.moves.map((move: RescueMove, idx: number) => (
                  <Card key={idx} className="p-4 bg-slate-900 border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-200">
                          {resourceMap.get(move.candidate_id) || `Candidate ${move.candidate_id.slice(0, 8)}`}
                        </span>
                        {move.directly_affected ? (
                          <Badge variant="danger" size="sm">
                            Direct Hit
                          </Badge>
                        ) : (
                          <Badge variant="warning" size="sm">
                            Collateral Shift
                          </Badge>
                        )}
                      </div>
                      <div className="flex gap-1">
                        {move.changes.map((ch: string) => (
                          <Badge key={ch} variant="brand" size="sm">
                            {ch} changed
                          </Badge>
                        ))}
                      </div>
                    </div>

                    {/* Comparison: Old vs New Placement */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                      {/* Old */}
                      <div className="p-2.5 rounded-lg bg-rose-950/20 border border-rose-500/20 text-rose-300 space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400 block">
                          Before Repair:
                        </span>
                        <p>
                          Time: {formatTimeUTC(move.old.start_time)} - {formatTimeUTC(move.old.end_time)}
                        </p>
                        <p>
                          Room: {resourceMap.get(move.old.room_id || '') || 'Unassigned'}
                        </p>
                      </div>

                      {/* New */}
                      <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/20 text-emerald-300 space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 block">
                          After Repair:
                        </span>
                        <p>
                          Time: {formatTimeUTC(move.new.start_time)} - {formatTimeUTC(move.new.end_time)}
                        </p>
                        <p>
                          Room: {resourceMap.get(move.new.room_id || '') || 'Assigned'}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              {/* Dropped / Unrepairable Sessions */}
              {previewPlan.dropped.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800">
                  <label className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                    <XCircle className="w-3.5 h-3.5" />
                    Unrepairable Dropped Sessions ({previewPlan.dropped.length})
                  </label>
                  {previewPlan.dropped.map((drop: RescueDropped, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-rose-950/20 border border-rose-500/30 flex items-center justify-between text-xs"
                    >
                      <span className="font-semibold text-rose-200">
                        {resourceMap.get(drop.candidate_id) || drop.candidate_id}
                      </span>
                      <div className="flex gap-1.5">
                        {drop.reasons.map((r: any, ri: number) => (
                          <Badge key={ri} variant="danger" size="sm">
                            {r.code}: {r.detail}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
