import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Layers, Building, Plus, ArrowRight, Calendar, Users, ClipboardCheck, Activity, Search, RefreshCw } from 'lucide-react';
import { apiClient } from '@/api/client';
import { RecruitmentDrive, Room } from '@/types/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Button, Badge, Spinner, EmptyState } from '@/components/ui';
import { AnalyticsOverview, DriveAnalytics, InterviewersAnalytics } from '@/types/analytics';
import { Input } from '@/components/ui/Input';

export const CoordinatorDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dateFilter, setDateFilter] = useState('');
  const [selectedDriveId, setSelectedDriveId] = useState('');
  const { data: drives = [], isLoading: drivesLoading } = useQuery<RecruitmentDrive[]>({
    queryKey: ['drives'],
    queryFn: () => apiClient<RecruitmentDrive[]>('/drives'),
  });

  const { data: rooms = [] } = useQuery<Room[]>({
    queryKey: ['rooms'],
    queryFn: () => apiClient<Room[]>('/rooms'),
  });

  const { data: overview, isLoading: overviewLoading, isError: overviewError, refetch: refreshOverview } = useQuery<AnalyticsOverview>({
    queryKey: ['analytics-overview', selectedDriveId],
    queryFn: () => apiClient.get<AnalyticsOverview>('/analytics/overview', { params: { drive_id: selectedDriveId || undefined } }),
  });

  const activeDriveId = selectedDriveId || drives[0]?.id || '';
  const { data: driveAnalytics, isLoading: funnelLoading } = useQuery<DriveAnalytics>({
    queryKey: ['drive-analytics', activeDriveId],
    queryFn: () => apiClient.get<DriveAnalytics>(`/analytics/drives/${activeDriveId}`),
    enabled: !!activeDriveId,
  });

  const { data: interviewerAnalytics } = useQuery<InterviewersAnalytics>({
    queryKey: ['analytics-interviewers'],
    queryFn: () => apiClient.get<InterviewersAnalytics>('/analytics/interviewers'),
  });

  const activeDrives = drives.filter(
    (d) => ['collecting_availability', 'published', 'in_progress'].includes(d.status)
  );
  const filteredDrives = drives.filter((drive) => {
    const searchMatches = !search || drive.title.toLowerCase().includes(search.toLowerCase());
    const statusMatches = statusFilter === 'all'
      || (statusFilter === 'active' && ['collecting_availability', 'published', 'in_progress'].includes(drive.status))
      || drive.status === statusFilter;
    const dateMatches = !dateFilter || new Date(drive.window_start) <= new Date(`${dateFilter}T23:59:59`)
      && new Date(drive.window_end) >= new Date(`${dateFilter}T00:00:00`);
    return searchMatches && statusMatches && dateMatches;
  });
  const upcomingInterviews = (overview?.upcoming_interviews ?? []).filter((interview) =>
    !dateFilter || new Date(interview.start_time).toLocaleDateString('en-CA') === dateFilter
  );
  const workload = [...(interviewerAnalytics?.interviewers ?? [])]
    .sort((a, b) => b.pending_evaluations - a.pending_evaluations || b.total_assigned_interviews - a.total_assigned_interviews)
    .slice(0, 5);

  const driveStatusVariant = (status: string): 'brand' | 'success' | 'warning' | 'danger' | 'neutral' => {
    switch (status) {
      case 'published':
      case 'in_progress':
        return 'success';
      case 'collecting_availability':
        return 'brand';
      case 'completed':
        return 'neutral';
      case 'archived':
        return 'neutral';
      default:
        return 'warning';
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Coordinator Console</h1>
          <p className="text-xs text-slate-400 mt-1">
            Orchestrate drives, calibrate solver parameters, manage candidate pipelines, and run Ripple Rescue
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link to="/coordinator/drives/new">
            <Button variant="primary" size="sm" leftIcon={<Plus className="w-4 h-4" />}>
              Create Drive
            </Button>
          </Link>
          <Link to="/coordinator/rooms">
            <Button variant="secondary" size="sm" leftIcon={<Building className="w-4 h-4" />}>
              Rooms ({rooms.length})
            </Button>
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-500/10 text-brand-400 flex items-center justify-center border border-brand-500/20">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Total Drives</p>
            <h3 className="text-2xl font-bold text-slate-100">{overviewLoading ? '-' : overview?.total_drives ?? drives.length}</h3>
            <p className="text-[11px] text-slate-500 mt-0.5">{overview?.active_drives ?? activeDrives.length} active drives</p>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Candidates Enrolled</p>
            <h3 className="text-2xl font-bold text-slate-100">{overviewLoading ? '-' : overview?.total_candidates_enrolled ?? 0}</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">{overview?.total_candidates_registered ?? 0} registered candidates</p>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-violet-500/10 text-violet-400 flex items-center justify-center border border-violet-500/20">
            <ClipboardCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Pending Evaluations</p>
            <h3 className="text-2xl font-bold text-slate-100">
              {overviewLoading ? '-' : overview?.pending_evaluations_count ?? 0}
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">Panel scorecards awaiting feedback</p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-500/10 text-sky-400 flex items-center justify-center border border-sky-500/20"><Users className="w-6 h-6" /></div>
          <div><p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Interviews</p><h3 className="text-2xl font-bold text-slate-100">{overviewLoading ? '-' : overview?.total_interviews_scheduled ?? 0}</h3><p className="text-[11px] text-slate-500 mt-0.5">{overview?.total_interviews_completed ?? 0} completed</p></div>
        </Card>
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20"><ClipboardCheck className="w-6 h-6" /></div>
          <div><p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Completion</p><h3 className="text-2xl font-bold text-slate-100">{overviewLoading ? '-' : `${overview?.global_completion_rate ?? 0}%`}</h3><p className="text-[11px] text-slate-500 mt-0.5">Across scheduled interviews</p></div>
        </Card>
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20"><Activity className="w-6 h-6" /></div>
          <div><p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Scorecards</p><h3 className="text-2xl font-bold text-slate-100">{overviewLoading ? '-' : overview?.total_evaluations_submitted ?? 0}</h3><p className="text-[11px] text-slate-500 mt-0.5">{overview?.average_score_across_all_evaluations ?? '—'} average score / 10</p></div>
        </Card>
      </div>

      {overviewError && <Card className="p-4 flex items-center justify-between gap-4 border-rose-500/30"><p className="text-sm text-rose-300">Dashboard analytics could not be loaded.</p><Button variant="outline" size="sm" onClick={() => void refreshOverview()} leftIcon={<RefreshCw className="w-3.5 h-3.5" />}>Retry</Button></Card>}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader><div><CardTitle>Upcoming Interviews</CardTitle><CardDescription>Next scheduled candidate sessions from the live schedule</CardDescription></div><Calendar className="w-5 h-5 text-indigo-400" /></CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2 mb-4">
              <select aria-label="Filter upcoming interviews by drive" value={selectedDriveId} onChange={(e) => setSelectedDriveId(e.target.value)} className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200"><option value="">All drives</option>{drives.map((drive) => <option key={drive.id} value={drive.id}>{drive.title}</option>)}</select>
              <Input aria-label="Filter dashboard by date" type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} className="max-w-44 text-xs" />
            </div>
            {overviewLoading ? <Spinner size="sm" /> : upcomingInterviews.length === 0 ? <p className="py-5 text-center text-xs text-slate-500">No upcoming interviews match these filters.</p> : <div className="divide-y divide-slate-800/70">{upcomingInterviews.map((interview) => <div key={interview.interview_id} className="py-3 flex items-start justify-between gap-3"><div className="min-w-0"><p className="text-xs font-semibold text-slate-200 truncate">{interview.candidate_name} <span className="text-slate-500">·</span> {interview.stage_name}</p><p className="text-[11px] text-slate-500 truncate">{interview.drive_title} · {interview.room_name || 'Room not assigned'}</p></div><span className="shrink-0 text-[11px] text-indigo-300">{new Date(interview.start_time).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span></div>)}</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><div><CardTitle>Recent Activity</CardTitle><CardDescription>Latest schedule and pipeline events</CardDescription></div><Activity className="w-5 h-5 text-emerald-400" /></CardHeader>
          <CardContent>{overviewLoading ? <Spinner size="sm" /> : overview?.recent_activity.length ? <div className="divide-y divide-slate-800/70">{overview.recent_activity.map((event, index) => <div key={`${event.action}-${event.timestamp}-${index}`} className="py-3 flex items-center justify-between gap-3"><span className="text-xs text-slate-300 capitalize">{event.action.replace(/[._]/g, ' ')}</span><span className="text-[11px] text-slate-500 shrink-0">{new Date(event.timestamp).toLocaleString()}</span></div>)}</div> : <p className="py-5 text-center text-xs text-slate-500">No recruitment activity recorded yet.</p>}</CardContent>
        </Card>

        <Card>
          <CardHeader><div><CardTitle>Stage Funnel</CardTitle><CardDescription>Candidate progression from the selected drive</CardDescription></div><select aria-label="Choose funnel drive" value={activeDriveId} onChange={(e) => setSelectedDriveId(e.target.value)} className="max-w-48 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200">{drives.map((drive) => <option key={drive.id} value={drive.id}>{drive.title}</option>)}</select></CardHeader>
          <CardContent>{funnelLoading ? <Spinner size="sm" /> : !driveAnalytics?.stage_funnel.length ? <p className="py-5 text-center text-xs text-slate-500">No stage funnel data for this drive.</p> : <div className="space-y-4">{driveAnalytics.stage_funnel.map((stage) => <div key={stage.stage_id}><div className="flex justify-between gap-3 text-xs mb-1.5"><span className="text-slate-300">{stage.order_index + 1}. {stage.stage_name}</span><span className="text-slate-400">{stage.passed_count} passed · {stage.pending_count} pending · {stage.failed_count} not advanced</span></div><div className="h-2 rounded-full bg-slate-800 overflow-hidden"><div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-400" style={{ width: `${Math.max(0, Math.min(100, stage.conversion_rate))}%` }} /></div><p className="mt-1 text-right text-[10px] text-slate-500">{stage.conversion_rate}% conversion</p></div>)}</div>}</CardContent>
        </Card>

        <Card>
          <CardHeader><div><CardTitle>Interviewer Workload</CardTitle><CardDescription>Assigned interviews and feedback still due</CardDescription></div><Users className="w-5 h-5 text-violet-400" /></CardHeader>
          <CardContent>{!workload.length ? <p className="py-5 text-center text-xs text-slate-500">No interviewer assignments to summarize.</p> : <div className="divide-y divide-slate-800/70">{workload.map((interviewer) => <div key={interviewer.interviewer_id} className="py-3 flex items-center justify-between gap-3"><div><p className="text-xs font-semibold text-slate-200">{interviewer.name}</p><p className="text-[11px] text-slate-500">{interviewer.total_assigned_interviews} assigned · {interviewer.utilization_rate}% utilization</p></div><Badge variant={interviewer.pending_evaluations ? 'warning' : 'success'}>{interviewer.pending_evaluations} pending</Badge></div>)}</div>}</CardContent>
        </Card>
      </div>

      {/* Drives Section */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Recruitment Drives</CardTitle>
            <CardDescription>Manage interview windows, stages, candidate enrolment, and schedules</CardDescription>
          </div>
          <Link to="/coordinator/drives">
            <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-4 h-4" />}>
              View All Drives
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
            <Input aria-label="Search drives" placeholder="Search drives" value={search} onChange={(e) => setSearch(e.target.value)} leftIcon={<Search className="w-3.5 h-3.5" />} />
            <select aria-label="Filter drives by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200"><option value="all">All statuses</option><option value="active">Active</option><option value="draft">Draft</option><option value="completed">Completed</option><option value="archived">Archived</option></select>
            <Input aria-label="Filter drives by date" type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} className="text-xs" />
          </div>
          {drivesLoading ? (
            <Spinner size="md" label="Loading recruitment drives..." />
          ) : drives.length === 0 ? (
            <EmptyState
              icon={Layers}
              title="No recruitment drives created yet"
              description="Create your first drive to set up interview stages, invite candidates, and run the automated scheduler."
              actionLabel="Create Drive"
              onAction={() => navigate('/coordinator/drives/new')}
            />
          ) : (
            <div className="divide-y divide-surface-border/40">
              {filteredDrives.length === 0 ? <p className="py-6 text-center text-xs text-slate-500">No drives match these filters.</p> : filteredDrives.slice(0, 5).map((drive) => (
                <div
                  key={drive.id}
                  className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-elevated/30 -mx-5 px-5 transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Link
                        to={`/coordinator/drives/${drive.id}`}
                        className="text-sm font-semibold text-slate-100 hover:text-brand-400 transition-colors"
                      >
                        {drive.title}
                      </Link>
                      <Badge variant={driveStatusVariant(drive.status)} size="sm">
                        {drive.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-400 flex items-center gap-2">
                      <span>Timezone: {drive.timezone}</span>
                      <span>•</span>
                      <span>
                        {new Date(drive.window_start).toLocaleDateString()} — {new Date(drive.window_end).toLocaleDateString()}
                      </span>
                      <span>•</span>
                      <span>{drive.stages?.length || 0} stages</span>
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    <Link to={`/coordinator/drives/${drive.id}`}>
                      <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                        Open Drive
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
