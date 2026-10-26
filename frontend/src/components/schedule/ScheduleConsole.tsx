import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Settings2,
  Trash2,
  Download,
  Send,
  Building,
  User as UserIcon,
  Layers,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { Modal } from '../ui/Modal';
import { ConfirmDialog } from '../ui/ConfirmDialog';
import { Spinner } from '../ui/Spinner';
import { EmptyState } from '../ui/EmptyState';
import { FormField } from '../ui/FormField';
import { Input } from '../ui/Input';
import {
  calculateSlotPosition,
  groupByDay,
  calculateInterviewerLoads,
  formatTimeUTC,
} from '../../lib/timelineMath';

export interface ScheduleConsoleProps {
  driveId: string;
  drive: {
    id: string;
    title: string;
    timezone: string;
    status: string;
    schedule_version: number;
    start_date: string;
    end_date: string;
    slot_minutes?: number;
    interviewer_buffer_minutes?: number;
    min_round_gap_minutes?: number;
  };
  stages?: Array<{ id: string; name: string }>;
  users?: Array<{ id: string; name: string; role: string; capacity?: number; skills?: string[] }>;
  rooms?: Array<{ id: string; name: string; capacity?: number; is_active?: boolean }>;
}

export interface ProposedInterview {
  id: string;
  candidate_id: string;
  stage_id: string;
  room_id?: string;
  start_time: string;
  end_time: string;
  status: string;
  interviewer_ids: string[];
}

export interface UnscheduledCandidate {
  candidate_id: string;
  stage_id: string;
  reasons: Array<{ code: string; detail?: string }>;
}

export interface ProposalOut {
  drive_id: string;
  schedule_version: number;
  solver_status?: string;
  complete?: boolean;
  interviews: ProposedInterview[];
  unscheduled?: UnscheduledCandidate[];
}

export interface DriveInterviewDetailOut {
  id: string;
  drive_id: string;
  stage_id: string;
  stage_name: string;
  candidate_id: string;
  candidate_name: string;
  room_id?: string;
  room_name?: string;
  panel: Array<{ id: string; name: string }>;
  start_time: string;
  end_time: string;
  status: string;
  version: number;
}

export interface Blocker {
  kind: string;
  resource_id?: string;
  interviews?: any[];
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
  best_slot?: { start_time: string; end_time: string };
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
  budget_exhausted: boolean;
}

