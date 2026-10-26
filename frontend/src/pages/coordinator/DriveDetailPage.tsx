import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Layers,
  Calendar,
  Clock,
  Globe,
  Users,
  Plus,
  ArrowUp,
  ArrowDown,
  Trash2,
  Edit3,
  UserCheck,
  UserMinus,
  AlertTriangle,
  Lock,
  ArrowLeft,
  Tag,
  X,
  Play,
  Send,
  LifeBuoy,
  Kanban,
  CalendarCheck,
  Link2,
} from 'lucide-react';
import { apiClient, ApiError } from '@/api/client';
import { ScheduleConsole } from '@/components/schedule/ScheduleConsole';
import { BookingLinksModal } from '@/components/booking/BookingLinksModal';
import { PipelineBoard } from '@/components/pipeline/PipelineBoard';
import { RippleRescueConsole } from '@/components/rescue/RippleRescueConsole';
import {
  RecruitmentDrive,
  Stage,
  Enrollment,
  User,
} from '@/types/api';
import {
  Button,
  Input,
  Select,
  FormField,
  Modal,
  ConfirmDialog,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Badge,
  Tabs,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  Spinner,
  EmptyState,
  useToast,
} from '@/components/ui';

export const DriveDetailPage: React.FC = () => {
  const { driveId } = useParams<{ driveId: string }>();
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();

  const [activeTab, setActiveTab] = useState<'overview' | 'stages' | 'candidates' | 'schedule' | 'pipeline' | 'rescue'>('overview');
  const [isBookingLinksModalOpen, setIsBookingLinksModalOpen] = useState(false);

  // Fetch Drive Details
  const { data: drive, isLoading: driveLoading } = useQuery<RecruitmentDrive>({
    queryKey: ['drive', driveId],
    queryFn: () => apiClient<RecruitmentDrive>(`/drives/${driveId}`),
    enabled: !!driveId,
  });

  // Fetch Stages
  const { data: stages = [], isLoading: stagesLoading } = useQuery<Stage[]>({
    queryKey: ['stages', driveId],
    queryFn: () => apiClient<Stage[]>(`/drives/${driveId}/stages`),
    enabled: !!driveId,
  });

  // Fetch Enrolled Candidates
  const { data: enrollments = [], isLoading: enrollmentsLoading } = useQuery<Enrollment[]>({
    queryKey: ['enrollments', driveId],
    queryFn: () => apiClient<Enrollment[]>(`/drives/${driveId}/candidates`),
    enabled: !!driveId,
  });

  // Fetch all candidates for enrollment modal
  const { data: allCandidates = [] } = useQuery<User[]>({
    queryKey: ['all-candidates'],
    queryFn: () => apiClient<User[]>('/users?role=candidate&limit=100'),
    enabled: !!driveId,
  });

  const { data: allUsers = [] } = useQuery<User[]>({
    queryKey: ['all-users'],
    queryFn: () => apiClient<User[]>('/users?limit=200'),
    enabled: !!driveId,
  });

  const { data: rooms = [] } = useQuery<any[]>({
    queryKey: ['all-rooms'],
    queryFn: () => apiClient<any[]>('/rooms'),
    enabled: !!driveId,
  });

  const isLocked = drive ? drive.status !== 'draft' && drive.status !== 'collecting_availability' : false;

  // ---------------- Drive Status Transitions ----------------
  const updateDriveStatusMutation = useMutation({
    mutationFn: (newStatus: string) =>
      apiClient<RecruitmentDrive>(`/drives/${driveId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      }),
    onSuccess: (updated) => {
      success('Drive Status Updated', `Drive is now in ${updated.status.replace('_', ' ')} phase`);
      queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
      queryClient.invalidateQueries({ queryKey: ['drives'] });
    },
    onError: (err: any) => {
      if (err instanceof ApiError) {
        toastError('Status Move Failed', err.message);
      } else {
        toastError('Error', 'Failed to update status');
      }
    },
  });

  // ---------------- Stages CRUD ----------------
  const [isStageModalOpen, setIsStageModalOpen] = useState(false);
  const [editingStage, setEditingStage] = useState<Stage | null>(null);
  const [stageName, setStageName] = useState('');
  const [stageType, setStageType] = useState<Stage['stage_type']>('technical');
  const [duration, setDuration] = useState(45);
  const [panelSize, setPanelSize] = useState(1);
  const [skills, setSkills] = useState<string[]>([]);
  const [skillTag, setSkillTag] = useState('');
  const [minScore, setMinScore] = useState(6);
  const [stageToDelete, setStageToDelete] = useState<Stage | null>(null);

  const handleOpenAddStage = () => {
    setEditingStage(null);
    setStageName('');
    setStageType('technical');
    setDuration(drive?.slot_minutes || 45);
    setPanelSize(1);
    setSkills([]);
    setMinScore(6);
    setIsStageModalOpen(true);
  };

  const handleOpenEditStage = (s: Stage) => {
    setEditingStage(s);
    setStageName(s.name);
    setStageType(s.stage_type);
    setDuration(s.duration_minutes);
    setPanelSize(s.panel_size);
    setSkills(s.required_skills || []);
    setMinScore(s.rule?.min_score || 6);
    setIsStageModalOpen(true);
  };

  const handleAddSkillTag = () => {
    if (skillTag.trim() && !skills.includes(skillTag.trim().toLowerCase())) {
      setSkills([...skills, skillTag.trim().toLowerCase()]);
      setSkillTag('');
    }
  };

  const saveStageMutation = useMutation({
    mutationFn: (body: any) => {
      if (editingStage) {
        return apiClient<Stage>(`/drives/${driveId}/stages/${editingStage.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
      }
      return apiClient<Stage>(`/drives/${driveId}/stages`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      success('Stage Saved', 'Stage definition updated');
      queryClient.invalidateQueries({ queryKey: ['stages', driveId] });
      setIsStageModalOpen(false);
    },
    onError: (err: any) => {
      toastError('Error', err.message || 'Failed to save stage');
    },
  });

  const deleteStageMutation = useMutation({
    mutationFn: (id: string) => apiClient(`/drives/${driveId}/stages/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      success('Stage Deleted', 'Stage removed from drive');
      queryClient.invalidateQueries({ queryKey: ['stages', driveId] });
      setStageToDelete(null);
    },
    onError: (err: any) => {
      toastError('Error', err.message || 'Cannot delete stage');
    },
  });

  const reorderStageMutation = useMutation({
    mutationFn: async ({ stage, newOrder }: { stage: Stage; newOrder: number }) => {
      return apiClient(`/drives/${driveId}/stages/${stage.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ order_index: newOrder }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stages', driveId] });
    },
    onError: (err: any) => {
      toastError('Error', err.message);
    },
  });

  const handleMoveStage = (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= stages.length) return;

    const currentStage = stages[index];
    const targetStage = stages[targetIndex];

    // Swap order indices
    reorderStageMutation.mutate({ stage: currentStage, newOrder: targetStage.order_index });
  };

  const handleStageSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name: stageName,
      stage_type: stageType,
      duration_minutes: Number(duration),
      panel_size: Number(panelSize),
      required_skills: skills,
      order_index: editingStage ? editingStage.order_index : stages.length + 1,
      rule: {
        min_score: Number(minScore),
        min_evaluations: Number(panelSize),
      },
    };
    saveStageMutation.mutate(payload);
  };

  // ---------------- Candidates Enrollment & Withdrawal ----------------
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [candidateToWithdraw, setCandidateToWithdraw] = useState<string | null>(null);

  const enrolledIds = new Set(enrollments.map((e) => e.candidate_id));
  const availableToEnroll = allCandidates.filter((c) => !enrolledIds.has(c.id));

  const enrollMutation = useMutation({
    mutationFn: (ids: string[]) =>
      apiClient<Enrollment[]>(`/drives/${driveId}/candidates`, {
        method: 'POST',
        body: JSON.stringify({ candidate_ids: ids }),
      }),
    onSuccess: (res) => {
      success('Candidates Enrolled', `${res.length} candidate(s) enrolled into the drive`);
      queryClient.invalidateQueries({ queryKey: ['enrollments', driveId] });
      setIsEnrollModalOpen(false);
      setSelectedCandidateIds([]);
    },
    onError: (err: any) => {
      toastError('Enrollment Failed', err.message);
    },
  });

  const withdrawMutation = useMutation({
    mutationFn: (candId: string) =>
      apiClient(`/drives/${driveId}/candidates/${candId}`, { method: 'DELETE' }),
    onSuccess: () => {
      success('Candidate Withdrawn', 'Candidate status updated to Withdrawn');
      queryClient.invalidateQueries({ queryKey: ['enrollments', driveId] });
      setCandidateToWithdraw(null);
    },
    onError: (err: any) => {
      toastError('Error', err.message);
    },
  });

  if (driveLoading) {
    return <Spinner size="lg" label="Loading drive details..." />;
  }

  if (!drive) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Drive Not Found"
        description="The recruitment drive you are looking for does not exist."
        actionLabel="Back to Drives"
        onAction={() => {}}
      />
    );
  }

  const tabsList = [
    { id: 'overview', label: 'Overview', icon: <Layers className="w-4 h-4" /> },
    { id: 'stages', label: 'Stages', icon: <Clock className="w-4 h-4" />, badge: stages.length },
    { id: 'candidates', label: 'Candidates', icon: <Users className="w-4 h-4" />, badge: enrollments.length },
    { id: 'schedule', label: 'Schedule', icon: <CalendarCheck className="w-4 h-4" /> },
    { id: 'pipeline', label: 'Pipeline', icon: <Kanban className="w-4 h-4" /> },
    { id: 'rescue', label: 'Ripple Rescue', icon: <LifeBuoy className="w-4 h-4" /> },
  ];

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
            <Link to="/coordinator/drives" className="hover:text-slate-200 flex items-center gap-1">
              <ArrowLeft className="w-3 h-3" />
              <span>All Drives</span>
            </Link>
            <span>/</span>
            <span className="text-slate-300">{drive.title}</span>
          </div>

          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">{drive.title}</h1>
            <Badge variant={drive.status === 'published' ? 'success' : 'brand'}>
              {drive.status.replace('_', ' ')}
            </Badge>
          </div>
        </div>

        {/* Status Transition Button */}
        <div className="flex items-center gap-2">
          {drive.status === 'draft' && (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Send className="w-4 h-4" />}
              onClick={() => updateDriveStatusMutation.mutate('collecting_availability')}
              isLoading={updateDriveStatusMutation.isPending}
            >
              Open for Availability
            </Button>
          )}

          {drive.status === 'collecting_availability' && (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Play className="w-4 h-4" />}
              onClick={() => setActiveTab('schedule')}
            >
              Go to Scheduling
            </Button>
          )}
        </div>
      </div>

      {/* Locked Notice */}
      {isLocked && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-3 text-xs text-amber-300">
          <Lock className="w-4 h-4 shrink-0 text-amber-400" />
          <span>
            The drive window, timezone, and stage parameters are locked because this drive has a published schedule.
          </span>
        </div>
      )}

      {/* Tabs */}
      <Tabs
        tabs={tabsList}
        activeTab={activeTab}
        onChange={(t) => setActiveTab(t as any)}
      />

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="md:col-span-2 space-y-6">
            <CardHeader>
              <div>
                <CardTitle>Drive Specification</CardTitle>
                <CardDescription>Core parameters and window constraints</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {drive.description && (
                <p className="text-sm text-slate-300 leading-relaxed">{drive.description}</p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="p-4 rounded-xl bg-surface-elevated/70 border border-surface-border">
                  <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                    <Calendar className="w-4 h-4 text-brand-400" />
                    <span>Drive Window</span>
                  </div>
                  <p className="text-sm font-semibold text-slate-100">
                    {new Date(drive.window_start).toLocaleDateString()} — {new Date(drive.window_end).toLocaleDateString()}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {new Date(drive.window_start).toLocaleTimeString()} to {new Date(drive.window_end).toLocaleTimeString()}
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-surface-elevated/70 border border-surface-border">
                  <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                    <Globe className="w-4 h-4 text-brand-400" />
                    <span>Drive Timezone</span>
                  </div>
                  <p className="text-sm font-semibold text-slate-100 font-mono">{drive.timezone}</p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    All candidate invitations &amp; ICS downloads format to this timezone
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 pt-2">
                <div className="p-3.5 rounded-xl bg-surface-elevated/50 border border-surface-border text-center">
                  <p className="text-[11px] text-slate-400">Slot Duration</p>
                  <p className="text-lg font-bold text-slate-100 mt-0.5">{drive.slot_minutes} min</p>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-elevated/50 border border-surface-border text-center">
                  <p className="text-[11px] text-slate-400">Interviewer Buffer</p>
                  <p className="text-lg font-bold text-slate-100 mt-0.5">{drive.interviewer_buffer_minutes} min</p>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-elevated/50 border border-surface-border text-center">
                  <p className="text-[11px] text-slate-400">Min Round Gap</p>
                  <p className="text-lg font-bold text-slate-100 mt-0.5">{drive.min_round_gap_minutes} min</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="space-y-4">
            <CardHeader>
              <div>
                <CardTitle>Next Unfinished Step</CardTitle>
                <CardDescription>Derived from live drive progress</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {drive.status === 'draft' ? (
                <div className="p-4 rounded-xl bg-brand-500/10 border border-brand-500/20 text-xs space-y-2">
                  <p className="font-semibold text-brand-300">1. Setup Stages &amp; Enrol Candidates</p>
                  <p className="text-slate-400">
                    Add interview stages and enrol applicants, then click "Open for Availability" to allow panelists to submit free windows.
                  </p>
                </div>
              ) : drive.status === 'collecting_availability' ? (
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs space-y-2">
                  <p className="font-semibold text-emerald-300">2. Generate Optimal Schedule</p>
                  <p className="text-slate-400">
                    Availability is active. When candidate &amp; interviewer windows are submitted, launch the solver in the Schedule tab.
                  </p>
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full mt-2"
                    onClick={() => setActiveTab('schedule')}
                  >
                    Go to Schedule Console
                  </Button>
                </div>
              ) : drive.status === 'published' ? (
                <div className="p-4 rounded-xl bg-violet-500/10 border border-violet-500/20 text-xs space-y-2">
                  <p className="font-semibold text-violet-300">3. Live Drive Execution</p>
                  <p className="text-slate-400">
                    Schedules are live! Issue booking links for candidates, collect interviewer feedback, advance candidates, or run Ripple Rescue if emergencies arise.
                  </p>
                  <div className="flex gap-2 pt-1">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="flex-1"
                      onClick={() => setActiveTab('pipeline')}
                    >
                      Pipeline
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => setActiveTab('rescue')}
                    >
                      Rescue
                    </Button>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB 2: STAGES */}
      {activeTab === 'stages' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-100">Interview Stages</h3>
              <p className="text-xs text-slate-400">
                Ordered rounds, required panelist skills, and pass criteria
              </p>
            </div>
            {!isLocked && (
              <Button variant="primary" size="sm" onClick={handleOpenAddStage} leftIcon={<Plus className="w-4 h-4" />}>
                Add Stage
              </Button>
            )}
          </div>

          {stagesLoading ? (
            <Spinner size="md" label="Loading stages..." />
          ) : stages.length === 0 ? (
            <EmptyState
              icon={Clock}
              title="No stages defined yet"
              description="Drives require at least one stage (e.g. Technical Round, HR Interview) before generating schedules."
              actionLabel={!isLocked ? 'Add First Stage' : undefined}
              onAction={handleOpenAddStage}
            />
          ) : (
            <div className="space-y-3">
              {stages.map((stage, idx) => (
                <Card key={stage.id} className="p-4 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-surface-elevated text-brand-400 font-bold flex items-center justify-center text-xs border border-surface-border">
                      {idx + 1}
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-slate-100">{stage.name}</h4>
                        <Badge variant="neutral" size="sm">
                          {stage.stage_type}
                        </Badge>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Duration: {stage.duration_minutes}m • Panel Size: {stage.panel_size} • Pass Score: {stage.rule?.min_score || 6}/10
                      </p>
                      {stage.required_skills?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {stage.required_skills.map((s) => (
                            <span
                              key={s}
                              className="px-1.5 py-0.2 rounded text-[10px] bg-brand-500/10 text-brand-300 border border-brand-500/20 font-mono"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {!isLocked && (
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={idx === 0}
                        onClick={() => handleMoveStage(idx, 'up')}
                      >
                        <ArrowUp className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={idx === stages.length - 1}
                        onClick={() => handleMoveStage(idx, 'down')}
                      >
                        <ArrowDown className="w-3.5 h-3.5" />
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => handleOpenEditStage(stage)}>
                        <Edit3 className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-rose-400 hover:text-rose-300"
                        onClick={() => setStageToDelete(stage)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: CANDIDATES */}
      {activeTab === 'candidates' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-100">Enrolled Candidates</h3>
              <p className="text-xs text-slate-400">
                Applicants active in this drive, their current stage, and enrollment status
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsBookingLinksModalOpen(true)}
                leftIcon={<Link2 className="w-4 h-4" />}
                className="text-slate-300 border-slate-700 hover:bg-slate-800"
              >
                Issue Booking Links
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsEnrollModalOpen(true)}
                leftIcon={<UserCheck className="w-4 h-4" />}
              >
                Enrol Candidates
              </Button>
            </div>
          </div>

          {enrollmentsLoading ? (
            <Spinner size="md" label="Loading enrolled candidates..." />
          ) : enrollments.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No candidates enrolled in this drive"
              description="Enrol candidates from your people directory so they can be matched into interview stages."
              actionLabel="Enrol Candidates"
              onAction={() => setIsEnrollModalOpen(true)}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Current Stage</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {enrollments.map((enr) => {
                  const candidateUser = allCandidates.find((c) => c.id === enr.candidate_id);
                  const candName = candidateUser?.name || enr.candidate_name || `Candidate #${enr.candidate_id.slice(0, 8)}`;
                  const candEmail = candidateUser?.email || enr.candidate_email || '';
                  const currentStageObj = stages.find((s) => s.id === enr.current_stage_id);

                  return (
                    <TableRow key={enr.candidate_id}>
                      <TableCell>
                        <div className="font-semibold text-slate-100">{candName}</div>
                        {candEmail && <div className="text-xs text-slate-400 font-mono">{candEmail}</div>}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            enr.status === 'active'
                              ? 'success'
                              : enr.status === 'withdrawn'
                              ? 'danger'
                              : 'neutral'
                          }
                          size="sm"
                        >
                          {enr.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs font-medium text-slate-300">
                          {currentStageObj?.name || 'Stage 1 (Pending)'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        {enr.status === 'active' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-rose-400 hover:text-rose-300"
                            onClick={() => setCandidateToWithdraw(enr.candidate_id)}
                            leftIcon={<UserMinus className="w-3.5 h-3.5" />}
                          >
                            Withdraw
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </div>
      )}

      {/* Scheduling Console (F4) */}
      {activeTab === 'schedule' && (
        <ScheduleConsole
          driveId={drive.id}
          drive={drive as any}
          stages={stages}
          users={allUsers as any}
          rooms={rooms}
        />
      )}

      {/* Pipeline Board (F7) */}
      {activeTab === 'pipeline' && (
        <PipelineBoard
          driveId={drive.id}
          driveTitle={drive.title}
          onGoToSchedule={() => setActiveTab('schedule')}
        />
      )}

      {/* Ripple Rescue (F7) */}
      {activeTab === 'rescue' && (
        <RippleRescueConsole
          driveId={drive.id}
          driveTitle={drive.title}
          scheduleVersion={drive.schedule_version || 1}
          users={allUsers as any}
          rooms={rooms}
          onRescueApplied={() => {
            queryClient.invalidateQueries({ queryKey: ['drive', driveId] });
          }}
        />
      )}

      {/* Booking Links Modal (F5) */}
      {drive && (
        <BookingLinksModal
          isOpen={isBookingLinksModalOpen}
          onClose={() => setIsBookingLinksModalOpen(false)}
          driveId={drive.id}
          driveTitle={drive.title}
          candidates={enrollments.map((enr) => {
            const userObj = allUsers.find((u) => u.id === enr.candidate_id);
            return {
              id: enr.candidate_id,
              name: userObj?.name || `Candidate ${enr.candidate_id.slice(0, 8)}`,
              email: userObj?.email,
              status: enr.status,
            };
          })}
        />
      )}

      {/* Stage Add/Edit Modal */}
      <Modal
        isOpen={isStageModalOpen}
        onClose={() => setIsStageModalOpen(false)}
        title={editingStage ? 'Edit Stage' : 'Add Interview Stage'}
        description="Define interview duration, panel size, required skills, and rubric passing rule"
        maxWidth="md"
      >
        <form onSubmit={handleStageSubmit} className="space-y-4">
          <FormField label="Stage Name" required>
            <Input
              value={stageName}
              onChange={(e) => setStageName(e.target.value)}
              placeholder="e.g. Technical Round 1, System Design"
              required
            />
          </FormField>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Stage Type" required>
              <Select value={stageType} onChange={(e) => setStageType(e.target.value as any)}>
                <option value="technical">Technical</option>
                <option value="system_design">System Design</option>
                <option value="hr">HR &amp; Behavioral</option>
                <option value="managerial">Managerial</option>
                <option value="general">General</option>
              </Select>
            </FormField>

            <FormField label="Duration (mins)" required>
              <Input
                type="number"
                min={15}
                max={240}
                step={5}
                value={duration}
                onChange={(e) => setDuration(parseInt(e.target.value, 10))}
                required
              />
            </FormField>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Panel Size" required hint="Interviewers per session">
              <Input
                type="number"
                min={1}
                max={5}
                value={panelSize}
                onChange={(e) => setPanelSize(parseInt(e.target.value, 10))}
                required
              />
            </FormField>

            <FormField label="Min Passing Score (0-10)" required hint="Rubric threshold">
              <Input
                type="number"
                min={0}
                max={10}
                step={0.5}
                value={minScore}
                onChange={(e) => setMinScore(parseFloat(e.target.value))}
                required
              />
            </FormField>
          </div>

          <FormField label="Required Skills" hint="Panelists must have these skills to be scheduled">
            <div className="flex gap-2">
              <Input
                value={skillTag}
                onChange={(e) => setSkillTag(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddSkillTag();
                  }
                }}
                placeholder="e.g. python, algorithms"
                leftIcon={<Tag className="w-3.5 h-3.5" />}
              />
              <Button type="button" variant="secondary" size="sm" onClick={handleAddSkillTag}>
                <Plus className="w-4 h-4" />
              </Button>
            </div>

            {skills.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {skills.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-brand-500/20 text-brand-300 border border-brand-500/30"
                  >
                    <span>{s}</span>
                    <button
                      type="button"
                      onClick={() => setSkills(skills.filter((sk) => sk !== s))}
                      className="hover:text-rose-400"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </FormField>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
            <Button type="button" variant="outline" onClick={() => setIsStageModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={saveStageMutation.isPending}>
              {editingStage ? 'Save Changes' : 'Add Stage'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Stage Confirm */}
      <ConfirmDialog
        isOpen={!!stageToDelete}
        onClose={() => setStageToDelete(null)}
        onConfirm={() => stageToDelete && deleteStageMutation.mutate(stageToDelete.id)}
        title="Delete Stage"
        message={`Are you sure you want to remove "${stageToDelete?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        isLoading={deleteStageMutation.isPending}
      />

      {/* Enrol Candidates Modal */}
      <Modal
        isOpen={isEnrollModalOpen}
        onClose={() => setIsEnrollModalOpen(false)}
        title="Enrol Candidates into Drive"
        description="Select candidates to participate in this recruitment cycle"
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="max-h-72 overflow-y-auto divide-y divide-surface-border/40 border border-surface-border rounded-xl">
            {availableToEnroll.length === 0 ? (
              <p className="text-xs text-slate-400 p-6 text-center">
                All candidates in the directory are already enrolled in this drive.
              </p>
            ) : (
              availableToEnroll.map((c) => {
                const isSelected = selectedCandidateIds.includes(c.id);
                return (
                  <label
                    key={c.id}
                    className="p-3 flex items-center justify-between gap-3 hover:bg-surface-elevated/60 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedCandidateIds([...selectedCandidateIds, c.id]);
                          } else {
                            setSelectedCandidateIds(selectedCandidateIds.filter((id) => id !== c.id));
                          }
                        }}
                        className="rounded bg-surface-elevated border-surface-border text-brand-600 focus:ring-brand-500 w-4 h-4"
                      />
                      <div>
                        <p className="text-sm font-semibold text-slate-100">{c.name}</p>
                        <p className="text-xs text-slate-400 font-mono">{c.email}</p>
                      </div>
                    </div>

                    <div className="text-right text-xs text-slate-400">
                      {c.roll_number && <span className="font-mono">{c.roll_number}</span>}
                      {c.branch && <span> • {c.branch}</span>}
                    </div>
                  </label>
                );
              })
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-surface-border">
            <span className="text-xs text-slate-400">
              {selectedCandidateIds.length} candidate(s) selected
            </span>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" onClick={() => setIsEnrollModalOpen(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="primary"
                disabled={selectedCandidateIds.length === 0}
                isLoading={enrollMutation.isPending}
                onClick={() => enrollMutation.mutate(selectedCandidateIds)}
              >
                Enrol Selected
              </Button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Withdraw Candidate Confirm */}
      <ConfirmDialog
        isOpen={!!candidateToWithdraw}
        onClose={() => setCandidateToWithdraw(null)}
        onConfirm={() => candidateToWithdraw && withdrawMutation.mutate(candidateToWithdraw)}
        title="Withdraw Candidate"
        message="Are you sure you want to withdraw this candidate from the drive? Their enrollment status will become Withdrawn, but historical interviews are preserved."
        confirmLabel="Withdraw Candidate"
        isLoading={withdrawMutation.isPending}
      />
    </div>
  );
};
