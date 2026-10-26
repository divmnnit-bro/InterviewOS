import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  TrendingUp,
  Users,
  CheckCircle2,
  Layers,
  Award,
  RefreshCw,
  UserCheck,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import {
  AnalyticsOverview,
  DriveAnalytics,
  InterviewersAnalytics,
} from '@/types/analytics';
import { RecruitmentDrive } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';

export const AnalyticsDashboardPage: React.FC = () => {
  const [selectedDriveId, setSelectedDriveId] = useState<string>('');

  // 1. Overview Analytics Query
  const {
    data: overview,
    isLoading: isOverviewLoading,
    refetch: refetchOverview,
  } = useQuery<AnalyticsOverview>({
    queryKey: ['analytics-overview'],
    queryFn: () => apiClient.get<AnalyticsOverview>('/analytics/overview'),
  });

  // 2. Drives List for Dropdown
  const { data: drives = [] } = useQuery<RecruitmentDrive[]>({
    queryKey: ['drives'],
    queryFn: () => apiClient.get<RecruitmentDrive[]>('/drives'),
  });

  // Auto-select first drive
  React.useEffect(() => {
    if (drives.length > 0 && !selectedDriveId) {
      setSelectedDriveId(drives[0].id);
    }
  }, [drives]);

  // 3. Drive-specific Analytics Query
  const {
    data: driveAnalytics,
    isLoading: isDriveLoading,
    refetch: refetchDrive,
  } = useQuery<DriveAnalytics>({
    queryKey: ['analytics-drive', selectedDriveId],
    queryFn: () => apiClient.get<DriveAnalytics>(`/analytics/drives/${selectedDriveId}`),
    enabled: Boolean(selectedDriveId),
  });

  // 4. Interviewer Calibration Analytics Query
  const {
    data: interviewerAnalytics,
    isLoading: isInterviewersLoading,
    refetch: refetchInterviewers,
  } = useQuery<InterviewersAnalytics>({
    queryKey: ['analytics-interviewers'],
    queryFn: () => apiClient.get<InterviewersAnalytics>('/analytics/interviewers'),
  });

  const interviewers = interviewerAnalytics?.interviewers ?? [];

  const handleRefreshAll = () => {
    refetchOverview();
    refetchDrive();
    refetchInterviewers();
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-surface-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400">
              <BarChart3 className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-bold text-slate-100">Recruitment Analytics & Intelligence</h1>
            <Badge variant="outline" className="text-xs bg-emerald-500/10 text-emerald-300 border-emerald-500/30">
              Live Analytics
            </Badge>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real-time pipeline metrics, conversion funnels, interviewer calibration, and schedule execution rates.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            className="flex items-center gap-2 text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh Metrics
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-surface-card border-surface-border p-5 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-400">Active Drives</p>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <p className="text-3xl font-extrabold text-slate-100 mt-2">
            {isOverviewLoading ? <Spinner size="sm" /> : overview?.active_drives ?? 0}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {overview?.total_drives ?? 0} total drives registered
          </p>
        </Card>

        <Card className="bg-surface-card border-surface-border p-5 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-400">Enrolled Candidates</p>
            <Users className="w-4 h-4 text-sky-400" />
          </div>
          <p className="text-3xl font-extrabold text-sky-400 mt-2">
            {isOverviewLoading ? <Spinner size="sm" /> : overview?.total_candidates_enrolled ?? 0}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {overview?.total_candidates_registered ?? 0} registered in system
          </p>
        </Card>

        <Card className="bg-surface-card border-surface-border p-5 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-400">Completion Rate</p>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-3xl font-extrabold text-emerald-400 mt-2">
            {isOverviewLoading ? <Spinner size="sm" /> : `${overview?.global_completion_rate ?? 0}%`}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {overview?.total_interviews_completed ?? 0} of {overview?.total_interviews_scheduled ?? 0} interviews
          </p>
        </Card>

        <Card className="bg-surface-card border-surface-border p-5 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-400">Avg Evaluation Score</p>
            <Award className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-3xl font-extrabold text-amber-400 mt-2">
            {isOverviewLoading ? (
              <Spinner size="sm" />
            ) : overview?.average_score_across_all_evaluations != null ? (
              `${overview.average_score_across_all_evaluations} / 10`
            ) : (
              'N/A'
            )}
          </p>
          <p className="text-xs text-slate-500 mt-1">
            {overview?.total_evaluations_submitted ?? 0} rubric evaluations
          </p>
        </Card>
      </div>

      {/* Drive-Level Conversion Funnel & Stage Progression */}
      <Card className="bg-surface-card border-surface-border">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-indigo-400" />
                Drive Stage Conversion & Funnel
              </CardTitle>
              <CardDescription>
                Detailed stage-by-stage progression, candidate conversion rates, and feedback velocity
              </CardDescription>
            </div>
            <div className="w-64">
              <Select
                value={selectedDriveId}
                onChange={(e) => setSelectedDriveId(e.target.value)}
                options={drives.map((d) => ({ value: d.id, label: d.title }))}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isDriveLoading ? (
            <div className="py-12 text-center">
              <Spinner size="md" className="mx-auto mb-2 text-indigo-400" />
              <p className="text-sm text-slate-400">Loading drive progression metrics...</p>
            </div>
          ) : !driveAnalytics ? (
            <div className="py-12 text-center text-slate-500">No drive data available</div>
          ) : (
            <div className="space-y-6">
              {/* Drive Summary Pill Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 p-4 bg-slate-900/60 rounded-xl border border-surface-border">
                <div>
                  <span className="text-xs text-slate-400 block">Enrolled</span>
                  <span className="text-lg font-bold text-slate-100">{driveAnalytics.total_enrolled}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-400 block">Active Pipeline</span>
                  <span className="text-lg font-bold text-indigo-400">{driveAnalytics.active_in_pipeline}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-400 block">Selected</span>
                  <span className="text-lg font-bold text-emerald-400">{driveAnalytics.selected_count}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-400 block">Rejected</span>
                  <span className="text-lg font-bold text-rose-400">{driveAnalytics.rejected_count}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-400 block">Pending Feedback</span>
                  <span className="text-lg font-bold text-amber-400">{driveAnalytics.pending_feedback_count}</span>
                </div>
              </div>

              {/* Stage Funnel */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-surface-border text-slate-400 text-xs uppercase tracking-wider">
                      <th className="py-3 px-4 font-semibold">Stage</th>
                      <th className="py-3 px-4 font-semibold">Candidates</th>
                      <th className="py-3 px-4 font-semibold">Passed</th>
                      <th className="py-3 px-4 font-semibold">Failed</th>
                      <th className="py-3 px-4 font-semibold">Pending</th>
                      <th className="py-3 px-4 font-semibold">Conversion Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border text-slate-200">
                    {driveAnalytics.stage_funnel.length === 0 ? (
                      <tr><td colSpan={6} className="py-6 text-center text-slate-500">No stage data available for this drive yet.</td></tr>
                    ) : (
                      driveAnalytics.stage_funnel.map((stage) => (
                        <tr key={stage.stage_id} className="hover:bg-slate-900/40 transition-colors">
                          <td className="py-3 px-4 font-medium text-slate-100">
                            <div className="flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-300 text-xs flex items-center justify-center font-bold">{stage.order_index + 1}</span>
                              <span>{stage.stage_name}</span>
                            </div>
                          </td>
                          <td className="py-3 px-4">{stage.candidates_count}</td>
                          <td className="py-3 px-4 text-emerald-400 font-semibold">{stage.passed_count}</td>
                          <td className="py-3 px-4 text-rose-400">{stage.failed_count}</td>
                          <td className="py-3 px-4 text-amber-400">{stage.pending_count}</td>
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <div className="w-24 bg-slate-800 rounded-full h-2 overflow-hidden">
                                <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${Math.min(stage.conversion_rate, 100)}%` }} />
                              </div>
                              <span className="font-semibold">{stage.conversion_rate}%</span>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Interviewer Workload & Calibration Table */}
      <Card className="bg-surface-card border-surface-border">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-emerald-400" />
            Interviewer Workload & Calibration
          </CardTitle>
          <CardDescription>
            Assigned interviews, pending evaluations, weekly capacity utilization, and evaluator calibration across the interviewer panel
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isInterviewersLoading ? (
            <div className="py-12 text-center">
              <Spinner size="md" className="mx-auto mb-2 text-emerald-400" />
              <p className="text-sm text-slate-400">Loading interviewer calibration records...</p>
            </div>
          ) : interviewers.length === 0 ? (
            <div className="py-12 text-center text-slate-500">No interviewers registered yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-surface-border text-slate-400 text-xs uppercase tracking-wider">
                    <th className="py-3 px-4 font-semibold">Interviewer</th>
                    <th className="py-3 px-4 font-semibold">Skills / Dept</th>
                    <th className="py-3 px-4 font-semibold">Assigned</th>
                    <th className="py-3 px-4 font-semibold">Completed</th>
                    <th className="py-3 px-4 font-semibold">Pending Evals</th>
                    <th className="py-3 px-4 font-semibold">Utilization</th>
                    <th className="py-3 px-4 font-semibold">Avg Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border text-slate-200">
                  {interviewers.map((iv) => (
                    <tr key={iv.interviewer_id} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-3 px-4 font-medium text-slate-100">
                        <div><div>{iv.name}</div><div className="text-xs text-slate-500 font-normal">{iv.email}</div></div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-xs text-slate-400 mb-1">{iv.department || '—'}</div>
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {iv.skills.slice(0, 3).map((skill, i) => <Badge key={i} variant="outline" className="text-xs bg-slate-800 text-slate-300">{skill}</Badge>)}
                          {iv.skills.length > 3 && <span className="text-xs text-slate-500">+{iv.skills.length - 3}</span>}
                        </div>
                      </td>
                      <td className="py-3 px-4">{iv.total_assigned_interviews}</td>
                      <td className="py-3 px-4 text-emerald-400 font-semibold">{iv.completed_interviews}</td>
                      <td className="py-3 px-4 text-amber-400">{iv.pending_evaluations}</td>
                      <td className="py-3 px-4">{iv.utilization_rate}%</td>
                      <td className="py-3 px-4">
                        {iv.average_score_given != null ? (
                          <Badge variant="outline" className={`text-xs ${iv.average_score_given >= 8 ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' : iv.average_score_given <= 5 ? 'bg-amber-500/10 text-amber-300 border-amber-500/20' : 'bg-slate-800 text-slate-300 border-slate-700'}`}>
                            {iv.average_score_given} / 10.0
                          </Badge>
                        ) : <span className="text-slate-500 text-xs">No evals</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