export const ScheduleConsole: React.FC<ScheduleConsoleProps> = ({
  driveId,
  drive,
  stages = [],
  users = [],
  rooms = [],
}) => {
  const queryClient = useQueryClient();

  // State
  const [viewMode, setViewMode] = useState<'room' | 'interviewer' | 'table' | 'unscheduled'>('room');
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);
  const [staleVersionError, setStaleVersionError] = useState<string | null>(null);

  // Settings for solver
  const [settings, setSettings] = useState({
    slot_minutes: drive.slot_minutes || 30,
    interviewer_buffer_minutes: drive.interviewer_buffer_minutes || 10,
    min_round_gap_minutes: drive.min_round_gap_minutes || 30,
    time_limit_seconds: 15,
    workers: 4,
  });

  // Queries
  const { data: proposal, isLoading: isProposalLoading, refetch: refetchProposal } = useQuery<ProposalOut>({
    queryKey: ['drive-proposal', driveId],
    queryFn: async () => {
      try {
        return await apiClient.get<ProposalOut>(`/drives/${driveId}/schedule/proposal`);
      } catch {
        return { drive_id: driveId, schedule_version: drive.schedule_version, interviews: [] };
      }
    },
  });

  const { data: publishedInterviews, isLoading: isPublishedLoading, refetch: refetchPublished } = useQuery<DriveInterviewDetailOut[]>({
    queryKey: ['drive-interviews', driveId],
    queryFn: () => apiClient.get<DriveInterviewDetailOut[]>(`/drives/${driveId}/interviews`),
  });

  const { data: explanationData, isPending: isExplaining, mutate: runExplain } = useMutation<ExplainOut>({
    mutationFn: () => apiClient.post<ExplainOut>(`/drives/${driveId}/schedule/explain`, {}),
  });

  // Mutations
  const proposeMutation = useMutation({
    mutationFn: (opts: typeof settings) =>
      apiClient.post<ProposalOut>(`/drives/${driveId}/schedule/propose`, opts),
    onSuccess: () => {
      setStaleVersionError(null);
      queryClient.invalidateQueries({ queryKey: ['drive-proposal', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
      setShowSettingsModal(false);
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setStaleVersionError('The schedule version has changed. Please refresh to load the latest state.');
      }
    },
  });

  const publishMutation = useMutation({
    mutationFn: (expectedVersion: number) =>
      apiClient.post(`/drives/${driveId}/schedule/publish`, { expected_version: expectedVersion }),
    onSuccess: () => {
      setStaleVersionError(null);
      setShowPublishDialog(false);
      queryClient.invalidateQueries({ queryKey: ['drive-proposal', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drive-interviews', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
      refetchProposal();
      refetchPublished();
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setShowPublishDialog(false);
        setStaleVersionError('The schedule version has changed since this proposal was generated. Please reload to see the latest version.');
      }
    },
  });

  const discardMutation = useMutation({
    mutationFn: () => apiClient.delete(`/drives/${driveId}/schedule/proposal`),
    onSuccess: () => {
      setShowDiscardDialog(false);
      queryClient.invalidateQueries({ queryKey: ['drive-proposal', driveId] });
      refetchProposal();
    },
  });

  // Active dataset: if pending proposal exists, preview proposal; otherwise published interviews
  const hasProposal = (proposal?.interviews?.length ?? 0) > 0;
  const hasPublished = (publishedInterviews?.length ?? 0) > 0;

  // Lookup maps
  const userMap = new Map(users.map((u) => [u.id, u.name]));
  const stageMap = new Map(stages.map((s) => [s.id, s.name]));
  const roomMap = new Map(rooms.map((r) => [r.id, r.name]));

  // Standardized interview items for rendering
  const unifiedInterviews = hasProposal
    ? proposal!.interviews.map((iv) => ({
        id: iv.id,
        candidateName: userMap.get(iv.candidate_id) || `Candidate ${iv.candidate_id.slice(0, 6)}`,
        stageName: stageMap.get(iv.stage_id) || 'Stage',
        roomName: iv.room_id ? roomMap.get(iv.room_id) || 'Room' : 'TBD',
        roomId: iv.room_id,
        panelNames: iv.interviewer_ids.map((id) => userMap.get(id) || `Interviewer ${id.slice(0, 6)}`),
        interviewerIds: iv.interviewer_ids,
        startTime: iv.start_time,
        endTime: iv.end_time,
        status: iv.status || 'proposed',
        isProposal: true,
      }))
    : (publishedInterviews || []).map((iv) => ({
        id: iv.id,
        candidateName: iv.candidate_name || userMap.get(iv.candidate_id) || 'Candidate',
        stageName: iv.stage_name || stageMap.get(iv.stage_id) || 'Stage',
        roomName: iv.room_name || (iv.room_id ? roomMap.get(iv.room_id) : undefined) || 'Unassigned',
        roomId: iv.room_id,
        panelNames: iv.panel.map((p) => p.name),
        interviewerIds: iv.panel.map((p) => p.id),
        startTime: iv.start_time,
        endTime: iv.end_time,
        status: iv.status || 'scheduled',
        isProposal: false,
      }));

  const dayGroups = groupByDay(unifiedInterviews);
  const currentDay = dayGroups[selectedDayIndex] || dayGroups[0] || { dateStr: '', label: 'No Interviews', items: [] };
  const currentInterviews = currentDay.items;

  // Interviewers with capacities
  const interviewers = users.filter((u) => u.role === 'interviewer');
  const interviewerLoads = calculateInterviewerLoads(
    unifiedInterviews,
    interviewers,
    currentDay.dateStr
  );

  const unscheduledList = proposal?.unscheduled || [];

  return (
    <div className="space-y-6">
      {/* Stale Version Alert */}
      {staleVersionError && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <h4 className="text-sm font-semibold text-amber-300">Schedule Version Conflict</h4>
            <p className="text-sm text-amber-200/80 mt-0.5">{staleVersionError}</p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="border-amber-500/30 text-amber-300 hover:bg-amber-500/20"
            onClick={() => {
              setStaleVersionError(null);
              refetchProposal();
              refetchPublished();
            }}
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Reload Latest
          </Button>
        </div>
      )}

      {/* Main Action Bar */}
      <Card className="p-5 bg-slate-900/90 border-slate-800">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Calendar className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-100">Scheduling Console</h3>
                {hasProposal && (
                  <Badge variant="warning" className="animate-pulse">
                    Proposal Ready (v{proposal?.schedule_version})
                  </Badge>
                )}
                {hasPublished && !hasProposal && (
                  <Badge variant="success">Published (v{drive.schedule_version})</Badge>
                )}
                {proposal?.solver_status && (
                  <Badge
                    variant={
                      proposal.solver_status === 'optimal'
                        ? 'success'
                        : proposal.solver_status === 'feasible'
                        ? 'warning'
                        : 'neutral'
                    }
                  >
                    Solver: {proposal.solver_status}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {hasProposal
                  ? `${proposal?.interviews.length} proposed interviews ready for review.`
                  : hasPublished
                  ? `${publishedInterviews?.length} interviews published and active.`
                  : 'No schedule generated yet. Run the solver to create a proposed schedule.'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowSettingsModal(true)}
              className="text-slate-300 border-slate-700 hover:bg-slate-800"
            >
              <Settings2 className="w-4 h-4 mr-1.5 text-slate-400" />
              Settings
            </Button>

            {hasProposal && (
              <>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => setShowDiscardDialog(true)}
                  disabled={discardMutation.isPending}
                >
                  <Trash2 className="w-4 h-4 mr-1.5" />
                  Discard
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setShowPublishDialog(true)}
                  disabled={publishMutation.isPending}
                  className="bg-emerald-600 hover:bg-emerald-500"
                >
                  <Send className="w-4 h-4 mr-1.5" />
                  Publish Schedule
                </Button>
              </>
            )}

            <Button
              variant="primary"
              size="sm"
              onClick={() => proposeMutation.mutate(settings)}
              disabled={proposeMutation.isPending}
              className="bg-indigo-600 hover:bg-indigo-500"
            >
              {proposeMutation.isPending ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  Solving Schedule...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-1.5" />
                  {hasProposal ? 'Re-generate Schedule' : 'Generate Schedule'}
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>

      {/* View Switcher & Days Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Tabs: Room, Interviewer, Table, Unscheduled */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-900/80 border border-slate-800 rounded-xl">
          <button
            onClick={() => setViewMode('room')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
              viewMode === 'room'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Building className="w-3.5 h-3.5" />
            By Room
          </button>
          <button
            onClick={() => setViewMode('interviewer')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
              viewMode === 'interviewer'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <UserIcon className="w-3.5 h-3.5" />
            By Interviewer
          </button>
          <button
            onClick={() => setViewMode('table')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
              viewMode === 'table'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Table View
          </button>
          <button
            onClick={() => setViewMode('unscheduled')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1.5 ${
              viewMode === 'unscheduled'
                ? 'bg-rose-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <HelpCircle className="w-3.5 h-3.5" />
            Unscheduled
            {unscheduledList.length > 0 && (
              <span className="ml-1 px-1.5 py-0.2 bg-rose-500/30 text-rose-300 text-[10px] rounded-full">
                {unscheduledList.length}
              </span>
            )}
          </button>
        </div>

        {/* Days selector for timeline */}
        {viewMode !== 'unscheduled' && dayGroups.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
            {dayGroups.map((group, idx) => (
              <button
                key={group.dateStr}
                onClick={() => setSelectedDayIndex(idx)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all whitespace-nowrap ${
                  selectedDayIndex === idx
                    ? 'bg-slate-800 border-indigo-500/50 text-indigo-300 shadow-sm'
                    : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                }`}
              >
                {group.label} ({group.items.length})
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Main Content Areas */}
      {isProposalLoading || isPublishedLoading ? (
        <Card className="p-12 text-center bg-slate-900/50 border-slate-800">
          <Spinner size="lg" className="mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Loading schedule state...</p>
        </Card>
      ) : unifiedInterviews.length === 0 && viewMode !== 'unscheduled' ? (
        <Card className="p-12 text-center bg-slate-900/50 border-slate-800">
          <EmptyState
            title="No Interviews in Schedule"
            description="Generate a schedule proposal using the solver to match candidates, interviewers, and rooms."
            icon={Calendar}
            actionLabel="Generate Schedule Now"
            onAction={() => proposeMutation.mutate(settings)}
          />
        </Card>
      ) : (
        <>
          {/* VIEW 1: TIMELINE BY ROOM */}
          {viewMode === 'room' && (
            <Card className="p-5 bg-slate-900/90 border-slate-800 overflow-x-auto">
              <div className="min-w-[760px]">
                {/* Time Scale Header (08:00 to 18:00, 2h major labels, 30m grid) */}
                <div className="flex border-b border-slate-800 pb-3 mb-3 text-xs text-slate-400 font-mono">
                  <div className="w-48 shrink-0 font-sans font-medium text-slate-300">Room</div>
                  <div className="flex-1 flex justify-between px-2">
                    <span>08:00</span>
                    <span>10:00</span>
                    <span>12:00</span>
                    <span>14:00</span>
                    <span>16:00</span>
                    <span>18:00</span>
                  </div>
                </div>

                {/* Rooms Grid */}
                <div className="space-y-4">
                  {rooms.map((room) => {
                    const roomInterviews = currentInterviews.filter((iv) => iv.roomId === room.id);
                    return (
                      <div key={room.id} className="flex items-center group">
                        <div className="w-48 shrink-0 pr-4">
                          <p className="text-sm font-medium text-slate-200 truncate">{room.name}</p>
                          <p className="text-[11px] text-slate-500">Cap: {room.capacity || 1}</p>
                        </div>
                        <div className="flex-1 h-14 bg-slate-950/60 rounded-lg border border-slate-800/80 relative overflow-hidden">
                          {/* 30m grid tick backgrounds */}
                          <div className="absolute inset-0 grid grid-cols-10 pointer-events-none opacity-20 divide-x divide-slate-700" />
                          {/* Interviews */}
                          {roomInterviews.map((iv) => {
                            const { leftPercent, widthPercent } = calculateSlotPosition(
                              iv.startTime,
                              iv.endTime,
                              8,
                              18
                            );
                            return (
                              <div
                                key={iv.id}
                                style={{
                                  left: `${leftPercent}%`,
                                  width: `${widthPercent}%`,
                                }}
                                className="absolute top-1.5 bottom-1.5 rounded-md p-1.5 bg-gradient-to-r from-indigo-900/90 to-violet-900/90 border border-indigo-500/40 hover:border-indigo-400 shadow-sm flex flex-col justify-between overflow-hidden cursor-pointer group/card transition-all hover:z-20 hover:scale-[1.02]"
                                title={`${iv.candidateName} - ${iv.stageName} (${formatTimeUTC(iv.startTime)} - ${formatTimeUTC(iv.endTime)})`}
                              >
                                <div className="flex items-center justify-between text-[11px] font-semibold text-indigo-200 truncate leading-tight">
                                  <span className="truncate">{iv.candidateName}</span>
                                  {!iv.isProposal && (
                                    <a
                                      href={`${apiClient.getBaseUrl()}/interviews/${iv.id}/ics`}
                                      target="_blank"
                                      rel="noreferrer"
                                      onClick={(e) => e.stopPropagation()}
                                      className="text-slate-400 hover:text-white p-0.5"
                                      title="Download .ics"
                                    >
                                      <Download className="w-2.5 h-2.5" />
                                    </a>
                                  )}
                                </div>
                                <div className="flex items-center justify-between text-[9px] text-slate-300/80 truncate">
                                  <span>{iv.stageName}</span>
                                  <span>{formatTimeUTC(iv.startTime)}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>
          )}

          {/* VIEW 2: TIMELINE BY INTERVIEWER */}
          {viewMode === 'interviewer' && (
            <Card className="p-5 bg-slate-900/90 border-slate-800 overflow-x-auto">
              <div className="min-w-[760px]">
                {/* Time Scale Header */}
                <div className="flex border-b border-slate-800 pb-3 mb-3 text-xs text-slate-400 font-mono">
                  <div className="w-56 shrink-0 font-sans font-medium text-slate-300">Interviewer & Capacity</div>
                  <div className="flex-1 flex justify-between px-2">
                    <span>08:00</span>
                    <span>10:00</span>
                    <span>12:00</span>
                    <span>14:00</span>
                    <span>16:00</span>
                    <span>18:00</span>
                  </div>
                </div>

                {/* Interviewers Grid */}
                <div className="space-y-4">
                  {interviewerLoads.map((load) => {
                    const invInterviews = currentInterviews.filter((iv) =>
                      iv.interviewerIds.includes(load.interviewerId)
                    );
                    return (
                      <div key={load.interviewerId} className="flex items-center group">
                        <div className="w-56 shrink-0 pr-4">
                          <p className="text-sm font-medium text-slate-200 truncate">{load.interviewerName}</p>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span
                              className={`text-[11px] font-mono px-1.5 py-0.5 rounded ${
                                load.isOverCapacity
                                  ? 'bg-rose-500/20 text-rose-300 font-bold border border-rose-500/40'
                                  : load.isAtCapacity
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                  : 'bg-slate-800 text-slate-400'
                              }`}
                            >
                              Load: {load.count}/{load.capacity} slots
                            </span>
                          </div>
                        </div>
                        <div className="flex-1 h-14 bg-slate-950/60 rounded-lg border border-slate-800/80 relative overflow-hidden">
                          <div className="absolute inset-0 grid grid-cols-10 pointer-events-none opacity-20 divide-x divide-slate-700" />
                          {invInterviews.map((iv) => {
                            const { leftPercent, widthPercent } = calculateSlotPosition(
                              iv.startTime,
                              iv.endTime,
                              8,
                              18
                            );
                            return (
                              <div
                                key={iv.id}
                                style={{
                                  left: `${leftPercent}%`,
                                  width: `${widthPercent}%`,
                                }}
                                className="absolute top-1.5 bottom-1.5 rounded-md p-1.5 bg-gradient-to-r from-violet-900/90 to-purple-900/90 border border-violet-500/40 hover:border-violet-400 shadow-sm flex flex-col justify-between overflow-hidden cursor-pointer transition-all hover:z-20 hover:scale-[1.02]"
                                title={`${iv.candidateName} - ${iv.stageName} in ${iv.roomName} (${formatTimeUTC(iv.startTime)} - ${formatTimeUTC(iv.endTime)})`}
                              >
                                <div className="text-[11px] font-semibold text-violet-200 truncate leading-tight">
                                  {iv.candidateName}
                                </div>
                                <div className="flex items-center justify-between text-[9px] text-slate-300/80 truncate">
                                  <span>{iv.roomName}</span>
                                  <span>{formatTimeUTC(iv.startTime)}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </Card>
          )}

          {/* VIEW 3: TABLE VIEW */}
          {viewMode === 'table' && (
            <Card className="p-0 bg-slate-900/90 border-slate-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-5 py-3">Candidate</th>
                      <th className="px-5 py-3">Stage</th>
                      <th className="px-5 py-3">Time Window</th>
                      <th className="px-5 py-3">Room</th>
                      <th className="px-5 py-3">Panelists</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-200">
                    {unifiedInterviews.map((iv) => (
                      <tr key={iv.id} className="hover:bg-slate-800/40 transition-colors">
                        <td className="px-5 py-3.5 font-medium text-slate-100">{iv.candidateName}</td>
                        <td className="px-5 py-3.5 text-slate-300">{iv.stageName}</td>
                        <td className="px-5 py-3.5 font-mono text-xs text-slate-300">
                          {formatTimeUTC(iv.startTime)} - {formatTimeUTC(iv.endTime)}
                        </td>
                        <td className="px-5 py-3.5 text-slate-300">{iv.roomName}</td>
                        <td className="px-5 py-3.5 text-slate-300">
                          {iv.panelNames.length > 0 ? iv.panelNames.join(', ') : 'None assigned'}
                        </td>
                        <td className="px-5 py-3.5">
                          <Badge
                            variant={
                              iv.status === 'scheduled' || iv.status === 'confirmed'
                                ? 'success'
                                : iv.status === 'proposed'
                                ? 'warning'
                                : 'neutral'
                            }
                          >
                            {iv.status}
                          </Badge>
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          {!iv.isProposal && (
                            <a
                              href={`${apiClient.getBaseUrl()}/interviews/${iv.id}/ics`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                            >
                              <Download className="w-3.5 h-3.5" />
                              .ics
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* VIEW 4: UNSCHEDULED PANEL & EXPLAIN DIAGNOSIS */}
          {viewMode === 'unscheduled' && (
            <div className="space-y-6">
              <Card className="p-6 bg-slate-900/90 border-slate-800">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                      <HelpCircle className="w-5 h-5 text-rose-400" />
                      Unscheduled Candidates ({unscheduledList.length})
                    </h3>
                    <p className="text-xs text-slate-400 mt-1">
                      Candidates who could not be placed due to capacity, room, or availability constraints.
                    </p>
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => runExplain()}
                    disabled={isExplaining}
                    className="bg-violet-600 hover:bg-violet-500"
                  >
                    {isExplaining ? (
                      <>
                        <Spinner size="sm" className="mr-2" />
                        Running Diagnosis...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4 mr-1.5" />
                        Explain Unscheduled (Run Solver Diagnosis)
                      </>
                    )}
                  </Button>
                </div>

                {unscheduledList.length === 0 ? (
                  <div className="text-center py-8">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
                    <p className="text-slate-200 font-medium">All Candidates Scheduled!</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      100% of candidates have valid slots assigned by the solver.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {unscheduledList.map((u, i) => (
                      <div
                        key={i}
                        className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-3"
                      >
                        <div>
                          <p className="text-sm font-semibold text-slate-200">
                            {userMap.get(u.candidate_id) || `Candidate ${u.candidate_id.slice(0, 8)}`}
                          </p>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Stage: <span className="text-indigo-300">{stageMap.get(u.stage_id) || u.stage_id}</span>
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {u.reasons.map((r, ri) => (
                            <Badge key={ri} variant="danger" className="text-[11px]">
                              {r.code}: {r.detail || 'Constraint violation'}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Diagnosis Report from /explain */}
              {explanationData && (
                <Card className="p-6 bg-slate-900/90 border-violet-500/30">
                  <div className="border-b border-slate-800 pb-4 mb-4">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-violet-400" />
                      <h4 className="text-base font-bold text-slate-100">Solver Diagnosis & Verified Fixes</h4>
                      <Badge variant="neutral">Solver: {explanationData.solver_status}</Badge>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Verified fixes have been checked by re-running the solver on relaxed copies of the problem.
                    </p>
                  </div>

                  <div className="space-y-4">
                    {explanationData.explanations.map((exp, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-xl bg-violet-950/20 border border-violet-500/20 space-y-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h5 className="text-sm font-semibold text-violet-200">
                              {userMap.get(exp.candidate_id) || `Candidate ${exp.candidate_id.slice(0, 8)}`}
                            </h5>
                            <p className="text-xs text-slate-300 mt-0.5">{exp.summary}</p>
                          </div>
                          {exp.best_slot && (
                            <div className="text-right text-xs font-mono text-slate-400">
                              <span>Best Slot: </span>
                              <span className="text-indigo-300">
                                {formatTimeUTC(exp.best_slot.start_time)} - {formatTimeUTC(exp.best_slot.end_time)}
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Verified Fixes */}
                        {exp.fixes.length > 0 && (
                          <div className="pt-2 border-t border-violet-500/10 space-y-1.5">
                            <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                              Verified Fixes:
                            </span>
                            {exp.fixes.map((fix, fi) => (
                              <div
                                key={fi}
                                className="flex items-center justify-between text-xs p-2 rounded-lg bg-emerald-950/30 border border-emerald-500/20 text-emerald-200"
                              >
                                <span className="flex items-center gap-1.5">
                                  <ChevronRight className="w-3.5 h-3.5 text-emerald-400" />
                                  {fix.description}
                                </span>
                                <Badge variant="success" className="bg-emerald-500/20 text-emerald-300">
                                  +{fix.extra_interviews} interviews
                                </Badge>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}
        </>
      )}

      {/* Advanced Settings Modal */}
      <Modal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        title="Solver Run Settings"
        maxWidth="md"
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-400">
            Configure solver parameters for this run. These override drive defaults without modifying the drive template.
          </p>
          <FormField label="Slot Minutes (duration per interview)">
            <Input
              type="number"
              value={settings.slot_minutes}
              onChange={(e) => setSettings({ ...settings, slot_minutes: Number(e.target.value) })}
              min={15}
              max={120}
            />
          </FormField>
          <FormField label="Interviewer Buffer Minutes (cooldown between sessions)">
            <Input
              type="number"
              value={settings.interviewer_buffer_minutes}
              onChange={(e) =>
                setSettings({ ...settings, interviewer_buffer_minutes: Number(e.target.value) })
              }
              min={0}
              max={60}
            />
          </FormField>
          <FormField label="Min Round Gap Minutes (cooldown between candidate rounds)">
            <Input
              type="number"
              value={settings.min_round_gap_minutes}
              onChange={(e) =>
                setSettings({ ...settings, min_round_gap_minutes: Number(e.target.value) })
              }
              min={0}
              max={120}
            />
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Time Limit (seconds)">
              <Input
                type="number"
                value={settings.time_limit_seconds}
                onChange={(e) =>
                  setSettings({ ...settings, time_limit_seconds: Number(e.target.value) })
                }
                min={5}
                max={60}
              />
            </FormField>
            <FormField label="Worker Threads">
              <Input
                type="number"
                value={settings.workers}
                onChange={(e) => setSettings({ ...settings, workers: Number(e.target.value) })}
                min={1}
                max={8}
              />
            </FormField>
          </div>
          <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
            <Button variant="ghost" onClick={() => setShowSettingsModal(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => proposeMutation.mutate(settings)}
              disabled={proposeMutation.isPending}
            >
              {proposeMutation.isPending ? 'Generating...' : 'Run with Settings'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Publish Confirm Dialog */}
      <ConfirmDialog
        isOpen={showPublishDialog}
        onClose={() => setShowPublishDialog(false)}
        onConfirm={() => publishMutation.mutate(proposal?.schedule_version ?? drive.schedule_version)}
        title="Publish Schedule"
        message={`Are you sure you want to publish this schedule proposal (version ${proposal?.schedule_version})? Once published, candidate stages are locked, notifications will be prepared, and interviews become live.`}
        confirmLabel={publishMutation.isPending ? 'Publishing...' : 'Yes, Publish Schedule'}
        variant="primary"
      />

      {/* Discard Confirm Dialog */}
      <ConfirmDialog
        isOpen={showDiscardDialog}
        onClose={() => setShowDiscardDialog(false)}
        onConfirm={() => discardMutation.mutate()}
        title="Discard Pending Proposal"
        message="Are you sure you want to discard this pending schedule proposal? The proposal will be cleared and no changes will be made to any published interviews."
        confirmLabel="Discard Proposal"
        variant="danger"
      />
    </div>
  );
};
